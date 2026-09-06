"""Contact REST lifecycle and dashboard management contract."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import db
from app.main import app


def test_contact_rest_lifecycle_and_incident_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "contacts.db")
    with TestClient(app) as client:
        room = "contact-lifecycle"
        initial = client.get(f"/api/rooms/{room}/contacts")
        assert initial.status_code == 200

        created = client.post(
            f"/api/rooms/{room}/contacts",
            json={"phone": "+15551234567", "label": "Clinic", "status": "blocked"},
        )
        assert created.status_code == 201
        contact = created.json()

        patched = client.patch(
            f"/api/rooms/{room}/contacts/{contact['id']}",
            json={"status": "trusted"},
        )
        assert patched.status_code == 200
        assert patched.json()["status"] == "trusted"

        db.create_call({
            "id": "contact-incident", "room": room, "from_phone": "+15551234567",
            "from_label": "Clinic", "classification": "unknown", "peak_risk": 91,
        })
        db.add_incident(
            "contact-incident",
            {"summary": "The caller urgently requested a card number."},
            "Caller requested ####.",
        )
        client.patch(
            f"/api/rooms/{room}/contacts/{contact['id']}",
            json={"status": "blocked"},
        )
        listed = client.get(f"/api/rooms/{room}/contacts")
        linked = next(item for item in listed.json() if item["id"] == contact["id"])
        assert linked["related_call_id"] == "contact-incident"
        assert "card number" in linked["block_reason"]

        deleted = client.delete(f"/api/rooms/{room}/contacts/{contact['id']}")
        assert deleted.status_code == 204
        assert all(item["id"] != contact["id"] for item in client.get(
            f"/api/rooms/{room}/contacts"
        ).json())


def test_dashboard_exposes_all_contact_actions_and_confirmation() -> None:
    client = TestClient(app)
    dashboard = client.get("/dashboard").text
    script = client.get("/static/js/dashboard.js").text
    assert '<option value="trusted">Trusted</option>' in dashboard
    assert '<option value="blocked">Blocked</option>' in dashboard
    assert '<option value="pending">' not in dashboard
    for action in ("Trust", "Block", "Untrust", "Unblock"):
        assert action in script
    assert "window.confirm" in script
    assert "related_call_id" in script
