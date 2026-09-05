"""Phase 2 escalation behavior: L1 acts once; L2/L3 only announce."""

import pytest

from app.rules.engine import RiskUpdate
from app.session.state_machine import CallStateMachine


class FakePublisher:
    call_id = "call-test"

    def __init__(self) -> None:
        self.levels: list[tuple[int, int, str]] = []

    async def level(self, t_ms: int, level: int, trigger: str) -> None:
        self.levels.append((t_ms, level, trigger))


@pytest.mark.asyncio
async def test_l1_chime_once_and_l2_l3_are_dry_run() -> None:
    publisher = FakePublisher()
    sent: list[dict] = []

    async def send(payload: dict) -> bool:
        sent.append(payload)
        return True

    machine = CallStateMachine(publisher, send)  # type: ignore[arg-type]
    await machine.on_risk(RiskUpdate(1000, 45, ["urgency"], [], []))
    await machine.on_risk(RiskUpdate(1500, 70, ["pii_request"], [], ["trigger_l2"]))
    await machine.on_risk(
        RiskUpdate(2000, 95, ["payment_method"], [], ["trigger_l2", "trigger_l3"])
    )

    assert [level for _, level, _ in publisher.levels] == [1, 2, 3]
    assert sent == [
        {"type": "tone", "name": "chime"},
        {"type": "agent_say", "text": "Eufisky is listening.", "agent": "guardian"},
    ]
