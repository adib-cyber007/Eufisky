# STATE SNAPSHOT

Follow-up microphone interruption fix completed on 2026-09-07. Deployed call
`5dd30e3b70e24de291db077840b28076` proved Front Door requested and executed
`connect_caller` at 24.2 seconds; the server never chose `take_message` or
`decline`, and the caller hung up at 32.1 seconds. The audible promise that a
message would be passed was therefore unsanctioned conversational agent output,
not a hidden routing decision.

The confirmed code cause affected both agents: each microphone frame was sent
to the live AssemblyAI Voice Agent, while the same audio was independently
transcribed and its finalized text was sent into that Voice Agent a second time.
One human utterance could therefore produce two competing agent turns, premature
speech, or an early tool-like response. Front Door and Guardian now use live PCM
as their sole conversational input in `voice_agent` mode; the parallel STT
stream remains transcript/risk-only. LLM/fallback mode still uses finalized STT
text, and typed browser input still uses text. Voice turn detection now waits
through a natural pause (`1200` ms minimum, `2500` ms maximum silence) instead
of responding after only `500`/`1500` ms. Protocol documentation records this
single-input invariant. Focused audio tests passed and the full suite now passes
all 77 tests.

Audio/room reliability patch completed on 2026-09-07. The owner's manual frontend restyle was preserved. Before patching, the pre-existing untracked `STATE_after_phase0.txt` was committed unchanged as `a683d5e` (`wip: pre-patch snapshot`), and safety branch `backup-pre-audio-patch-2026-09-07` was created at exactly that commit. The earlier `backup-restyle-2026-09-07` branch also remains.

Root causes and diagnosis:

- Senior did not ring and Dashboard did not update: this was not an HTTPS/WSS or Render configuration failure. Both clients already built WebSocket URLs with `location.protocol === "https:" ? "wss" : "ws"` plus `location.host`. The deployed database showed three same-day real Medicare test calls in room `demo`, while `test1` contained only its three seeded incidents. Caller therefore registered/dialed in `demo` while the laptop Senior and Dashboard watched `test1`. A missing `?room=` silently defaulted a page to `demo`, and Back links discarded the current room, making this mismatch easy to create and hard to see.
- No call record in `test1`: Dial did reach the deployed server and successful call rows/events were created, but under `demo`; there was no call-creation exception in the failed attempt. Historical role/room logs did not exist, so the database is the durable evidence for that old attempt. New logs now record every phone/dashboard registration and Dial with role and room. A patched local run logged `Phone websocket registered role=caller room=test1`, `Phone websocket registered role=senior room=test1`, `Dashboard websocket registered room=test1`, and `Dial received role=caller room=test1`.
- Overlapping voices: this was a universal code bug, independent of Render. There was no per-call ownership guard for Front Door versus Guardian. On `take_message`/`decline`, browser speech could begin before the Front Door Voice Agent's awaited close completed. Browser `speak()` canceled prior speech synthesis but did not stop queued Voice Agent PCM. The Voice Agent decision watchdog could also forward fallback LLM speech while the Voice Agent socket was still open. Finally, a replaced phone WebSocket left the old tab's playback pipeline alive. Normal calls did already call `speechSynthesis.cancel()` before each `speak()`; the missing piece was canceling the other PCM path and enforcing server lifecycle order.
- Local Step A before the fix: an unknown type-to-talk call connected, Margaret rang and answered, and Dashboard transcript/risk/state events updated live. Microphone capture could be toggled on in the existing localhost browser origin, but automated browser tooling cannot judge what a physical speaker sounds like. After the fix, a full typed local call reached Guardian and completed with a new incident. Logs showed the strict order `front_door opened -> front_door closed -> guardian opened -> guardian closed`, never two active sessions.

What changed:

- Added `AgentSessionRegistry`, which rejects/logs any second agent session until the active session's awaited `close()` has completed. Front Door references are cleared after close; Guardian is closed before deterministic reassurance or any resume/family/end action.
- Front Door closing speech starts only after Voice Agent closure. Guardian handoff/output resets cancel stale playback. Watchdog fallback remains decision-only while a Voice Agent socket is open, so it cannot inject a second voice.
- Browser audio tracks/stops queued PCM before `speechSynthesis.speak()`, calls `speechSynthesis.cancel()` before every new utterance, resets both playback paths at handoffs/end, and destroys mic/audio/WebSocket state on page exit. A newly opened duplicate role tab replaces and closes the older server connection.
- Phone WebSockets acknowledge `registered{role,room}`. Caller, Senior, and Family visibly show `Room <name> • connected`; Dashboard shows `Live · room <name>`. Pages with no explicit room visibly say `default room`, and Back links preserve the active room.
- Call creation failures roll back the in-memory call, log the real server exception, and show `Sorry, something went wrong. Please try again.` instead of disappearing silently.
- Protocol and demo documentation were updated. The restyled HTML/CSS structure was not replaced; only room-status wiring and cache-version query strings were added.

