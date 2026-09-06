"""Check a deployed Eufisky URL, including WebSocket replay delivery."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
import websockets


def normalize_base_url(value: str) -> str:
    """Return a validated HTTP(S) origin without a trailing slash."""

    candidate = value.strip().rstrip("/")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must start with http:// or https:// and include a host")
    if parsed.query or parsed.fragment:
        raise ValueError("URL must not include a query string or fragment")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


async def wait_for_health(client: httpx.AsyncClient, base_url: str) -> dict:
    """Allow enough time for a sleeping free Render service to wake."""

    deadline = time.monotonic() + 90
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = await client.get(f"{base_url}/api/health")
            response.raise_for_status()
            payload = response.json()
            if payload.get("ok") is True and payload.get("db_ok") is True:
                return payload
            last_error = RuntimeError("health response did not report ok=true and db_ok=true")
        except (httpx.HTTPError, ValueError) as error:
            last_error = error
        await asyncio.sleep(3)
    raise RuntimeError(f"health check did not become ready within 90 seconds: {last_error}")


async def run(base_url: str) -> None:
    room = f"public-smoke-{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient(timeout=75, follow_redirects=True) as client:
        await wait_for_health(client, base_url)
        print("PASS health and database")

        pages = {
            "/": "<title>Eufisky</title>",
            f"/caller?room={quote(room)}": "Caller",
            f"/senior?room={quote(room)}": "Margaret",
            f"/family?room={quote(room)}": "Sarah",
            f"/dashboard?room={quote(room)}": "Dashboard",
        }
        for path, marker in pages.items():
            response = await client.get(f"{base_url}{path}")
            response.raise_for_status()
            if marker not in response.text:
                raise RuntimeError(f"{path} loaded but did not contain its expected page marker")
        print("PASS landing, Caller, Senior, Family, and Dashboard pages")

        parsed = urlsplit(base_url)
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_url = urlunsplit(
            (ws_scheme, parsed.netloc, f"{parsed.path}/ws/dashboard", f"room={quote(room)}", "")
        )
        async with websockets.connect(ws_url, open_timeout=30) as socket:
            first = json.loads(await asyncio.wait_for(socket.recv(), timeout=20))
            if first.get("type") != "state":
                raise RuntimeError("dashboard WebSocket did not send its initial state")
            print("PASS dashboard WebSocket handshake")

            response = await client.post(
                f"{base_url}/api/rooms/{quote(room)}/replay",
                json={"file": "demo_call.json", "speed": 20},
            )
            response.raise_for_status()
            if response.json().get("status") != "started":
                raise RuntimeError("replay endpoint did not report status=started")

            seen: set[str] = set()
            completed = False
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and not completed:
                remaining = max(0.1, deadline - time.monotonic())
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=remaining))
                event_type = str(message.get("type", ""))
                seen.add(event_type)
                completed = event_type == "replay" and message.get("status") == "completed"
            required = {"risk", "transcript", "state", "tool", "replay"}
            missing = sorted(required - seen)
            if not completed:
                raise RuntimeError("replay did not emit its completed event")
            if missing:
                raise RuntimeError(f"replay omitted expected WebSocket events: {', '.join(missing)}")
            print("PASS replay endpoint and complete WebSocket event story")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Deployed Eufisky origin, for example https://eufisky.onrender.com")
    args = parser.parse_args()
    try:
        asyncio.run(run(normalize_base_url(args.url)))
    except (OSError, ValueError, RuntimeError, httpx.HTTPError, asyncio.TimeoutError) as error:
        print(f"FAIL {error}")
        return 1
    print("Public smoke check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
