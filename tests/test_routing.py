"""Routing and trusted-call privacy guarantees."""

from pathlib import Path

import pytest

from app import db
from app.phone.calls import CallController
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
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    return path


def test_classification_order_and_withheld(isolated_db: Path) -> None:
    db.create_contact("routing", "+15550000000", "Trusted duplicate", "trusted")
    db.create_contact("routing", "+15550000000", "Blocked duplicate", "blocked")
    assert db.classify_phone("routing", "+15550000000") == ("blocked", "Blocked duplicate")
    assert db.classify_phone("routing", "")[0] == "unknown"
    assert db.classify_phone("routing", None)[0] == "unknown"
    assert db.classify_phone("routing", "+15559999999")[0] == "unknown"


def test_empty_existing_room_is_not_reseeded(isolated_db: Path) -> None:
    contacts = db.list_contacts("empty-room")
    assert len(contacts) == 2
    for contact in contacts:
        assert db.delete_contact("empty-room", contact["id"])
    db.ensure_room("empty-room")
    assert db.list_contacts("empty-room") == []


@pytest.mark.asyncio
async def test_trusted_call_never_records_or_stores_segments(isolated_db: Path) -> None:
    registry = RoomRegistry()
    caller, senior = FakeSocket(), FakeSocket()
    registry.register_phone("demo", "caller", caller, "+15550100101")
    registry.register_phone("demo", "senior", senior)
    controller = CallController(registry)

    call = await controller.dial("demo", "+15550100101")
    await controller.answer("demo", "senior")
    await controller.text("demo", "caller", "This must remain private")
    await controller.relay("demo", "caller", b"\x00\x00" * 1600)
    await controller.hangup("demo")

    stored = db.get_call(call.id)
    assert call.monitored is False
    assert call.recorders == {}
    assert stored["recording_caller"] is None
    assert stored["recording_senior"] is None
    assert db.list_segments(call.id) == []
    assert senior.audio == [b"\x00\x00" * 1600]
