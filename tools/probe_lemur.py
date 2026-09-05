"""Probe batch analytics and the LLM Gateway successor to LeMUR."""

from __future__ import annotations

from array import array
import json
from pathlib import Path
import time
from typing import Any
import wave

import httpx

from probe_utils import FIXTURES, ProbeReport, api_key

API_BASE = "https://api.assemblyai.com"
LLM_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
STEREO_PATH = FIXTURES / "stereo_30s.wav"


def create_stereo_fixture() -> Path:
    """Repeat both eight-second mono fixtures into a 30-second stereo call."""

    channels: list[array[int]] = []
    for name in ("caller.wav", "senior.wav"):
        with wave.open(str(FIXTURES / name), "rb") as wav_file:
            if (wav_file.getframerate(), wav_file.getnchannels(), wav_file.getsampwidth()) != (16000, 1, 2):
                raise ValueError(f"{name} is not PCM16 mono 16 kHz")
            samples = array("h")
            samples.frombytes(wav_file.readframes(wav_file.getnframes()))
            channels.append(samples)
    frame_count = 16_000 * 30
    stereo = array("h")
    for index in range(frame_count):
        stereo.append(channels[0][index % len(channels[0])])
        stereo.append(channels[1][index % len(channels[1])])
    with wave.open(str(STEREO_PATH), "wb") as wav_out:
        wav_out.setnchannels(2)
        wav_out.setsampwidth(2)
        wav_out.setframerate(16_000)
        wav_out.writeframes(stereo.tobytes())
    return STEREO_PATH


def extract_json(value: str) -> dict[str, Any]:
    """Parse a direct JSON response or a fenced JSON response."""

    stripped = value.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1])
    result = json.loads(stripped)
    if not isinstance(result, dict):
        raise ValueError("LLM response was not a JSON object")
    return result


def run() -> int:
    """Upload, transcribe with all requested options, then request incident JSON."""

    report = ProbeReport("lemur")
    key = api_key("ASSEMBLYAI_API_KEY")
    if not key:
        return report.finish("FAIL", "ASSEMBLYAI_API_KEY is empty")
    if not all((FIXTURES / name).exists() for name in ("caller.wav", "senior.wav")):
        return report.finish("FAIL", "fixtures are missing; run tools/generate_fixtures.py")

    try:
        stereo = create_stereo_fixture()
        headers = {"authorization": key}
        with httpx.Client(timeout=httpx.Timeout(60, connect=20)) as client:
            report.sample("client", {"method": "POST", "url": f"{API_BASE}/v2/upload", "body_bytes": stereo.stat().st_size})
            with stereo.open("rb") as audio:
                upload_response = client.post(f"{API_BASE}/v2/upload", headers=headers, content=audio)
            upload_response.raise_for_status()
            upload_url = upload_response.json()["upload_url"]
            report.sample("server", {"upload_url": "<temporary-upload-url>"})

            policies = [
                "us_social_security_number",
                "credit_card_number",
                "banking_information",
                "date_of_birth",
                "phone_number",
                "medical_process",
            ]
            submission = {
                "audio_url": upload_url,
                "speech_models": ["universal-3-pro", "universal-2"],
                "multichannel": True,
                "redact_pii": True,
                "redact_pii_policies": policies,
                "redact_pii_sub": "entity_name",
                "redact_pii_audio": True,
                "redact_pii_audio_quality": "wav",
                "entity_detection": True,
                "sentiment_analysis": True,
            }
            report.sample("client", {**submission, "audio_url": "<temporary-upload-url>"})
            submitted = client.post(f"{API_BASE}/v2/transcript", headers=headers, json=submission)
            submitted.raise_for_status()
            transcript_id = submitted.json()["id"]
            report.sample("server", {"id": transcript_id, "status": submitted.json().get("status")})

            deadline = time.monotonic() + 900
            transcript: dict[str, Any] = {}
            while time.monotonic() < deadline:
                poll = client.get(f"{API_BASE}/v2/transcript/{transcript_id}", headers=headers)
                poll.raise_for_status()
                transcript = poll.json()
                status = transcript.get("status")
                if status == "completed":
                    break
                if status == "error":
                    raise RuntimeError(str(transcript.get("error", "transcription failed")))
                time.sleep(3)
            else:
                raise TimeoutError("batch transcription did not finish within 15 minutes")

            redacted_text = str(transcript.get("text") or "").strip()
            report.sample(
                "server",
                {
                    "status": transcript.get("status"),
                    "audio_channels": transcript.get("audio_channels"),
                    "text": redacted_text[:180],
                    "entities_count": len(transcript.get("entities") or []),
                    "sentiments_count": len(transcript.get("sentiment_analysis_results") or []),
                },
            )

            audio_status = "not_checked"
            audio_deadline = time.monotonic() + 120
            while time.monotonic() < audio_deadline:
                redacted_audio = client.get(
                    f"{API_BASE}/v2/transcript/{transcript_id}/redacted-audio", headers=headers
                )
                redacted_audio.raise_for_status()
                audio_body = redacted_audio.json()
                audio_status = str(audio_body.get("status"))
                if audio_status in {"redacted_audio_ready", "error"}:
                    break
                time.sleep(3)

            prompt = (
                "Return only valid JSON with exactly these keys: summary, caller_claim, requests_made, "
                "disclosed_by_senior, recommendation. Analyze this PII-redacted call transcript:\n\n"
                + redacted_text
            )
            llm_payload = {
                "model": "qwen3.5-4b-32k-fast",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 600,
                "temperature": 0,
            }
            report.sample("client", {"url": LLM_URL, **llm_payload})
            llm_response = client.post(LLM_URL, headers=headers, json=llm_payload)
            llm_response.raise_for_status()
            llm_body = llm_response.json()
            report.sample("server", llm_body)
            content = llm_body["choices"][0]["message"]["content"]
            incident = extract_json(content)

        required = {"summary", "caller_claim", "requests_made", "disclosed_by_senior", "recommendation"}
        options = {
            "multichannel": transcript.get("multichannel"),
            "audio_channels": transcript.get("audio_channels"),
            "redact_pii": transcript.get("redact_pii"),
            "redact_pii_audio_status": audio_status,
            "entity_detection": transcript.get("entity_detection"),
            "sentiment_analysis": transcript.get("sentiment_analysis"),
            "llm_surface": "LLM Gateway (documented LeMUR successor)",
        }
        passed = bool(redacted_text) and required.issubset(incident)
        return report.finish("PASS" if passed else "FAIL", json.dumps(options, separators=(",", ":")))
    except Exception as error:
        return report.finish("FAIL", f"{type(error).__name__}: {error}")


if __name__ == "__main__":
    raise SystemExit(run())
