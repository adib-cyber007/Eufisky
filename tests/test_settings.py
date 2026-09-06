"""Per-room routing settings API and dashboard toggle."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import db
from app.main import app


def test_always_ring_first_setting_defaults_off_and_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "settings.db")
    with TestClient(app) as client:
        url = "/api/rooms/settings-room/settings"
        initial = client.get(url)
        assert initial.status_code == 200
        assert initial.json() == {"always_ring_first": False}
        saved = client.patch(url, json={"always_ring_first": True})
        assert saved.status_code == 200
        assert saved.json() == {"always_ring_first": True}
        assert client.get(url).json() == {"always_ring_first": True}


def test_notice_and_settings_ui_contract() -> None:
    client = TestClient(app)
    senior = client.get("/senior").text
    dashboard = client.get("/dashboard").text
    phone_script = client.get("/static/js/phone.js").text
    dashboard_script = client.get("/static/js/dashboard.js").text
    assert 'id="screening-notice"' in senior
    assert "A call from ${message.caller_label" in phone_script
    assert "audio.notice()" in phone_script
    assert 'id="message-unread"' in dashboard
    assert "unreadMessages += 1" in dashboard_script
    assert "Always ring me first, even for calls that look risky" in dashboard
