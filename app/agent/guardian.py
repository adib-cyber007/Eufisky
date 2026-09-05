"""Private Guardian conversation for a paused risky call."""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any, Awaitable, Callable

from app.agent.backend import AgentBackend
from app.agent.personas.guardian import TOOLS, instructions


class GuardianSession:
    def __init__(self, call: Any, backend: AgentBackend, context: dict[str, str], on_tool: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self.call, self.backend, self.context, self.on_tool = call, backend, context, on_tool
        self.task: asyncio.Task[Any] | None = None
        self.closed = False
        self.tool_called = False
        self.fallback = False

    @property
    def greeting(self) -> str:
        extra = f" I recommend bringing {self.context['family_name']} in." if self.context["recommendation"] == "bring in family" else ""
        return f"I paused the call because this person {self.context['trigger_plain']}.{extra} Would you like me to end the call, or bring {self.context['family_name']} on the line?"

    async def start(self) -> None:
        try:
            if os.getenv("SIMULATE_AGENT_FAIL", "").strip() == "1":
                raise RuntimeError("simulated Guardian backend failure")
            await asyncio.wait_for(self.backend.start(instructions(self.context), TOOLS, {**self.context, "agent_role": "guardian", "greeting": self.greeting}), timeout=3.0)
            self.task = asyncio.create_task(self._consume(), name=f"guardian-{self.call.id}")
        except Exception:
            self.fallback = True
            with contextlib.suppress(Exception):
                await self.backend.close()
            await self.call.room.send_phone("senior", {"type": "agent_say", "text": self.greeting, "agent": "guardian"})
        await self.call.room.send_phone("senior", {"type": "guardian_controls", "visible": True, "family_name": self.context["family_name"], "fallback": self.fallback})

    async def _consume(self) -> None:
        try:
            async for event in self.backend.events():
                if self.closed:
                    return
                kind = event.get("type")
                if kind == "say":
                    await self.call.room.send_phone("senior", {"type": "agent_say", "text": str(event.get("text") or ""), "agent": "guardian"})
                elif kind == "caption":
                    await self.call.room.send_phone("senior", {"type": "agent_caption", "text": str(event.get("text") or ""), "agent": "guardian"})
                elif kind == "audio":
                    await self.call.room.send_audio("senior", bytes(event.get("data") or b""))
                elif kind == "tool_call" and not self.tool_called:
                    self.tool_called = True
                    await self.on_tool(event)
                    return
        except asyncio.CancelledError:
            raise

    async def on_text(self, text: str) -> None:
        if self.closed or self.tool_called:
            return
        lower = text.casefold()
        direct: tuple[str, dict[str, Any]] | None = None
        if any(term in lower for term in ("get sarah", "bring sarah", "call sarah", "family")):
            direct = ("conference_family", {"keep_caller_on_hold": True})
        elif any(term in lower for term in ("continue", "resume", "keep talking", "go back")):
            direct = ("resume_call", {})
        elif any(term in lower for term in ("end the call", "hang up", "block them", "stop the call")):
            direct = ("end_call", {"block_number": True})
        elif "trust" in lower or "i know" in lower:
            direct = ("add_to_trusted", {"label": self.call.caller_name or "Known caller"})
        if direct:
            self.tool_called = True
            await self.on_tool({"type": "tool_call", "name": direct[0], "args": direct[1], "id": "guardian-direct"})
        elif self.fallback:
            await self.call.room.send_phone("senior", {"type": "agent_say", "text": "Please choose one of the buttons below, or press 1, 2, or 3.", "agent": "guardian"})
        else:
            await self.backend.on_user_text(text)

    async def on_audio(self, pcm: bytes) -> None:
        method = getattr(self.backend, "on_audio", None)
        if not self.closed and not self.fallback and method is not None:
            await method(pcm)

    async def tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        if not self.fallback:
            await self.backend.tool_result(call_id, result)

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self.backend.close()
        if self.task and self.task is not asyncio.current_task() and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
