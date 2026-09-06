"""Replay file validation and timed dashboard publication."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import db
from app.replay import load_replay, play_events
from app.rooms import rooms


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
        "started", "complete"
    ]
    published = [message for message in socket.messages if message["type"] in {"state", "caption"}]
    assert [message["t_ms"] for message in published] == [1000, 3000]
    assert all(message["replay"] is True for message in published)


def test_replay_rejects_paths_outside_data() -> None:
    with pytest.raises(ValueError):
        load_replay("../secret.json")
