"""Exercise the Phase-4 Guardian story against a running Eufisky server."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from typing import Any, Callable

import httpx
from websockets.asyncio.client import connect


async def receive_json(socket: Any, predicate: Callable[[dict[str, Any]], bool], timeout: float = 20) -> dict[str, Any]:
    async def wait() -> dict[str, Any]:
        async for raw in socket:
            if isinstance(raw, bytes):
                continue
            message = json.loads(raw)
            if message.get("type") == "ping":
                await socket.send(json.dumps({"type": "pong"}))
                continue
            if predicate(message):
                return message
        raise RuntimeError("socket closed before expected event")
    return await asyncio.wait_for(wait(), timeout)


async def send(socket: Any, message_type: str, **values: Any) -> None:
    await socket.send(json.dumps({"type": message_type, **values}))


async def verify(base_url: str, scenario: str) -> None:
    room = f"guardian-{uuid.uuid4().hex[:8]}"
    ws_base = base_url.replace("http://", "ws://").replace("https://", "wss://")
    async with (
        connect(f"{ws_base}/ws/phone") as caller,
        connect(f"{ws_base}/ws/phone") as senior,
        connect(f"{ws_base}/ws/phone") as family,
        connect(f"{ws_base}/ws/dashboard?room={room}") as dashboard,
    ):
        await send(caller, "hello", role="caller", room=room, caller_phone="+15550199321")
        await send(senior, "hello", role="senior", room=room)
        await send(family, "hello", role="family", room=room)
        await asyncio.gather(*(
            receive_json(socket, lambda item: item.get("type") == "state")
            for socket in (caller, senior, family, dashboard)
        ))

        await send(caller, "dial")
        # A live Voice Agent greets with PCM audio/captions, while the
        # deterministic fallback emits agent_say. Either proves the Front Door
        # is ready for the typed manual-test turn.
        await receive_json(
            caller,
            lambda item: item.get("type") in {"agent_say", "agent_caption", "audio"},
        )
        await send(caller, "text", text="This is Michael, calling about a routine account service update.")
        ring = await receive_json(senior, lambda item: item.get("type") == "ring")
        assert "Michael" in ring.get("from_label", "")
        await send(senior, "answer")
        await receive_json(caller, lambda item: item.get("type") == "state" and item.get("call_state") == "BRIDGED")

        await send(caller, "text", text="This is your bank's fraud department. Your debit card may be at risk.")
        await send(caller, "text", text="To verify your account, read me your credit card number and CVV.")
        hold_started = time.perf_counter()
        hold = await receive_json(caller, lambda item: item.get("type") == "hold" and item.get("on") is True, 5)
        hold_latency = time.perf_counter() - hold_started
        assert hold["on"] is True and hold_latency < 0.5, hold_latency
        moment = await receive_json(senior, lambda item: item.get("type") == "agent_say" and "One moment" in item.get("text", ""), 2)
        assert "Margaret" in moment["text"]
        controls = await receive_json(senior, lambda item: item.get("type") == "guardian_controls", 4)
        assert controls["visible"] is True
        if scenario == "fallback":
            assert controls.get("fallback") is True
            await send(senior, "guardian_action", action="continue")
            await receive_json(caller, lambda item: item.get("type") == "hold" and item.get("on") is False, 3)
        elif scenario == "continue":
            await send(senior, "text", text="Continue the call.")
            await receive_json(caller, lambda item: item.get("type") == "hold" and item.get("on") is False, 3)
        else:
            await send(senior, "text", text="Get Sarah.")
            family_ring = await receive_json(family, lambda item: item.get("type") == "ring", 3)
            assert "Eufisky paused a risky call" in family_ring.get("reason", "")
            await send(family, "answer")
            await receive_json(family, lambda item: item.get("type") == "tone" and item.get("name") == "connected")

        await send(caller, "hangup")
        ended = await receive_json(dashboard, lambda item: item.get("type") == "call" and item.get("event") == "ended")
        assert ended["event"] == "ended"

    async with httpx.AsyncClient(timeout=5) as client:
        contacts = (await client.get(f"{base_url}/api/rooms/{room}/contacts")).json()
        blocked = [item for item in contacts if item["phone"] == "+15550199321" and item["status"] == "blocked"]
        assert blocked
    outcome = "family joined" if scenario == "family" else "fallback control resumed" if scenario == "fallback" else "senior resumed"
    print(f"PASS Guardian {scenario} flow: hold={hold_latency * 1000:.0f}ms, {outcome}, caller blocked, room={room}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--scenario", choices=("family", "continue", "fallback"), default="family")
    args = parser.parse_args()
    asyncio.run(verify(args.base_url.rstrip("/"), args.scenario))


if __name__ == "__main__":
    main()
