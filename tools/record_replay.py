"""Export a completed real call as an Eufisky replay file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import db


def _fallback_incident_captions(call_id: str, end_ms: int) -> list[dict[str, Any]]:
    """Turn a seeded incident transcript into replay captions when raw segments are absent."""
    incident = db.get_incident(call_id) or {}
    lines = [
        line.strip()
        for line in str(incident.get("redacted_transcript") or "").splitlines()
        if line.strip()
    ]
    captions: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        label, separator, text = line.partition(":")
        if not separator or not text.strip():
            label, text = "Caller", line
        normalized = label.strip().casefold()
        speaker = (
            "senior" if normalized in {"margaret", "senior"}
            else "family" if normalized in {"sarah", "family"}
            else "agent" if normalized in {"eufisky", "agent", "guardian"}
            else "caller"
        )
        t_ms = max(500, int((index / (len(lines) + 1)) * max(1000, end_ms)))
        captions.append({
            "type": "transcript",
            "t_ms": t_ms,
            "role": speaker,
            "speaker": speaker,
            "text": text.strip(),
            "final": True,
            "call_id": "replay-demo",
        })
    return captions


def export_call(call_id: str, destination: Path) -> dict[str, Any]:
    call = db.get_call(call_id)
    if not call:
        raise ValueError("Call was not found")
    events: list[dict[str, Any]] = [
        {
            "type": "call",
            "t_ms": 0,
            "event": "started",
            "call_id": "replay-demo",
            "classification": call["classification"],
        }
    ]
    stored_events = db.list_events(call_id)
    for row in stored_events:
        payload = dict(row.get("payload") or {})
        event_type = str(payload.get("type") or row["type"])
        if event_type not in {"state", "level", "risk", "tool", "guardian"}:
            continue
        payload["type"] = event_type
        payload["t_ms"] = int(row["t_ms"])
        payload["call_id"] = "replay-demo"
        events.append(payload)
    if not any(event["type"] == "risk" for event in events):
        for sample in db.list_risk_samples(call_id):
            events.append({
                "type": "risk",
                "t_ms": int(sample["t_ms"]),
                "score": int(sample["score"]),
                "signals": sample.get("signals") or [],
                "evidence": [],
                "call_id": "replay-demo",
            })
    segments = db.list_segments(call_id)
    for segment in segments:
        events.append(
            {
                "type": "transcript",
                "t_ms": int(segment["t_ms"]),
                "role": segment["speaker"],
                "speaker": segment["speaker"],
                "text": segment["text"],
                "final": bool(segment.get("is_final", True)),
                "call_id": "replay-demo",
            }
        )
    story_end_ms = max(
        (int(event.get("t_ms") or 0) for event in events),
        default=0,
    )
    if not segments:
        events.extend(_fallback_incident_captions(call_id, story_end_ms))
    end_ms = max((int(event.get("t_ms") or 0) for event in events), default=0) + 1000
    events.append(
        {
            "type": "call",
            "t_ms": end_ms,
            "event": "ended",
            "call_id": "replay-demo",
            "classification": call["classification"],
        }
    )
    result = {
        "version": 1,
        "title": f"Recorded call from {call.get('from_label') or call.get('from_phone')}",
        "source_call_id": call_id,
        "events": sorted(events, key=lambda item: int(item.get("t_ms") or 0)),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("call_id", nargs="?")
    parser.add_argument("--room", default="demo")
    parser.add_argument("--output", default="data/demo_call.json")
    args = parser.parse_args()
    db.init_db()
    call_id = args.call_id
    if not call_id:
        calls = [call for call in db.list_calls(args.room) if call.get("classification") == "unknown"]
        if not calls:
            print(f"No monitored calls were found in room {args.room}.")
            return 1
        call_id = str(calls[0]["id"])
    try:
        result = export_call(call_id, Path(args.output))
    except ValueError as error:
        print(str(error))
        return 1
    print(f"Saved {len(result['events'])} replay events to {args.output}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
