"""Backend-neutral events and protocol for the Front Door agent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, TypedDict


class SayEvent(TypedDict):
    type: str
    text: str


class ToolCallEvent(TypedDict):
    type: str
    name: str
    args: dict[str, Any]
    id: str


AgentEvent = SayEvent | ToolCallEvent | dict[str, Any]


class AgentBackend(Protocol):
    async def start(
        self, instructions: str, tools: list[dict[str, Any]], context: dict[str, Any]
    ) -> None: ...

    async def on_user_text(self, text: str) -> None: ...

    def events(self) -> AsyncIterator[AgentEvent]: ...

    async def tool_result(self, call_id: str, result: dict[str, Any]) -> None: ...

    async def close(self) -> None: ...
