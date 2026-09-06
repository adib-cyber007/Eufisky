"""Privacy-first post-call transcription and incident summarization."""

from __future__ import annotations

from array import array
import asyncio
from collections import Counter
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Awaitable, Callable
import wave

import httpx

from app import db
from app.config import settings
from app.rooms import rooms

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECORDINGS_DIR = PROJECT_ROOT / "data" / "recordings"
PROMPT_PATH = Path(__file__).with_name("lemur_prompt.txt")
API_BASE = "https://api.assemblyai.com"
LLM_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
PII_POLICIES = [
    "us_social_security_number",
    "credit_card_number",
    "banking_information",
    "date_of_birth",
    "phone_number",
    "medical_process",
    "email_address",
    "location",
]
SUMMARY_KEYS = (
    "summary",
    "caller_claim",
    "requests_made",
    "disclosed_by_senior",
    "intervention",
    "outcome",
    "recommendation",
)
DIGIT_RUN = re.compile(r"(?<!\w)(?:\d[\s().-]*){3,}(?!\w)")
BatchRunner = Callable[[Path], Awaitable["BatchResult"]]
SummaryRunner = Callable[[str], Awaitable[dict[str, Any]]]
_TASKS: set[asyncio.Task[Any]] = set()


@dataclass(slots=True)
class BatchResult:
    transcript: str
    analytics: dict[str, Any]
    redacted_audio: bytes | None = None


def local_redact(text: str) -> str:
    """Replace runs of three or more digits while preserving readable prose."""

    def replace(match: re.Match[str]) -> str:
        count = sum(character.isdigit() for character in match.group(0))
        return "#" * max(4, count)

    return DIGIT_RUN.sub(replace, text)


def _read_mono(path: Path) -> tuple[int, array[int]]:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f"{path.name} must be PCM16 mono")
        rate = source.getframerate()
        samples = array("h")
        samples.frombytes(source.readframes(source.getnframes()))
    return rate, samples


