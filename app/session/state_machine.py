"""Session ladder with Phase 2 L1 behavior and dry-run L2/L3 signals."""

from __future__ import annotations

from enum import Enum
import logging
from typing import Awaitable, Callable

from app.rules.engine import RiskUpdate
from app.session.events import EventPublisher

LOGGER = logging.getLogger(__name__)


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


class CallStateMachine:
    def __init__(
        self,
        publisher: EventPublisher,
        send_senior: Callable[[dict], Awaitable[bool]],
    ) -> None:
        self.publisher = publisher
        self.send_senior = send_senior
        self.state = SessionState.BRIDGED
        self.nudged = False
        self.levels_published: set[int] = set()

    async def on_risk(self, update: RiskUpdate) -> None:
        if update.score >= 40 and not self.nudged:
            self.nudged = True
            self.levels_published.add(1)
            await self.publisher.level(update.t_ms, 1, "score_gte_40")
            await self.send_senior({"type": "tone", "name": "chime"})
            await self.send_senior({
                "type": "agent_say",
                "text": "Eufisky is listening.",
                "agent": "guardian",
            })

        trigger_l2 = "trigger_l2" in update.flags
        if trigger_l2 and 2 not in self.levels_published:
            self.levels_published.add(2)
            trigger = (
                "pii_disclosure"
                if "pii_disclosure" in update.flags and update.score < 65
                else "payment_compliance"
                if "payment_compliance" in update.flags and update.score < 65
                else "score_gte_65"
            )
            await self.publisher.level(update.t_ms, 2, trigger)
            LOGGER.warning(
                "L2 would fire call_id=%s score=%s trigger=%s",
                self.publisher.call_id,
                update.score,
                trigger,
            )

        if update.score >= 90 and 3 not in self.levels_published:
            self.levels_published.add(3)
            await self.publisher.level(update.t_ms, 3, "score_gte_90")
            LOGGER.warning(
                "L3 would fire call_id=%s score=%s",
                self.publisher.call_id,
                update.score,
            )