Changed files: `README.md`; `app/agent/frontdoor.py`; `app/agent/guardian.py`; `app/agent/voice_agent_backend.py`; `app/phone/calls.py`; `app/phone/protocol.md`; `app/phone/ws.py`; `app/session/state_machine.py`; `app/web/caller.html`; `app/web/senior.html`; `app/web/family.html`; `app/web/dashboard.html`; `app/web/static/css/app.css`; `app/web/static/js/audio.js`; `app/web/static/js/phone.js`; `app/web/static/js/dashboard.js`; `docs/DEMO_SCRIPT.md`; `tools/smoke_public.py`; `tests/test_calls.py`; `tests/test_deployment.py`; `tests/test_replay.py`; `tests/test_smoke.py`; `tests/test_state_machine.py`; `tests/test_voice_agent_backend.py`; and `STATE.md`.

Verification: `node --check` passed for all three changed JavaScript files. `.\.venv\Scripts\python.exe -m pytest -q` passes all 77 tests. After the prior Render deployment, `.\.venv\Scripts\python.exe tools\smoke_public.py https://eufisky.onrender.com` passed health/database, all five pages, the production Dashboard WebSocket room acknowledgement, Replay risk/transcript/state/tool events, and replay completion. New microphone-path coverage asserts Front Door PCM reaches the live Voice Agent exactly once without duplicate finalized text, Guardian STT text is suppressed while live PCM is active, fallback/typed text still works, and the caller gets at least one second of silence before the agent may take the turn.

Environment variables are unchanged. Local `.env`: `ASSEMBLYAI_API_KEY`, optional `GROQ_API_KEY`, optional `GEMINI_API_KEY`, `AGENT_BACKEND`, `SENIOR_NAME`, and `FAMILY_NAME`. Render additionally supplies `PORT` and `RENDER`. Deployed health reports the AssemblyAI key present and `AGENT_BACKEND=voice_agent`; no missing/expired environment variable was identified.

Local run command:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Local URLs: `http://localhost:8000/caller?room=test1`, `http://localhost:8000/senior?room=test1`, `http://localhost:8000/family?room=test1`, and `http://localhost:8000/dashboard?room=test1`.

Deployed URLs: `https://eufisky.onrender.com/caller?room=test1`, `https://eufisky.onrender.com/senior?room=test1`, `https://eufisky.onrender.com/family?room=test1`, and `https://eufisky.onrender.com/dashboard?room=test1`.

# HUMAN ACTIONS REQUIRED NOW

1. On the laptop, open `https://eufisky.onrender.com/dashboard?room=test1`. Wait until the top status says **Live · room test1**.
2. On the laptop, open `https://eufisky.onrender.com/senior?room=test1`. Confirm its header says **Room test1 • connected**. Optionally open `https://eufisky.onrender.com/family?room=test1` and confirm the same label.
3. On the phone, open `https://eufisky.onrender.com/caller?room=test1`. Confirm the header says **Room test1 • connected** before touching Dial. If any page says **default room**, stop and reopen the exact link above.
4. Choose **Unknown caller**, turn **Mic ON**, allow microphone access, and tap **Dial Margaret**. Success means Front Door is audible only once and the laptop Senior tab rings with **Answer** and **Decline**.
5. Answer on the Senior tab. On the phone say: “This is Michael from Medicare. Your benefits will be suspended today unless you verify your account. Please read me the number on your Medicare card.” Success means Dashboard changes in real time, risk rises, and Guardian places Caller on hold.
6. While Guardian speaks privately to Margaret, listen on both devices. Success means there is never more than one agent voice at once; the phone hears hold music, not Guardian, and Senior hears one Guardian voice.
7. Click **Bring in Sarah** or **End the call**. Then open Dashboard -> **History**. Success means the new completed call appears.
8. During both Front Door and Guardian, speak a complete sentence with a short natural pause in the middle. Success means the agent waits for you to finish and only one agent voice answers.
9. Reply with `two-device test worked` or name the single screen/step that failed.

# BLOCKERS

The automated code, WebSocket, persistence, and rendered-browser checks are complete. The only remaining check is inherently physical: the owner must confirm on the deployed phone/laptop microphone and speakers that Front Door and Guardian wait through natural pauses and that no second voice is audible. Recommendation: perform the nine steps above after Render finishes deploying the pushed commit.
