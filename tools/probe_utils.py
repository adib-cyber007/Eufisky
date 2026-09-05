"""Shared helpers for Eufisky's external capability probes."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import time
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tools" / "fixtures"
load_dotenv(ROOT / ".env")


@dataclass(slots=True)
class ProbeReport:
    """Collect a stable, secret-safe result for a command-line probe."""

    name: str
    started: float = field(default_factory=time.perf_counter)
    samples: list[str] = field(default_factory=list)

    def sample(self, direction: str, message: Any) -> None:
        """Store a compact wire sample with credential-shaped values removed."""

        rendered = message if isinstance(message, str) else json.dumps(message, separators=(",", ":"))
        rendered = re.sub(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?)([^\s,}\"']+)", r"\1<hidden>", rendered)
        self.samples.append(f"{direction} {rendered[:500]}")

    def finish(self, status: str, reason: str) -> int:
        """Print the required summary, latency, and observed wire samples."""

        elapsed_ms = (time.perf_counter() - self.started) * 1_000
        print(f"{status} {self.name} | {reason} | latency_ms={elapsed_ms:.0f}")
        for sample in self.samples[:8]:
            print(f"WIRE {sample}")
        return 0 if status in {"PASS", "SKIPPED"} else 1


def api_key(name: str) -> str:
    """Read and trim a credential without ever displaying it."""

    return os.getenv(name, "").strip()
