"""AssemblyAI streaming message parsing and reconnect behavior."""

import pytest

from app.stt.assemblyai_stream import STTStream, TurnEndEvent, WordEvent


@pytest.mark.asyncio
async def test_turn_parser_emits_new_words_and_turn_end() -> None:
    stream = STTStream("caller", ["Medicare", "gift card"])
    assert "sample_rate=16000" in stream.url
    assert "mode=max_accuracy" in stream.url
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
async def test_provisional_words_are_corrected_before_publication() -> None:
    stream = STTStream("caller", ["Medicare"])
    await stream._parse_turn({"turn_order": 0, "words": [
        {"text": "from", "end": 100, "word_is_final": True},
        {"text": "medical", "end": 300, "word_is_final": False},
    ]})
    assert (await stream._events.get()).text == "from"
    assert stream._events.empty()
    final = {"turn_order": 0, "end_of_turn": True, "transcript": "from Medicare.", "words": [
        {"text": "from", "end": 100, "word_is_final": True},
        {"text": "Medicare.", "end": 300, "word_is_final": True},
    ]}
    await stream._parse_turn(final)
    assert (await stream._events.get()).text == "Medicare."
    assert isinstance(await stream._events.get(), TurnEndEvent)
    await stream._parse_turn(final)  # formatted final mustn't answer twice
    assert stream._events.empty()


@pytest.mark.asyncio
async def test_transcript_only_pro_turn_is_not_lost() -> None:
    stream = STTStream("senior", ["Sarah"])
    await stream._parse_turn({"turn_order": 0, "transcript": "Please get Sara", "end_of_turn": False})
    assert stream._events.empty()
    await stream._parse_turn({"turn_order": 0, "transcript": "Please get Sarah.", "end_of_turn": True})
    assert [(await stream._events.get()).text for _ in range(3)] == ["Please", "get", "Sarah."]
    assert (await stream._events.get()).text == "Please get Sarah."


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
