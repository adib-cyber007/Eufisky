"""Voice-agent backends and backend selection."""

from __future__ import annotations

from app.agent.llm_backend import LLMBackend
from app.agent.voice_agent_backend import VoiceAgentBackend
from app.config import settings


def make_backend():
    """Auto uses Voice Agent because the recorded account probe passed."""

    selected = settings.agent_backend.strip().casefold()
    if selected in {"auto", "voice_agent"}:
        return VoiceAgentBackend()
    return LLMBackend()


__all__ = ["make_backend", "LLMBackend", "VoiceAgentBackend"]
