"""PCM16 utilities used by the browser phone bridge."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Iterable

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2


def clamp_pcm16(value: float | int) -> int:
    return max(-32768, min(32767, int(value)))


def samples_to_pcm16(samples: Iterable[float | int]) -> bytes:
    return b"".join(struct.pack("<h", clamp_pcm16(sample)) for sample in samples)


def silence(duration_ms: int) -> bytes:
    return b"\x00\x00" * max(0, int(SAMPLE_RATE * duration_ms / 1000))


def hold_tone(duration_ms: int = 600, frequency: float = 440.0, volume: float = 0.12) -> bytes:
    count = max(0, int(SAMPLE_RATE * duration_ms / 1000))
    return samples_to_pcm16(
        math.sin(2 * math.pi * frequency * index / SAMPLE_RATE) * 32767 * volume
        for index in range(count)
    )


class WavWriter:
    """Incrementally write raw 16 kHz mono PCM16 frames to a valid WAV."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._wave = wave.open(str(self.path), "wb")
        self._wave.setnchannels(1)
        self._wave.setsampwidth(SAMPLE_WIDTH)
        self._wave.setframerate(SAMPLE_RATE)
        self.closed = False

    def write(self, pcm: bytes) -> None:
        if not self.closed and pcm:
            self._wave.writeframesraw(pcm[: len(pcm) - (len(pcm) % 2)])

    def close(self) -> None:
        if not self.closed:
            self._wave.close()
            self.closed = True

    def __enter__(self) -> "WavWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
