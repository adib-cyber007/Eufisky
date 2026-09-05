"""Per-call monitoring context joining STT, rules, events, and escalation."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import statistics
from typing import Any, Awaitable, Callable

from app.config import settings
from app.rules.engine import RuleEngine
from app.rules.loader import streaming_keyterms
from app.session.events import EventPublisher
from app.session.state_machine import CallStateMachine
from app.stt.assemblyai_stream import STTStream, TurnEndEvent, WordEvent

LOGGER = logging.getLogger(__name__)


def guardian_context(
    evidence: list[dict[str, Any]], *, caller_name: str, claim: str,
    senior_name: str, family_name: str, family_role: str = "daughter",
    recommendation: str = "end the call or bring in family",
) -> dict[str, str]:
    """Turn rule evidence into calm, non-technical Guardian facts."""
    families = {str(item.get("family") or "") for item in evidence}
    if {"pii_request", "authority_impersonation"}.issubset(families):
        trigger = "asked for your Medicare number while claiming to be from Medicare"
    elif "payment_method" in families:
        trigger = "asked you to buy gift cards"
    elif "family_emergency" in families:
        trigger = "said a family member is in trouble and needs money"
    elif "remote_access" in families:
        trigger = "asked to get onto your computer"
    elif "pii_disclosure" in families:
        trigger = "you had started reading out numbers"
    else:
        trigger = "used urgent language that did not feel safe"
    request_map = {
        "pii_request": "personal or account numbers", "payment_method": "gift cards or payment",
        "remote_access": "access to your computer", "family_emergency": "money for a family emergency",
    }
    requests = [label for family, label in request_map.items() if family in families]
    return {
        "senior_name": senior_name, "family_name": family_name,
        "caller_name": caller_name or "unknown", "claim": claim or "unknown",
        "trigger_plain": trigger, "requests": ", ".join(requests) or "none",
        "disclosed": "started reading digits" if "pii_disclosure" in families else "none",
        "family_role": family_role, "recommendation": recommendation,
    }


class CallMonitor:
    """Own the two streaming sessions for one bridged unknown call."""

    def __init__(
        self,
        call: Any,
        lexicon: dict[str, Any],
        stt_factory: Callable[[str, list[str], int], Any] = STTStream,
        seed_score: int = 0,
        on_guardian: Callable[[Any, str], Awaitable[None]] | None = None,
        on_action: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
        on_recommendation: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self.call = call
        self.engine = RuleEngine(lexicon, seed_score=seed_score)
        self.publisher = EventPublisher(call.id, call.room)
        self.machine = CallStateMachine(
            self.publisher, lambda payload: call.room.send_phone("senior", payload),
            on_transition=self._machine_transition if on_guardian else None,
            on_action=on_action,
            on_recommendation=on_recommendation,
        )
        self.on_guardian = on_guardian
        self.guardian_turn: Callable[[str], Awaitable[None]] | None = None
        self.mode = "monitor"
        self.stt_factory = stt_factory
        self.keyterms = streaming_keyterms(
            lexicon,
            org_names=["Medicare", "Social Security", "IRS", "Walgreens"],
            people_names=[settings.senior_name, settings.family_name],
        )
        self.streams: dict[str, Any] = {}
        self.stream_offsets: dict[str, int] = {}
        self.tasks: list[asyncio.Task[Any]] = []
        self.word_lags_ms: list[int] = []
        self.closed = False

    async def start(self) -> None:
        for speaker in ("caller", "senior"):
            await self._start_leg(speaker)
        self.tasks.append(asyncio.create_task(self._tick(), name=f"risk-{self.call.id}"))

    async def _start_leg(self, speaker: str) -> None:
        if self.closed or speaker in self.streams:
            return
        stream = self.stt_factory(speaker, self.keyterms, 16000)
        try:
            await stream.start()
        except Exception as error:
            LOGGER.warning("Could not start %s STT leg: %s", speaker, error)
            return
        self.streams[speaker] = stream
        self.stream_offsets[speaker] = self.call.elapsed_ms
        self.tasks.append(
            asyncio.create_task(self._consume(speaker, stream), name=f"words-{speaker}-{self.call.id}")
        )

    async def _consume(self, speaker: str, stream: Any) -> None:
        try:
            async for event in stream:
                if isinstance(event, TurnEndEvent):
                    if self.mode == "guardian" and speaker == "senior" and self.guardian_turn and event.text.strip():
                        await self.guardian_turn(event.text)
                    continue
                if not isinstance(event, WordEvent):
                    continue
                offset = self.stream_offsets.get(speaker, 0)
                arrival = self.call.elapsed_ms
                call_t_ms = offset + event.t_ms
                self.word_lags_ms.append(max(0, arrival - call_t_ms))
                word = WordEvent(event.speaker, event.text, call_t_ms, event.final)
                if self.mode == "guardian":
                    await self.publisher.transcript(word)
                else:
                    await self.process_word(word)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            LOGGER.warning("STT consumer %s stopped: %s", speaker, error)

    async def process_word(self, event: WordEvent) -> None:
        await self.publisher.transcript(event)
        update = self.engine.ingest(event)
        if update is not None:
            await self.publisher.risk(update)
            await self.machine.on_risk(update)

    async def inject_text(self, speaker: str, text: str) -> None:
        await self.process_word(
            WordEvent(speaker=speaker, text=text, t_ms=self.call.elapsed_ms, final=True)
        )

    async def feed_audio(self, speaker: str, pcm: bytes) -> None:
        stream = self.streams.get(speaker)
        if stream is not None:
            await stream.send_audio(pcm)

    async def hold(self, speaker: str, on: bool) -> None:
        if on:
            stream = self.streams.pop(speaker, None)
            if stream is not None:
                await stream.close()
        else:
            await self._start_leg(speaker)

    async def _stop_all_legs(self) -> None:
        streams = list(self.streams.values())
        self.streams.clear()
        await asyncio.gather(*(stream.close() for stream in streams), return_exceptions=True)

    async def pause_for_guardian(self, on_turn: Callable[[str], Awaitable[None]]) -> None:
        self.mode = "guardian"
        self.guardian_turn = on_turn
        # Detach immediately so the phone bridge can be held without waiting
        # for remote STT termination handshakes.
        streams = list(self.streams.values())
        self.streams.clear()
        for stream in streams:
            self.tasks.append(asyncio.create_task(stream.close(), name=f"pause-stt-{self.call.id}"))

    async def start_guardian_listening(self) -> None:
        await self._start_leg("senior")

    async def resume_monitoring(self) -> None:
        await self._stop_all_legs()
        self.mode = "monitor"
        self.guardian_turn = None
        await self._start_leg("caller")
        await self._start_leg("senior")

    async def _machine_transition(self, target: Any, trigger: str, update: Any) -> None:
        if target.value == "GUARDIAN" and self.on_guardian is not None:
            await self.on_guardian(update, trigger)

    async def _tick(self) -> None:
        try:
            while not self.closed:
                await asyncio.sleep(0.5)
                update = self.engine.tick(self.call.elapsed_ms)
                await self.publisher.risk(update)
                await self.machine.on_risk(update)
        except asyncio.CancelledError:
            raise

    @property
    def median_word_lag_ms(self) -> int | None:
        if not self.word_lags_ms:
            return None
        return int(round(statistics.median(self.word_lags_ms)))

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self._stop_all_legs()
        current = asyncio.current_task()
        for task in self.tasks:
            if task is not current and not task.done():
                task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(
                *(task for task in self.tasks if task is not current),
                return_exceptions=True,
            )
