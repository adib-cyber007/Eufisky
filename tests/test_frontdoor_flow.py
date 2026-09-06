"""End-to-end Front Door state paths with a scripted backend and fake STT."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app import db
from app.phone import calls as call_module
from app.phone.calls import CallController, CallState
from app.rooms import RoomRegistry


class FakeSocket:
    def __init__(self) -> None:
        self.json: list[dict[str, Any]] = []
        self.audio: list[bytes] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.json.append(payload)

    async def send_bytes(self, payload: bytes) -> None:
        self.audio.append(payload)


class FakeSTT:
    def __init__(self, speaker: str, keyterms: list[str], sample_rate: int) -> None:
        self.speaker = speaker
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.closed = False

    async def start(self) -> None: pass
    async def send_audio(self, pcm: bytes) -> None: pass
    async def close(self) -> None:
        if not self.closed:
            self.closed = True
            await self.queue.put(None)
    def __aiter__(self): return self
    async def __anext__(self):
        item = await self.queue.get()
        if item is None: raise StopAsyncIteration
        return item


class ScriptedBackend:
    def __init__(self, tool: str, args: dict[str, Any]) -> None:
        self.tool, self.args = tool, args
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.sent = False

    async def start(self, instructions, tools, context) -> None:
        await self.queue.put({"type": "say", "text": "Hello, who's calling?"})

    async def on_user_text(self, text: str) -> None:
        if not self.sent:
            self.sent = True
            await self.queue.put({"type": "tool_call", "name": self.tool,
                                  "args": self.args, "id": "tool-1"})

    async def tool_result(self, call_id: str, result: dict[str, Any]) -> None: pass
    async def close(self) -> None: pass
    async def events(self):
        while True:
            yield await self.queue.get()


@pytest.fixture()
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "frontdoor.db")
    monkeypatch.setattr(call_module, "RECORDINGS_DIR", tmp_path / "recordings")
    db.init_db()

    def build(tool: str, args: dict[str, Any]):
        registry = RoomRegistry()
        sockets = {role: FakeSocket() for role in ("caller", "senior", "family")}
        for role, socket in sockets.items():
            registry.register_phone("demo", role, socket,
                                    "+15550199321" if role == "caller" else None)
        backend = ScriptedBackend(tool, args)
        controller = CallController(
            registry, stt_factory=FakeSTT, backend_factory=lambda: backend,
            closing_delay=0, intro_delay=0, senior_timeout=25,
        )
        return controller, sockets
    return build


@pytest.mark.asyncio
async def test_connect_rings_introduces_and_bridges_with_seed(setup) -> None:
    controller, sockets = setup("connect_caller", {
        "caller_name": "Michael", "purpose": "urgent update to Medicare benefits"
    })
    call = await controller.dial("demo", "+15550199321")
    assert call.state == CallState.SCREENING
    await controller.text("demo", "caller", "This is Michael from Medicare calling about an urgent update to her benefits")
    await asyncio.sleep(0.02)
    assert call.state == CallState.DIALING_SENIOR
    assert any(item.get("type") == "ring" for item in sockets["senior"].json)
    assert call.seed_score < 40
    await controller.answer("demo", "senior")
    assert call.state == CallState.BRIDGED
    assert call.monitor is not None and call.monitor.engine.seed_score == call.seed_score
    assert any("Call from Michael" in item.get("text", "") for item in sockets["senior"].json)
    await controller.hangup("demo")


@pytest.mark.asyncio
async def test_take_message_persists_and_ends(setup) -> None:
    controller, _ = setup("take_message", {
        "caller_name": "Unknown caller", "message": "Would not provide a name",
        "callback_number": "",
    })
    call = await controller.dial("demo", "+15550199321")
    await controller.text("demo", "caller", "I refuse to give my name")
    await asyncio.sleep(0.02)
    assert call.state == CallState.ENDED
    assert db.list_messages("demo")[0]["body"] == "Would not provide a name"


@pytest.mark.asyncio
async def test_decline_ends_without_message(setup) -> None:
    controller, _ = setup("decline", {"reason": "sales"})
    call = await controller.dial("demo", "+15550199321")
    await controller.text("demo", "caller", "I'm selling extended car warranties")
    await asyncio.sleep(0.02)
    assert call.state == CallState.ENDED
    assert all(message["call_id"] != call.id for message in db.list_messages("demo"))


@pytest.mark.asyncio
async def test_high_risk_connect_is_overridden(setup) -> None:
    controller, _ = setup("connect_caller", {
        "caller_name": "Alex", "purpose": "pay the IRS with gift cards immediately"
    })
    call = await controller.dial("demo", "+15550199321")
    await controller.text("demo", "caller", "This is Alex from the IRS. Pay with gift cards immediately or police will arrest you")
    await asyncio.sleep(0.02)
    assert call.state == CallState.ENDED
    assert db.get_call(call.id)["front_door_outcome"] == "take_message"
    assert db.list_messages("demo")
