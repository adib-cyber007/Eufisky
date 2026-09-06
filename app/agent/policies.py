"""Server-side Front Door policy; model tool choices are never trusted directly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    action: str
    args: dict[str, Any]
    result: dict[str, Any]


def decide(
    tool_name: str,
    args: dict[str, Any],
    risk_score: int,
    *,
    always_ring_first: bool = False,
) -> PolicyDecision:
    """Validate a single tool call and enforce the score-40 connection boundary."""

    if tool_name == "connect_caller":
        caller_name = str(args.get("caller_name") or "Unknown caller").strip()
        purpose = str(args.get("purpose") or "No purpose provided").strip()
        if risk_score >= 40 and not always_ring_first:
            message_args = {
                "caller_name": caller_name,
                "message": purpose,
                "callback_number": str(args.get("callback_number") or "").strip(),
            }
            return PolicyDecision(
                "take_message",
                message_args,
                {"status": "policy_override", "say": "I'll pass along a message instead."},
            )
        return PolicyDecision(
            "connect_caller",
            {**args, "caller_name": caller_name, "purpose": purpose},
            {"status": "connecting", "say": "Thank you. I'll connect you now."},
        )
    if tool_name == "take_message":
        return PolicyDecision(
            "take_message",
            {
                "caller_name": str(args.get("caller_name") or "Unknown caller").strip(),
                "message": str(args.get("message") or "No message provided").strip(),
                "callback_number": str(args.get("callback_number") or "").strip(),
            },
            {"status": "message_saved", "say": "Thank you. I'll pass along your message. Goodbye."},
        )
    if tool_name == "decline":
        return PolicyDecision(
            "decline",
            {"reason": str(args.get("reason") or "Call declined").strip()},
            {"status": "declined", "say": "I can't help with this call. Goodbye."},
        )
    return PolicyDecision(
        "decline",
        {"reason": "Unsupported agent action"},
        {"status": "invalid_tool", "say": "I can't complete this call. Goodbye."},
    )
