"""Server policy tests independent of any model provider."""

from app.agent.policies import decide


def test_connect_below_40_is_allowed() -> None:
    result = decide("connect_caller", {"caller_name": "Pat", "purpose": "delivery"}, 39)
    assert result.action == "connect_caller"
    assert result.result["status"] == "connecting"


def test_connect_at_40_is_converted_to_message() -> None:
    result = decide("connect_caller", {"caller_name": "Pat", "purpose": "urgent account"}, 40)
    assert result.action == "take_message"
    assert result.result == {
        "status": "policy_override", "say": "I'll pass along a message instead."
    }


def test_always_ring_first_skips_only_score_override() -> None:
    result = decide(
        "connect_caller",
        {"caller_name": "Pat", "purpose": "urgent account"},
        90,
        always_ring_first=True,
    )
    assert result.action == "connect_caller"
    assert result.result["status"] == "connecting"


def test_message_and_decline_are_normalized() -> None:
    message = decide("take_message", {"caller_name": "", "message": "Call me"}, 0)
    declined = decide("decline", {"reason": "sales"}, 0)
    assert message.args["caller_name"] == "Unknown caller"
    assert message.result["status"] == "message_saved"
    assert declined.action == "decline"
