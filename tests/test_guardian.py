"""Private Guardian output routing."""

import asyncio
from types import SimpleNamespace

import pytest

from app.agent.guardian import GuardianSession


class Room:
    def __init__(self) -> None:
        self.json = {"caller": [], "senior": [], "family": []}
        self.audio = {"caller": [], "senior": [], "family": []}

    async def send_phone(self, role, payload): self.json[role].append(payload); return True
    async def send_audio(self, role, payload): self.audio[role].append(payload); return True


class OutputBackend:
    def __init__(self) -> None:
        self.queue = asyncio.Queue()
        self.closed = False

    async def start(self, instructions, tools, context):
        await self.queue.put({"type": "say", "text": "Private guidance"})
        await self.queue.put({"type": "audio", "data": b"private-audio"})

    async def events(self):
        while True: yield await self.queue.get()

    async def on_user_text(self, text): pass
    async def tool_result(self, call_id, result): pass
    async def close(self): self.closed = True


@pytest.mark.asyncio
async def test_guardian_speech_and_audio_are_senior_only() -> None:
    room = Room()
    call = SimpleNamespace(id="private", room=room, caller_name="Michael")
    context = {
        "senior_name": "Margaret", "family_name": "Sarah", "caller_name": "Michael",
        "claim": "Medicare", "trigger_plain": "asked for your card number",
        "requests": "personal numbers", "disclosed": "none", "family_role": "daughter",
        "recommendation": "bring in family",
    }
    session = GuardianSession(call, OutputBackend(), context, lambda event: None)
    await session.start()
    await asyncio.sleep(0.01)
    assert any(item.get("text") == "Private guidance" for item in room.json["senior"])
    assert room.audio["senior"] == [b"private-audio"]
    assert room.json["caller"] == [] and room.audio["caller"] == []
    await session.close()
