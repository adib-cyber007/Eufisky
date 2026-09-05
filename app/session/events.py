"""Persist and broadcast the live monitoring event stream."""

from __future__ import annotations

from typing import Any

from app import db
from app.rooms import LiveRoom
from app.rules.engine import RiskUpdate
from app.stt.assemblyai_stream import WordEvent


class EventPublisher:
    def __init__(self, call_id: str, room: LiveRoom) -> None:
        self.call_id = call_id
        self.room = room

    async def transcript(self, event: WordEvent) -> None:
        db.add_segment(
            self.call_id, event.speaker, event.t_ms, event.text, event.final
        )
        await self.room.broadcast_dashboard({
            "type": "transcript",
            "call_id": self.call_id,
            "speaker": event.speaker,
            "t_ms": event.t_ms,
            "text": event.text,
            "final": event.final,
        })

    async def risk(self, update: RiskUpdate) -> None:
        db.add_risk_sample(
            self.call_id, update.t_ms, update.score, update.active_signals
        )
        payload = {
            "type": "risk",
            "call_id": self.call_id,
            "t_ms": update.t_ms,
            "score": update.score,
            "signals": update.active_signals,
            "evidence": update.evidence,
            "flags": update.flags,
        }
        db.add_event(self.call_id, update.t_ms, "risk", payload)
        await self.room.broadcast_dashboard(payload)

    async def state(
        self, t_ms: int, previous: str, target: str, trigger: str
    ) -> None:
        payload = {
            "type": "state",
            "call_id": self.call_id,
            "t_ms": t_ms,
            "from": previous,
            "to": target,
            "trigger": trigger,
        }
        db.add_event(self.call_id, t_ms, "state", payload)
        await self.room.broadcast_dashboard(payload)

    async def level(self, t_ms: int, level: int, trigger: str) -> None:
        payload: dict[str, Any] = {
            "type": "level",
            "call_id": self.call_id,
            "t_ms": t_ms,
            "level": level,
            "trigger": trigger,
        }
        db.add_event(self.call_id, t_ms, "level", payload)
        await self.room.broadcast_dashboard(payload)