def mix_to_stereo(caller_path: Path, senior_path: Path, destination: Path) -> Path:
    """Mix caller to the left channel and senior to the right channel."""

    caller_rate, caller = _read_mono(caller_path)
    senior_rate, senior = _read_mono(senior_path)
    if caller_rate != senior_rate:
        raise ValueError("recording sample rates do not match")
    stereo = array("h")
    for index in range(max(len(caller), len(senior))):
        stereo.append(caller[index] if index < len(caller) else 0)
        stereo.append(senior[index] if index < len(senior) else 0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(caller_rate)
        output.writeframes(stereo.tobytes())
    return destination


def _extract_json(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1])
    try:
        result = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        result = json.loads(stripped[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("summary response is not an object")
    missing = [key for key in SUMMARY_KEYS if key not in result]
    if missing:
        raise ValueError(f"summary is missing keys: {', '.join(missing)}")
    summary = {key: result[key] for key in SUMMARY_KEYS}
    if not isinstance(summary["requests_made"], list):
        summary["requests_made"] = [str(summary["requests_made"])]
    return summary


def _channel_transcript(payload: dict[str, Any]) -> str:
    utterances = payload.get("utterances") or []
    lines: list[str] = []
    for utterance in utterances:
        text = str(utterance.get("text") or "").strip()
        if not text:
            continue
        channel = int(utterance.get("channel") or utterance.get("audio_channel") or 1)
        lines.append(f"{'Caller' if channel == 1 else 'Margaret'}: {text}")
    return "\n".join(lines) or str(payload.get("text") or "").strip()


async def assemblyai_batch(stereo_path: Path) -> BatchResult:
    """Run the confirmed multichannel, redacted AssemblyAI batch workflow."""

    if not settings.assemblyai_api_key:
        raise RuntimeError("AssemblyAI key is not configured")
    headers = {"authorization": settings.assemblyai_api_key}
    timeout = httpx.Timeout(20, connect=10)
    async with httpx.AsyncClient(timeout=timeout) as client:
        upload = await client.post(
            f"{API_BASE}/v2/upload", headers=headers, content=stereo_path.read_bytes()
        )
        upload.raise_for_status()
        submission = {
            "audio_url": upload.json()["upload_url"],
            "speech_models": ["universal-3-pro", "universal-2"],
            "multichannel": True,
            "redact_pii": True,
            "redact_pii_policies": PII_POLICIES,
            "redact_pii_sub": "entity_name",
            "redact_pii_audio": True,
            "redact_pii_audio_quality": "wav",
            "entity_detection": True,
            "sentiment_analysis": True,
        }
        submitted = await client.post(
            f"{API_BASE}/v2/transcript", headers=headers, json=submission
        )
        submitted.raise_for_status()
        transcript_id = str(submitted.json()["id"])
        deadline = time.monotonic() + 38
        payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            response = await client.get(
                f"{API_BASE}/v2/transcript/{transcript_id}", headers=headers
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") == "completed":
                break
            if payload.get("status") == "error":
                raise RuntimeError(str(payload.get("error") or "batch transcription failed"))
            await asyncio.sleep(2)
        else:
            raise TimeoutError("batch transcription exceeded the post-call time budget")

        redacted_audio: bytes | None = None
        audio_deadline = time.monotonic() + 6
        while time.monotonic() < audio_deadline:
            response = await client.get(
                f"{API_BASE}/v2/transcript/{transcript_id}/redacted-audio",
                headers=headers,
            )
            response.raise_for_status()
            audio_payload = response.json()
            if audio_payload.get("status") == "redacted_audio_ready":
                audio_url = audio_payload.get("redacted_audio_url")
                if audio_url:
                    audio_response = await client.get(str(audio_url))
                    audio_response.raise_for_status()
                    redacted_audio = audio_response.content
                break
            if audio_payload.get("status") == "error":
                break
            await asyncio.sleep(1)

    return BatchResult(
        transcript=_channel_transcript(payload),
        analytics={
            "entities": payload.get("entities") or [],
            "sentiments": payload.get("sentiment_analysis_results") or [],
        },
        redacted_audio=redacted_audio,
    )


async def lemur_summary(transcript: str) -> dict[str, Any]:
    """Use AssemblyAI's LLM Gateway, the documented successor to LeMUR."""

    if not settings.assemblyai_api_key:
        raise RuntimeError("AssemblyAI key is not configured")
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    payload = {
        "model": "qwen3.5-4b-32k-fast",
        "messages": [
            {
                "role": "user",
                "content": f"{prompt}\n\nPII-redacted call transcript:\n{transcript}",
            }
        ],
        "max_tokens": 700,
        "temperature": 0,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5)) as client:
        response = await client.post(
            LLM_URL,
            headers={"authorization": settings.assemblyai_api_key},
            json=payload,
        )
        response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return _extract_json(str(content))


def _live_transcript(call_id: str) -> str:
    lines = []
    for segment in db.list_segments(call_id):
        speaker = "Margaret" if segment["speaker"] == "senior" else str(segment["speaker"]).title()
        lines.append(f"{speaker}: {segment['text']}")
    return local_redact("\n".join(lines))


def template_summary(call: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic incident summary from persisted events and signals."""

    samples = db.list_risk_samples(str(call["id"]))
    counts = Counter(
        signal for sample in samples for signal in sample.get("signals", [])
    )
    top = [signal for signal, _ in counts.most_common(4)]
    request_labels = {
        "pii_request": "Sensitive personal or account details",
        "payment_method": "A payment or gift cards",
        "remote_access": "Access to a computer or device",
        "family_emergency": "Money for a family emergency",
        "banking_information": "Banking information",
    }
    requests = [request_labels[signal] for signal in top if signal in request_labels]
    peak = int(call.get("peak_risk") or 0)
    outcome_name = str(call.get("guardian_outcome") or "")
    outcome = {
        "end_call": "The call was ended by Margaret or Eufisky.",
        "conference_family": "Sarah joined Margaret while the caller remained on hold.",
        "resume_call": "Margaret chose to resume the call.",
        "add_to_trusted": "Margaret chose to save and resume the caller.",
    }.get(outcome_name, "The call ended without a Guardian action.")
    intervention = (
        "Eufisky paused the caller and spoke privately with Margaret."
        if peak >= 65 or outcome_name
        else "No intervention was needed; Eufisky monitored quietly."
    )
    recommendation = (
        "Keep the number blocked and verify any claim through an official number."
        if peak >= 85
        else "Verify the caller through a known number before sharing information."
        if peak >= 40
        else "No immediate action is needed."
    )
    claim = str(call.get("from_label") or call.get("from_phone") or "Unknown caller")
    signal_text = ", ".join(signal.replace("_", " ") for signal in top[:3])
    summary_text = (
        f"This monitored call reached a peak risk of {peak}."
        + (f" The strongest signals were {signal_text}." if signal_text else " No scam signals persisted.")
        + f" {outcome}"
    )
    return {
        "summary": summary_text,
        "caller_claim": f"The caller was identified as {claim}.",
        "requests_made": requests or ["No specific risky request was captured."],
        "disclosed_by_senior": (
            "Margaret may have begun sharing digits; all captured digit runs were redacted."
            if "pii_disclosure" in counts
            else "No sensitive details were detected in the captured transcript."
        ),
        "intervention": intervention,
        "outcome": outcome,
        "recommendation": recommendation,
    }


def _recording_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else PROJECT_ROOT / path


def _stored_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


async def process_call(
    call_id: str,
    *,
    batch_runner: BatchRunner = assemblyai_batch,
    summary_runner: SummaryRunner = lemur_summary,
) -> dict[str, Any] | None:
    """Create one incident; provider failures resolve through local fallbacks."""

    call = db.get_call(call_id)
    if not call or call.get("classification") != "unknown":
        return None
    caller_path = _recording_path(call.get("recording_caller"))
    senior_path = _recording_path(call.get("recording_senior"))
    raw_paths = [path for path in (caller_path, senior_path) if path and path.exists()]
    stereo_path = RECORDINGS_DIR / f"{call_id}_stereo.wav"
    transcript_source = "live_fallback"
    batch = BatchResult("", {})
    if caller_path and senior_path and caller_path.exists() and senior_path.exists():
        try:
            await asyncio.to_thread(mix_to_stereo, caller_path, senior_path, stereo_path)
            batch = await batch_runner(stereo_path)
            if batch.transcript.strip():
                transcript_source = "batch"
        except Exception as error:
            LOGGER.warning("Post-call batch fallback for %s: %s", call_id, error)
    transcript = batch.transcript.strip() if transcript_source == "batch" else _live_transcript(call_id)
    transcript = local_redact(transcript) or "No monitored speech was captured."

    summary_source = "lemur"
    try:
        summary = await summary_runner(transcript)
        summary = _extract_json(json.dumps(summary))
    except Exception as error:
        LOGGER.warning("Post-call summary fallback for %s: %s", call_id, error)
        summary = template_summary(call)
        summary_source = "template"

    redacted_audio_path: str | None = None
    if batch.redacted_audio:
        destination = RECORDINGS_DIR / f"{call_id}_redacted.wav"
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(destination.write_bytes, batch.redacted_audio)
        redacted_audio_path = _stored_path(destination)

    incident = db.add_incident(
        call_id,
        summary,
        transcript,
        analytics={**batch.analytics, "transcript_source": transcript_source},
        redacted_audio=redacted_audio_path,
        analysis_source=(
            summary_source if transcript_source == "batch" else f"{summary_source}_live_fallback"
        ),
    )
    for path in [*raw_paths, stereo_path]:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            LOGGER.warning("Could not remove post-call working audio %s: %s", path.name, error)
    await rooms.get(str(call["room"])).broadcast_dashboard(
        {"type": "incident", "call_id": call_id, "status": "ready"}
    )
    return incident


def _task_finished(task: asyncio.Task[Any]) -> None:
    _TASKS.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        LOGGER.exception("Post-call task failed")


def enqueue(call_id: str) -> None:
    """Schedule processing after WRAPUP without delaying phone teardown."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(process_call(call_id), name=f"postcall-{call_id}")
    _TASKS.add(task)
    task.add_done_callback(_task_finished)
