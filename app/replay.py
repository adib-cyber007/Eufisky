"""Replay a saved dashboard event stream without phones or microphones."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from app import db
from app.rooms import rooms

Sleep = Callable[[float], Awaitable[None]]
_REPLAYS: dict[str, asyncio.Task[None]] = {}


def load_replay(file_name: str = "demo_call.json") -> dict[str, Any]:
    safe_name = Path(file_name).name
    if safe_name != file_name or not safe_name.endswith(".json"):
        raise ValueError("Replay file must be a JSON file from the data folder")
    path = db.DATA_DIR / safe_name
    if not path.exists():
        raise FileNotFoundError(safe_name)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("Replay file must contain an events list")
    events = payload["events"]
    for event in events:
        if not isinstance(event, dict) or "type" not in event:
            raise ValueError("Every replay event must be an object with a type")
    return payload


async def play_events(
    room: str,
    events: list[dict[str, Any]],
    speed: float = 1.0,
    *,
    sleep: Sleep = asyncio.sleep,
) -> None:
    speed = max(0.25, min(20.0, float(speed)))
    db.ensure_room(room)
    live = rooms.get(room)
    previous_ms = 0
    await live.broadcast_dashboard({"type": "replay", "status": "started"})
    for saved in sorted(events, key=lambda item: int(item.get("t_ms") or 0)):
        t_ms = max(0, int(saved.get("t_ms") or 0))
        delay = max(0, t_ms - previous_ms) / 1000 / speed
        if delay:
            await sleep(delay)
        event = dict(saved)
        event["replay"] = True
        event.setdefault("call_id", "replay-demo")
        await live.broadcast_dashboard(event)
        previous_ms = t_ms
    await live.broadcast_dashboard({"type": "replay", "status": "complete"})


def start(room: str, file_name: str = "demo_call.json", speed: float = 1.0) -> dict[str, Any]:
    payload = load_replay(file_name)
    current = _REPLAYS.get(room)
    if current and not current.done():
        current.cancel()
    task = asyncio.create_task(
        play_events(room, payload["events"], speed), name=f"replay-{room}"
    )
    _REPLAYS[room] = task

    def finished(done: asyncio.Task[None]) -> None:
        if _REPLAYS.get(room) is done:
            _REPLAYS.pop(room, None)
        if done.cancelled():
            return
        done.exception()

    task.add_done_callback(finished)
    duration_ms = max((int(event.get("t_ms") or 0) for event in payload["events"]), default=0)
    return {
        "ok": True,
        "status": "started",
        "file": file_name,
        "speed": max(0.25, min(20.0, float(speed))),
        "events": len(payload["events"]),
        "duration_ms": duration_ms,
    }
