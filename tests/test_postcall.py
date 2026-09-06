"""Post-call privacy pipeline with provider fakes."""

from __future__ import annotations

from pathlib import Path
import wave

import pytest

from app import db
from app.postcall import pipeline


def write_wav(path: Path, sample: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(int(sample).to_bytes(2, "little", signed=True) * 1600)


@pytest.fixture()
def postcall_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path, Path]:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "postcall.db")
    monkeypatch.setattr(pipeline, "RECORDINGS_DIR", tmp_path / "recordings")
    db.init_db()
    caller = tmp_path / "recordings" / "caller.wav"
    senior = tmp_path / "recordings" / "senior.wav"
    write_wav(caller, 120)
    write_wav(senior, -120)
    call_id = "postcall-test"
    db.create_call(
        {
            "id": call_id,
            "room": "postcall",
            "from_phone": "+15550123456",
            "from_label": "Unknown caller",
            "classification": "unknown",
            "peak_risk": 82,
            "final_state": "WRAPUP",
            "recording_caller": str(caller),
            "recording_senior": str(senior),
        }
    )
    db.add_segment(call_id, "caller", 1000, "My account is 4123 5678", True)
    db.add_segment(call_id, "senior", 2200, "I will not share that", True)
    db.add_risk_sample(call_id, 1800, 82, ["pii_request", "urgency"])
    db.add_event(call_id, 1900, "level", {"type": "level", "level": 2})
    return call_id, caller, senior


def complete_summary() -> dict:
    return {
        "summary": "A risky request was stopped.",
        "caller_claim": "The caller claimed to be a bank.",
        "requests_made": ["Account number"],
        "disclosed_by_senior": "Nothing was disclosed.",
        "intervention": "Eufisky paused the call.",
        "outcome": "The call ended.",
        "recommendation": "Verify through an official number.",
    }


@pytest.mark.asyncio
async def test_success_deletes_raw_wavs_and_stores_redacted_output(postcall_setup) -> None:
    call_id, caller, senior = postcall_setup

    async def fake_batch(stereo: Path) -> pipeline.BatchResult:
        assert stereo.exists()
        with wave.open(str(stereo), "rb") as audio:
            assert audio.getnchannels() == 2
        return pipeline.BatchResult(
            "Caller: Send the card ending in ####.",
            {"entities": [{"entity_type": "credit_card_number"}]},
            b"RIFF-redacted-audio",
        )

    async def fake_summary(transcript: str) -> dict:
        assert "####" in transcript
        return complete_summary()

    incident = await pipeline.process_call(
        call_id, batch_runner=fake_batch, summary_runner=fake_summary
    )

    assert incident is not None
    assert incident["analysis_source"] == "lemur"
    assert incident["summary"] == complete_summary()
    assert incident["analytics"]["transcript_source"] == "batch"
    assert not caller.exists() and not senior.exists()
    redacted = Path(incident["redacted_audio"])
    assert redacted.exists() and redacted.read_bytes() == b"RIFF-redacted-audio"
    assert not (pipeline.RECORDINGS_DIR / f"{call_id}_stereo.wav").exists()


@pytest.mark.asyncio
async def test_provider_failures_use_redacted_live_transcript_and_template(postcall_setup) -> None:
    call_id, caller, senior = postcall_setup

    async def failed_batch(_stereo: Path) -> pipeline.BatchResult:
        raise TimeoutError("batch unavailable")

    async def failed_summary(_transcript: str) -> dict:
        raise TimeoutError("summary unavailable")

    incident = await pipeline.process_call(
        call_id, batch_runner=failed_batch, summary_runner=failed_summary
    )

    assert incident is not None
    assert incident["analysis_source"] == "template_live_fallback"
    assert "4123" not in incident["redacted_transcript"]
    assert "####" in incident["redacted_transcript"]
    assert set(pipeline.SUMMARY_KEYS) == set(incident["summary"])
    assert not caller.exists() and not senior.exists()
