"""Smoke tests for the Phase-0 HTTP surface."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import db
from app.main import app


def test_health() -> None:
    """The liveness endpoint returns the documented payload."""

    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["db_ok"] is True
    assert isinstance(payload["assemblyai_key_present"], bool)
    assert payload["agent_backend"] in {"auto", "voice_agent", "llm"}


def test_index_title() -> None:
    """The browser shell is served and clearly titled."""

    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "<title>Eufisky</title>" in response.text


def test_dashboard_socket_survives_malformed_messages_and_seeds_room(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "socket.db")
    with TestClient(app) as client:
        with client.websocket_connect("/ws/dashboard?room=fresh-socket") as socket:
            assert socket.receive_json()["trigger"] == "snapshot"
            socket.send_text("not-json")
            assert socket.receive_json()["type"] == "error"
            socket.send_json({"type": "unsupported"})
            assert socket.receive_json()["type"] == "error"
    assert len(db.list_contacts("fresh-socket")) == 2
    assert len([call for call in db.list_calls("fresh-socket") if call["incident"]]) == 3


def test_phone_socket_connects_and_survives_malformed_messages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "phone-socket.db")
    with TestClient(app) as client:
        with client.websocket_connect("/ws/phone") as socket:
            socket.send_json(
                {"type": "hello", "role": "senior", "room": "fresh-phone"}
            )
            assert socket.receive_json()["type"] == "state"
            socket.send_text("[]")
            assert socket.receive_json()["type"] == "error"
            socket.send_json({"type": "unsupported"})
            assert socket.receive_json()["type"] == "error"


def test_landing_and_dashboard_expose_guidance_replay_and_reconnect() -> None:
    client = TestClient(app)
    landing = client.get("/").text
    dashboard = client.get("/dashboard").text
    script = client.get("/static/js/dashboard.js").text
    assert "Try the scam demo" in landing
    assert "Use type-to-talk if you don’t have a mic" in landing
    assert "▶ Replay demo call" in dashboard
    assert "setTimeout(connectDashboard" in script
