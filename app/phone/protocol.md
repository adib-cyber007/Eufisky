# Phone and dashboard protocols

Every phone connects to `/ws/phone` and first sends
`hello{role,room,caller_phone?}`. Caller then sends `dial{}`; the senior or family
sends `answer{}`. Any phone can send `hangup{}`, `text{text}`, `mic{on}`, or
`dtmf{digit}`. Guardian controls send `guardian_action{action}` where action is
`end`, `family`, or `continue`. Binary messages are 100 ms frames of signed little-endian PCM16,
mono, 16 kHz. The server sends `state{call_state,badge,monitored}`,
`ring{from_label,trusted,reason?}`, `agent_say{text,agent}`, `hold{on}`, `tone{name}`,
`guardian_controls{visible,family_name?,fallback?}`,
`ended{reason}`, or binary PCM16. A JSON `ping` is sent every 15 seconds.
Clients may encode an event as `{"type":"text","text":"hello"}` or the
equivalent `{"text":{"text":"hello"}}`; the server normalizes both forms.

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
5. `conference_family` enters `FAMILY_CONF` and rings the family with a reason.
   Senior and family can speak privately while the caller remains held. Either
   can explicitly resume the caller or end the call.
6. Hangup enters `WRAPUP`, closes the agent/STT/WAV sessions, stores the final
   risk and outcome, applies the high-risk block policy, and emits `ended`.

Dashboard clients connect to `/ws/dashboard?room=` and receive the documented
`risk`, `transcript`, `state`, `level`, `tool`, `guardian`, and `call` events.
