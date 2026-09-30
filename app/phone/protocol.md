# Phone and dashboard protocols

Every phone connects to `/ws/phone` and first sends
`hello{role,room,caller_phone?}`. Caller then sends `dial{}`; the senior or family
sends `answer{}`. Any phone can send `hangup{}`, `text{text}`, `mic{on}`, or
`dtmf{digit}`. Guardian controls send `guardian_action{action}` where action is
`end`, `family`, or `continue`. Binary messages are 100 ms frames of signed little-endian PCM16,
mono, 16 kHz. The server sends `state{call_state,badge,monitored}`,
`registered{role,room}` immediately after accepting the hello,
`ring{from_label,trusted,reason?}`, `agent_say{text,agent,playback}`, `agent_output_reset{}`,
`hold{on}`, `tone{name}`,
`guardian_controls{visible,family_name?,fallback?}`,
`notice{t_ms,kind,caller_label,purpose,callback_number}`, `ended{reason}`, or binary
PCM16. A JSON `ping` is sent every 15 seconds. `notice` is sent to the Senior
phone for each Front Door `take_message` or `decline` outcome and is also
published once on the dashboard feed.
Clients may encode an event as `{"type":"text","text":"hello"}` or the
equivalent `{"text":{"text":"hello"}}`; the server normalizes both forms.
The `registered` acknowledgement is the authoritative active room shown by each
browser page. `agent_say` uses browser speech only when `playback` is `speech`;
binary PCM is the returned Voice Agent audio path. `agent_output_reset` cancels
both paths before an agent handoff, deterministic closing line, or a confirmed
Voice Agent interruption (`reply.done` with `status: interrupted`). Completed
replies do not reset playback; their buffered audio plays to the end.

Browser capture preserves resampling state across worklet blocks and sends a
continuous 16 kHz stream. PCM playback uses browser echo cancellation, allowing
both people to speak at once. During system speech fallback, the browser sends
silence rather than removing time from the microphone stream. PCM playback has
an 80 ms initial buffer and schedules subsequent chunks contiguously.

Closing `agent_say` messages include `utterance_id`. The receiving phone sends
`playback_done{utterance_id}` only after speech finishes. The server then ends
the call; a bounded timeout covers older clients or unavailable system speech.
Manual hangup remains immediate.

For microphone calls, conversational agent input also has exactly one path. In
`voice_agent` mode, live PCM is sent to the Voice Agent while the separate STT
stream is used only for speaker-labeled transcript and deterministic risk
scoring. Its finalized `TurnEndEvent` must not be sent back to that same agent
as text. In LLM/fallback mode there is no live agent-audio input, so the STT
turn text supplies the conversational input instead. Typed browser input always
uses the text path.

STT and Voice Agent transcription use `max_accuracy`. Voice Agent silence
windows remain unset to preserve adaptive pacing and waiting for complete
names/numbers. Only finalized STT words enter the transcript/risk engine;
provisional replacements and repeated formatted turns aren't appended twice.
Transcript-only final turns are supported. A live Voice Agent socket drop
switches to STT plus the text backend, preserves conversation context, and
asks the person to repeat the last sentence rather than leaving a silent call.

## Trusted call

1. Caller sends `hello` with a trusted number, then `dial`.
2. Server classifies blocked first, then trusted, then unknown. It creates a call
   row, enters `RINGING_SENIOR`, and sends the senior `ring{trusted:true}`. Both
   phones see the badge `Trusted — not monitored`.
3. Senior sends `answer`; state becomes `TRUSTED_ACTIVE`.
4. PCM is relayed directly caller→senior and senior→caller. No recorder, STT
   adapter, transcript segment, or dashboard transcript is created.
5. Either side sends `hangup` (or disconnects); state becomes `ENDED`.

## Unknown call

1. Caller sends `hello` with an unrecognized or withheld number, then `dial`.
2. Server enters `SCREENING`, sends the temporary Front Door `agent_say`, then
   enters `RINGING_SENIOR` and sends `ring{trusted:false}`. Typed caller speech
   is accepted and stored from this point, including while Margaret's phone is
   still ringing. Caller PCM is recorded for the future Front Door/STT path but
   is not relayed to Margaret before she answers.
3. Senior sends `answer`; state becomes `BRIDGED` and both sides' PCM is relayed.
   Each source leg is also written to `<call_id>_caller.wav` or
   `<call_id>_senior.wav`. Typed speech continues to be stored as a
   transcript-equivalent segment and broadcast to the dashboard.
4. A deterministic L2 risk trigger enters `GUARDIAN`, detaches both monitoring
   streams, and sends the caller `hold{on:true}` plus `tone{hold_music}` before
   the private Guardian backend starts. Only the senior receives Guardian speech.
   The per-call agent registry rejects Guardian startup until the Front Door
   session's awaited close has completed, so at most one Voice Agent session is
   open for the call.
5. `conference_family` enters `FAMILY_CONF` and rings the family with a reason.
   Senior and family can speak privately while the caller remains held. Either
   can explicitly resume the caller or end the call.
6. Hangup enters `WRAPUP`, closes the agent/STT/WAV sessions, stores the final
   risk and outcome, applies the high-risk block policy, and emits `ended`.

Dashboard clients connect to `/ws/dashboard?room=` and receive the documented
`risk`, `transcript`, `state`, `level`, `tool`, `guardian`, `call`, and `notice`
events.
