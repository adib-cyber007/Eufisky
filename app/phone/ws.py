"""WebSocket transport for phone and dashboard clients."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.phone.calls import CallState, calls
from app.rooms import rooms

VALID_ROLES = {"caller", "senior", "family"}


def normalize_message(raw: str) -> dict[str, Any]:
    """Accept both `{type: ...}` and documented `event{...}` envelopes."""
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("phone message must be a JSON object")
    if payload.get("type"):
        return payload
    if len(payload) == 1:
        message_type, body = next(iter(payload.items()))
        return {"type": message_type, **(body if isinstance(body, dict) else {})}
    raise ValueError("phone message type is missing")


async def _heartbeat(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(15)
        await websocket.send_json({"type": "ping"})


async def _receive_hello(websocket: WebSocket) -> dict[str, Any]:
    message = await websocket.receive_text()
    payload = normalize_message(message)
    if payload.get("type") != "hello":
        raise ValueError("first message must be hello")
    role = payload.get("role")
    if role not in VALID_ROLES:
        raise ValueError("invalid phone role")
    return payload


async def phone_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    room_name = ""
    role = ""
    heartbeat: asyncio.Task[None] | None = None
    try:
        hello = await _receive_hello(websocket)
        room_name = str(hello.get("room") or "demo").strip()
        role = str(hello["role"])
        connection = rooms.register_phone(room_name, role, websocket, hello.get("caller_phone"))
        live = rooms.get(room_name)
        current = live.current_call
        if current and current.state != CallState.ENDED:
            await websocket.send_json({"type": "state", "call_state": current.state.value,
                                       "badge": current.badge, "monitored": current.monitored,
                                       "family_joined": current.family_joined,
                                       "family_ringing": current.family_ringing})
            if role == "senior" and current.state in {CallState.RINGING_SENIOR, CallState.DIALING_SENIOR}:
                await websocket.send_json({"type": "ring", "from_label": current.label,
                                           "trusted": current.classification == "trusted"})
            if role == "family" and current.family_ringing:
                await websocket.send_json({"type": "ring", "from_label": "Margaret's call",
                                           "trusted": True})
        else:
            await websocket.send_json({"type": "state", "call_state": "IDLE",
                                       "badge": "Ready", "monitored": False})
        heartbeat = asyncio.create_task(_heartbeat(websocket))
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            pcm = message.get("bytes")
            if pcm is not None:
                await calls.relay(room_name, role, pcm)
                continue
            raw = message.get("text")
            if raw is None:
                continue
            payload = normalize_message(raw)
            message_type = payload["type"]
            if message_type == "hello":
                connection.caller_phone = payload.get("caller_phone", connection.caller_phone)
            elif message_type == "dial" and role == "caller":
                await calls.dial(room_name, connection.caller_phone)
            elif message_type == "answer":
                await calls.answer(room_name, role)
            elif message_type == "hangup":
                await calls.hangup(room_name, f"{role} hung up")
            elif message_type == "text":
                await calls.text(room_name, role, str(payload.get("text", "")))
            elif message_type == "dtmf" and live.current_call:
                from app import db
                db.add_event(live.current_call.id, live.current_call.elapsed_ms, "dtmf",
                             {"role": role, "digit": str(payload.get("digit", ""))[:1]})
                digit = str(payload.get("digit", ""))[:1]
                if role == "senior" and digit in {"1", "2", "3"}:
                    await calls.guardian_action(room_name, role, {"1": "end", "2": "family", "3": "continue"}[digit])
            elif message_type == "guardian_action":
                await calls.guardian_action(room_name, role, str(payload.get("action") or ""))
            elif message_type in {"mic", "pong", "ping"}:
                continue
    except (WebSocketDisconnect, RuntimeError):
        pass
    except (ValueError, json.JSONDecodeError) as exc:
        with suppress(Exception):
            await websocket.send_json({"type": "ended", "reason": str(exc)})
    finally:
        if heartbeat:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
        if room_name and role and rooms.unregister_phone(room_name, role, websocket):
            live = rooms.get(room_name)
            current = live.current_call
            if current and current.state != CallState.ENDED:
                participating = role in {"caller", "senior"} or (role == "family" and current.family_joined)
                if participating:
                    await calls.hangup(room_name, f"{role} disconnected")


async def dashboard_socket(websocket: WebSocket, room_name: str) -> None:
    await websocket.accept()
    rooms.register_dashboard(room_name, websocket)
    heartbeat = asyncio.create_task(_heartbeat(websocket))
    try:
        await websocket.send_json(rooms.snapshot(room_name))
        while True:
            raw = await websocket.receive_text()
            payload = normalize_message(raw)
            message_type = payload["type"]
            if message_type in {"ring_family", "conference_family"}:
                await calls.ring_family(room_name)
            elif message_type in {"pong", "ping"}:
                continue
    except (WebSocketDisconnect, RuntimeError, json.JSONDecodeError):
        pass
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
        rooms.unregister_dashboard(room_name, websocket)
