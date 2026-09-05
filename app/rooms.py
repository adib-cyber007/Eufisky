"""In-memory live room state; durable call history lives in SQLite."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PhoneConnection:
    role: str
    socket: Any
    caller_phone: str | None = None


@dataclass(slots=True)
class LiveRoom:
    room: str
    phones: dict[str, PhoneConnection] = field(default_factory=dict)
    dashboards: list[Any] = field(default_factory=list)
    current_call: Any = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send_phone(self, role: str, payload: dict[str, Any]) -> bool:
        connection = self.phones.get(role)
        if not connection:
            return False
        try:
            await connection.socket.send_json(payload)
            return True
        except Exception:
            return False

    async def send_audio(self, role: str, pcm: bytes) -> bool:
        connection = self.phones.get(role)
        if not connection:
            return False
        try:
            await connection.socket.send_bytes(pcm)
            return True
        except Exception:
            return False

    async def broadcast_dashboard(self, payload: dict[str, Any]) -> None:
        stale: list[Any] = []
        for socket in list(self.dashboards):
            try:
                await socket.send_json(payload)
            except Exception:
                stale.append(socket)
        for socket in stale:
            if socket in self.dashboards:
                self.dashboards.remove(socket)


class RoomRegistry:
    def __init__(self) -> None:
        self._rooms: dict[str, LiveRoom] = {}

    def get(self, room: str) -> LiveRoom:
        room = room.strip() or "demo"
        if room not in self._rooms:
            self._rooms[room] = LiveRoom(room)
        return self._rooms[room]

    def register_phone(
        self, room: str, role: str, socket: Any, caller_phone: str | None = None
    ) -> PhoneConnection:
        connection = PhoneConnection(role, socket, caller_phone)
        self.get(room).phones[role] = connection
        return connection

    def unregister_phone(self, room: str, role: str, socket: Any) -> bool:
        live = self.get(room)
        current = live.phones.get(role)
        if current and current.socket is socket:
            del live.phones[role]
            return True
        return False

    def register_dashboard(self, room: str, socket: Any) -> None:
        live = self.get(room)
        if socket not in live.dashboards:
            live.dashboards.append(socket)

    def unregister_dashboard(self, room: str, socket: Any) -> None:
        live = self.get(room)
        if socket in live.dashboards:
            live.dashboards.remove(socket)

    def snapshot(self, room: str) -> dict[str, Any]:
        live = self.get(room)
        call = live.current_call
        return {
            "type": "state",
            "t_ms": call.elapsed_ms if call else 0,
            "from": call.state.value if call else "IDLE",
            "to": call.state.value if call else "IDLE",
            "trigger": "snapshot",
            "call_id": call.id if call else None,
            "classification": call.classification if call else None,
        }


rooms = RoomRegistry()
