"""AssemblyAI streaming message parsing and reconnect behavior."""

import pytest

from app.stt.assemblyai_stream import STTStream, TurnEndEvent, WordEvent


@pytest.mark.asyncio
async def test_turn_parser_emits_new_words_and_turn_end() -> None:
    stream = STTStream("caller", ["Medicare", "gift card"])
    assert "sample_rate=16000" in stream.url
    assert "format_turns=true" in stream.url
    assert "keyterms_prompt=" in stream.url

    await stream._parse_turn({
        "type": "Turn",
        "turn_order": 0,
        "end_of_turn": True,
        "transcript": "This is Medicare.",
        "words": [
            {"text": "This", "end": 120, "word_is_final": True},
            {"text": "is", "end": 220, "word_is_final": True},
            {"text": "Medicare.", "end": 400, "word_is_final": True},
        ],
    })
    events = [await stream._events.get() for _ in range(4)]
    assert [event.text for event in events[:3]] == ["This", "is", "Medicare."]
    assert all(isinstance(event, WordEvent) for event in events[:3])
    assert isinstance(events[3], TurnEndEvent)


@pytest.mark.asyncio
async def test_one_reconnect_replays_last_two_seconds(monkeypatch) -> None:
    stream = STTStream("senior", [])
    stream._replay.extend([bytes([index]) for index in range(25)])
    calls: list[list[bytes]] = []

    async def fake_session(replay: list[bytes]) -> None:
        calls.append(replay)
        if len(calls) == 1:
            raise ConnectionError("simulated drop")

    monkeypatch.setattr(stream, "_session", fake_session)
    await stream._run()
    assert stream.reconnects == 1
    assert len(calls) == 2
    assert calls[1] == [bytes([index]) for index in range(5, 25)]
