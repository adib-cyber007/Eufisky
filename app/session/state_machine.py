"""Deterministic safety ladder for one monitored call."""

from __future__ import annotations

from enum import Enum
from typing import Any, Awaitable, Callable

from app.rules.engine import RiskUpdate
from app.session.events import EventPublisher


class SessionState(str, Enum):
    IDLE = "IDLE"
    SCREENING = "SCREENING"
    DIALING_SENIOR = "DIALING_SENIOR"
    INTRO = "INTRO"
    BRIDGED = "BRIDGED"
    GUARDIAN = "GUARDIAN"
    FAMILY_CONF = "FAMILY_CONF"
    WRAPUP = "WRAPUP"
    POST_CALL = "POST_CALL"
    DONE = "DONE"


TransitionCallback = Callable[[SessionState, str, RiskUpdate | None], Awaitable[None]]
ActionCallback = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
RecommendationCallback = Callable[[str], Awaitable[None]]


class CallStateMachine:
    """Own transitions; model output is inert unless it is an explicit tool event."""

    def __init__(
        self,
        publisher: EventPublisher,
        send_senior: Callable[[dict], Awaitable[bool]],
        on_transition: TransitionCallback | None = None,
        on_action: ActionCallback | None = None,
        on_recommendation: RecommendationCallback | None = None,
    ) -> None:
        self.publisher = publisher
        self.send_senior = send_senior
        self.on_transition = on_transition
        self.on_action = on_action
        self.on_recommendation = on_recommendation
        self.state = SessionState.BRIDGED
        self.nudged = False
        self.levels_published: set[int] = set()
        self.l2_threshold = 65
        self.cooldown_until_ms = 0
        self.recommendation = ""

    @staticmethod
    def should_trigger_l2(update: RiskUpdate, threshold: int = 65) -> bool:
        active = set(update.active_signals)
        return (
            update.score >= threshold
            or ("pii_disclosure" in active and update.score >= 45)
            or {"payment_method", "compliance_cue"}.issubset(active)
        )

    async def _transition(
        self, target: SessionState, trigger: str, update: RiskUpdate | None = None,
        t_ms: int = 0,
    ) -> None:
        previous = self.state
        self.state = target
        t_ms = update.t_ms if update is not None else t_ms
        await self.publisher.state(t_ms, previous.value, target.value, trigger)
        if self.on_transition is not None:
            await self.on_transition(target, trigger, update)

    async def on_risk(self, update: RiskUpdate) -> None:
        if update.score >= 40 and not self.nudged:
            self.nudged = True
            self.levels_published.add(1)
            await self.publisher.level(update.t_ms, 1, "score_gte_40")
            await self.send_senior({"type": "tone", "name": "chime"})
            await self.send_senior({
                "type": "agent_say", "text": "Eufisky is listening.", "agent": "guardian"
            })

        if update.score >= 90 and 3 not in self.levels_published:
            self.levels_published.add(3)
            self.recommendation = "bring in family"
            await self.publisher.level(update.t_ms, 3, "score_gte_90")
            if self.state in {SessionState.GUARDIAN, SessionState.FAMILY_CONF} and self.on_recommendation:
                await self.on_recommendation(self.recommendation)

        if (
            self.state == SessionState.BRIDGED
            and update.t_ms >= self.cooldown_until_ms
            and self.should_trigger_l2(update, self.l2_threshold)
        ):
            active = set(update.active_signals)
            trigger = (
                "pii_disclosure" if "pii_disclosure" in active and update.score < self.l2_threshold
                else "payment_compliance" if {"payment_method", "compliance_cue"}.issubset(active) and update.score < self.l2_threshold
                else f"score_gte_{self.l2_threshold}"
            )
            self.levels_published.add(2)
            await self.publisher.level(update.t_ms, 2, trigger)
            await self._transition(SessionState.GUARDIAN, trigger, update)

    async def on_agent_event(self, event: dict[str, Any], t_ms: int = 0) -> dict[str, Any] | None:
        """Speech/captions never transition state; registered tool calls may."""
        if event.get("type") != "tool_call":
            return None
        return await self.on_tool(
            str(event.get("name") or ""),
            event.get("args") if isinstance(event.get("args"), dict) else {},
            t_ms,
        )

    async def on_tool(self, name: str, args: dict[str, Any], t_ms: int) -> dict[str, Any]:
        allowed = {"resume_call", "conference_family", "end_call", "add_to_trusted"}
        if name not in allowed or self.state not in {SessionState.GUARDIAN, SessionState.FAMILY_CONF}:
            return {"ok": False, "reason": "tool is not valid in this state"}
        await self.publisher.tool(t_ms, "guardian", name, args)
        result = await self.on_action(name, args) if self.on_action else {"ok": True}
        if not result.get("ok", False):
            return result
        if name in {"resume_call", "add_to_trusted"}:
            self.cooldown_until_ms = t_ms + 60_000
            self.l2_threshold = min(85, self.l2_threshold + 10)
            await self._transition(SessionState.BRIDGED, name, t_ms=t_ms)
        elif name == "conference_family":
            await self._transition(SessionState.FAMILY_CONF, name, t_ms=t_ms)
        elif name == "end_call":
            await self._transition(SessionState.WRAPUP, name, t_ms=t_ms)
        return result

    async def on_hangup(self, t_ms: int = 0) -> None:
        if self.state not in {SessionState.WRAPUP, SessionState.DONE}:
            previous = self.state
            self.state = SessionState.WRAPUP
            await self.publisher.state(t_ms, previous.value, SessionState.WRAPUP.value, "hangup")
