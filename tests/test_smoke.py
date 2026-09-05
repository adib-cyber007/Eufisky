"""Smoke tests for the Phase-0 HTTP surface."""

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    """The liveness endpoint returns the documented payload."""

    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_index_title() -> None:
    """The browser shell is served and clearly titled."""

    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "<title>Eufisky</title>" in response.text
