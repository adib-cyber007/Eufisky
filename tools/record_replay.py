"""Export a completed real call as an Eufisky replay file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from app import db


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
    for row in db.list_events(call_id):
        payload = dict(row.get("payload") or {})
        event_type = str(payload.get("type") or row["type"])
        if event_type not in {"state", "level", "risk", "tool", "guardian"}:
            continue
        payload["type"] = event_type
        payload["t_ms"] = int(row["t_ms"])
        payload["call_id"] = "replay-demo"
        events.append(payload)
    for segment in db.list_segments(call_id):
        events.append(
            {
                "type": "caption",
                "t_ms": int(segment["t_ms"]),
                "role": segment["speaker"],
                "speaker": segment["speaker"],
                "text": segment["text"],
                "call_id": "replay-demo",
            }
        )
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
