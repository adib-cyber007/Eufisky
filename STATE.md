STATE SNAPSHOT:

Current milestone: **Phase 2 — Monitoring, AssemblyAI streaming, deterministic rules, and live risk meter (complete).**

Next milestone: **Phase 3 — Front Door agent (not started).**

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
|   |-- scripts/
|   |-- test_calls.py
|   |-- test_routing.py
|   |-- test_rules.py
|   |-- test_smoke.py
|   |-- test_state_machine.py
|   `-- test_stt.py
|-- tools/
|   `-- verify_phase2_stt.py
|-- .env.example
|-- .gitignore
|-- README.md
|-- requirements.txt
`-- STATE.md
```

(b) What works end-to-end

- The Phase 1 phone system remains intact: trusted calls ring and bridge directly, while unknown calls are recorded and monitored only after Margaret answers.
- Each bridged unknown call opens one AssemblyAI Universal-Streaming session for the caller and one for Margaret. Both consume PCM16 mono 16 kHz audio, preserve speaker labels, parse word/final/turn events, and close on hold or call end.
- A dropped streaming session reconnects at most once and replays the last 2 seconds of 100 ms PCM frames.
- Type-to-talk bypasses STT but creates a final `WordEvent` and follows the same transcript, normalization, scoring, persistence, and dashboard path.
- The deterministic engine normalizes punctuation, common synonyms, spoken digit runs, and numeric dates; matches a rolling 12-word window per speaker; deduplicates repeated evidence within 2 seconds; caps each family at three active hits; applies exponential half-life decay and the specified combination bonuses; and clamps risk to 0–100.
- The lexicon contains all 10 required speaker-specific families with at least 12 phrases each, the senior PII-disclosure regex, and all three required combinations.
- While bridged, a 500 ms ticker publishes and persists risk updates. Transcript segments, state changes, safety levels, and risk events are broadcast and stored; calls track peak risk.
- L1 sends a soft chime and “Eufisky is listening.” to Margaret only, once. L2 and L3 publish dry-run level events and log that they would fire; no Guardian intervention occurs in Phase 2.
- Dashboard Live shows a caller-left/Margaret-right rolling transcript, a 0–100 risk instrument with 40/65/90 bands, evidence chips with tooltips, and a state/level timeline. History shows peak risk, while trusted calls remain labeled Private.
- The call-detail API returns events, risk samples, and transcript segments.
- The exact typed verification flow passed in room `phase2verify`: the first caller line crossed L1; the second crossed L2; the senior compliance/digit line reached 100; the server logged `L2 would fire`; the completed History row showed `Peak risk 100`.
- The verified call persisted three labeled segments, 205 samples at a 517 ms median interval, levels 1/2/3, both speakers, final state `ENDED`, and peak risk 100. Caller, Margaret, and Dashboard browser consoles had no errors.
- Production AssemblyAI verification passed with both saved speech fixtures. The final median word lag was 1,280 ms, below the 1,500 ms gate.
- Verification: `16 passed` with only two known third-party deprecation warnings. Python compilation passed.

(c) What is stubbed/deferred

- The unknown-caller Front Door remains the Phase 1 placeholder. The real screening conversation is Phase 3.
- L2/L3 Guardian intervention, caller hold, private senior conversation, and Guardian tools remain Phase 4. Phase 2 deliberately emits/logs would-fire events only.
- Post-call PII redaction, incident summaries, auto-blocking, and functional Replay Mode remain Phase 5 or later.
- The owner’s real-microphone check (T4 step 3) remains a human verification action; production STT itself was verified with the saved real-speech fixtures.

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

The current Phase 2 server is running on port 8000 after verification.

(f) Harness numbers

```text
class   total  L2  no-L2
scam       60  60      0
benign     40   0     40
precision=100.0% recall=100.0% benign_L2=0.0% benign_L1=0.0%
```

Required gates all pass: scam L2 recall ≥90%, benign L2 false-trigger ≤5%, and benign L1 ≤15%.

(g) Decisions/defaults chosen

- Kept scoring fully deterministic; no LLM, agent backend, or external model participates in risk decisions.
- Kept the account-tested raw v3 streaming model identifier `universal-3-5-pro` for reproducibility. Current official material also uses `u3-rt-pro`; `docs/ASSUMPTIONS.md` records the distinction.
- Capped keyterms at the documented 100-term streaming limit and 50 characters per term, prioritizing organization names and Margaret/Sarah before lexicon phrases of at most three words.
- Preserved the phone WebSocket protocol. Phase 2 adds only the already-documented dashboard transcript/risk/level event producers.
- Used separate per-leg STT sessions instead of diarization so caller and senior labels remain deterministic.
- Retained the existing navy/sky and Georgia/Verdana interface language. The live risk instrument is visually dominant; transcript and timeline support it without a generic equal-card layout.
- Preserved the owner’s unrelated untracked `STATE_after_phase0.txt` file and excluded it from this phase.

HUMAN ACTIONS REQUIRED NOW:

1. Keep the server running. Open http://localhost:8000/caller?room=demo, http://localhost:8000/senior?room=demo, and http://localhost:8000/dashboard?room=demo in three browser tabs. Expected result: all three pages show room `demo`, and Dashboard says `Live connection`.
2. In Caller, choose `Unknown caller`, click `Dial Margaret`, switch to Margaret, and click `Answer`. Expected result: both phones show `Screened — monitored`, and Dashboard changes to `BRIDGED`.
3. In Caller only, click `Mic OFF` so it becomes `Mic ON`, allow microphone access if the browser asks, and say: “This is Medicare, your benefits will be suspended today unless we verify. Read me the number on your Medicare card.” Keep Margaret’s microphone off to prevent feedback. Expected result: within about 1–2 seconds, the words appear on the Caller side of Dashboard, the risk meter crosses 40 and then 65, and Margaret plays one soft chime.
4. Turn Caller’s mic off. In Margaret, turn the mic on and say: “Hold on, let me get my purse, four one two three.” Expected result: the words appear on Margaret’s side of Dashboard and evidence includes compliance cue and PII disclosure.
5. Hang up from either phone and open Dashboard → History. Expected result: the unknown call shows its peak risk; trusted calls continue to show `Private`.

BLOCKERS:

None.
