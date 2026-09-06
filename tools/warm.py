"""Keep a free Eufisky deployment awake before a demonstration."""

from __future__ import annotations

import argparse
from datetime import datetime
import sys
import time

import httpx

try:
    from tools.smoke_public import normalize_base_url
except ModuleNotFoundError:  # Direct invocation: python tools\warm.py
    from smoke_public import normalize_base_url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Deployed Eufisky origin")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between checks")
    parser.add_argument("--once", action="store_true", help="Check once, then exit")
    args = parser.parse_args()
    try:
        base_url = normalize_base_url(args.url)
    except ValueError as error:
        print(f"FAIL {error}")
        return 1
    if args.interval < 1:
        print("FAIL --interval must be at least 1 second")
        return 1

    print("Warming Eufisky. Press Ctrl+C after the demo.")
    try:
        with httpx.Client(timeout=75, follow_redirects=True) as client:
            while True:
                stamp = datetime.now().astimezone().strftime("%H:%M:%S")
                try:
                    response = client.get(f"{base_url}/api/health")
                    response.raise_for_status()
                    payload = response.json()
                    healthy = payload.get("ok") is True and payload.get("db_ok") is True
                    print(f"{stamp} {'READY' if healthy else 'NOT READY'}", flush=True)
                except (httpx.HTTPError, ValueError) as error:
                    print(f"{stamp} RETRYING: {error}", flush=True)
                if args.once:
                    return 0
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nWarmer stopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
