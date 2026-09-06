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
from app.agent.guardian import GuardianSession
from app.agent.policies import decide
from app.audio import WavWriter
from app.config import settings
from app.rules.loader import load_lexicon
from app.rooms import LiveRoom, RoomRegistry, rooms
from app.session.context import CallMonitor, guardian_context
from app.session.events import EventPublisher
from app.stt.assemblyai_stream import STTStream
from app.postcall import pipeline as postcall
from app.runtime_paths import PROJECT_ROOT, recordings_dir

RECORDINGS_DIR = recordings_dir()


class CallState(str, Enum):
    IDLE = "IDLE"
    RINGING_SENIOR = "RINGING_SENIOR"
    TRUSTED_ACTIVE = "TRUSTED_ACTIVE"
    SCREENING = "SCREENING"
    DIALING_SENIOR = "DIALING_SENIOR"
    INTRO = "INTRO"
    BRIDGED = "BRIDGED"
    GUARDIAN = "GUARDIAN"
    FAMILY_CONF = "FAMILY_CONF"
    WRAPUP = "WRAPUP"
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
        self.guardian: GuardianSession | None = None
        self.guardian_outcome = ""
        self.guardian_evidence: list[dict[str, Any]] = []
        self.guardian_recommendation = "end the call or bring in family"
        self.block_requested = False
        self.seed_score = 0
        self.caller_name = label
        self.purpose = ""
        self.claimed_org = ""
        self.notice_sent = False
        self.dial_timeout: asyncio.Task[None] | None = None
        if self.monitored:
            for leg in ("caller", "senior"):
                path = RECORDINGS_DIR / f"{self.id}_{leg}.wav"
                try:
                    stored_path = path.resolve().relative_to(PROJECT_ROOT).as_posix()
                except ValueError:
                    stored_path = str(path.resolve())
                self.recording_paths[leg] = stored_path
                self.recorders[leg] = WavWriter(path)

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
                   "badge": call.badge, "monitored": call.monitored,
                   "family_joined": call.family_joined,
                   "family_ringing": call.family_ringing}
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
        decision = decide(
            requested,
            args,
            score,
            always_ring_first=db.get_room_settings(call.room.room)["always_ring_first"],
        )
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
            call.claimed_org = str(decision.args.get("claimed_org") or "")
            if not call.claimed_org and "medicare" in call.purpose.casefold():
                call.claimed_org = "Medicare"
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
        await self._screening_notice(call, decision.action, decision.args)
        await call.room.send_phone("caller", {
            "type": "agent_say", "text": decision.result["say"], "agent": "front_door"
        })
        if call.frontdoor:
            await call.frontdoor.close()
        await asyncio.sleep(self.closing_delay)
        await self.hangup(call.room.room, decision.action)

    async def _screening_notice(
        self, call: CallSession, outcome: str, args: dict[str, Any]
    ) -> None:
        """Publish one calm visibility notice for a filtered Front Door outcome."""
        if outcome not in {"take_message", "decline"} or call.notice_sent:
            return
        call.notice_sent = True
        caller_label = str(args.get("caller_name") or call.caller_name or call.label)
        purpose = str(args.get("message") or args.get("reason") or call.purpose or "No details provided")
        callback_number = str(args.get("callback_number") or "")
        notice = {
            "type": "notice",
            "t_ms": call.elapsed_ms,
            "kind": "message_taken" if outcome == "take_message" else "declined",
            "caller_label": caller_label,
            "purpose": purpose,
            "callback_number": callback_number,
        }
        await asyncio.gather(
            call.room.send_phone("senior", notice),
            call.room.broadcast_dashboard(notice),
        )

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
                    call, self.lexicon, self.stt_factory, seed_score=call.seed_score,
                    on_guardian=lambda update, trigger: self._start_guardian(call, update, trigger),
                    on_action=lambda name, args: self._guardian_action(call, name, args),
                    on_recommendation=lambda value: self._guardian_recommendation(call, value),
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

    async def _start_guardian(self, call: CallSession, update: Any, trigger: str) -> None:
        """Sever the public bridge before starting any Guardian network work."""
        call.state = CallState.GUARDIAN
        call.guardian_evidence = list(update.evidence)
        if update.score >= 90:
            call.guardian_recommendation = "bring in family"
        call.held.add("caller")
        if call.monitor is not None:
            await call.monitor.pause_for_guardian(lambda text: self._guardian_text(call, text))
        await call.room.send_phone("caller", {"type": "hold", "on": True})
        await call.room.send_phone("caller", {"type": "tone", "name": "hold_music"})
        await call.room.send_phone("senior", {
            "type": "agent_say", "text": "One moment, Margaret.", "agent": "guardian"
        })
        await self._send_state(call)
        await call.room.broadcast_dashboard({
            "type": "guardian", "call_id": call.id, "t_ms": call.elapsed_ms,
            "state": "GUARDIAN", "trigger": trigger, "recommendation": call.guardian_recommendation,
        })
        context = guardian_context(
            call.guardian_evidence, caller_name=call.caller_name,
            claim=call.claimed_org or call.purpose or call.caller_name,
            senior_name=settings.senior_name, family_name=settings.family_name,
            recommendation=call.guardian_recommendation,
        )
        call.guardian = GuardianSession(
            call, self.backend_factory(), context,
            lambda event: self._guardian_tool(call, event),
        )
        await call.guardian.start()
        if call.monitor is not None:
            await call.monitor.start_guardian_listening()

    async def _guardian_recommendation(self, call: CallSession, value: str) -> None:
        call.guardian_recommendation = value
        if call.guardian is not None:
            call.guardian.context["recommendation"] = value
        await call.room.broadcast_dashboard({
            "type": "guardian", "call_id": call.id, "t_ms": call.elapsed_ms,
            "state": call.state.value, "recommendation": value,
        })

    async def _guardian_text(self, call: CallSession, text: str) -> None:
        if call.guardian is not None:
            await call.guardian.on_text(text)

    def _save_contact(self, call: CallSession, label: str, status: str) -> None:
        existing = next((item for item in db.list_contacts(call.room.room) if item["phone"] == call.caller_phone), None)
        if existing:
            db.update_contact(call.room.room, int(existing["id"]), {"label": label, "status": status})
        else:
            db.create_contact(call.room.room, call.caller_phone, label, status, "guardian")

    async def _guardian_action(self, call: CallSession, name: str, args: dict[str, Any]) -> dict[str, Any]:
        call.guardian_outcome = name
        db.update_call(call.id, guardian_outcome=name)
        if name == "conference_family":
            call.family_ringing = True
            identity = call.caller_name
            if call.claimed_org and call.claimed_org.casefold() not in identity.casefold():
                identity = f"{identity} from {call.claimed_org}"
            reason = f"Eufisky paused a risky call with '{identity}'"
            await call.room.send_phone("family", {"type": "ring", "from_label": call.caller_name, "reason": reason, "trusted": False})
            await call.room.send_phone("family", {"type": "guardian_controls", "visible": True, "family": True})
            db.add_event(call.id, call.elapsed_ms, "family", {"event": "ringing", "reason": reason})
        elif name == "end_call":
            call.block_requested = bool(args.get("block_number", True))
        elif name == "add_to_trusted":
            peak = int((db.get_call(call.id) or {}).get("peak_risk") or 0)
            status = "pending" if peak >= 85 else "trusted"
            self._save_contact(call, str(args.get("label") or call.caller_name or "Known caller"), status)
            call.family_ringing = False
        elif name == "resume_call":
            call.family_ringing = False
        return {"ok": True, "action": name}

    async def _guardian_tool(self, call: CallSession, event: dict[str, Any]) -> None:
        if call.monitor is None:
            return
        result = await call.monitor.machine.on_agent_event(event, call.elapsed_ms)
        if result is None or not result.get("ok"):
            return
        name = str(event.get("name") or "")
        guardian = call.guardian
        if guardian is not None:
            await guardian.tool_result(str(event.get("id") or ""), result)
        reassurance = {
            "resume_call": "All right. I will reconnect you now.",
            "add_to_trusted": "All right. I saved that choice and will reconnect you.",
            "conference_family": f"{settings.family_name}'s phone is ringing. You're not alone.",
            "end_call": "You're safe. I have ended the call.",
        }[name]
        await call.room.send_phone("senior", {"type": "agent_say", "text": reassurance, "agent": "guardian"})
        call.state = CallState(call.monitor.machine.state.value)
        await self._send_state(call)
        await call.room.broadcast_dashboard({
            "type": "guardian", "call_id": call.id, "t_ms": call.elapsed_ms,
            "state": call.state.value, "tool": name,
        })
        if name in {"resume_call", "add_to_trusted"}:
            call.held.discard("caller")
            call.family_ringing = False
            await call.room.send_phone("caller", {"type": "hold", "on": False})
            await call.room.send_phone("caller", {"type": "tone", "name": "hold_stop"})
            await call.room.send_phone("senior", {"type": "guardian_controls", "visible": False})
            await call.room.send_phone("family", {"type": "guardian_controls", "visible": False})
            call.guardian = None
            if guardian is not None:
                await guardian.close()
            await call.monitor.resume_monitoring()
        elif name == "conference_family":
            call.state = CallState.FAMILY_CONF
            await self._send_state(call)
            call.guardian = None
            if guardian is not None:
                await guardian.close()
        elif name == "end_call":
            if self.closing_delay:
                await asyncio.sleep(self.closing_delay)
            await self.hangup(call.room.room, "Guardian ended the call")

    async def guardian_action(self, room_name: str, role: str, action: str) -> bool:
        call = self.registry.get(room_name).current_call
        if not call or not call.monitor or call.state not in {CallState.GUARDIAN, CallState.FAMILY_CONF}:
            return False
        mapping = {
            "resume": ("resume_call", {}), "continue": ("resume_call", {}),
            "family": ("conference_family", {"keep_caller_on_hold": True}),
            "end": ("end_call", {"block_number": True}),
        }
        if action not in mapping:
            return False
        name, args = mapping[action]
        await self._guardian_tool(call, {"type": "tool_call", "name": name, "args": args, "id": f"{role}-control"})
        return True

    async def hangup(self, room_name: str, reason: str = "Call ended") -> None:
        live = self.registry.get(room_name)
        call: CallSession | None = live.current_call
        if not call or call.state == CallState.ENDED:
            return
        if call.dial_timeout and call.dial_timeout is not asyncio.current_task() and not call.dial_timeout.done():
            call.dial_timeout.cancel()
        if call.frontdoor is not None:
            await call.frontdoor.close()
        machine_wrapped = False
        if call.monitor is not None:
            await call.monitor.machine.on_hangup(call.elapsed_ms)
            call.state = CallState.WRAPUP
            machine_wrapped = True
            await call.monitor.close()
        if call.guardian is not None:
            await call.guardian.close()
            call.guardian = None
        if not machine_wrapped:
            await self._transition(call, CallState.WRAPUP, reason)
        call.close_recorders()
        ended_at = datetime.now(timezone.utc).isoformat()
        peak = int((db.get_call(call.id) or {}).get("peak_risk") or 0)
        if call.monitored and call.caller_phone and (call.block_requested or peak >= 85):
            classification, _ = db.classify_phone(call.room.room, call.caller_phone)
            if classification != "trusted":
                self._save_contact(call, call.caller_name or "Blocked caller", "blocked")
        db.update_call(call.id, ended_at=ended_at, final_state=CallState.WRAPUP.value,
                       peak_risk=peak, guardian_outcome=call.guardian_outcome or None)
        await asyncio.gather(*(live.send_phone(role, {"type": "ended", "reason": reason})
                               for role in ("caller", "senior", "family")))
        await live.broadcast_dashboard({"type": "call", "t_ms": call.elapsed_ms, "event": "ended",
                                         "call_id": call.id, "classification": call.classification})
        postcall.enqueue(call.id)
        call.state = CallState.ENDED

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
        if not call or call.state not in {CallState.TRUSTED_ACTIVE, CallState.BRIDGED, CallState.GUARDIAN}:
            return False
        if call.state == CallState.GUARDIAN:
            return await self.guardian_action(room_name, "dashboard", "family")
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
        active = call.state in {CallState.TRUSTED_ACTIVE, CallState.BRIDGED, CallState.FAMILY_CONF}
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
        if call.state == CallState.GUARDIAN and sender == "senior":
            if call.monitor is not None:
                await call.monitor.feed_audio("senior", pcm)
            if call.guardian is not None:
                await call.guardian.on_audio(pcm)
        if not active:
            return
        targets: list[str] = []
        if call.state == CallState.FAMILY_CONF:
            if sender == "senior" and call.family_joined:
                targets = ["family"]
            elif sender == "family" and call.family_joined:
                targets = ["senior"]
        elif sender == "caller":
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
            elif call.state in {CallState.GUARDIAN, CallState.FAMILY_CONF} and sender == "senior" and call.guardian is not None:
                db.add_segment(call.id, sender, call.elapsed_ms, text, True)
                await live.broadcast_dashboard({"type": "transcript", "call_id": call.id, "speaker": sender, "t_ms": call.elapsed_ms, "text": text, "final": True})
                await call.guardian.on_text(text)
                return
            else:
                db.add_segment(call.id, sender, call.elapsed_ms, text, True)
                await live.broadcast_dashboard({
                    "type": "transcript", "call_id": call.id, "speaker": sender,
                    "t_ms": call.elapsed_ms, "text": text, "final": True,
                })
        if call.state not in {CallState.TRUSTED_ACTIVE, CallState.BRIDGED, CallState.FAMILY_CONF}:
            return
        if call.state == CallState.FAMILY_CONF:
            targets = ["family"] if sender == "senior" and call.family_joined else ["senior"] if sender == "family" and call.family_joined else []
        else:
            targets = [role for role in ("caller", "senior", "family") if role != sender and (role != "family" or call.family_joined)]
        await asyncio.gather(*(live.send_phone(role, {"type": "agent_say", "text": text,
                                                       "agent": sender}) for role in targets))


calls = CallController()
