"""Guardian controls are shipped on every browser surface."""

from fastapi.testclient import TestClient

from app.main import app


def test_guardian_controls_are_rendered() -> None:
    with TestClient(app) as client:
        senior = client.get("/senior").text
        family = client.get("/family").text
        dashboard = client.get("/dashboard").text
        audio = client.get("/static/js/audio.js").text
    assert all(label in senior for label in ("End the call", "Bring in Sarah", "Continue the call"))
    assert all(label in family for label in ("Resume caller", "End call"))
    assert "Guardian is with Margaret" in dashboard and "Join call" in dashboard
    assert "holdMusic" in audio and "setInterval" in audio
    assert "window.speechSynthesis.speaking || pcmOutputPlaying" in audio
    assert "peak > 0.08 && window.speechSynthesis.speaking" not in audio
