"""Start a saved Eufisky replay through the running server."""

from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--room", default="demo")
    parser.add_argument("--file", default="demo_call.json")
    parser.add_argument("--speed", type=float, default=2.0)
    args = parser.parse_args()
    try:
        response = httpx.post(
            f"{args.url.rstrip('/')}/api/rooms/{args.room}/replay",
            json={"file": args.file, "speed": args.speed},
            timeout=8,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        print(f"Replay could not start: {error}")
        return 1
    result = response.json()
    print(
        f"Replay started in room {args.room}: {result['events']} events at {result['speed']}x."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
