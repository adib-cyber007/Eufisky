"""Deterministic, speaker-aware live scam-risk scoring."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import math
import re
from typing import Any

from app.rules.normalize import normalize
from app.stt.assemblyai_stream import WordEvent


@dataclass(frozen=True, slots=True)
class Evidence:
    speaker: str
    family: str
    phrase: str
    t_ms: int


@dataclass(frozen=True, slots=True)
class RiskUpdate:
    t_ms: int
    score: int
    active_signals: list[str]
    evidence: list[dict[str, Any]]
    flags: list[str]


@dataclass(frozen=True, slots=True)
class _Hit:
    family: str
    speaker: str
    phrase: str
    t_ms: int
    weight: float
    half_life_s: float


class RuleEngine:
    """Score normalized words with rolling per-speaker twelve-word windows."""

    def __init__(self, lexicon: dict[str, Any], seed_score: int = 0) -> None:
        self.lexicon = lexicon
        self.seed_score = max(0, min(100, int(seed_score)))
        self.windows: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=12))
        self.hits: dict[str, list[_Hit]] = defaultdict(list)
        self.last_seen: dict[tuple[str, str, str], int] = {}
        self._phrases: dict[str, list[tuple[str, ...]]] = {}
        for family, config in lexicon.get("signals", {}).items():
            self._phrases[family] = [
                tuple(normalize(str(phrase)).split())
                for phrase in config.get("phrases", [])
                if normalize(str(phrase))
            ]
        self._patterns = {
            family: re.compile(str(config["regex"]))
            for family, config in lexicon.get("patterns", {}).items()
            if config.get("regex")
        }

    def ingest(self, event: WordEvent) -> RiskUpdate | None:
        """Ingest new word(s), returning an update only when evidence changes."""

        tokens = normalize(event.text).split()
        if not tokens:
            return None
        changed = False
        for token in tokens:
            window = self.windows[event.speaker]
            window.append(token)
            words = tuple(window)
            text = " ".join(words)
            for family, config in self.lexicon.get("signals", {}).items():
                if config.get("speaker") != event.speaker:
                    continue
                for phrase_tokens in self._phrases.get(family, []):
                    if len(phrase_tokens) <= len(words) and words[-len(phrase_tokens):] == phrase_tokens:
                        changed |= self._record(
                            family, event.speaker, " ".join(phrase_tokens), event.t_ms, config
                        )
            for family, pattern in self._patterns.items():
                config = self.lexicon["patterns"][family]
                if config.get("speaker") != event.speaker:
                    continue
                matches = list(pattern.finditer(text))
                if matches and matches[-1].end() == len(text):
                    changed |= self._record(
                        family, event.speaker, matches[-1].group(0), event.t_ms, config
                    )
        return self._update(event.t_ms) if changed else None

    def tick(self, t_ms: int) -> RiskUpdate:
        """Return the current decayed score for the 500 ms session ticker."""

        return self._update(t_ms)

    def _record(
        self, family: str, speaker: str, phrase: str, t_ms: int, config: dict[str, Any]
    ) -> bool:
        key = (speaker, family, phrase)
        previous = self.last_seen.get(key)
        if previous is not None and abs(t_ms - previous) <= 2000:
            return False
        self.last_seen[key] = t_ms
        self.hits[family].append(
            _Hit(
                family=family,
                speaker=speaker,
                phrase=phrase,
                t_ms=t_ms,
                weight=float(config["weight"]),
                half_life_s=float(config["half_life_s"]),
            )
        )
        return True

    def _active_hits(self, family: str, t_ms: int) -> list[_Hit]:
        config = (
            self.lexicon.get("signals", {}).get(family)
            or self.lexicon.get("patterns", {}).get(family)
            or {}
        )
        cap = int(config.get("cap", 3))
        viable = [
            hit for hit in self.hits.get(family, [])
            if t_ms - hit.t_ms <= hit.half_life_s * 8000
        ]
        return viable[-cap:]

    def _update(self, t_ms: int) -> RiskUpdate:
        total = float(self.seed_score)
        active: set[str] = set()
        evidence: list[Evidence] = []
        families = set(self.lexicon.get("signals", {})) | set(self.lexicon.get("patterns", {}))
        for family in families:
            for hit in self._active_hits(family, t_ms):
                age_s = max(0.0, (t_ms - hit.t_ms) / 1000)
                contribution = hit.weight * math.pow(2, -age_s / hit.half_life_s)
                total += contribution
                if abs(contribution) >= 0.25:
                    active.add(family)
                    evidence.append(Evidence(hit.speaker, family, hit.phrase, hit.t_ms))

        for combo in self.lexicon.get("combos", []):
            combo_families = set(combo.get("families", []))
            required = set(combo.get("required", []))
            minimum = int(combo.get("minimum", len(combo_families)))
            if required.issubset(active) and len(combo_families & active) >= minimum:
                total += float(combo.get("bonus", 0))

        score = max(0, min(100, int(round(total))))
        flags: list[str] = []
        if "pii_disclosure" in active:
            flags.append("pii_disclosure")
        if {"payment_method", "compliance_cue"}.issubset(active):
            flags.append("payment_compliance")
        if score >= 65 or (score >= 45 and "pii_disclosure" in active) or "payment_compliance" in flags:
            flags.append("trigger_l2")
        if score >= 90:
            flags.append("trigger_l3")
        evidence.sort(key=lambda item: (item.t_ms, item.family, item.phrase))
        return RiskUpdate(
            t_ms=t_ms,
            score=score,
            active_signals=sorted(active),
            evidence=[asdict(item) for item in evidence],
            flags=flags,
        )
