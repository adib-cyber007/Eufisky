"""Replay file validation and timed dashboard publication."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import db
from app.main import app
from app.replay import load_replay, play_events
from app.rooms import rooms
from tools.record_replay import export_call


class FakeDashboard:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


def test_demo_replay_has_complete_event_story() -> None:
    replay = load_replay("demo_call.json")
    event_types = {event["type"] for event in replay["events"]}
    assert {"call", "state", "caption", "risk", "level", "guardian", "tool"} <= event_types
    assert {event.get("role") for event in replay["events"] if event["type"] == "caption"} >= {
        "caller", "senior"
    }
    assert replay["events"][-1]["event"] == "ended"


@pytest.mark.asyncio
async def test_replay_publishes_in_order_at_selected_speed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "replay.db")
    db.init_db()
    room = "replay-timing"
    socket = FakeDashboard()
    rooms.register_dashboard(room, socket)
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    events = [
        {"type": "state", "t_ms": 1000, "to": "BRIDGED"},
        {"type": "caption", "t_ms": 3000, "speaker": "caller", "text": "Hello"},
    ]
    await play_events(room, events, speed=2, sleep=fake_sleep)
    rooms.unregister_dashboard(room, socket)

    assert delays == [0.5, 1.0]
    assert [message.get("status") for message in socket.messages if message["type"] == "replay"] == [
        "started", "completed"
    ]
    published = [message for message in socket.messages if message["type"] in {"state", "transcript"}]
    assert [message["t_ms"] for message in published] == [1000, 3000]
    assert all(message["replay"] is True for message in published)
    assert published[1]["final"] is True


def test_replay_rejects_paths_outside_data() -> None:
    with pytest.raises(ValueError):
        load_replay("../secret.json")


def test_seeded_call_export_restores_risk_and_transcript(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seeded-export.db")
    db.init_db()
    seeded = next(
        call for call in db.list_calls("demo")
        if call["from_phone"] == "+15550198740"
    )
    output = tmp_path / "seeded.json"
    replay = export_call(str(seeded["id"]), output)
    event_types = {event["type"] for event in replay["events"]}
    assert {"call", "risk", "transcript", "state", "level", "tool"} <= event_types
    assert max(event.get("score", 0) for event in replay["events"]) == 96
    assert any(event.get("speaker") == "senior" for event in replay["events"])


def test_replay_endpoint_delivers_complete_story_to_websocket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "replay-websocket.db")
    with TestClient(app) as client:
        with client.websocket_connect("/ws/dashboard?room=replay-websocket") as socket:
            assert socket.receive_json()["trigger"] == "snapshot"
            response = client.post(
                "/api/rooms/replay-websocket/replay",
                json={"file": "demo_call.json", "speed": 20},
            )
            assert response.status_code == 200
            received: list[dict] = []
            while True:
                message = socket.receive_json()
                received.append(message)
                if message.get("type") == "replay" and message.get("status") == "completed":
                    break
    event_types = {message["type"] for message in received}
    assert {"risk", "transcript", "state", "tool", "replay"} <= event_types
    assert any(message.get("status") == "completed" for message in received)
