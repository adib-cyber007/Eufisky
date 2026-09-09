"""Privacy-safe presentation helpers for persisted batch call analytics."""

from __future__ import annotations

import re
from typing import Any


# Only organizations are useful to this scam-review surface without exposing a
# person's attributes. Treat every current or future category as sensitive by
# default instead of trying to maintain an incomplete deny-list.
_DISPLAYABLE_ENTITY_TYPES = {"organization"}
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_DIGITS = re.compile(r"\b(?:\d[\s().+-]*){4,}\b")


def _integer(value: Any) -> int:
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _confidence(value: Any) -> float | None:
    try:
        return round(max(0.0, min(1.0, float(value))), 3)
    except (TypeError, ValueError):
        return None


def _plain_label(value: Any) -> str:
    return str(value or "Entity").replace("_", " ").strip().title()


def _redact_text(value: Any) -> str:
    text = _EMAIL.sub("[EMAIL]", str(value or "").strip())
    return _DIGITS.sub("####", text)


def build_insight_timeline(analytics: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Merge entity and sentiment results into one sanitized time-ordered list."""

    source = analytics if isinstance(analytics, dict) else {}
    timeline: list[dict[str, Any]] = []
    for entity in source.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        entity_type = str(entity.get("entity_type") or entity.get("type") or "entity")
        sensitive = entity_type.casefold() not in _DISPLAYABLE_ENTITY_TYPES
        text = "Sensitive value redacted" if sensitive else _redact_text(entity.get("text"))
        if not text:
            continue
        timeline.append(
            {
                "kind": "entity",
                "t_ms": _integer(entity.get("start") or entity.get("start_ms")),
                "end_ms": _integer(entity.get("end") or entity.get("end_ms")),
                "label": _plain_label(entity_type),
                "text": text,
                "confidence": _confidence(entity.get("confidence")),
            }
        )

    for sentiment in source.get("sentiments") or []:
        if not isinstance(sentiment, dict):
            continue
        value = str(sentiment.get("sentiment") or "neutral").strip().casefold()
        if value not in {"positive", "negative", "neutral"}:
            value = "neutral"
        speaker = str(sentiment.get("speaker") or "").strip()
        if not speaker:
            channel = _integer(sentiment.get("channel") or sentiment.get("audio_channel"))
            speaker = "Caller" if channel in {0, 1} else "Margaret"
        text = _redact_text(sentiment.get("text")) or f"{speaker} turn"
        timeline.append(
            {
                "kind": "sentiment",
                "t_ms": _integer(sentiment.get("start") or sentiment.get("start_ms")),
                "end_ms": _integer(sentiment.get("end") or sentiment.get("end_ms")),
                "label": f"{value.title()} sentiment",
                "text": text,
                "speaker": speaker,
                "sentiment": value,
                "confidence": _confidence(sentiment.get("confidence")),
            }
        )

    return sorted(
        timeline,
        key=lambda item: (
            int(item["t_ms"]),
            0 if item["kind"] == "entity" else 1,
            str(item["label"]),
        ),
    )


__all__ = ["build_insight_timeline"]
