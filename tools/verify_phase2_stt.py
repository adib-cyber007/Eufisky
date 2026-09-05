"""Exercise the production Phase 2 STT adapter with both saved call legs."""

from __future__ import annotations

import asyncio
from pathlib import Path
import statistics
import sys
import time
import wave

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rules.loader import load_lexicon, streaming_keyterms  # noqa: E402
from app.stt.assemblyai_stream import STTStream, WordEvent  # noqa: E402

FIXTURES = PROJECT_ROOT / "tools" / "fixtures"


async def run_leg(speaker: str, path: Path, keyterms: list[str]) -> tuple[list[str], list[int]]:
    stream = STTStream(speaker, keyterms)
    words: list[str] = []
    lags: list[int] = []
    started = time.perf_counter()

    async def consume() -> None:
        async for event in stream:
            if isinstance(event, WordEvent):
                arrival_ms = int((time.perf_counter() - started) * 1000)
                words.append(event.text)
                lags.append(max(0, arrival_ms - event.t_ms))

    await stream.start()
    consumer = asyncio.create_task(consume())
    with wave.open(str(path), "rb") as audio:
        assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (16000, 1, 2)
        while frame := audio.readframes(1600):
            await stream.send_audio(frame)
            await asyncio.sleep(0.1)
    await asyncio.sleep(2.5)
    await stream.close()
    await consumer
    return words, lags


async def main() -> int:
    lexicon = load_lexicon()
    terms = streaming_keyterms(
        lexicon,
        org_names=["Medicare", "Social Security", "IRS", "Walgreens"],
        people_names=["Margaret", "Sarah"],
    )
    results = await asyncio.gather(
        run_leg("caller", FIXTURES / "caller.wav", terms),
        run_leg("senior", FIXTURES / "senior.wav", terms),
    )
    all_lags = [lag for _, lags in results for lag in lags]
    median = int(round(statistics.median(all_lags))) if all_lags else -1
    for speaker, (words, _) in zip(("caller", "senior"), results):
        print(f"{speaker}: {' '.join(words)}")
    passed = all(words for words, _ in results) and 0 <= median < 1500
    print(f"PHASE2_STT={'PASS' if passed else 'FAIL'} median_word_lag_ms={median}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
