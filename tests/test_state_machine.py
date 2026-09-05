"""Phase 4 deterministic Guardian state transitions."""

import pytest

from app.rules.engine import RiskUpdate
from app.session.state_machine import CallStateMachine, SessionState


class FakePublisher:
    call_id = "call-test"

    def __init__(self) -> None:
        self.levels = []
        self.states = []
        self.tools = []

    async def level(self, t_ms, level, trigger): self.levels.append((t_ms, level, trigger))
    async def state(self, t_ms, previous, target, trigger): self.states.append((previous, target, trigger))
    async def tool(self, t_ms, agent, name, args): self.tools.append((t_ms, agent, name, args))


def update(score, active=(), t_ms=1000):
    return RiskUpdate(t_ms, score, list(active), [], [])


def test_l2_formula_is_deterministic() -> None:
    assert CallStateMachine.should_trigger_l2(update(65))
    assert CallStateMachine.should_trigger_l2(update(45, ["pii_disclosure"]))
    assert CallStateMachine.should_trigger_l2(update(20, ["payment_method", "compliance_cue"]))
    assert not CallStateMachine.should_trigger_l2(update(64, ["pii_request"]))
    assert not CallStateMachine.should_trigger_l2(update(44, ["pii_disclosure"]))


@pytest.mark.asyncio
async def test_every_guardian_transition_and_l3_recommendation() -> None:
    publisher = FakePublisher()
    actions = []
    recommendations = []
    async def send(_): return True
    async def action(name, args): actions.append((name, args)); return {"ok": True}
    async def recommend(value): recommendations.append(value)
    machine = CallStateMachine(publisher, send, on_action=action, on_recommendation=recommend)

    await machine.on_risk(update(65, t_ms=1000))
    assert machine.state == SessionState.GUARDIAN
    await machine.on_risk(update(92, t_ms=1100))
    assert machine.recommendation == "bring in family"
    assert recommendations == ["bring in family"]
    await machine.on_tool("conference_family", {"keep_caller_on_hold": True}, 1200)
    assert machine.state == SessionState.FAMILY_CONF
    await machine.on_tool("resume_call", {}, 1300)
    assert machine.state == SessionState.BRIDGED
    assert machine.cooldown_until_ms == 61_300 and machine.l2_threshold == 75

    machine.state = SessionState.GUARDIAN
    await machine.on_tool("add_to_trusted", {"label": "Pat"}, 2000)
    assert machine.state == SessionState.BRIDGED and machine.l2_threshold == 85
    machine.state = SessionState.GUARDIAN
    await machine.on_tool("end_call", {}, 3000)
    assert machine.state == SessionState.WRAPUP
    assert [name for name, _ in actions] == ["conference_family", "resume_call", "add_to_trusted", "end_call"]


@pytest.mark.asyncio
async def test_cooldown_and_escalated_threshold() -> None:
    publisher = FakePublisher()
    async def send(_): return True
    machine = CallStateMachine(publisher, send)
    await machine.on_risk(update(65, t_ms=1000))
    await machine.on_tool("resume_call", {}, 2000)
    await machine.on_risk(update(100, t_ms=61_999))
    assert machine.state == SessionState.BRIDGED
    await machine.on_risk(update(74, t_ms=62_001))
    assert machine.state == SessionState.BRIDGED
    await machine.on_risk(update(75, t_ms=62_002))
    assert machine.state == SessionState.GUARDIAN


@pytest.mark.asyncio
async def test_speech_cannot_transition_but_tool_event_can() -> None:
    publisher = FakePublisher()
    async def send(_): return True
    machine = CallStateMachine(publisher, send)
    await machine.on_agent_event({"type": "say", "text": "Put the caller on hold"})
    assert machine.state == SessionState.BRIDGED
    await machine.on_risk(update(70))
    await machine.on_agent_event({"type": "caption", "text": "resume_call"}, 1100)
    assert machine.state == SessionState.GUARDIAN
    await machine.on_agent_event({"type": "tool_call", "name": "resume_call", "args": {}}, 1200)
    assert machine.state == SessionState.BRIDGED


@pytest.mark.asyncio
async def test_any_hangup_goes_to_wrapup() -> None:
    async def send(_): return True
    for state in (SessionState.BRIDGED, SessionState.GUARDIAN, SessionState.FAMILY_CONF):
        machine = CallStateMachine(FakePublisher(), send)
        machine.state = state
        await machine.on_hangup(100)
        assert machine.state == SessionState.WRAPUP
