"""Voice Agent startup always reaches its fallback by the deadline."""

import asyncio
from types import SimpleNamespace

import pytest

import app.agent.voice_agent_backend as voice_module
from app.agent.voice_agent_backend import VoiceAgentBackend


class Fallback:
    provider = "test-fallback"

    def __init__(self) -> None:
        self.started = False
        self.closed = False

    async def start(self, instructions, tools, context): self.started = True
    async def on_user_text(self, text): pass
    async def tool_result(self, call_id, result): pass
    async def close(self): self.closed = True
    async def events(self):
        while not self.closed:
            await asyncio.sleep(1)
            if False:
                yield {}


@pytest.mark.asyncio
async def test_hanging_connection_falls_back_at_deadline(monkeypatch) -> None:
    async def hanging_connect(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(voice_module, "connect", hanging_connect)
    monkeypatch.setattr(voice_module, "START_TIMEOUT", 0.01)
    monkeypatch.setattr(voice_module, "settings", SimpleNamespace(assemblyai_api_key="configured"))
    fallback = Fallback()
    backend = VoiceAgentBackend(fallback=fallback)  # type: ignore[arg-type]
    started = asyncio.get_running_loop().time()
    await backend.start("prompt", [], {})
    assert asyncio.get_running_loop().time() - started < 0.1
    assert backend.using_fallback and fallback.started
    await backend.close()
