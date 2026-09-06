"""Deployment-contract tests for the free Render Blueprint."""

from pathlib import Path

import pytest
import yaml

from app.runtime_paths import LOCAL_DATA_DIR, database_path, recordings_dir
from tools.smoke_public import normalize_base_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_is_one_free_python_web_service() -> None:
    blueprint = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert len(blueprint["services"]) == 1
    service = blueprint["services"][0]
    assert service["type"] == "web"
    assert service["runtime"] == "python"
    assert service["plan"] == "free"
    assert service["buildCommand"] == "pip install -r requirements.txt"
    assert service["startCommand"] == (
        "uvicorn app.main:app --host 0.0.0.0 --port $PORT --ws websockets"
    )
    assert service["healthCheckPath"] == "/api/health"

    env = {item["key"]: item for item in service["envVars"]}
    assert env["PYTHON_VERSION"]["value"] == "3.12.14"
    assert env["AGENT_BACKEND"]["value"] == "voice_agent"
    assert env["SENIOR_NAME"]["value"] == "Margaret"
    assert env["FAMILY_NAME"]["value"] == "Sarah"
    for secret in ("ASSEMBLYAI_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"):
        assert env[secret] == {"key": secret, "sync": False}


def test_render_uses_tmp_and_local_development_keeps_data_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RENDER", "true")
    assert database_path() == Path("/tmp/eufisky.db")
    assert recordings_dir() == Path("/tmp/eufisky-recordings")

    monkeypatch.delenv("RENDER")
    assert database_path() == LOCAL_DATA_DIR / "eufisky.db"
    assert recordings_dir() == LOCAL_DATA_DIR / "recordings"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://eufisky.onrender.com/", "https://eufisky.onrender.com"),
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
    ],
)
def test_public_tool_normalizes_valid_origins(value: str, expected: str) -> None:
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize("value", ["eufisky.onrender.com", "ftp://example.test", "https://"])
def test_public_tool_rejects_invalid_origins(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_base_url(value)


def test_landing_explains_free_host_cold_start() -> None:
    landing = (PROJECT_ROOT / "app" / "web" / "index.html").read_text(encoding="utf-8")
    assert "first load after a quiet period may take about 40 seconds" in landing
