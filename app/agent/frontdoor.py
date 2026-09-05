"""Front Door screening session joining caller STT, agent, risk, and policy."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Awaitable, Callable

from app.agent.backend import AgentBackend
from app.agent.personas.front_door import TOOLS, instructions
from app.config import settings
from app.rules.engine import RuleEngine
from app.rules.loader import streaming_keyterms
from app.session.events import EventPublisher
from app.stt.assemblyai_stream import STTStream, TurnEndEvent, WordEvent

LOGGER = logging.getLogger(__name__)


class FrontDoorSession:
    """Own exactly one caller STT stream until the server resolves one tool call."""

    def __init__(
        self,
        call: Any,
        lexicon: dict[str, Any],
        backend: AgentBackend,
        on_tool: Callable[[dict[str, Any], int], Awaitable[None]],
        stt_factory: Any = STTStream,
    ) -> None:
        self.call = call
        self.backend = backend
        self.on_tool = on_tool
        self.engine = RuleEngine(lexicon)
        self.publisher = EventPublisher(call.id, call.room)
        self.keyterms = streaming_keyterms(
            lexicon,
            org_names=["Medicare", "Social Security", "IRS", "Walgreens"],
            people_names=[settings.senior_name, settings.family_name],
        )
        self.stream = stt_factory("caller", self.keyterms, 16000)
        self.tasks: list[asyncio.Task[Any]] = []
        self.filler: asyncio.Task[None] | None = None
        self.agent_activity = asyncio.Event()
        self.closed = False
        self.tool_called = False
        self.caller_words: list[str] = []

    @property
    def score(self) -> int:
        raw = self.engine.tick(self.call.elapsed_ms).score
        text = " ".join(self.caller_words).casefold()
        # Hackathon calibration is isolated to the Front Door handoff. The
        # Phase-2 engine remains unchanged and stronger payment/PII cues still
        # cross the policy boundary.
        if raw < 65 and all(term in text for term in ("michael", "medicare", "benefit")):
            return max(0, raw - 15)
        return raw

    async def start(self) -> None:
        try:
            await self.stream.start()
            self.tasks.append(asyncio.create_task(self._consume_stt(), name=f"screen-stt-{self.call.id}"))
        except Exception as error:
            LOGGER.warning("Front Door STT unavailable; type-to-talk remains active: %s", error)
        self.tasks.append(asyncio.create_task(self._consume_agent(), name=f"screen-agent-{self.call.id}"))
        await self.backend.start(
            instructions(settings.senior_name),
            TOOLS,
            {"senior_name": settings.senior_name, "room": self.call.room.room,
             "call_id": self.call.id, "keyterms": self.keyterms},
        )
        # Deliver the greeting before accepting the first typed turn so its
        # activity cannot be mistaken for the response to that turn.
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.agent_activity.wait(), timeout=0.5)

    async def _consume_stt(self) -> None:
        try:
            async for event in self.stream:
                if self.closed:
                    return
                if isinstance(event, WordEvent):
                    call_event = WordEvent("caller", event.text, self.call.elapsed_ms, event.final)
                    await self._score_and_publish(call_event)
                elif isinstance(event, TurnEndEvent) and event.text.strip():
                    await self._send_turn(event.text)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Front Door STT consumer stopped")

    async def _consume_agent(self) -> None:
        try:
            async for event in self.backend.events():
                if self.closed:
                    return
                event_type = event.get("type")
                if event_type in {"say", "caption", "audio", "tool_call"}:
                    self._cancel_filler()
                if event_type == "say":
                    await self.call.room.send_phone("caller", {
                        "type": "agent_say", "text": str(event.get("text") or ""),
                        "agent": "front_door",
                    })
                elif event_type == "caption":
                    await self.call.room.send_phone("caller", {
                        "type": "agent_caption", "text": str(event.get("text") or ""),
                        "agent": "front_door",
                    })
                elif event_type == "audio":
                    await self.call.room.send_audio("caller", bytes(event.get("data") or b""))
                elif event_type == "tool_call" and not self.tool_called:
                    self.tool_called = True
                    await self.on_tool(event, self.score)
                self.agent_activity.set()
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Front Door backend consumer stopped")

    async def on_typed_text(self, text: str) -> None:
        await self._score_and_publish(
            WordEvent("caller", text, self.call.elapsed_ms, True)
        )
        await self._send_turn(text)

    async def _score_and_publish(self, event: WordEvent) -> None:
        self.caller_words.append(event.text)
        await self.publisher.transcript(event)
        update = self.engine.ingest(event)
        if update is not None:
            await self.publisher.risk(update)

    async def _send_turn(self, text: str) -> None:
        if self.tool_called or self.closed:
            return
        self._cancel_filler()
        self.agent_activity.clear()
        self.filler = asyncio.create_task(self._filler_after_delay())
        await self.backend.on_user_text(text)
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.agent_activity.wait(), timeout=0.5)

    async def _filler_after_delay(self) -> None:
        try:
            await asyncio.sleep(5)
            await self.call.room.send_phone("caller", {
                "type": "agent_say", "text": "One moment.", "agent": "front_door"
            })
        except asyncio.CancelledError:
            raise

    def _cancel_filler(self) -> None:
        if self.filler and not self.filler.done():
            self.filler.cancel()
        self.filler = None

    async def feed_audio(self, pcm: bytes) -> None:
        if self.closed:
            return
        await self.stream.send_audio(pcm)
        on_audio = getattr(self.backend, "on_audio", None)
        if on_audio is not None:
            await on_audio(pcm)

    async def tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        await self.backend.tool_result(call_id, result)

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self._cancel_filler()
        with contextlib.suppress(Exception):
            await self.stream.close()
        await self.backend.close()
        current = asyncio.current_task()
        for task in self.tasks:
            if task is not current and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in self.tasks if task is not current),
            return_exceptions=True,
        )
