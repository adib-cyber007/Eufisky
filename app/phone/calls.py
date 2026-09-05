"""Deterministic phone call lifecycle and privacy-aware audio routing."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from app import db
from app.audio import WavWriter
from app.rules.loader import load_lexicon
from app.rooms import LiveRoom, RoomRegistry, rooms
from app.session.context import CallMonitor
from app.session.events import EventPublisher
from app.stt.assemblyai_stream import STTStream

RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "data" / "recordings"
PLACEHOLDER = "Eufisky screening will run here in the next phase"


class CallState(str, Enum):
    IDLE = "IDLE"
    RINGING_SENIOR = "RINGING_SENIOR"
    TRUSTED_ACTIVE = "TRUSTED_ACTIVE"
    SCREENING = "SCREENING"
    BRIDGED = "BRIDGED"
    ENDED = "ENDED"


class CallSession:
    def __init__(self, room: LiveRoom, caller_phone: str | None, label: str, classification: str) -> None:
        self.room = room
        self.id = uuid.uuid4().hex
        self.caller_phone = caller_phone or ""
        self.label = label
        self.classification = classification
        self.monitored = classification == "unknown"
        self.state = CallState.IDLE
        self.started_monotonic = time.monotonic()
        self.held: set[str] = set()
        self.family_ringing = False
        self.family_joined = False
        self.recorders: dict[str, WavWriter] = {}
        self.recording_paths: dict[str, str] = {}
        self.publisher = EventPublisher(self.id, room)
        self.monitor: CallMonitor | None = None
        if self.monitored:
            for leg in ("caller", "senior"):
                relative = Path("data") / "recordings" / f"{self.id}_{leg}.wav"
                self.recording_paths[leg] = relative.as_posix()
                self.recorders[leg] = WavWriter(RECORDINGS_DIR / f"{self.id}_{leg}.wav")

    @property
    def elapsed_ms(self) -> int:
        return max(0, int((time.monotonic() - self.started_monotonic) * 1000))

    @property
    def badge(self) -> str:
        if self.classification == "trusted":
            return "Trusted — not monitored"
        if self.classification == "blocked":
            return "Blocked"
        return "Screened — monitored"

    def close_recorders(self) -> None:
        for writer in self.recorders.values():
            writer.close()


class CallController:
    def __init__(
        self,
        registry: RoomRegistry = rooms,
        stt_factory: Any = STTStream,
        lexicon: dict[str, Any] | None = None,
    ) -> None:
        self.registry = registry
        self.stt_factory = stt_factory
        self.lexicon = lexicon or load_lexicon()

    async def _transition(self, call: CallSession, state: CallState, trigger: str) -> None:
        previous = call.state
        call.state = state
        await call.publisher.state(
            call.elapsed_ms, previous.value, state.value, trigger
        )

    async def _send_state(self, call: CallSession, roles: tuple[str, ...] = ("caller", "senior", "family")) -> None:
        payload = {"type": "state", "call_state": call.state.value,
                   "badge": call.badge, "monitored": call.monitored}
        await asyncio.gather(*(call.room.send_phone(role, payload) for role in roles))

    async def dial(self, room_name: str, caller_phone: str | None) -> CallSession:
        live = self.registry.get(room_name)
        async with live.lock:
            if live.current_call and live.current_call.state != CallState.ENDED:
                await live.send_phone("caller", {"type": "ended", "reason": "Line is already busy"})
                return live.current_call
            classification, label = db.classify_phone(room_name, caller_phone)
            call = CallSession(live, caller_phone, label, classification)
            live.current_call = call
            db.create_call({
                "id": call.id, "room": room_name, "from_phone": call.caller_phone,
                "from_label": call.label, "classification": classification,
                "recording_caller": call.recording_paths.get("caller"),
                "recording_senior": call.recording_paths.get("senior"),
            })
            db.add_event(call.id, 0, "call", {"event": "started", "classification": classification})
            await live.broadcast_dashboard({"type": "call", "t_ms": 0, "event": "started",
                                             "call_id": call.id, "classification": classification})
            if classification == "blocked":
                await self._transition(call, CallState.ENDED, "blocked_number")
                await live.send_phone("caller", {"type": "ended", "reason": "This number is blocked"})
                db.update_call(call.id, ended_at=datetime.now(timezone.utc).isoformat(),
                               final_state=CallState.ENDED.value)
                await live.broadcast_dashboard({"type": "call", "t_ms": call.elapsed_ms,
                                                 "event": "ended", "call_id": call.id,
                                                 "classification": classification})
                return call
            if classification == "unknown":
                await self._transition(call, CallState.SCREENING, "unknown_caller")
                await self._send_state(call, ("caller",))
                await live.send_phone("caller", {"type": "agent_say", "text": PLACEHOLDER,
                                                  "agent": "front_door"})
            await self._transition(call, CallState.RINGING_SENIOR, "screened" if call.monitored else "trusted")
            await self._send_state(call, ("caller", "senior"))
            await live.send_phone("senior", {"type": "ring", "from_label": label,
                                              "trusted": classification == "trusted"})
            return call

    async def answer(self, room_name: str, role: str) -> None:
        live = self.registry.get(room_name)
        call: CallSession | None = live.current_call
        if not call or call.state == CallState.ENDED:
            return
        if role == "senior" and call.state == CallState.RINGING_SENIOR:
            target = CallState.TRUSTED_ACTIVE if call.classification == "trusted" else CallState.BRIDGED
            await self._transition(call, target, "senior_answered")
            if target == CallState.BRIDGED:
                call.monitor = CallMonitor(call, self.lexicon, self.stt_factory)
                await call.monitor.start()
            await self._send_state(call)
            await live.send_phone("caller", {"type": "tone", "name": "connected"})
        elif role == "family" and call.family_ringing:
            call.family_ringing = False
            call.family_joined = True
            await self._send_state(call)
            await live.send_phone("family", {"type": "tone", "name": "connected"})
            db.add_event(call.id, call.elapsed_ms, "family", {"event": "joined"})

    async def hangup(self, room_name: str, reason: str = "Call ended") -> None:
        live = self.registry.get(room_name)
        call: CallSession | None = live.current_call
        if not call or call.state == CallState.ENDED:
            return
        if call.monitor is not None:
            await call.monitor.close()
        await self._transition(call, CallState.ENDED, reason)
        call.close_recorders()
        ended_at = datetime.now(timezone.utc).isoformat()
        db.update_call(call.id, ended_at=ended_at, final_state=CallState.ENDED.value)
        await asyncio.gather(*(live.send_phone(role, {"type": "ended", "reason": reason})
                               for role in ("caller", "senior", "family")))
        await live.broadcast_dashboard({"type": "call", "t_ms": call.elapsed_ms, "event": "ended",
                                         "call_id": call.id, "classification": call.classification})

    async def hold(self, room_name: str, leg: str, on: bool = True) -> None:
        live = self.registry.get(room_name)
        call: CallSession | None = live.current_call
        if not call or call.state == CallState.ENDED:
            return
        if on:
            call.held.add(leg)
        else:
            call.held.discard(leg)
        if call.monitor is not None and leg in {"caller", "senior"}:
            await call.monitor.hold(leg, on)
        await live.send_phone(leg, {"type": "hold", "on": on})
        db.add_event(call.id, call.elapsed_ms, "hold", {"leg": leg, "on": on})

    async def ring_family(self, room_name: str) -> bool:
        live = self.registry.get(room_name)
        call: CallSession | None = live.current_call
        if not call or call.state not in {CallState.TRUSTED_ACTIVE, CallState.BRIDGED}:
            return False
        call.family_ringing = True
        await live.send_phone("family", {"type": "ring", "from_label": "Margaret's call", "trusted": True})
        await live.send_phone("family", {"type": "state", "call_state": call.state.value,
                                          "badge": "Family invited", "monitored": call.monitored})
        db.add_event(call.id, call.elapsed_ms, "family", {"event": "ringing"})
        return True

    async def relay(self, room_name: str, sender: str, pcm: bytes) -> None:
        live = self.registry.get(room_name)
        call: CallSession | None = live.current_call
        if not call or call.state == CallState.ENDED:
            return
        if sender in call.held:
            return
        active = call.state in {CallState.TRUSTED_ACTIVE, CallState.BRIDGED}
        if call.monitored and sender in call.recorders and (active or sender == "caller"):
            call.recorders[sender].write(pcm)
        if (
            call.state == CallState.BRIDGED
            and call.monitor is not None
            and sender in {"caller", "senior"}
        ):
            await call.monitor.feed_audio(sender, pcm)
        if not active:
            return
        targets: list[str] = []
        if sender == "caller":
            targets = ["senior"] + (["family"] if call.family_joined else [])
        elif sender == "senior":
            targets = ["caller"] + (["family"] if call.family_joined else [])
        elif sender == "family" and call.family_joined:
            targets = ["caller", "senior"]
        await asyncio.gather(*(live.send_audio(target, pcm) for target in targets if target not in call.held))

    async def text(self, room_name: str, sender: str, text: str) -> None:
        text = text.strip()
        if not text:
            return
        live = self.registry.get(room_name)
        call: CallSession | None = live.current_call
        if not call or call.state == CallState.ENDED:
            return
        if call.monitored:
            if call.state == CallState.BRIDGED and call.monitor is not None:
                await call.monitor.inject_text(sender, text)
            else:
                db.add_segment(call.id, sender, call.elapsed_ms, text, True)
                await live.broadcast_dashboard({
                    "type": "transcript", "call_id": call.id, "speaker": sender,
                    "t_ms": call.elapsed_ms, "text": text, "final": True,
                })
        if call.state not in {CallState.TRUSTED_ACTIVE, CallState.BRIDGED}:
            return
        targets = [role for role in ("caller", "senior", "family")
                   if role != sender and (role != "family" or call.family_joined)]
        await asyncio.gather(*(live.send_phone(role, {"type": "agent_say", "text": text,
                                                       "agent": sender}) for role in targets))


calls = CallController()
