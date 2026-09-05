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
from app.agent import make_backend
from app.agent.frontdoor import FrontDoorSession
from app.agent.policies import decide
from app.audio import WavWriter
from app.rules.loader import load_lexicon
from app.rooms import LiveRoom, RoomRegistry, rooms
from app.session.context import CallMonitor
from app.session.events import EventPublisher
from app.stt.assemblyai_stream import STTStream

RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "data" / "recordings"


class CallState(str, Enum):
    IDLE = "IDLE"
    RINGING_SENIOR = "RINGING_SENIOR"
    TRUSTED_ACTIVE = "TRUSTED_ACTIVE"
    SCREENING = "SCREENING"
    DIALING_SENIOR = "DIALING_SENIOR"
    INTRO = "INTRO"
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
        self.frontdoor: FrontDoorSession | None = None
        self.seed_score = 0
        self.caller_name = label
        self.purpose = ""
        self.dial_timeout: asyncio.Task[None] | None = None
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
        backend_factory: Any = make_backend,
        closing_delay: float = 1.5,
        intro_delay: float = 1.0,
        senior_timeout: float = 25.0,
    ) -> None:
        self.registry = registry
        self.stt_factory = stt_factory
        self.lexicon = lexicon or load_lexicon()
        self.backend_factory = backend_factory
        self.closing_delay = closing_delay
        self.intro_delay = intro_delay
        self.senior_timeout = senior_timeout

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
                call.frontdoor = FrontDoorSession(
                    call, self.lexicon, self.backend_factory(),
                    lambda event, score: self._agent_tool(call, event, score),
                    self.stt_factory,
                )
                await call.frontdoor.start()
                return call
            await self._transition(call, CallState.RINGING_SENIOR, "trusted")
            await self._send_state(call, ("caller", "senior"))
            await live.send_phone("senior", {"type": "ring", "from_label": label,
                                              "trusted": classification == "trusted"})
            return call

    async def _agent_tool(self, call: CallSession, event: dict[str, Any], score: int) -> None:
        if call.state != CallState.SCREENING:
            return
        requested = str(event.get("name") or "")
        args = event.get("args") if isinstance(event.get("args"), dict) else {}
        decision = decide(requested, args, score)
        db.add_event(call.id, call.elapsed_ms, "front_door_decision", {
            "requested": requested, "executed": decision.action, "risk_score": score,
            "policy_override": decision.result.get("status") == "policy_override",
        })
        db.update_call(call.id, front_door_outcome=decision.action)
        if call.frontdoor:
            await call.frontdoor.tool_result(str(event.get("id") or ""), decision.result)

        if decision.action == "connect_caller":
            call.seed_score = score
            call.caller_name = str(decision.args["caller_name"])
            call.purpose = str(decision.args["purpose"])
            if call.frontdoor:
                await call.frontdoor.close()
            await call.room.send_phone("caller", {
                "type": "agent_say", "text": decision.result["say"], "agent": "front_door"
            })
            await self._transition(call, CallState.DIALING_SENIOR, "front_door_connected")
            await self._send_state(call, ("caller", "senior"))
            await call.room.send_phone("senior", {
                "type": "ring", "from_label": call.caller_name, "trusted": False
            })
            call.dial_timeout = asyncio.create_task(
                self._senior_timeout(call), name=f"senior-timeout-{call.id}"
            )
            return

        if decision.action == "take_message":
            db.add_message(
                call.room.room, call_id=call.id, from_phone=call.caller_phone,
                caller_name=decision.args["caller_name"], body=decision.args["message"],
                callback_number=decision.args.get("callback_number"),
            )
            await call.room.broadcast_dashboard({
                "type": "message", "call_id": call.id,
                "caller_name": decision.args["caller_name"], "body": decision.args["message"],
            })
        await call.room.send_phone("caller", {
            "type": "agent_say", "text": decision.result["say"], "agent": "front_door"
        })
        if call.frontdoor:
            await call.frontdoor.close()
        await asyncio.sleep(self.closing_delay)
        await self.hangup(call.room.room, decision.action)

    async def _senior_timeout(self, call: CallSession) -> None:
        try:
            await asyncio.sleep(self.senior_timeout)
            if call.state != CallState.DIALING_SENIOR:
                return
            db.add_message(
                call.room.room, call_id=call.id, from_phone=call.caller_phone,
                caller_name=call.caller_name, body=call.purpose,
                callback_number=call.caller_phone,
            )
            db.update_call(call.id, front_door_outcome="take_message_no_answer")
            await call.room.send_phone("caller", {
                "type": "agent_say",
                "text": "She couldn't answer, so I'll pass along your message. Goodbye.",
                "agent": "front_door",
            })
            await asyncio.sleep(2)
            await self.hangup(call.room.room, "senior did not answer")
        except asyncio.CancelledError:
            raise

    async def answer(self, room_name: str, role: str) -> None:
        live = self.registry.get(room_name)
        call: CallSession | None = live.current_call
        if not call or call.state == CallState.ENDED:
            return
        if role == "senior" and call.state in {CallState.RINGING_SENIOR, CallState.DIALING_SENIOR}:
            if call.dial_timeout and not call.dial_timeout.done():
                call.dial_timeout.cancel()
            target = CallState.TRUSTED_ACTIVE if call.classification == "trusted" else CallState.BRIDGED
            if target == CallState.BRIDGED:
                await self._transition(call, CallState.INTRO, "senior_answered")
                await self._send_state(call)
                await live.send_phone("senior", {
                    "type": "agent_say",
                    "text": f"Call from {call.caller_name} about {call.purpose}. Connecting.",
                    "agent": "front_door",
                })
                await asyncio.sleep(self.intro_delay)
                await self._transition(call, target, "intro_complete")
                call.monitor = CallMonitor(
                    call, self.lexicon, self.stt_factory, seed_score=call.seed_score
                )
                await call.monitor.start()
            else:
                await self._transition(call, target, "senior_answered")
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
        if call.dial_timeout and call.dial_timeout is not asyncio.current_task() and not call.dial_timeout.done():
            call.dial_timeout.cancel()
        if call.frontdoor is not None:
            await call.frontdoor.close()
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
        if call.state == CallState.SCREENING and sender == "caller" and call.frontdoor is not None:
            await call.frontdoor.feed_audio(pcm)
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
            if call.state == CallState.SCREENING and sender == "caller" and call.frontdoor is not None:
                await call.frontdoor.on_typed_text(text)
                return
            elif call.state == CallState.BRIDGED and call.monitor is not None:
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
