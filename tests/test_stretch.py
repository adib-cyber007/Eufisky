"""Opt-in stretch features must remain isolated from the submission demo."""

from dataclasses import replace
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
import pytest

from app import db
import app.main as main_module
import app.phone.calls as calls_module
from app.config import settings
from app.incident_insights import build_insight_timeline
from app.main import app
from app.phone.calls import CallController
from app.rules.engine import RuleEngine
from app.rules.loader import load_lexicon
from app.stt.assemblyai_stream import STTStream, WordEvent


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _seed_incident_id() -> str:
    return str(next(call["id"] for call in db.list_calls("demo") if call["incident"]))


def test_incident_insights_are_flagged_and_privacy_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert settings.feature_incident_insights is False
    timeline = build_insight_timeline(
        {
            "entities": [
                {
                    "entity_type": "credit_card_number",
                    "text": "4111 1111 1111 1111",
                    "start": 900,
                    "confidence": 0.99,
                },
                {"entity_type": "organization", "text": "Medicare", "start": 300},
            ],
            "sentiments": [
                {
                    "speaker": "Caller",
                    "sentiment": "NEGATIVE",
                    "text": "Pay 5555 now",
                    "start": 600,
                    "confidence": 0.91,
                }
            ],
        }
    )
    assert [item["kind"] for item in timeline] == ["entity", "sentiment", "entity"]
    assert "4111" not in json.dumps(timeline)
    assert "5555" not in json.dumps(timeline)
    assert "Sensitive value redacted" in json.dumps(timeline)

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "insights.db")
    with TestClient(app) as client:
        call_id = _seed_incident_id()
        default_detail = client.get(f"/api/rooms/demo/calls/{call_id}").json()
        assert "insight_timeline" not in default_detail["incident"]
        monkeypatch.setattr(
            main_module,
            "settings",
            replace(main_module.settings, feature_incident_insights=True),
        )
        enabled_detail = client.get(f"/api/rooms/demo/calls/{call_id}").json()
        assert enabled_detail["features"]["incident_insights"] is True
        assert enabled_detail["incident"]["insight_timeline"]


def test_guardian_voice_tuning_is_guardian_only_and_opt_in() -> None:
    assert settings.feature_guardian_voice_tuning is False
    audio = (PROJECT_ROOT / "app" / "web" / "static" / "js" / "audio.js").read_text(
        encoding="utf-8"
    )
    phone = (PROJECT_ROOT / "app" / "web" / "static" / "js" / "phone.js").read_text(
        encoding="utf-8"
    )
    assert "options.confidenceFriendly ? 0.82 : 0.93" in audio
    assert "preferredGuardianVoice" in audio and "microsoft zira" in audio
    assert 'guardianVoiceTuning && message.agent === "guardian"' in phone


def test_spanish_monitoring_is_flagged_and_uses_spanish_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert settings.feature_spanish_monitoring is False
    stream = STTStream("caller", ["Medicare"], language="es")
    query = parse_qs(urlsplit(stream.url).query)
    assert json.loads(query["language_codes"][0]) == ["es"]
    assert "language_codes" not in parse_qs(urlsplit(STTStream("caller", []).url).query)

    english = load_lexicon()
    spanish = load_lexicon(language="es")
    for family, config in english["signals"].items():
        assert spanish["signals"][family]["weight"] == config["weight"]
        assert spanish["signals"][family]["half_life_s"] == config["half_life_s"]
        assert spanish["signals"][family]["cap"] == config["cap"]
    engine = RuleEngine(spanish)
    update = engine.ingest(
        WordEvent(
            "caller",
            "Soy de Medicare. Su cuenta será suspendida ahora mismo. Léame el número de Medicare.",
            1000,
            True,
        )
    )
    assert update is not None and "trigger_l2" in update.flags

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "spanish.db")
    with TestClient(app) as client:
        assert client.patch(
            "/api/rooms/spanish/settings", json={"language": "es"}
        ).status_code == 403
        enabled = replace(main_module.settings, feature_spanish_monitoring=True)
        monkeypatch.setattr(main_module, "settings", enabled)
        monkeypatch.setattr(calls_module, "settings", enabled)
        saved = client.patch(
            "/api/rooms/spanish/settings", json={"language": "es"}
        )
        assert saved.status_code == 200 and saved.json()["language"] == "es"
        language, lexicon = CallController()._monitoring_profile("spanish")
        assert language == "es"
        assert "número de medicare" in lexicon["signals"]["pii_request"]["phrases"]


def test_incident_export_route_and_browser_contract_are_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert settings.feature_incident_export is False
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "export.db")
    with TestClient(app) as client:
        call_id = _seed_incident_id()
        url = f"/incident/demo/{call_id}"
        assert client.get(url).status_code == 404
        monkeypatch.setattr(
            main_module,
            "settings",
            replace(main_module.settings, feature_incident_export=True),
        )
        response = client.get(url)
        assert response.status_code == 200
        assert "Preparing the redacted incident report" in response.text
        detail = client.get(f"/api/rooms/demo/calls/{call_id}").json()
        assert detail["features"]["incident_export"] is True

    dashboard = (PROJECT_ROOT / "app" / "web" / "static" / "js" / "dashboard.js").read_text(
        encoding="utf-8"
    )
    report = (PROJECT_ROOT / "app" / "web" / "static" / "js" / "incident-report.js").read_text(
        encoding="utf-8"
    )
    assert "detail.features?.incident_export" in dashboard
    assert "Copy incident report" in dashboard and "Printable report" in dashboard
    assert "redacted_transcript" in report and "navigator.clipboard.writeText" in report


def test_telephony_remains_a_disabled_documented_roadmap() -> None:
    assert settings.feature_twilio_telephony is False
    roadmap = (PROJECT_ROOT / "docs" / "TELEPHONY_ROADMAP.md").read_text(encoding="utf-8")
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
    assert all(
        marker in roadmap
        for marker in (
            'track="both_tracks"',
            "private whisper to one leg",
            "callSidToCoach",
            "FEATURE_TWILIO_TELEPHONY",
        )
    )
    assert "twilio" not in requirements
