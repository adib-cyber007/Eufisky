"""AssemblyAI Voice Agent adapter with a transparent LLM fallback."""

from __future__ import annotations

import asyncio
import audioop
import base64
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from websockets.asyncio.client import connect

from app.agent.llm_backend import LLMBackend
from app.config import settings

URL = "wss://agents.assemblyai.com/v1/ws"
_END = object()


class VoiceAgentBackend:
    """Expose the Voice Agent socket through the same events as the text backend."""

    def __init__(self, fallback: LLMBackend | None = None) -> None:
        self.fallback = fallback or LLMBackend()
        self.socket: Any = None
        self.queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue()
        self.reader: asyncio.Task[None] | None = None
        self.ready = asyncio.Event()
        self.using_fallback = False
        self.closed = False
        self._input_state: Any = None
        self._output_state: Any = None
        self._instructions = ""
        self._tools: list[dict[str, Any]] = []
        self._context: dict[str, Any] = {}
        self._pending_results: list[tuple[str, dict[str, Any]]] = []
        self._tool_count = 0
        self._watchdogs: list[asyncio.Task[None]] = []
        self._text_history: list[str] = []
        self._fallback_pump: asyncio.Task[None] | None = None

    @property
    def provider(self) -> str:
        return self.fallback.provider if self.using_fallback else "voice_agent"

    async def start(
        self, instructions: str, tools: list[dict[str, Any]], context: dict[str, Any]
    ) -> None:
        self._instructions, self._tools, self._context = instructions, tools, context
        if not settings.assemblyai_api_key:
            await self._start_fallback()
            return
        try:
            self.socket = await asyncio.wait_for(
                connect(
                    URL,
                    additional_headers={"Authorization": f"Bearer {settings.assemblyai_api_key}"},
                    open_timeout=3,
                ),
                timeout=3,
            )
            self.reader = asyncio.create_task(self._read(), name="frontdoor-voice-agent")
            voice_tools = [
                {"type": "function", **tool["function"]} for tool in tools
            ]
            await self.socket.send(json.dumps({
                "type": "session.update",
                "session": {
                    "system_prompt": instructions,
                    "greeting": (
                        f"Hello, you've reached {context.get('senior_name', settings.senior_name)}'s line. "
                        "May I ask who's calling and what it's regarding?"
                    ),
                    "input": {
                        "format": {"encoding": "audio/pcm"},
                        "keyterms": context.get("keyterms", []),
                        "turn_detection": {"min_silence": 500, "max_silence": 1500},
                    },
                    "output": {"voice": "alba", "format": {"encoding": "audio/pcm"}},
                    "tools": voice_tools,
                },
            }))
            await asyncio.wait_for(self.ready.wait(), timeout=3)
        except Exception:
            await self._stop_socket()
            await self._start_fallback()

    async def _start_fallback(self) -> None:
        self.using_fallback = True
        await self.fallback.start(self._instructions, self._tools, self._context)
        self._fallback_pump = asyncio.create_task(
            self._pump_fallback(), name="voice-agent-fallback-pump"
        )

    async def _pump_fallback(self) -> None:
        async for event in self.fallback.events():
            await self.queue.put(event)

    async def _read(self) -> None:
        try:
            async for raw in self.socket:
                event = json.loads(raw)
                event_type = str(event.get("type") or "")
                if event_type == "session.ready":
                    self.ready.set()
                elif event_type == "reply.audio":
                    pcm24 = base64.b64decode(event.get("data") or "")
                    pcm16, self._output_state = audioop.ratecv(
                        pcm24, 2, 1, 24000, 16000, self._output_state
                    )
                    if pcm16:
                        await self.queue.put({"type": "audio", "data": pcm16})
                elif event_type.startswith("transcript.agent"):
                    text = str(event.get("text") or event.get("transcript") or "").strip()
                    if text and (event.get("final", True) or event_type.endswith("final")):
                        await self.queue.put({"type": "caption", "text": text})
                elif event_type == "tool.call":
                    self._tool_count += 1
                    args = event.get("arguments") or event.get("args") or {}
                    if isinstance(args, str):
                        with suppress(json.JSONDecodeError):
                            args = json.loads(args)
                    await self.queue.put({
                        "type": "tool_call",
                        "name": str(event.get("name") or ""),
                        "args": args if isinstance(args, dict) else {},
                        "id": str(event.get("call_id") or event.get("id") or ""),
                    })
                elif event_type == "reply.done" and self._pending_results:
                    pending = self._pending_results[:]
                    self._pending_results.clear()
                    for call_id, result in pending:
                        await self.socket.send(json.dumps({
                            "type": "tool.result", "call_id": call_id,
                            "result": json.dumps(result, separators=(",", ":")),
                        }))
                elif event_type == "session.error":
                    raise RuntimeError(str(event.get("message") or event.get("error") or event))
        except asyncio.CancelledError:
            raise
        except Exception:
            if not self.closed and not self.ready.is_set():
                self.ready.set()

    async def on_user_text(self, text: str) -> None:
        if self.using_fallback:
            await self.fallback.on_user_text(text)
            return
        await self.socket.send(json.dumps({
            "type": "conversation.message", "role": "user", "content": text
        }))
        self._text_history.append(text)
        await self.socket.send(json.dumps({
            "type": "reply.create",
            "instructions": (
                "Follow the Front Door rules now. If the caller supplied both a name and a "
                "reason, call exactly one registered tool rather than merely paraphrasing them."
            ),
        }))
        expected_count = self._tool_count
        self._watchdogs.append(asyncio.create_task(
            self._text_turn_watchdog(" ".join(self._text_history), expected_count),
            name="voice-agent-text-watchdog"
        ))

    async def _text_turn_watchdog(self, text: str, expected_count: int) -> None:
        """Resolve a text turn through the LLM chain if Voice Agent does not choose a tool."""

        try:
            await asyncio.sleep(5)
            if self.closed or self._tool_count != expected_count:
                return
            backup = LLMBackend()
            await backup.start(self._instructions, self._tools, self._context)
            events = backup.events()
            # Drop the duplicate greeting; the Voice Agent already delivered it.
            with suppress(StopAsyncIteration):
                await anext(events)
            backup.messages.append({
                "role": "assistant",
                "content": "I already asked one clarifying question. I must now call exactly one tool.",
            })
            await backup.on_user_text(text)
            chose_tool = False
            for _ in range(2):
                try:
                    event = await asyncio.wait_for(anext(events), timeout=0.2)
                except (StopAsyncIteration, asyncio.TimeoutError):
                    break
                await self.queue.put(event)
                if event.get("type") == "tool_call":
                    self._tool_count += 1
                    chose_tool = True
                    break
            await backup.close()
            if not chose_tool and not self.closed:
                terminal = LLMBackend(groq_key="", gemini_key="")
                await terminal.start(self._instructions, self._tools, self._context)
                terminal_events = terminal.events()
                await anext(terminal_events)  # duplicate greeting
                await terminal.on_user_text(text)
                async for event in terminal_events:
                    await self.queue.put(event)
                    if event.get("type") == "tool_call":
                        self._tool_count += 1
                        break
                await terminal.close()
        except (asyncio.CancelledError, TimeoutError):
            if self.closed:
                return
            raise
        except Exception:
            # LLMBackend itself has a deterministic terminal fallback, so this
            # is only a final guard against lifecycle cancellation.
            return

    async def on_audio(self, pcm16: bytes) -> None:
        if self.using_fallback or not self.socket or not pcm16:
            return
        pcm24, self._input_state = audioop.ratecv(
            pcm16, 2, 1, 16000, 24000, self._input_state
        )
        await self.socket.send(json.dumps({
            "type": "input.audio", "audio": base64.b64encode(pcm24).decode("ascii")
        }))

    async def tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        if self.using_fallback:
            await self.fallback.tool_result(call_id, result)
            return
        self._pending_results.append((call_id, result))

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        async for event in self._events():
            yield event

    async def _events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self.queue.get()
            if event is _END:
                return
            yield event  # type: ignore[misc]

    async def _stop_socket(self) -> None:
        if self.reader and not self.reader.done():
            self.reader.cancel()
            with suppress(asyncio.CancelledError):
                await self.reader
        if self.socket:
            with suppress(Exception):
                await self.socket.close()
        self.reader = None
        self.socket = None

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for task in self._watchdogs:
            if not task.done():
                task.cancel()
        if self.using_fallback:
            await self.fallback.close()
            if self._fallback_pump:
                with suppress(asyncio.CancelledError):
                    await self._fallback_pump
            await self.queue.put(_END)
            return
        if self.socket:
            with suppress(Exception):
                await self.socket.send(json.dumps({"type": "session.end"}))
        await self._stop_socket()
        await self.queue.put(_END)
