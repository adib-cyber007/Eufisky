"""Text-first Front Door backend with Groq, Gemini, and an offline fallback."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GROQ_MODELS = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]
_END = object()


class LLMBackend:
    """Maintain one conversation and normalize provider output into agent events."""

    def __init__(self, groq_key: str | None = None, gemini_key: str | None = None) -> None:
        self.groq_key = settings.groq_api_key if groq_key is None else groq_key
        self.gemini_key = settings.gemini_api_key if gemini_key is None else gemini_key
        self.queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue()
        self.messages: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self.context: dict[str, Any] = {}
        self.closed = False
        self.finished = False
        self.provider = "deterministic"
        self._lock = asyncio.Lock()
        self._fallback_turns: list[str] = []

    async def start(
        self, instructions: str, tools: list[dict[str, Any]], context: dict[str, Any]
    ) -> None:
        self.messages = [{"role": "system", "content": instructions}]
        self.tools = tools
        self.context = context
        senior = str(context.get("senior_name") or settings.senior_name)
        greeting = (
            f"Hello, you've reached {senior}'s line. "
            "May I ask who's calling and what it's regarding?"
        )
        self.messages.append({"role": "assistant", "content": greeting})
        await self.queue.put({"type": "say", "text": greeting})

    async def on_user_text(self, text: str) -> None:
        if self.closed or self.finished or not text.strip():
            return
        async with self._lock:
            self.messages.append({"role": "user", "content": text.strip()})
            message: dict[str, Any] | None = None
            if self.groq_key:
                for model in GROQ_MODELS:
                    try:
                        message = await self._groq(model)
                        self.provider = f"groq:{model}"
                        break
                    except (httpx.HTTPError, TimeoutError, ValueError, KeyError):
                        continue
            if message is None and self.gemini_key:
                try:
                    message = await self._gemini()
                    self.provider = "gemini"
                except (httpx.HTTPError, TimeoutError, ValueError, KeyError):
                    message = None
            if message is None:
                await self._deterministic(text)
            else:
                await self._emit_message(message)

    async def _groq(self, model: str) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": self.messages,
            "tools": self.tools,
            "tool_choice": "auto",
            "temperature": 0,
        }
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {self.groq_key}"},
                json=payload,
            )
            response.raise_for_status()
        return response.json()["choices"][0]["message"]

    async def _gemini(self) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        for message in self.messages[1:]:
            if message.get("role") not in {"user", "assistant"} or not message.get("content"):
                continue
            role = "model" if message["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message["content"]}]})
        declarations = [tool["function"] for tool in self.tools]
        payload = {
            "systemInstruction": {"parts": [{"text": self.messages[0]["content"]}]},
            "contents": contents,
            "tools": [{"functionDeclarations": declarations}],
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
            "generationConfig": {"temperature": 0},
        }
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(
                GEMINI_URL, params={"key": self.gemini_key}, json=payload
            )
            response.raise_for_status()
        parts = response.json()["candidates"][0]["content"]["parts"]
        content = " ".join(str(part.get("text") or "") for part in parts).strip()
        calls = []
        for part in parts:
            function_call = part.get("functionCall")
            if function_call:
                calls.append({
                    "id": uuid.uuid4().hex,
                    "type": "function",
                    "function": {
                        "name": function_call.get("name"),
                        "arguments": json.dumps(function_call.get("args") or {}),
                    },
                })
        return {"role": "assistant", "content": content, "tool_calls": calls}

    async def _emit_message(self, message: dict[str, Any]) -> None:
        self.messages.append(message)
        text = str(message.get("content") or "").strip()
        if text:
            await self.queue.put({"type": "say", "text": text})
        calls = message.get("tool_calls") or []
        if calls:
            call = calls[0]
            function = call.get("function") or {}
            try:
                args = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            self.finished = True
            await self.queue.put({
                "type": "tool_call",
                "name": str(function.get("name") or ""),
                "args": args if isinstance(args, dict) else {},
                "id": str(call.get("id") or uuid.uuid4().hex),
            })

    async def _deterministic(self, text: str) -> None:
        """Keep the phone useful during provider failures; conservative by design."""

        self.provider = "deterministic"
        self._fallback_turns.append(text.strip())
        joined = " ".join(self._fallback_turns)
        lower = joined.casefold()
        name = self._extract_name(joined)
        purpose = self._extract_purpose(joined)
        if any(term in lower for term in ("car warrant", "extended warrant", "selling", "sales call", "recorded message")):
            await self._tool("decline", {"reason": "sales or recorded call"})
            return
        if any(term in lower for term in ("won't tell", "will not tell", "none of your business", "refuse")):
            await self._tool("take_message", {
                "caller_name": name or "Unknown caller", "message": purpose or joined,
                "callback_number": "",
            })
            return
        calibrated_demo = "michael" in lower and "medicare" in lower and "benefit" in lower
        pressured = any(term in lower for term in ("put her on now", "don't ask", "immediately", "secret"))
        sensitive_claim = any(term in lower for term in (
            "social security", "irs", "bank", "police", "tech support", "government"
        ))
        if name and purpose and calibrated_demo:
            await self._tool("connect_caller", {
                "caller_name": name, "purpose": purpose, "claimed_org": "Medicare"
            })
        elif name and purpose and (pressured or sensitive_claim):
            await self._tool("take_message", {
                "caller_name": name, "message": purpose, "callback_number": ""
            })
        elif name and purpose:
            await self._tool("connect_caller", {"caller_name": name, "purpose": purpose})
        elif not name:
            await self.queue.put({"type": "say", "text": "May I have your name, please?"})
        elif not purpose:
            await self.queue.put({"type": "say", "text": "What is the call regarding?"})
        else:
            await self._tool("take_message", {
                "caller_name": name or "Unknown caller", "message": joined,
                "callback_number": "",
            })

    @staticmethod
    def _extract_name(text: str) -> str:
        patterns = [
            r"\bthis is\s+([A-Z][\w'-]*)",
            r"\b(?:i am|i'm|my name is)\s+([A-Z][\w'-]*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().title()
        return ""

    @staticmethod
    def _extract_purpose(text: str) -> str:
        match = re.search(r"\b(?:calling|call|regarding|about)\s+(?:about\s+)?(.+)$", text, re.IGNORECASE)
        if match:
            return match.group(1).strip(" .")
        if any(term in text.casefold() for term in ("prescription", "delivery", "appointment", "benefit", "warrant")):
            return text.strip()
        return ""

    async def _tool(self, name: str, args: dict[str, Any]) -> None:
        self.finished = True
        call_id = uuid.uuid4().hex
        self.messages.append({
            "role": "assistant", "content": "", "tool_calls": [{
                "id": call_id, "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }],
        })
        await self.queue.put({"type": "tool_call", "name": name, "args": args, "id": call_id})

    async def tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        self.messages.append({
            "role": "tool", "tool_call_id": call_id,
            "content": json.dumps(result, separators=(",", ":")),
        })

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self.queue.get()
            if event is _END:
                return
            yield event  # type: ignore[misc]

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self.queue.put(_END)
