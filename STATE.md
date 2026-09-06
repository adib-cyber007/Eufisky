# STATE SNAPSHOT

Phase 5 is complete on `main`.

- Post-call work is a true background task from WRAPUP. It mixes Caller and Margaret recordings into stereo, submits the confirmed eight PII policies with multichannel text/audio redaction, entity detection, and sentiment analysis, then requests the strict seven-field incident JSON through AssemblyAI's documented LeMUR successor.
- Provider failures are demo-safe: batch failure uses the persisted live transcript with local digit-run redaction, and summary failure uses a deterministic event/signal template. Fallback reports are visibly labeled. Raw Caller/Margaret WAVs and the stereo working file are deleted after the incident is persisted.
- SQLite incidents now include parsed summaries, analytics, analysis source, and an optional redacted-audio path. Call APIs expose complete events, samples, segments, and incident detail; redacted audio is served through a room/call-checked endpoint.
- Dashboard History renders report cards with peak-risk badges, caller claim, requests, disclosure status, intervention, outcome, recommendation, redacted transcript, optional redacted audio, a risk sparkline, and a safety timeline. Messages shows Front Door records.
- Replay Mode is complete: `data/demo_call.json` contains a 28-event ideal call with Caller/Margaret/Sarah captions; `POST /api/rooms/{room}/replay` republishes it at 0.25–20×; the dashboard has a speed selector and **▶ Replay demo call**; `tools/replay.py` starts it; `tools/record_replay.py` exports a real call.
- Every new room receives two trusted contacts, three historical incident reports (Medicare scam blocked, grandparent scam ended by Margaret, benign pharmacy), and two messages. Existing local `demo` databases receive missing Phase 5 history without duplicating it.
- Hardening includes dashboard WebSocket reconnection, per-message malformed JSON handling on phone/dashboard sockets, stale socket cleanup, graceful participant disconnect wrapup, bounded external calls, and shared-room URL propagation. `/api/health` reports `assemblyai_key_present`, `agent_backend`, and `db_ok` without exposing secrets.
- The landing page now explains Eufisky, presents the Caller → Margaret → Sarah phone sequence, links the dashboard separately, gives exact scam-demo steps, and explains microphone permission and type-to-talk. Responsive layouts and keyboard focus remain covered. The temporary always-visible family-ring button was removed.
- `docs/DEMO_SCRIPT.md` is the exact click-by-click three-minute script, including trusted Sarah, benign Walgreens, the Medicare scam, the incident card, and replay fallback.
- Rule scoring, lexicon, triggers, and agent personas were not changed. `STATE_after_phase0.txt` remains untouched and untracked.

Verification:

- Full pytest suite: `52 passed`.
- Python compile, all four browser JavaScript syntax checks, JSON parsing, and `git diff --check`: green.
- Fresh-room API check: health `ok=true`, AssemblyAI key present, backend `voice_agent`, `db_ok=true`, 2 contacts, 3 incidents, 2 messages, and 28 replay events scheduled.
- Browser verification: landing page and shared-room links render correctly; History shows all three report cards and `####` in the redacted Medicare transcript; the 4× replay reaches risk 94, levels 1/2/3, Guardian, family conference, and WRAPUP with all role captions and timeline events.
- Live four-WebSocket type-to-talk scam run: risk reached 100, Caller HOLD began in 86 ms, Sarah joined privately, and the caller was blocked. The post-call card appeared immediately as a clearly flagged template fallback (network access was unavailable in the local sandbox); `4123 5678` was absent, `####` was present, and both raw WAVs were gone.
- Local server is healthy at `http://127.0.0.1:8000`.

# HUMAN ACTIONS REQUIRED NOW

None. For a demo, open `http://localhost:8000` and follow the page, or use the single command in `docs/DEMO_SCRIPT.md` if the server has been stopped.

# BLOCKERS

None. The real AssemblyAI batch + LLM path is implemented and covered by fakes; this run exercised the required visible, flagged fallback because the local server sandbox could not open external sockets.
