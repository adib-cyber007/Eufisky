"""Generate deterministic eight-second probe fixtures with Windows TTS."""

from __future__ import annotations

import audioop
import math
from pathlib import Path
import struct
import subprocess
import wave

SAMPLE_RATE = 16_000
DURATION_SECONDS = 8
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SCRIPTS = {
    "caller.wav": (
        "This is Michael from Medicare, your benefits will be suspended today "
        "unless we verify your card number"
    ),
    "senior.wav": "Hold on, let me get my purse, my card says four one two three",
}


def _powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _run_windows_tts(path: Path, text: str) -> None:
    script = "; ".join(
        [
            "Add-Type -AssemblyName System.Speech",
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
            (
                "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo("
                "16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, "
                "[System.Speech.AudioFormat.AudioChannel]::Mono)"
            ),
            f"$s.SetOutputToWaveFile({_powershell_literal(str(path))}, $f)",
            f"$s.Speak({_powershell_literal(text)})",
            "$s.Dispose()",
        ]
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
    )


def _fit_to_eight_seconds(source: Path, destination: Path) -> None:
    with wave.open(str(source), "rb") as wav_in:
        channels = wav_in.getnchannels()
        width = wav_in.getsampwidth()
        rate = wav_in.getframerate()
        frames = wav_in.readframes(wav_in.getnframes())

    if channels == 2:
        frames = audioop.tomono(frames, width, 0.5, 0.5)
        channels = 1
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
        width = 2
    if rate != SAMPLE_RATE:
        frames, _ = audioop.ratecv(frames, width, channels, rate, SAMPLE_RATE, None)

    target_bytes = SAMPLE_RATE * DURATION_SECONDS * 2
    frames = frames[:target_bytes].ljust(target_bytes, b"\x00")
    with wave.open(str(destination), "wb") as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(2)
        wav_out.setframerate(SAMPLE_RATE)
        wav_out.writeframes(frames)


def _write_placeholder(destination: Path, seed: int) -> None:
    samples: list[bytes] = []
    for index in range(SAMPLE_RATE * DURATION_SECONDS):
        second = index / SAMPLE_RATE
        syllable = 0.20 + 0.80 * abs(math.sin(2 * math.pi * (2.7 + seed) * second))
        carrier = math.sin(2 * math.pi * (165 + 35 * seed) * second)
        value = int(7_000 * syllable * carrier)
        samples.append(struct.pack("<h", value))
    with wave.open(str(destination), "wb") as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(2)
        wav_out.setframerate(SAMPLE_RATE)
        wav_out.writeframes(b"".join(samples))


def main() -> int:
    """Generate both fixtures and record whether speech or fallback audio was used."""

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    modes: list[str] = []
    for seed, (name, text) in enumerate(SCRIPTS.items(), start=1):
        destination = FIXTURE_DIR / name
        temporary = FIXTURE_DIR / f".{name}.tts.wav"
        try:
            _run_windows_tts(temporary, text)
            _fit_to_eight_seconds(temporary, destination)
            modes.append(f"{name}: Windows System.Speech TTS")
        except Exception as error:  # The fallback is an explicit probe requirement.
            _write_placeholder(destination, seed)
            modes.append(f"{name}: tone-modulated placeholder ({type(error).__name__})")
        finally:
            temporary.unlink(missing_ok=True)

    (FIXTURE_DIR / "GENERATION.txt").write_text("\n".join(modes) + "\n", encoding="utf-8")
    print("PASS fixture_generation | " + "; ".join(modes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
