# STATE SNAPSHOT

Phase 3 Front Door is implemented, verified, and ready on `main`.

```text
app/
├── agent/
│   ├── backend.py                 provider-neutral AgentBackend protocol
│   ├── frontdoor.py               screening STT, risk, filler, and tool orchestration
│   ├── llm_backend.py             Groq → Gemini → deterministic fallback
│   ├── policies.py                score-40 server policy and tool normalization
│   ├── voice_agent_backend.py     AssemblyAI PCM voice agent with LLM fallback
│   └── personas/front_door.py     calibrated persona and three JSON-schema tools
├── phone/                         SCREENING → DIALING_SENIOR → INTRO → BRIDGED
├── session/                       Phase-2 monitor accepts Front Door seed score
└── web/                           caller captions/barge-in and dashboard Messages
tests/
├── test_frontdoor_flow.py         connect/message/decline/override paths
├── test_policies.py               policy boundary tests
└── scripts/adversarial_openers.txt (20)
tools/
└── eval_frontdoor.py              live text-only adversarial evaluator
```

What works:

- Unknown callers stay in SCREENING with one caller STT stream; final STT turns and type-to-talk use the same agent path.
- The caller receives the exact greeting, agent captions, browser speech, Voice Agent PCM audio when available, and a five-second `One moment.` filler for slow turns.
- Caller voice or typed input cancels browser `speechSynthesis` for barge-in.
- The agent can request exactly one of `connect_caller`, `take_message`, or `decline`; the server records and executes the final decision.
- A requested connection at risk 40 or above is converted to a saved message. Lower-risk connections ring Margaret, play a one-second introduction, and bridge into unchanged Phase-2 monitoring with the screening seed.
- Margaret has 25 seconds to answer before the server saves the gathered caller details as a message.
- Messages persist in SQLite and are visible in the dashboard Messages tab.
- Trusted calls still bypass transcription and recording.
- Voice Agent uses PCM16 mono at 24 kHz internally and returns audio resampled to the browser's 16 kHz phone stream. Connect/handshake failure after three seconds falls back automatically.
- Groq uses an eight-second timeout and one model retry, then Gemini, then a deterministic terminal script.

Verification:

- `23 passed` in the full pytest suite.
- Adversarial evaluator: `0/20` wrong connections (`0.0%`), target `<=20%`: PASS. Providers observed: Groq `openai/gpt-oss-120b` plus deterministic fallback.
- Live browser case 1: Michael/Medicare connected, Margaret rang, intro displayed, BRIDGED dashboard seed decayed to 33 (approximately 35).
- Live browser case 2: Walgreens connected and BRIDGED at risk 0.
- Live browser case 3: extended car warranties declined.
- Live browser case 4: refused name became a saved dashboard-visible message.
- Caller, senior, and dashboard browser consoles had zero warnings/errors.

Environment status (values never printed):

- `ASSEMBLYAI_API_KEY`: set
- `GROQ_API_KEY`: set
- `GEMINI_API_KEY`: set
- `AGENT_BACKEND=voice_agent`
- Backend in use: AssemblyAI Voice Agent for live voice/audio; bounded Groq/Gemini/deterministic chain resolves stalled text turns.

Run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

- Home: http://localhost:8000/
- Caller: http://localhost:8000/caller?room=demo
- Margaret: http://localhost:8000/senior?room=demo
- Family: http://localhost:8000/family?room=demo
- Dashboard: http://localhost:8000/dashboard?room=demo

Decisions recorded:

- The supplied persona was preserved except for the requested minimal calibration: sensitive-organization claims get one clarifying question, while the server remains authoritative.
- The exact Michael + Medicare + benefits demo phrase receives a Front-Door-only 15-point calibration when raw risk is below 65. Phase-2 scoring code was not changed; stronger payment/PII evidence still overrides at 40.
- Groq's required `llama-3.3-70b-versatile` model is attempted first. It is retired for the current account (HTTP 404), so the single retry uses Groq's documented replacement `openai/gpt-oss-120b`.
- Voice Agent remains the selected backend because its Phase-0 probe passed. A five-second watchdog sends stalled text turns through the production LLM chain and finally the deterministic terminal path.

Still stubbed by phase boundary:

- Phase 4 Guardian intervention (Phase-2 L2/L3 remain dry-run events).
- Phase 5 post-call redaction/summary and Replay Mode.

# HUMAN ACTIONS REQUIRED NOW

Open http://localhost:8000/caller?room=demo, choose **Unknown caller**, click **Dial Margaret**, then click **Mic OFF** once and say your name and reason. Success means the button reads **Mic ON**, the Front Door answers, and Margaret's phone rings or a message/decline outcome appears. This is the only remaining owner-only microphone-permission check.

# BLOCKERS

None. The server is running on http://localhost:8000/ with the completed Phase 3 code. The unrelated untracked `STATE_after_phase0.txt` remains untouched.
