"""Call transitions and bridge behavior with in-memory fake sockets."""

from pathlib import Path
import time

import pytest

from app import db
from app.phone import calls as call_module
from app.phone.calls import CallController, CallState
from app.phone.ws import normalize_message
from app.rooms import RoomRegistry


class FakeSocket:
    def __init__(self) -> None:
        self.json: list[dict] = []
        self.audio: list[bytes] = []

    async def send_json(self, payload: dict) -> None:
        self.json.append(payload)

    async def send_bytes(self, payload: bytes) -> None:
        self.audio.append(payload)


@pytest.fixture()
def call_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(call_module, "RECORDINGS_DIR", tmp_path / "recordings")
    db.init_db()
    registry = RoomRegistry()
    sockets = {role: FakeSocket() for role in ("caller", "senior", "family")}
    for role, socket in sockets.items():
        registry.register_phone("demo", role, socket,
                                "+15550199321" if role == "caller" else None)
    return CallController(registry), sockets


@pytest.mark.asyncio
async def test_unknown_call_transitions_records_and_family_joins(call_setup) -> None:
    controller, sockets = call_setup
    call = await controller.dial("demo", "+15550199321")
    assert call.state == CallState.RINGING_SENIOR
    assert any(message.get("type") == "agent_say" for message in sockets["caller"].json)
    assert any(message.get("type") == "ring" for message in sockets["senior"].json)
    await controller.text("demo", "caller", "My name is Pat")
    assert db.list_segments(call.id)[0]["text"] == "My name is Pat"
    screening_frame = b"\x02\x00" * 1600
    await controller.relay("demo", "caller", screening_frame)
    assert sockets["senior"].audio == []

    await controller.answer("demo", "senior")
    assert call.state == CallState.BRIDGED
    frame = b"\x01\x00" * 1600
    await controller.relay("demo", "caller", frame)
    assert sockets["senior"].audio == [frame]

    assert await controller.ring_family("demo") is True
    await controller.answer("demo", "family")
    await controller.relay("demo", "senior", frame)
    assert sockets["family"].audio == [frame]

    await controller.text("demo", "caller", "Please send gift cards")
    assert [segment["text"] for segment in db.list_segments(call.id)] == [
        "My name is Pat", "Please send gift cards"
    ]
    await controller.hangup("demo")
    assert call.state == CallState.ENDED
    assert all(writer.closed for writer in call.recorders.values())
    assert all((call_module.RECORDINGS_DIR / f"{call.id}_{leg}.wav").exists()
               for leg in ("caller", "senior"))
    assert (call_module.RECORDINGS_DIR / f"{call.id}_caller.wav").stat().st_size > 44


@pytest.mark.asyncio
async def test_hold_stops_audio_both_directions(call_setup) -> None:
    controller, sockets = call_setup
    await controller.dial("demo", "+15550199321")
    await controller.answer("demo", "senior")
    await controller.hold("demo", "caller", True)
    await controller.relay("demo", "caller", b"\x00\x00")
    await controller.relay("demo", "senior", b"\x00\x00")
    assert sockets["caller"].audio == []
    assert sockets["senior"].audio == []


@pytest.mark.asyncio
async def test_relay_adds_less_than_250ms(call_setup) -> None:
    controller, _ = call_setup
    await controller.dial("demo", "+15550199321")
    await controller.answer("demo", "senior")
    started = time.perf_counter()
    await controller.relay("demo", "caller", b"\x00\x00" * 1600)
    assert time.perf_counter() - started < 0.250
    await controller.hangup("demo")


def test_protocol_envelopes_are_normalized() -> None:
    assert normalize_message('{"type":"text","text":"hello"}') == {
        "type": "text", "text": "hello"
    }
    assert normalize_message('{"text":{"text":"hello"}}') == {
        "type": "text", "text": "hello"
    }
    assert normalize_message('{"mic":{"on":true}}') == {"type": "mic", "on": True}
