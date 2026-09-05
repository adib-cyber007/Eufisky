"""Probe Groq's OpenAI-compatible tool-calling API when configured."""

from __future__ import annotations

import json

import httpx

from probe_utils import ProbeReport, api_key

URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def run() -> int:
    """Request one deterministic tool call, falling back to the smaller model."""

    report = ProbeReport("groq")
    key = api_key("GROQ_API_KEY")
    if not key:
        return report.finish("SKIPPED", "GROQ_API_KEY is empty; Phase-3 human task T3 remains deferred")

    payload = {
        "messages": [
            {
                "role": "user",
                "content": "Take a message from Michael saying he called about Medicare benefits. Use take_message.",
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "take_message",
                    "description": "Save a caller message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "caller_name": {"type": "string"},
                            "message": {"type": "string"},
                        },
                        "required": ["caller_name", "message"],
                    },
                },
            }
        ],
        "tool_choice": "required",
        "temperature": 0,
    }
    report.sample("client", {"url": URL, **payload})
    failures: list[str] = []
    with httpx.Client(timeout=30) as client:
        for model in MODELS:
            response = client.post(
                URL,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, **payload},
            )
            if response.is_success:
                body = response.json()
                report.sample("server", body)
                calls = body.get("choices", [{}])[0].get("message", {}).get("tool_calls") or []
                if calls:
                    return report.finish("PASS", f"model={model}; tool={calls[0].get('function', {}).get('name')}")
                failures.append(f"{model}: no tool call")
            else:
                failures.append(f"{model}: HTTP {response.status_code}")
    return report.finish("FAIL", json.dumps(failures))


if __name__ == "__main__":
    raise SystemExit(run())
