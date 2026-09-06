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


class DecisionOnlyBackup:
    provider = "decision-test"

    def __init__(self, *args, **kwargs) -> None:
        self.messages = []

    async def start(self, instructions, tools, context) -> None: pass
    async def on_user_text(self, text) -> None: pass
    async def close(self) -> None: pass

    async def events(self):
        yield {"type": "say", "text": "duplicate greeting"}
        yield {"type": "say", "text": "late backup voice"}
        yield {"type": "tool_call", "name": "connect_caller", "args": {}, "id": "tool"}


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


@pytest.mark.asyncio
async def test_voice_watchdog_never_mixes_backup_speech_with_voice_pcm(monkeypatch) -> None:
    monkeypatch.setattr(voice_module, "WATCHDOG_DELAY", 0)
    monkeypatch.setattr(voice_module, "LLMBackend", DecisionOnlyBackup)
    backend = VoiceAgentBackend(fallback=Fallback())  # type: ignore[arg-type]
    backend._instructions = "prompt"
    await backend._text_turn_watchdog("caller text", 0)

    queued = []
    while not backend.queue.empty():
        queued.append(backend.queue.get_nowait())
    assert [event["type"] for event in queued] == ["tool_call"]
