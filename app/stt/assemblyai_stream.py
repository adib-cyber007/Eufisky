"""AssemblyAI Universal Streaming adapter for one call leg."""

from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from dataclasses import dataclass
import json
import logging
from typing import AsyncIterator
from urllib.parse import urlencode

from websockets.asyncio.client import connect

from app.config import settings

LOGGER = logging.getLogger(__name__)
BASE_URL = "wss://streaming.assemblyai.com/v3/ws"
MODEL = "universal-3-5-pro"
KEYTERM_LIMIT = 100
_END = object()


@dataclass(frozen=True, slots=True)
class WordEvent:
    speaker: str
    text: str
    t_ms: int
    final: bool


@dataclass(frozen=True, slots=True)
class TurnEndEvent:
    speaker: str
    t_ms: int
    text: str = ""
    type: str = "turn_end"


class STTStream:
    """Stream one PCM16 leg and expose word-level events.

    A dropped socket is reconnected once. The last two seconds of 100 ms audio
    frames are replayed so words around the disconnect are not lost.
    """

    def __init__(self, speaker: str, keyterms: list[str], sample_rate: int = 16000) -> None:
        self.speaker = speaker
        self.keyterms = [term for term in keyterms[:KEYTERM_LIMIT] if term]
        self.sample_rate = sample_rate
        self._audio: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._events: asyncio.Queue[WordEvent | TurnEndEvent | object] = asyncio.Queue()
        self._replay: deque[bytes] = deque(maxlen=20)
        self._runner: asyncio.Task[None] | None = None
        self._closed = False
        self._word_counts: dict[int, int] = {}
        self.reconnects = 0

    @property
    def url(self) -> str:
        params = {
            "sample_rate": str(self.sample_rate),
            "speech_model": MODEL,
            "format_turns": "true",
            "keyterms_prompt": json.dumps(self.keyterms),
        }
        return f"{BASE_URL}?{urlencode(params)}"

    async def start(self) -> None:
        if self._runner is not None:
            return
        if not settings.assemblyai_api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY is not configured")
        self._runner = asyncio.create_task(self._run(), name=f"stt-{self.speaker}")
        await asyncio.sleep(0)

    async def send_audio(self, pcm: bytes) -> None:
        if self._closed or not pcm:
            return
        if self._runner is None:
            await self.start()
        frame = bytes(pcm)
        self._replay.append(frame)
        await self._audio.put(frame)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._audio.put(None)
        if self._runner:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(self._runner, timeout=5)
        else:
            await self._events.put(_END)

    def __aiter__(self) -> AsyncIterator[WordEvent | TurnEndEvent]:
        return self

    async def __anext__(self) -> WordEvent | TurnEndEvent:
        event = await self._events.get()
        if event is _END:
            raise StopAsyncIteration
        return event  # type: ignore[return-value]

    async def _run(self) -> None:
        replay: list[bytes] = []
        try:
            for attempt in range(2):
                try:
                    await self._session(replay)
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    if self._closed or attempt == 1:
                        LOGGER.warning("STT %s stopped: %s", self.speaker, error)
                        return
                    self.reconnects += 1
                    replay = list(self._replay)
                    self._word_counts.clear()
                    LOGGER.warning("STT %s reconnecting once after drop", self.speaker)
        finally:
            await self._events.put(_END)

    async def _session(self, replay: list[bytes]) -> None:
        async with connect(
            self.url,
            additional_headers={"Authorization": settings.assemblyai_api_key},
            open_timeout=15,
        ) as socket:
            for frame in replay:
                await socket.send(frame)

            async def receive() -> None:
                async for raw in socket:
                    message = json.loads(raw)
                    message_type = message.get("type")
                    if message_type in {"Error", "SessionError"}:
                        raise RuntimeError(str(message.get("error") or message.get("message")))
                    if message_type == "Turn":
                        await self._parse_turn(message)
                    if message_type == "Termination":
                        return

            async def send() -> None:
                while True:
                    frame = await self._audio.get()
                    if frame is None:
                        await socket.send(json.dumps({"type": "Terminate"}))
                        return
                    await socket.send(frame)

            receiver = asyncio.create_task(receive())
            sender = asyncio.create_task(send())
            done, pending = await asyncio.wait(
                {receiver, sender}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                error = task.exception()
                if error:
                    for other in pending:
                        other.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    raise error
            if receiver in done and not self._closed:
                for other in pending:
                    other.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                raise ConnectionError("stream closed before termination")
            if sender in done and not receiver.done():
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(receiver, timeout=3)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    async def _parse_turn(self, message: dict) -> None:
        turn = int(message.get("turn_order", 0))
        words = message.get("words") or []
        seen = self._word_counts.get(turn, 0)
        for word in words[seen:]:
            text = str(word.get("text") or word.get("word") or "").strip()
            if not text:
                continue
            t_ms = int(word.get("end") or word.get("end_ms") or 0)
            final = bool(word.get("word_is_final", message.get("end_of_turn", False)))
            await self._events.put(WordEvent(self.speaker, text, t_ms, final))
        self._word_counts[turn] = len(words)
        if message.get("end_of_turn"):
            text = str(message.get("transcript") or "").strip()
            t_ms = int(words[-1].get("end") or words[-1].get("end_ms") or 0) if words else 0
            await self._events.put(TurnEndEvent(self.speaker, t_ms, text))
