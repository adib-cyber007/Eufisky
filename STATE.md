STATE SNAPSHOT:

Current milestone: **Phase 1 — Simulated phone system, routing, and audio bridge (complete).**

Next milestone: **Phase 2 — Monitoring, AssemblyAI streaming, deterministic rules, and live risk meter (not started).**

(a) File tree (2 levels)

```text
.
|-- app/
|   |-- agent/
|   |-- phone/
|   |-- postcall/
|   |-- rules/
|   |-- session/
|   |-- stt/
|   |-- web/
|   |-- audio.py
|   |-- config.py
|   |-- db.py
|   |-- main.py
|   `-- rooms.py
|-- data/
|   |-- recordings/       (runtime, gitignored)
|   |-- eufisky.db        (runtime, gitignored)
|   `-- seed.json
|-- docs/
|   |-- ASSUMPTIONS.md
|   |-- HUMAN_TASKS.md
|   |-- MASTER_SPEC.md
|   `-- PROJECT_CONTEXT.md
|-- tests/
|   |-- test_calls.py
|   |-- test_routing.py
|   `-- test_smoke.py
|-- tools/
|-- .env.example
|-- .gitignore
|-- README.md
|-- requirements.txt
`-- STATE.md
```

(b) What works end-to-end

- One FastAPI app serves the room picker, Caller phone, Margaret's phone, Sarah's family phone, and Family Dashboard.
- `POST /api/rooms/new` creates an isolated room. Every new room receives the two seed contacts: Sarah (daughter) and Walgreens Pharmacy.
- SQLite creates every table documented in `docs/PROJECT_CONTEXT.md` idempotently, plus a durable room marker that prevents deleted seed contacts from reappearing, and provides helpers for contacts, calls, events, transcript segments, and messages.
- Caller ID classification is deterministic: blocked wins over trusted, then unknown; withheld and empty caller IDs are unknown.
- Trusted calls ring Margaret immediately, show `Trusted — not monitored`, bridge PCM16 directly between phones, and create no WAV path, recording, transcript segment, or dashboard transcript.
- Unknown calls play `Eufisky screening will run here in the next phase`, then ring Margaret, show monitored status, capture caller PCM and typed speech from screening onward without leaking it to Margaret before answer, bridge answered-call PCM, and record caller/senior legs as separate WAV files.
- Family ringing and conference join work from the temporary Dashboard `Ring Sarah's phone` button.
- Hold excludes a leg from sending and receiving audio. Phone disconnects end active calls cleanly.
- Browser audio uses `getUserMedia`, AudioWorklet with ScriptProcessor fallback, 16 kHz PCM16 100 ms frames, queued playback, speech synthesis that cancels on real microphone barge-in, a live level meter, and Mic OFF by default.
- Contacts support add, trust, block, and delete. Live shows the current call state. History lists completed and active calls.
- Phone and dashboard WebSockets send a heartbeat every 15 seconds and dashboard call/state/transcript events are live.
- Visual browser verification passed for trusted and unknown call flows; browser console reported no errors.
- REST verification passed for contact create/patch/delete and call detail.
- Verification: `9 passed` with two third-party deprecation warnings. Python compile check passed. A direct 100 ms PCM relay frame stays below the 250 ms added-latency gate.
- Live verification covered trusted, bridged unknown, and pre-answer screening calls. The trusted detail had 0 segments and no recording paths; unknown calls stored typed segments and produced two valid WAV files. A new room seeded two contacts, and stayed empty after both were deleted and its contacts endpoint was reloaded.

(c) What is stubbed/deferred

- The unknown-caller Front Door is the required temporary placeholder; the real AssemblyAI Voice Agent conversation arrives in Phase 3.
- Live AssemblyAI per-leg STT, deterministic risk scoring, Guardian intervention, post-call processing, auto-blocking, and functional Replay Mode remain deferred to their planned phases.
- Dashboard `risk`, `level`, and `tool` event rendering is not active yet because those producers are deferred.
- Groq remains optional and unset because the AssemblyAI Voice Agent probe passed.

(d) Environment variables in use (values hidden where secret)

- `ASSEMBLYAI_API_KEY`: set (hidden)
- `AGENT_BACKEND`: `voice_agent`
- `GROQ_API_KEY`: not set
- `GEMINI_API_KEY`: not set
- `SENIOR_NAME`: `Margaret`
- `FAMILY_NAME`: `Sarah`
- `PORT`: `8000`

(e) Run command and URLs

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

- Room picker: http://localhost:8000
- Caller: http://localhost:8000/caller?room=demo
- Margaret: http://localhost:8000/senior?room=demo
- Sarah: http://localhost:8000/family?room=demo
- Dashboard: http://localhost:8000/dashboard?room=demo
- Health: http://localhost:8000/api/health

The current Phase 1 server was left running on port 8000 after verification.

(f) Decisions/defaults chosen

- Kept all Phase 0 probes and architecture stubs intact; Phase 1 extends only the phone system surfaces.
- Used synchronous stdlib SQLite helpers for short local operations and in-memory room objects for live sockets/call state.
- Opened unknown-call WAVs at call start so even type-only monitored demos produce valid WAV containers; PCM frames fill them when the mic is on.
- Reused `agent_say` for audible type-to-talk delivery, with `agent` naming the speaking phone role.
- Accepts both `{"type":"event",...}` and the documented `{"event":{...}}` WebSocket JSON envelopes.
- Added a small temporary REST action for the Dashboard family-ring button while keeping the documented phone/dashboard protocols intact.
- Used a calm household-handset visual language with large controls, strong contrast, and responsive layouts rather than a generic card dashboard.
- Repaired the laptop's registered Python 3.12.10 installation because the existing `.venv` launcher target had gone missing. The same virtual environment works again.
- Preserved the owner's unrelated untracked `STATE_after_phase0.txt` file and did not include it in the Phase 1 commit.

HUMAN ACTIONS REQUIRED NOW:

1. Keep the current server window running, then open http://localhost:8000/caller?room=demo and http://localhost:8000/senior?room=demo in separate tabs.
2. In Caller, leave `Sarah — trusted` selected, click `Dial Margaret`, switch to Margaret, and click `Answer`.
3. In Caller only, click `Mic OFF` so it changes to `Mic ON`, allow microphone access if the browser asks, then speak. Expected: your voice plays from Margaret's tab and both tabs show `Trusted — not monitored`. Keep Margaret's mic OFF to avoid feedback.
4. Hang up, choose `Unknown caller` in Caller, and click `Dial Margaret`. Expected: the Caller tab speaks and captions `Eufisky screening will run here in the next phase`; Margaret sees `Unknown — screened`.
5. Open http://localhost:8000/dashboard?room=demo and choose History. Expected: both calls appear; the trusted call has no audio/transcript, while the unknown call creates WAV files under `data/recordings` when audio is sent.

BLOCKERS:

None.
