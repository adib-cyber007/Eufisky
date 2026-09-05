# Phone and dashboard protocols

Phone clients connect to `/ws/phone`. Client JSON messages are `hello{role,room,caller_phone?}`, `dial{}`, `answer{}`, `hangup{}`, `text{text}`, `mic{on}`, and `dtmf{digit}`. Binary messages are PCM16 mono, 16 kHz, in 100 ms chunks.

The server sends `state{call_state,badge,monitored}`, `ring{from_label,trusted}`, `agent_say{text,agent}`, `hold{on}`, `tone{name}`, and `ended{reason}` JSON messages. Server binary messages are PCM16 audio to play.

Dashboard clients connect to `/ws/dashboard?room=` and receive `risk`, `transcript`, `state`, `level`, `tool`, and `call` JSON events as defined in `docs/PROJECT_CONTEXT.md`.
