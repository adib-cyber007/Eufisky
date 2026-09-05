"""Probe two concurrent AssemblyAI Universal Streaming sessions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import statistics
import time
from typing import Any
from urllib.parse import urlencode
import wave

from websockets.asyncio.client import connect

from probe_utils import FIXTURES, ProbeReport, api_key

BASE_URL = "wss://streaming.assemblyai.com/v3/ws"
KEYTERMS = ["Medicare", "gift card", "Social Security", "benefits"]


async def transcribe(label: str, path: Path, key: str, report: ProbeReport) -> dict[str, Any]:
    """Stream one fixture in wall-clock time and collect transcript latency."""

    params = {
        "sample_rate": "16000",
        "speech_model": "universal-3-5-pro",
        "format_turns": "true",
        "keyterms_prompt": json.dumps(KEYTERMS),
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    result: dict[str, Any] = {"label": label, "texts": [], "lags": [], "events": []}
    began = asyncio.Event()
    terminated = asyncio.Event()
    stream_started: float | None = None
    last_sent = time.perf_counter()
    printed_words: dict[int, int] = {}

    async with connect(url, additional_headers={"Authorization": key}, open_timeout=15) as socket:
        report.sample(f"client[{label}]", {"connect": url, "Authorization": "<hidden>"})

        async def receive() -> None:
            nonlocal stream_started
            async for raw in socket:
                event = json.loads(raw)
                event_type = str(event.get("type", "unknown"))
                result["events"].append(event_type)
                if len(result["events"]) <= 3:
                    report.sample(f"server[{label}]", event)
                if event_type == "Begin":
                    began.set()
                elif event_type == "Turn":
                    text = str(event.get("transcript", "")).strip()
                    if text:
                        result["texts"].append(text)
                    turn_order = int(event.get("turn_order", 0))
                    words = event.get("words") or []
                    already_printed = printed_words.get(turn_order, 0)
                    for word in words[already_printed:]:
                        token = str(word.get("text") or word.get("word") or "").strip()
                        end_ms = word.get("end") or word.get("end_ms")
                        if not token:
                            continue
                        if stream_started is not None and isinstance(end_ms, (int, float)):
                            lag_ms = max(0.0, (time.perf_counter() - stream_started) * 1_000 - end_ms)
                        else:
                            lag_ms = max(0.0, (time.perf_counter() - last_sent) * 1_000)
                        result["lags"].append(lag_ms)
                        print(f"WORD {label} | {token} | lag_ms={lag_ms:.0f}")
                    printed_words[turn_order] = len(words)
                    if event.get("end_of_turn"):
                        print(f"END_OF_TURN {label} | {text}")
                elif event_type == "Termination":
                    terminated.set()
                elif event_type in {"Error", "SessionError"}:
                    raise RuntimeError(str(event.get("error") or event.get("message") or event))

        receiver = asyncio.create_task(receive())
        await asyncio.wait_for(began.wait(), timeout=10)
        with wave.open(str(path), "rb") as wav_file:
            if (wav_file.getframerate(), wav_file.getnchannels(), wav_file.getsampwidth()) != (16000, 1, 2):
                raise ValueError(f"{path.name} is not PCM16 mono 16 kHz")
            frames_per_chunk = 1_600
            stream_started = time.perf_counter()
            while frames := wav_file.readframes(frames_per_chunk):
                last_sent = time.perf_counter()
                await socket.send(frames)
                if len(result["texts"]) == 0 and wav_file.tell() == frames_per_chunk:
                    report.sample(f"client[{label}]", {"binary_pcm16_bytes": len(frames), "duration_ms": 100})
                await asyncio.sleep(0.1)
        terminate = {"type": "Terminate"}
        report.sample(f"client[{label}]", terminate)
        await socket.send(json.dumps(terminate))
        await asyncio.wait_for(terminated.wait(), timeout=20)
        await asyncio.wait_for(receiver, timeout=5)

    return result


async def run() -> int:
    """Run both sessions concurrently and apply the Phase-0 pass criteria."""

    report = ProbeReport("realtime_stt")
    key = api_key("ASSEMBLYAI_API_KEY")
    if not key:
        return report.finish("FAIL", "ASSEMBLYAI_API_KEY is empty")
    paths = [FIXTURES / "caller.wav", FIXTURES / "senior.wav"]
    if not all(path.exists() for path in paths):
        return report.finish("FAIL", "fixtures are missing; run tools/generate_fixtures.py")
    try:
        results = await asyncio.gather(
            transcribe("caller", paths[0], key, report),
            transcribe("senior", paths[1], key, report),
        )
    except Exception as error:
        return report.finish("FAIL", f"{type(error).__name__}: {error}")

    have_text = all(result["texts"] for result in results)
    lags = [lag for result in results for lag in result["lags"]]
    median_lag = statistics.median(lags) if lags else float("inf")
    reason = f"both_text={have_text}; median_word_lag_ms={median_lag:.0f}; events={[r['events'] for r in results]}"
    return report.finish("PASS" if have_text and median_lag < 1_500 else "FAIL", reason)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
