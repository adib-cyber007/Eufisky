"""Probe AssemblyAI's inline Voice Agent API and client-side tool calling."""

from __future__ import annotations

import asyncio
import audioop
import base64
import json
import time
from typing import Any
import wave

from websockets.asyncio.client import connect

from probe_utils import FIXTURES, ProbeReport, api_key

URL = "wss://agents.assemblyai.com/v1/ws"
CALLER_TEXT = (
    "This is Michael from Medicare, your benefits will be suspended today unless we verify your card number."
)


def session_update() -> dict[str, Any]:
    """Return the documented inline Voice Agent configuration under test."""

    return {
        "type": "session.update",
        "session": {
            "system_prompt": (
                "You answer the phone for Margaret. Ask who is calling. As soon as the caller gives a name "
                "and reason, call take_message. You must use take_message rather than only replying."
            ),
            "greeting": "Hello, who is calling?",
            "input": {
                "format": {"encoding": "audio/pcm"},
                "keyterms": ["Margaret", "Michael", "Medicare"],
                "turn_detection": {"min_silence": 500, "max_silence": 1500},
            },
            "output": {"voice": "alba", "format": {"encoding": "audio/pcm"}},
            "tools": [
                {
                    "type": "function",
                    "name": "take_message",
                    "description": "Record the caller's name and message for Margaret.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "caller_name": {"type": "string"},
                            "message": {"type": "string"},
                        },
                        "required": ["caller_name", "message"],
                    },
                }
            ],
        },
    }


def pcm24k() -> bytes:
    """Read the required 16 kHz fixture and resample it to Voice Agent PCM 24 kHz."""

    with wave.open(str(FIXTURES / "caller.wav"), "rb") as wav_file:
        if (wav_file.getframerate(), wav_file.getnchannels(), wav_file.getsampwidth()) != (16000, 1, 2):
            raise ValueError("caller.wav is not PCM16 mono 16 kHz")
        source = wav_file.readframes(wav_file.getnframes())
    converted, _ = audioop.ratecv(source, 2, 1, 16000, 24000, None)
    return converted


async def run() -> int:
    """Exercise audio, transcript, response audio, text injection, and a tool call."""

    report = ProbeReport("voice_agent")
    key = api_key("ASSEMBLYAI_API_KEY")
    if not key:
        return report.finish("FAIL", "ASSEMBLYAI_API_KEY is empty")
    if not (FIXTURES / "caller.wav").exists():
        return report.finish("FAIL", "caller fixture is missing; run tools/generate_fixtures.py")

    events: list[str] = []
    transcripts: list[str] = []
    tool_call: dict[str, Any] | None = None
    audio_bytes = 0
    resolved_input: dict[str, Any] = {}
    text_only_sent = False
    text_only_error = False
    audio_started = False
    audio_finished = asyncio.Event()
    pending_tool_id: str | None = None

    try:
        async with connect(URL, additional_headers={"Authorization": f"Bearer {key}"}, open_timeout=15) as socket:
            update = session_update()
            report.sample("client", update)
            await socket.send(json.dumps(update))

            async def stream_audio() -> None:
                payload = pcm24k()
                chunk_bytes = 2 * 2_400  # 100 ms at 24 kHz PCM16 mono.
                for offset in range(0, len(payload), chunk_bytes):
                    chunk = payload[offset : offset + chunk_bytes]
                    message = {"type": "input.audio", "audio": base64.b64encode(chunk).decode("ascii")}
                    if offset == 0:
                        report.sample("client", {"type": "input.audio", "audio": f"<base64:{len(chunk)} bytes>"})
                    await socket.send(json.dumps(message))
                    await asyncio.sleep(0.1)
                audio_finished.set()

            async def text_only_fallback() -> None:
                nonlocal text_only_sent
                await audio_finished.wait()
                await asyncio.sleep(8)
                if tool_call is None:
                    message = {"type": "conversation.message", "role": "user", "content": CALLER_TEXT}
                    report.sample("client", message)
                    await socket.send(json.dumps(message))
                    create = {"type": "reply.create", "instructions": "Now call take_message with the caller details."}
                    report.sample("client", create)
                    await socket.send(json.dumps(create))
                    text_only_sent = True

            fallback_task: asyncio.Task[None] | None = None
            deadline = time.perf_counter() + 55
            while time.perf_counter() < deadline:
                try:
                    raw = await asyncio.wait_for(socket.recv(), timeout=5)
                except TimeoutError:
                    if tool_call is not None:
                        break
                    continue
                event = json.loads(raw)
                event_type = str(event.get("type", "unknown"))
                events.append(event_type)
                if len(events) <= 8 or event_type in {"tool.call", "session.error", "session.ended"}:
                    safe_event = dict(event)
                    if event_type == "reply.audio":
                        safe_event["data"] = f"<base64:{len(event.get('data', ''))} chars>"
                    report.sample("server", safe_event)

                if event_type == "session.ready":
                    resolved_input = (event.get("config") or {}).get("input") or {}
                    fallback_task = asyncio.create_task(text_only_fallback())
                elif event_type == "reply.done" and not audio_started:
                    audio_started = True
                    asyncio.create_task(stream_audio())
                elif event_type.startswith("transcript."):
                    text = str(event.get("text") or event.get("delta") or "").strip()
                    if text:
                        transcripts.append(f"{event_type}:{text}")
                elif event_type == "reply.audio":
                    audio_bytes += len(base64.b64decode(event.get("data", "")))
                elif event_type == "tool.call":
                    tool_call = event
                    pending_tool_id = str(event.get("call_id", ""))
                elif event_type == "reply.done" and pending_tool_id:
                    result = {
                        "type": "tool.result",
                        "call_id": pending_tool_id,
                        "result": json.dumps({"saved": True}),
                        "is_error": False,
                    }
                    report.sample("client", result)
                    await socket.send(json.dumps(result))
                    pending_tool_id = None
                    text_probe = {
                        "type": "conversation.message",
                        "role": "system",
                        "content": "Capability probe marker. Do not reply to this message.",
                    }
                    report.sample("client", text_probe)
                    await socket.send(json.dumps(text_probe))
                    text_only_sent = True
                    await asyncio.sleep(1)
                    end = {"type": "session.end"}
                    report.sample("client", end)
                    await socket.send(json.dumps(end))
                elif event_type == "session.error":
                    if text_only_sent:
                        text_only_error = True
                    raise RuntimeError(str(event.get("message") or event.get("error") or event))
                elif event_type == "session.ended":
                    break

            if fallback_task and not fallback_task.done():
                fallback_task.cancel()
            if tool_call is None:
                try:
                    await socket.send(json.dumps({"type": "session.end"}))
                except Exception:
                    pass
    except Exception as error:
        return report.finish("FAIL", f"{type(error).__name__}: {error}; events={events}")

    details = {
        "input_format": resolved_input.get("format"),
        "transcript_events": any(name.startswith("transcript.") for name in events),
        "audio_returned": audio_bytes > 0,
        "text_only_sent": text_only_sent,
        "text_only_accepted": text_only_sent and not text_only_error,
        "event_names": sorted(set(events)),
        "tool_name": tool_call.get("name") if tool_call else None,
        "transcript_samples": transcripts[:3],
    }
    return report.finish("PASS" if tool_call else "FAIL", json.dumps(details, separators=(",", ":")))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
