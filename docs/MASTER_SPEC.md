# MASTER_SPEC.md — Eufisky (browser-first)

## A. Project Brief

**One-liner:** Eufisky is a voice AI agent, built on AssemblyAI, that guards an older adult's phone line — it answers strangers, listens for scam patterns once they're connected, and steps in to talk privately with her (pausing the scammer, calling her daughter, or hanging up) before she reads out a card number.

**Problem:** Older adults lose billions every year to phone scams (Medicare/Social Security impersonation, "grandchild in jail," gift-card and tech-support scams). Call-blocking apps stop known numbers; nothing protects the person *during* the call, when a persuasive stranger walks her into reading digits.

**Target user:** Adult children of parents 70+ (the buyer); the senior (the protected user). Later: senior-living operators, banks, insurers, telcos.

**Solution:** A single web app serving a simulated phone line. Trusted contacts ring straight through and are never processed. Unknown callers meet the **Front Door** voice agent. If connected, both sides are transcribed by separate AssemblyAI real-time sessions (so every word is speaker-labeled), scored by a deterministic rule engine, and escalated: soft chime → **Guardian** agent pauses the caller and talks privately with the senior → acts through tool calls (resume / bring in family / end call & block / trust). After the call, AssemblyAI batch transcription redacts PII and LeMUR writes a plain-English incident summary for the family.

**Why it wins on the judging criteria**
- *Application of Technology:* five AssemblyAI capabilities used for exactly what they're for — Universal-Streaming (speaker-separated live words, turn detection to drive the agents), keyterm prompting (scam lexicon), batch PII redaction, LeMUR summaries, and the Voice Agent API if the Day-1 probe passes.
- *Presentation:* a 60-second live story with a visible risk meter and an audible intervention; judges can open the URL and play the scammer themselves.
- *Business Value:* universally understood problem, clear buyer (families/telcos/insurers), a privacy story ("your daughter's calls are never transcribed"), and a cost story (AI minutes only on the ~15% of calls from strangers).
- *Originality:* in-call, speaker-aware, reversible intervention that talks to the senior *privately*; not a blocklist, not a chatbot.

**NON-GOALS (the Building AI must not attempt):** real telephony/Twilio, SMS, WebRTC, user accounts/auth, payments, mobile apps, React/Node build tooling, Docker, Postgres/Redis, voice biometrics, outbound-call protection, any language other than English for the agents, any paid service.

## B. Technical Spec

### Architecture (text)
```
Browser tabs (same laptop or any device on the public URL), all keyed by ?room=<id>
 ┌─────────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────────────┐
 │ Caller Phone │   │ Senior Phone │   │ Family Phone│   │ Family Dashboard │
 │ mic/type,    │   │ (Margaret)   │   │ (Sarah)     │   │ contacts, live   │
 │ hears agent  │   │ hears agent  │   │ rings/joins │   │ risk meter,      │
 │ via browser  │   │ via browser  │   │             │   │ history, replay  │
 │ TTS          │   │ TTS          │   │             │   │                  │
 └──────┬───────┘   └──────┬───────┘   └──────┬──────┘   └────────┬─────────┘
        │ WS (JSON + binary PCM16 16 kHz)      │                   │ WS event feed
 ┌──────┴───────────────────┴──────────────────┴───────────────────┴─────────┐
 │                ONE FastAPI process (uvicorn)                              │
 │  phone/calls.py  ── call lifecycle, routing (trusted/blocked/unknown),    │
 │                     audio BRIDGE (relay caller↔senior, hold, family join) │
 │  stt/assemblyai_stream.py ── one Universal-Streaming session per leg      │
 │  rules/engine.py ── deterministic risk score 0–100 + evidence            │
 │  session/state_machine.py ── L1/L2/L3 ladder, drives hold + agents       │
 │  agent/ ── Front Door & Guardian personas; backend = AssemblyAI Voice     │
 │            Agent API (if probe passed) else Groq Llama tools + browser TTS│
 │  postcall/pipeline.py ── batch STT (PII redaction) + LeMUR summary        │
 │  db.py ── SQLite file; rooms.py ── in-memory live state per room          │
 │  web/ ── static HTML/JS pages incl. /slides                               │
 └───────────────────────────┬───────────────────────────────────────────────┘
                             │ HTTPS/WSS
                     AssemblyAI (Streaming, Batch, LeMUR, Voice Agent API)
                     Groq (fallback LLM, OpenAI-compatible)
```

### Tech stack (pinned)
Python 3.12 · fastapi 0.115.x · uvicorn[standard] 0.30.x · websockets 12.x · httpx 0.27.x · assemblyai (latest 0.3x SDK) · pyyaml 6.x · pydantic 2.x · pytest 8.x · Pillow 10.x (cover image only) · Frontend: vanilla HTML/CSS/JS, Web Audio API, `speechSynthesis`; reveal.js via CDN for `/slides` · SQLite via stdlib `sqlite3` · Hosting: Render free web service (`render.yaml`) · Repo: GitHub public.

### Folder structure
```
eufisky/
  app/
    main.py  config.py  db.py  rooms.py  audio.py
    phone/    calls.py  ws.py  protocol.md
    stt/      assemblyai_stream.py
    rules/    lexicon.yaml  engine.py  normalize.py  loader.py
    agent/    backend.py  llm_backend.py  voice_agent_backend.py  policies.py
              personas/front_door.py  personas/guardian.py
    session/  state_machine.py  context.py  events.py
    postcall/ pipeline.py  lemur_prompt.txt
    web/      index.html caller.html senior.html family.html dashboard.html slides.html
              static/css/app.css  static/js/{audio.js,phone.js,dashboard.js}
  data/       seed.json  demo_call.json  recordings/ (gitignored)  eufisky.db (gitignored)
  tools/      probe_realtime_stt.py probe_voice_agent.py probe_lemur.py probe_groq.py
              replay.py  make_cover.py  fixtures/*.wav
  tests/      test_rules.py test_normalize.py test_state_machine.py test_routing.py
              test_policies.py test_context.py  scripts/scam/*.txt scripts/benign/*.txt
  docs/       PROJECT_CONTEXT.md ARCHITECTURE.md DEMO_SCRIPT.md SUBMISSION.md
  requirements.txt  render.yaml  .env.example  .gitignore  README.md  STATE.md
```

### Data model (SQLite)
```
contacts(id, room, phone, label, status TEXT CHECK(status IN('trusted','blocked','pending')), source, created_at)
calls(id, room, from_phone, from_label, classification, started_at, ended_at, final_state,
      peak_risk, front_door_outcome, guardian_outcome, recording_caller, recording_senior)
call_events(id, call_id, t_ms, type, payload_json)          -- state, level, tool, risk crossings
risk_samples(call_id, t_ms, score, signals_json)
transcript_segments(id, call_id, speaker, t_ms, text, is_final)
incidents(id, call_id, summary_json, redacted_transcript, entities_json, created_at)
messages(id, room, call_id, from_phone, caller_name, body, callback_number, created_at)
```
Rooms: default room `demo`, seeded with senior "Margaret", family "Sarah", trusted contacts Sarah (+15550100101) and Walgreens Pharmacy (+15550100102). Any new room copies the seed.

### WebSocket protocol — phone tabs (`/ws/phone`)
Client→server JSON: `hello{role: caller|senior|family, room, caller_phone?}`, `dial{}`, `answer{}`, `hangup{}`, `text{text}` (type-to-talk: treated exactly like transcribed speech), `mic{on}`, `dtmf{digit}`. Binary frames = PCM16 mono 16 kHz, 100 ms.
Server→client JSON: `state{call_state, badge, monitored}`, `ring{from_label, trusted}`, `agent_say{text, agent: front_door|guardian}` (tab speaks it with speechSynthesis), `hold{on}`, `tone{name}`, `ended{reason}`. Binary frames = PCM16 to play.

### WebSocket — dashboard live feed (`/ws/dashboard?room=`)
```json
{"type":"risk","t_ms":48200,"score":78,"signals":["authority_impersonation","urgency","pii_request"],"evidence":[{"speaker":"caller","phrase":"medicare number"}]}
{"type":"transcript","speaker":"caller","t_ms":47900,"text":"...","final":true}
{"type":"state","t_ms":48250,"from":"BRIDGED","to":"GUARDIAN","trigger":"pii_disclosure"}
{"type":"level","t_ms":48250,"level":2}
{"type":"tool","t_ms":61000,"agent":"guardian","name":"conference_family","args":{}}
{"type":"call","t_ms":0,"event":"started|ended","call_id":"...","classification":"unknown"}
```

### REST
`GET /api/health` · `GET/POST/PATCH/DELETE /api/rooms/{room}/contacts` · `GET /api/rooms/{room}/calls` · `GET /api/rooms/{room}/calls/{id}` (events, samples, transcript, incident) · `GET /api/rooms/{room}/messages` · `POST /api/rooms/{room}/replay` (body `{file:"demo_call.json", speed:1.0}`) · `POST /api/rooms/new`.

### Environment variables
| Name | Purpose | Source | Human task |
|---|---|---|---|
| `ASSEMBLYAI_API_KEY` | all AssemblyAI calls | AssemblyAI dashboard | T2 |
| `AGENT_BACKEND` | `auto` / `voice_agent` / `llm` (default `auto`: voice_agent if probe passed) | set by Building AI | — |
| `GROQ_API_KEY` | fallback/primary LLM for agent personas | Groq console | T3 |
| `GEMINI_API_KEY` | optional backup LLM | Google AI Studio | T3 (optional) |
| `SENIOR_NAME` / `FAMILY_NAME` | persona templating (defaults Margaret / Sarah) | default | — |
| `PORT` | server port (Render sets it) | default 8000 | — |
| `PYTHON_VERSION` | Render build (3.12.x) | render.yaml | — |

### Third-party services
AssemblyAI (required; free hackathon credits), Groq (free key, no card), GitHub (free), Render (free, no card). Nothing else.

### Exact demo flow with sample data
1. Dashboard `/dashboard?room=demo`: contacts show Sarah and Walgreens as Trusted.
2. Caller tab, caller ID **Sarah (+1 555-010-0101)** → Dial → Senior tab rings with badge "Trusted — not monitored"; answer; talk; hang up. Dashboard shows a call record with no transcript.
3. Caller tab, caller ID **Unknown (+1 555-019-9321)** → Dial → Front Door speaks: *"Hello, you've reached Margaret's line. May I ask who's calling and what it's regarding?"* Caller: *"This is Michael from Medicare, about an urgent update to her benefits."* Front Door: *"One moment, I'll see if she's available."* → connects (pre-score 35).
4. Bridged. Caller: *"Your benefits will be suspended today unless we verify your account."* (risk → ~58, L1 chime on Senior tab). Caller: *"Please read me the number on your Medicare card."* (risk → ~74 → L2).
5. Caller tab shows HOLD; Senior tab hears Guardian: *"Margaret, I paused the call. This person said they were from Medicare and asked for your card number. Medicare never calls to ask for that. Would you like me to end the call, or bring Sarah on the line?"* Senior: *"Get Sarah."* → Family tab rings; answer; joined.
6. Caller hangs up → number auto-blocked → dashboard History shows incident card: LeMUR summary, redacted transcript, peak risk 74+, timeline.
7. Backup: Dashboard → Replay → `demo_call.json` animates the same sequence with no microphones.

## C. Phased Build Plan — Master Prompts for the Building AI

Phase order: 0 Environment, scaffold, probes → 1 Simulated phone system + routing → 2 Monitoring: STT + rule engine + risk meter → 3 Front Door agent → 4 Guardian intervention (demo moment complete) → 5 Post-call, replay, seed, hardening → 6 Deploy → 7 README, slides, cover, demo script, submission text → S Stretch.

### PHASE 0 — Environment, scaffold, probes
```
ROLE: You are the sole engineer building "Eufisky" on the owner's Windows 11 laptop. You have terminal (PowerShell), file-edit, and web access. Assume you have NO memory of anything before this message.

PROJECT CONTEXT: Eufisky — a voice AI agent (built on AssemblyAI) that guards an older adult's phone line. This is a browser-based simulation of a phone line (no real telephony): three web "phones" (Caller, Senior "Margaret", Family "Sarah") plus a Family Dashboard, all served by ONE Python FastAPI app. Trusted contacts ring straight through and are never transcribed. Unknown callers are answered by the FRONT DOOR voice agent (asks who/why; tools: connect_caller / take_message / decline). If connected, the call is bridged and silently monitored: audio from each side goes to its own AssemblyAI Universal-Streaming (Realtime STT) session so words are speaker-labeled; a DETERMINISTIC rule engine scores scam risk 0–100. A state machine escalates: L1 (score≥40) soft chime to the senior only; L2 (score≥65, or senior PII disclosure with score≥45, or payment_method + compliance_cue) puts the caller on hold and starts the GUARDIAN voice agent that talks privately to Margaret (tools: resume_call / conference_family / end_call / add_to_trusted); L3 (score≥90) recommends family. Post-call: AssemblyAI batch transcription with PII redaction and a LeMUR plain-English incident summary; numbers with peak risk ≥85 are auto-blocked. A Replay Mode drives the dashboard from a saved call file. Agent voice = browser speechSynthesis by default; agent brain = AssemblyAI Voice Agent API if the Phase-0 probe passes, else Groq (Llama) via its OpenAI-compatible API with tool calling (Gemini as backup). Stack: Python 3.12, FastAPI, uvicorn, plain HTML/CSS/JS (no build step), SQLite (stdlib sqlite3), assemblyai SDK, httpx, websockets, pyyaml, pydantic, pytest. Deployed on Render free tier from a public GitHub repo. Everything is keyed by a "room" id so several judges can try it at once. The owner is NON-TECHNICAL and will not read code: you install, run, test, and fix everything yourself; you only hand them copy-paste commands and click instructions. Never print or log secret keys. Never ask the human to write code.

CURRENT STATE: fresh machine, no repo. Folder to create: C:\Users\<current user>\eufisky (use $HOME).

OBJECTIVE: Set up the machine and a runnable skeleton, write the project context into the repo so later phases can read it, and run probes that establish exactly how the AssemblyAI APIs behave with the owner's free credits — so no later phase guesses.

DELIVERABLES:
1. Tooling: check `python --version` (need 3.12+) and `git --version`; if missing, install with `winget install -e --id Python.Python.3.12` and `winget install -e --id Git.Git`, then open a new shell so PATH updates. Create `.venv` and install pinned requirements (`fastapi, uvicorn[standard], websockets, httpx, assemblyai, pyyaml, pydantic, pytest, pytest-asyncio, python-dotenv, Pillow`). Always invoke `.\.venv\Scripts\python.exe` directly.
2. Repo skeleton exactly as in the folder structure below (create empty modules with docstrings where content comes later). `git init`, `.gitignore` (.venv, .env, data/eufisky.db, data/recordings/, __pycache__), `git config` user.name "Eufisky Builder" and a placeholder email if none set.
   Structure: app/{main.py,config.py,db.py,rooms.py,audio.py}, app/phone/{calls.py,ws.py,protocol.md}, app/stt/assemblyai_stream.py, app/rules/{lexicon.yaml,engine.py,normalize.py,loader.py}, app/agent/{backend.py,llm_backend.py,voice_agent_backend.py,policies.py,personas/front_door.py,personas/guardian.py}, app/session/{state_machine.py,context.py,events.py}, app/postcall/{pipeline.py,lemur_prompt.txt}, app/web/{index.html,static/css/app.css,static/js/}, data/{seed.json}, tools/, tests/, docs/, requirements.txt, .env.example, README.md (stub), STATE.md.
3. `docs/PROJECT_CONTEXT.md`: paste the PROJECT CONTEXT paragraph above verbatim plus the WebSocket protocols, REST list, data model and env-var table that follow here (copy them exactly into the file):
   - Phone WS `/ws/phone` — client→server JSON: hello{role,room,caller_phone?}, dial{}, answer{}, hangup{}, text{text} (type-to-talk, treated like speech), mic{on}, dtmf{digit}; binary = PCM16 mono 16 kHz 100 ms. Server→client JSON: state{call_state,badge,monitored}, ring{from_label,trusted}, agent_say{text,agent}, hold{on}, tone{name}, ended{reason}; binary = PCM16 to play.
   - Dashboard WS `/ws/dashboard?room=` JSON events: risk{t_ms,score,signals,evidence}, transcript{speaker,t_ms,text,final}, state{t_ms,from,to,trigger}, level{t_ms,level}, tool{t_ms,agent,name,args}, call{t_ms,event,call_id,classification}.
   - REST: GET /api/health; GET/POST/PATCH/DELETE /api/rooms/{room}/contacts; GET /api/rooms/{room}/calls; GET /api/rooms/{room}/calls/{id}; GET /api/rooms/{room}/messages; POST /api/rooms/{room}/replay; POST /api/rooms/new.
   - SQLite tables: contacts(id,room,phone,label,status trusted|blocked|pending,source,created_at); calls(id,room,from_phone,from_label,classification,started_at,ended_at,final_state,peak_risk,front_door_outcome,guardian_outcome,recording_caller,recording_senior); call_events(id,call_id,t_ms,type,payload_json); risk_samples(call_id,t_ms,score,signals_json); transcript_segments(id,call_id,speaker,t_ms,text,is_final); incidents(id,call_id,summary_json,redacted_transcript,entities_json,created_at); messages(id,room,call_id,from_phone,caller_name,body,callback_number,created_at).
   - Env vars: ASSEMBLYAI_API_KEY, AGENT_BACKEND (auto|voice_agent|llm), GROQ_API_KEY, GEMINI_API_KEY (optional), SENIOR_NAME=Margaret, FAMILY_NAME=Sarah, PORT.
4. `app/main.py`: FastAPI app serving `GET /api/health` → {"ok":true} and `app/web/index.html` at `/` with the title "Eufisky". `app/config.py` loads `.env` with python-dotenv.
5. `.env.example` with every variable and a comment; `.env` created with empty values. Run `notepad .env` so the owner can paste their AssemblyAI key (Human task T2). After they save, verify the key is non-empty WITHOUT printing it.
6. Probes in `tools/` — each prints PASS/FAIL, one-line reason, measured latency, and a sample of the exact wire messages (never the key), and exits non-zero on failure. First browse the official docs (https://www.assemblyai.com/docs — search "Universal-Streaming", "Streaming API", "keyterms_prompt", "Voice Agent API", "LeMUR", "PII redaction", "multichannel") and follow them exactly; note doc URLs used in `docs/ASSUMPTIONS.md`.
   a. `tools/fixtures/`: generate two 8-second 16 kHz mono WAVs using Windows built-in TTS via PowerShell `System.Speech` (caller says "This is Michael from Medicare, your benefits will be suspended today unless we verify your card number"; senior says "Hold on, let me get my purse, my card says four one two three"). If PowerShell TTS fails, synthesize a tone-modulated placeholder and note it.
   b. `probe_realtime_stt.py`: open TWO concurrent Universal-Streaming sessions (16 kHz PCM16, `format_turns` on, keyterms prompt ["Medicare","gift card","Social Security","benefits"]); stream one WAV to each in real time; print each session's words as they arrive with lag (ms since audio sent), and end-of-turn events. PASS if both produce text and median lag < 1500 ms.
   c. `probe_voice_agent.py`: attempt the AssemblyAI Voice Agent API per docs: start a session with instructions "You answer the phone for Margaret. Ask who is calling. Then call take_message." and a JSON-Schema tool `take_message{caller_name,message}`; stream the caller WAV; capture any transcript events, agent text/audio, and the tool call. Record precisely: audio formats accepted, whether transcript events are emitted, whether audio is returned, whether text-only turns can be sent, event names. PASS if a tool call is returned. If the API is not available on this account or docs cannot be found, print FAIL with reason — this is acceptable.
   d. `probe_lemur.py`: upload a 30 s stereo WAV (L=caller fixture, R=senior fixture) for batch transcription with multichannel, `redact_pii` (policies: us_social_security_number, credit_card_number, banking_information, date_of_birth, phone_number, medical_process) with audio redaction, entity_detection, sentiment_analysis; then run a LeMUR task asking for JSON {summary, caller_claim, requests_made, disclosed_by_senior, recommendation}. PASS if a redacted transcript and JSON come back. Report which options were accepted.
   e. `probe_groq.py`: if GROQ_API_KEY is set, call model `llama-3.3-70b-versatile` (fallback `llama-3.1-8b-instant`) at https://api.groq.com/openai/v1/chat/completions with one tool and a message; PASS if a tool call returns. If the key is empty, print SKIPPED (Human task T3 is scheduled before Phase 3).
7. Set `AGENT_BACKEND` in `.env`: `voice_agent` if probe (c) PASSED, else `llm`. Write results to `docs/ASSUMPTIONS.md` (table: item, confirmed behavior, doc URL, decision).
8. `tests/test_smoke.py` hitting `/api/health` with FastAPI TestClient.
9. Ask the owner to create the GitHub repo (Human task T1) named `eufisky`, public; then `git remote add origin <url>` and push `main`. If push prompts for login, tell the owner to click "Sign in with your browser" (Git Credential Manager) — Human task T1 covers it.

CONSTRAINTS: Python 3.12 only; no Node, Docker, Postgres, Redis, Twilio, ngrok. Plain HTML/JS frontend. Use PowerShell syntax (`;` not `&&`). Keep files small and typed. Do not build features beyond this phase.

HUMAN INPUTS NEEDED: ASSEMBLYAI_API_KEY (T2), GitHub repo URL and browser sign-in when pushing (T1). GROQ_API_KEY is optional now (T3). Use placeholders in .env.example; never ask the human to write code.

VERIFICATION (run yourself): `.\.venv\Scripts\python.exe -m pytest -q` → all pass. `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000` then open http://localhost:8000 → page titled Eufisky; http://localhost:8000/api/health → {"ok":true}. Run each probe and paste its PASS/FAIL summary in your final report. `git log --oneline` shows the initial commit; `git remote -v` shows origin.

END OF PHASE — print exactly these three sections:
STATE SNAPSHOT: (a) file tree (2 levels), (b) what works end-to-end, (c) what is stubbed/deferred, (d) env vars in use and which are set (values hidden), (e) exact command to run the app locally and URL(s) to open, (f) probe results and AGENT_BACKEND decision, (g) decisions/defaults you chose. Also save this verbatim to STATE.md and commit.
HUMAN ACTIONS REQUIRED NOW: numbered, click-by-click, each with "Expected result: …". Write "None" if none.
BLOCKERS: anything not completed and why, with your recommendation.

RULES: (1) Do not ask clarifying questions if a reasonable default exists — pick it and note it. (2) Keep the app runnable at the end; never leave it broken. (3) Run all verification yourself; when a human is needed, give ONE copy-paste command or one click and say in plain words what success looks like. (4) Never ask the human to write code or read a stack trace. (5) Never print secrets. (6) Commit at the end and push if a remote exists. (7) Update STATE.md.
```

### PHASE 1 — Simulated phone system, routing, audio bridge
```
ROLE: You are the sole engineer building "Eufisky" on the owner's Windows 11 laptop (PowerShell, file edit, web access). Assume NO memory of prior phases. First read `STATE.md`, `docs/PROJECT_CONTEXT.md`, and `docs/ASSUMPTIONS.md` in the repo at $HOME\eufisky.

PROJECT CONTEXT: Eufisky — a voice AI agent (built on AssemblyAI) that guards an older adult's phone line. Browser-based simulation of a phone line (no telephony): three web "phones" (Caller, Senior "Margaret", Family "Sarah") plus a Family Dashboard, served by ONE FastAPI app. Trusted contacts ring straight through and are never transcribed; unknown callers get a FRONT DOOR voice agent, then bridged monitoring with per-side AssemblyAI Universal-Streaming sessions, a deterministic risk engine, and a GUARDIAN agent that pauses the caller and talks privately with Margaret (tools: resume/family/end/trust). Post-call: batch PII redaction + LeMUR summary. Replay Mode for the dashboard. Agent voice = browser speechSynthesis; agent brain = AssemblyAI Voice Agent API if Phase-0 probe passed else Groq Llama tools. Stack: Python 3.12, FastAPI, uvicorn, plain HTML/CSS/JS, SQLite (stdlib), assemblyai SDK, httpx, websockets, pyyaml, pytest. Render free + public GitHub. Everything keyed by room id. Owner is NON-TECHNICAL; you do all installing/running/testing; give only copy-paste commands and click instructions; never print secrets; never ask the human to write code.

CURRENT STATE:
<<PASTE STATE SNAPSHOT FROM PREVIOUS PHASE HERE>>

OBJECTIVE: Build the working "phone system": three phone pages and a dashboard shell, contact classification, dial/ring/answer/hangup, and real two-way audio relayed through the server — so a trusted call rings straight through (no processing) and an unknown call reaches a temporary placeholder that will become the Front Door in Phase 3.

DELIVERABLES:
1. `app/db.py`: create tables from docs/PROJECT_CONTEXT.md on startup (idempotent); helpers for contacts/calls/events/segments/messages; `data/seed.json` → seed room `demo` (contacts: "Sarah (daughter)" +15550100101 trusted, "Walgreens Pharmacy" +15550100102 trusted); `ensure_room(room)` copies the seed into any new room.
2. `app/rooms.py`: in-memory live state per room: connected phone sockets by role, current call, bridge state. `app/audio.py`: PCM16 helpers, WAV writer, silence/hold-tone generators.
3. `app/phone/calls.py`: call lifecycle with states IDLE, RINGING_SENIOR, TRUSTED_ACTIVE, SCREENING (placeholder for Phase 3), BRIDGED, ENDED. Classification order: blocked → trusted → unknown; withheld/empty caller id → unknown. Trusted: ring senior immediately, badge "Trusted — not monitored", NO STT, NO recording, no dashboard transcript. Unknown: for now, play a short server text `agent_say` "Eufisky screening will run here in the next phase" on the caller tab, then ring the senior; mark `monitored=true`; record each leg's PCM to `data/recordings/<call_id>_<leg>.wav` (this is where Phase 2 attaches STT). Bridge = relay binary frames caller→senior and senior→caller (and family both ways when joined). `hold(leg)` = stop relaying to/from that leg and send `hold{on:true}`. Family leg: `ring_family()` + join (used in Phase 4; implement now, test manually via a temporary dashboard button "Ring family").
4. `app/phone/ws.py`: implement the WS protocol from PROJECT_CONTEXT exactly. `text{text}` messages are accepted and stored as transcript_segments for unknown calls (they will feed STT-equivalent paths later). Heartbeat/ping every 15 s; clean up on disconnect (hang up the call if a party drops).
5. Frontend (vanilla JS, one shared `static/js/audio.js`): mic capture via getUserMedia + AudioWorklet (fallback ScriptProcessor) → downsample to 16 kHz PCM16 → 100 ms binary frames; playback queue for incoming PCM16; `speechSynthesis` speaker with barge-in cancel; a visible **Mic ON/OFF toggle (default OFF)** on every phone page and a **type-to-talk box** ("Type what you'd say") that sends `text{}`; a volume meter. Pages: `index.html` (room picker: shows links to /caller, /senior, /family, /dashboard with `?room=`, button "New room" → POST /api/rooms/new), `caller.html` (caller-ID dropdown: Sarah trusted, Walgreens trusted, Unknown +15550199321, Custom; big Dial/Hang up; status; HOLD banner; agent speech shown as captions), `senior.html` (incoming-call screen with caller label + badge, Answer/Decline, in-call screen, chime element), `family.html` (idle/ringing/joined), `dashboard.html` (Contacts tab with add/trust/block/delete; Live tab placeholder that lists current call state; History tab listing calls). Mobile-friendly, large buttons, clear labels. Serve pages at `/caller`, `/senior`, `/family`, `/dashboard`.
6. Dashboard REST endpoints for contacts and calls per PROJECT_CONTEXT; `/ws/dashboard` broadcasting `call started/ended` and `state` events.
7. `app/phone/protocol.md` documenting message flows for the two call types. Tests: `tests/test_routing.py` (classification order, withheld→unknown; trusted call creates no recording and no segments — the privacy guarantee), `tests/test_calls.py` (state transitions with fake sockets).

CONSTRAINTS: No frameworks, no build step, no extra services. Do not touch probes or docs from Phase 0 except STATE.md/ASSUMPTIONS.md. Latency target for relay: < 250 ms added. Never send trusted-call audio anywhere but the other phone.

HUMAN INPUTS NEEDED: none new. (Owner will do a mic test — Human task T4 — after this phase.)

VERIFICATION: run `.\.venv\Scripts\python.exe -m pytest -q` → pass. Start the server, open http://localhost:8000/caller?room=demo and http://localhost:8000/senior?room=demo in two tabs. Use type-to-talk to avoid mic feedback yourself; then instruct the owner (T4) to: (1) turn Mic ON in the Caller tab only, dial as Sarah, answer on the Senior tab, speak, and hear themselves on the Senior tab with the "Trusted — not monitored" badge; (2) dial as Unknown and hear the placeholder message. Confirm `data/recordings/` gets a WAV for the unknown call and nothing for the trusted call. Confirm dashboard History lists both calls.

END OF PHASE — print exactly: STATE SNAPSHOT (file tree, what works, what's stubbed, env vars, run command + URLs, decisions; save to STATE.md and commit/push), HUMAN ACTIONS REQUIRED NOW (numbered, click-by-click, expected results; "None" if none), BLOCKERS.

RULES: (1) No clarifying questions when a default exists — choose and note it. (2) Do not refactor Phase 0; extend it. (3) App must run and be demoable at the end; never leave it broken. (4) Verify yourself; when a human is needed give ONE command/click with plain-English success criteria. (5) Never ask the human to write code or read errors. (6) PowerShell syntax; call `.\.venv\Scripts\python.exe` directly. (7) Never print secrets. (8) Commit and push at the end; update STATE.md.
```

### PHASE 2 — Monitoring: AssemblyAI streaming, rule engine, live risk meter
```
ROLE: Sole engineer building "Eufisky" on the owner's Windows 11 laptop (PowerShell, file edit, web). NO memory of prior phases. First read `STATE.md`, `docs/PROJECT_CONTEXT.md`, `docs/ASSUMPTIONS.md`, `app/phone/protocol.md`.

PROJECT CONTEXT: Eufisky — a voice AI agent (built on AssemblyAI) that guards an older adult's phone line, as a browser-based phone-line simulation: Caller/Senior/Family web phones + Family Dashboard on ONE FastAPI app. Trusted contacts ring straight through, never transcribed. Unknown callers: FRONT DOOR agent (Phase 3), then bridged and silently monitored — each side's audio goes to its own AssemblyAI Universal-Streaming session (speaker-labeled words), a DETERMINISTIC rule engine scores risk 0–100, a state machine escalates L1 (≥40 chime) / L2 (≥65, or PII disclosure with ≥45, or payment_method+compliance_cue → GUARDIAN, Phase 4) / L3 (≥90). Post-call PII redaction + LeMUR summary (Phase 5). Agent voice = browser speechSynthesis; brain = Voice Agent API if probe passed else Groq. Stack: Python 3.12, FastAPI, plain HTML/JS, SQLite, assemblyai SDK, pyyaml, pytest. Render + GitHub. Room-keyed. Owner is NON-TECHNICAL; you do everything; never print secrets; never ask the human to write code.

CURRENT STATE:
<<PASTE STATE SNAPSHOT FROM PREVIOUS PHASE HERE>>

OBJECTIVE: Make unknown bridged calls "heard": one AssemblyAI real-time session per leg producing speaker-labeled words, a deterministic rule engine turning those words into a live risk score with evidence, and a dashboard Live tab that shows the transcript and a moving risk meter. No interventions yet except the L1 chime.

DELIVERABLES:
1. `app/stt/assemblyai_stream.py`: class `STTStream(speaker, keyterms, sample_rate=16000)` wrapping the Universal-Streaming WebSocket exactly as confirmed in docs/ASSUMPTIONS.md (auth header, params incl. `format_turns` and keyterms prompt, binary PCM sends every 100 ms, parse Turn/word messages, expose async iterator of `WordEvent{speaker,text,t_ms,final}` and `turn_end` events). Auto-reconnect once on drop with a 2 s replay buffer. Sessions open only when an unknown call becomes BRIDGED (and during SCREENING in Phase 3) and close on hold/end. Type-to-talk `text{}` messages bypass STT and are injected as final WordEvents for that speaker (same code path downstream).
2. `app/rules/lexicon.yaml` — families with speaker, weight, half_life_s, cap=3, and ≥12 phrases each (US elder-scam vocabulary): authority_impersonation (caller, 20, 120: medicare, social security, irs, sheriff, warrant, fraud department, federal agent, your bank's fraud team, …), urgency (caller, 15, 60: right now, immediately, today only, suspended, last chance, before midnight, act now, …), secrecy (caller, 25, 120: don't tell anyone, between us, don't hang up, stay on the line, don't call your daughter, …), payment_method (caller, 30, 180: gift card, green dot, apple card, bitcoin, wire transfer, zelle, western union, cash app, money order, …), pii_request (caller, 25, 120: account number, medicare number, social security number, date of birth, pin, password, card number, number on your card, verify your identity, …), remote_access (caller, 30, 180: anydesk, teamviewer, download, control your computer, screen share, install this, …), family_emergency (caller, 25, 120: grandson, granddaughter, accident, jail, bail, hospital, lawyer, don't tell his parents, …), threat (caller, 20, 90: arrested, legal action, police will come, lose your benefits, cut off, disconnected, …), compliance_cue (senior, 15, 60: let me get my purse, hold on let me find, my card is, let me read it, it says, one moment I'll get it, …), benign (caller, −20, 180: appointment reminder, prescription is ready, calling from dr, confirm your appointment, this is your neighbor, delivery, …). Patterns: pii_disclosure (senior, 40, 300): regex for ≥4-digit sequences after number-word normalization and month-day-year dates. Combos: {authority_impersonation, urgency, pii_request} any 2 → +15; payment_method+urgency → +20; pii_disclosure + (pii_request or authority_impersonation) → +25.
3. `app/rules/normalize.py` (lowercase, strip punctuation, number-words→digits incl. "four one two three"→"4123", small synonyms) and `app/rules/engine.py`: `RuleEngine(lexicon, seed_score=0)`, `ingest(WordEvent) -> RiskUpdate|None`, `tick(t_ms) -> RiskUpdate`; score = clamp(Σ w·min(hits,cap)·2^(−Δt/half_life) + combos, 0, 100); match on a rolling 12-word window per speaker; dedupe (speaker, phrase, ±2 s); `RiskUpdate{t_ms,score,active_signals,evidence[{speaker,family,phrase,t_ms}],flags}`. Tick every 500 ms while bridged.
4. `app/session/state_machine.py` (partial): states IDLE, SCREENING, DIALING_SENIOR, INTRO, BRIDGED, GUARDIAN, FAMILY_CONF, WRAPUP, POST_CALL, DONE; implement BRIDGED + L1 now: when score ≥ 40 and not yet nudged, play a soft chime + `agent_say` "Eufisky is listening." on the Senior tab only, once. Compute trigger_L2/L3 booleans and publish `level` events, but do NOT intervene yet (log "L2 would fire"). `app/session/events.py`: publish every risk update, transcript segment, state, level to the room's dashboard sockets and persist (risk_samples, transcript_segments, call_events). Track `peak_risk` on the call.
5. Dashboard Live tab: speaker-labeled rolling transcript (caller left, Margaret right), risk meter 0–100 with color bands at 40/65/90, signal chips with evidence tooltips, a state/level timeline. History tab: per-call peak risk. Calls API returns samples + segments.
6. Harness: `tests/scripts/scam/` 60 scripts and `tests/scripts/benign/` 40 scripts as `t_ms|speaker|text` lines (varied: Medicare, SSA, IRS, grandparent, tech support, bank fraud, utility shutoff, lottery, charity; benign: pharmacy, doctor's office, real grandson chatting, neighbor, church, delivery, insurance renewal, survey, friend). `tests/test_rules.py` replays them through normalize+engine+trigger logic and asserts scam L2 recall ≥ 90 %, benign L2 false-trigger ≤ 5 %, benign L1 ≤ 15 %, printing a precision/recall table. Adjust weights/phrases until it passes; record final numbers in STATE.md.

CONSTRAINTS: No LLM anywhere in scoring. Keep trusted calls untouched (add a test asserting no STT session is created for trusted calls). Do not change the phone WS protocol. Keyterms list = lexicon phrases ≤ 3 words + org names + senior/family first names, capped to the limit noted in ASSUMPTIONS.md.

HUMAN INPUTS NEEDED: none (ASSEMBLYAI_API_KEY already set — T2).

VERIFICATION: pytest passes with the harness table printed. Live: start server; Caller tab dial as Unknown → answer on Senior tab → in the Caller tab type-to-talk "This is Medicare, your benefits will be suspended today unless we verify" then "read me the number on your medicare card"; in Senior tab type "hold on let me get my purse, four one two three". Dashboard Live must show labeled lines within ~1 s, risk climbing past 40 (chime on Senior tab) and past 65 with the "L2 would fire" log line. Then repeat with real microphone via the owner (T4 step 3) and confirm spoken words appear labeled. Report measured word lag.

END OF PHASE — print exactly: STATE SNAPSHOT (file tree, what works, what's stubbed, env vars, run command + URLs, harness numbers, decisions; save to STATE.md, commit/push), HUMAN ACTIONS REQUIRED NOW (numbered click-by-click with expected results, or "None"), BLOCKERS.

RULES: (1) Defaults over questions; note decisions. (2) Do not refactor earlier phases. (3) Demoable and unbroken at the end. (4) Verify yourself; ONE command/click for humans with plain success criteria. (5) No code or stack traces for the human. (6) PowerShell syntax; `.\.venv\Scripts\python.exe`. (7) No secrets in output. (8) Commit, push, update STATE.md.
```

### PHASE 3 — Front Door voice agent
```
ROLE: Sole engineer building "Eufisky" on the owner's Windows 11 laptop (PowerShell, file edit, web). NO memory of prior phases. First read `STATE.md`, `docs/PROJECT_CONTEXT.md`, `docs/ASSUMPTIONS.md`, `app/phone/protocol.md`.

PROJECT CONTEXT: Eufisky — a voice AI agent (built on AssemblyAI) that guards an older adult's phone line; browser-based phone simulation (Caller/Senior/Family phones + Dashboard) on ONE FastAPI app. Trusted contacts ring straight through, never transcribed. Unknown callers meet the FRONT DOOR voice agent (this phase): it asks who/why and calls exactly one tool — connect_caller / take_message / decline; a server-side policy overrides connect if the caller's words already scored ≥40. Connected calls are bridged and monitored by per-leg AssemblyAI Universal-Streaming + deterministic rule engine (done in Phase 2); GUARDIAN intervention is Phase 4; post-call redaction + LeMUR is Phase 5. Agent voice = browser speechSynthesis on the listening tab (server sends agent_say). Agent brain: `AGENT_BACKEND=voice_agent` (AssemblyAI Voice Agent API, only if the Phase-0 probe PASSED) or `llm` (Groq `llama-3.3-70b-versatile` via OpenAI-compatible chat completions with tools; Gemini backup). Stack: Python 3.12, FastAPI, plain HTML/JS, SQLite, assemblyai SDK, httpx, pytest. Render + GitHub. Room-keyed. Owner is NON-TECHNICAL; you do everything; never print secrets; never ask the human to write code.

CURRENT STATE:
<<PASTE STATE SNAPSHOT FROM PREVIOUS PHASE HERE>>

OBJECTIVE: Replace the Phase-1 placeholder with a real Front Door conversation: the unknown caller hears the agent, speaks (or types), the agent responds using AssemblyAI turn detection to know when the caller finished, and ends with exactly one tool call that the server executes — connect (ring Margaret with a short intro), take a message, or decline.

DELIVERABLES:
1. `app/agent/backend.py`: `AgentBackend` protocol: `start(instructions, tools, context)`, `on_user_text(text)` (called on each final turn from STT or type-to-talk), `events()` yielding `say{text}` and `tool_call{name,args,id}`, `tool_result(id, result)`, `close()`. Implement `app/agent/llm_backend.py` FIRST (must work): keeps conversation history, calls Groq chat completions with tools (`tool_choice=auto`), 8 s timeout, one retry, Gemini fallback if GEMINI_API_KEY set; if all fail, deterministic fallback script (ask name → ask purpose → take_message). Then, ONLY if ASSUMPTIONS.md says the Voice Agent probe PASSED, implement `voice_agent_backend.py` behind the same protocol (stream caller PCM to it, forward its text/audio to the caller tab — if it returns audio, play that instead of speechSynthesis) with an automatic fallback to llm_backend on connect failure > 3 s. `AGENT_BACKEND=auto` picks per ASSUMPTIONS.md.
2. `app/agent/personas/front_door.py` — use this text verbatim (templated with SENIOR_NAME):
   "You are the phone assistant for {senior_name}. You answer calls from people she does not know. Your job: learn who is calling and why, then call exactly one tool. Be warm, brief, plain-spoken; each reply at most two short sentences. Rules: Ask for the caller's name and the reason if not given. Call connect_caller only when the purpose is clear and ordinary (pharmacy, doctor's office, neighbor, delivery, friend). If the caller claims to be from the government, a bank, the police, Medicare, Social Security, tech support, or says it is urgent or an emergency: do NOT connect on that basis; ask for a callback number and call take_message. If the caller says they are family, ask their first name and relation, then call take_message (you have not been told to expect anyone). Never say whether {senior_name} is home, where she lives, who her family is, or anything about her; if asked, say you can only take a message. Do not argue; if pressured say 'I understand. I'll pass along a message,' and call take_message. For sales calls, recordings, or abusive callers call decline. Never call more than one tool. After the tool result, say one short closing sentence and stop. Start by saying: 'Hello, you've reached {senior_name}'s line. May I ask who's calling and what it's regarding?'"
   Tools (JSON Schema): connect_caller{caller_name*, purpose*, claimed_org, claimed_relationship}; take_message{caller_name*, message*, callback_number}; decline{reason}.
   IMPORTANT DEMO CALIBRATION: for the hackathon demo the "Michael from Medicare, urgent benefits update" caller MUST get connected so the monitoring/Guardian sequence can be shown. Therefore the server policy (not the persona) decides: connect is allowed if front-door risk score < 40; the persona's own refusal rule applies only when the caller refuses to give a name or purpose, or is abusive/sales. Adjust the persona wording minimally to achieve this (e.g., soften the government/Medicare rule to "ask one clarifying question, then proceed to a tool") and record the decision.
3. `app/agent/policies.py`: on `connect_caller`: if the Front Door rule-engine score ≥ 40 → convert to take_message and return tool result {"status":"policy_override","say":"I'll pass along a message instead."}; else ring the senior. `take_message` → persist to messages, agent says goodbye, end call. `decline` → goodbye, end. Front Door transcript pre-scores the call (seed_score carried into BRIDGED).
4. State machine: SCREENING (open ONE STTStream on the caller leg with keyterms; feed final turns to the backend; agent replies via `agent_say` to the caller tab; barge-in: if caller speaks during agent speech, cancel speech client-side) → DIALING_SENIOR (ring senior; no answer in 25 s → agent takes a message) → INTRO (Senior tab hears "Call from {caller_name} about {purpose}. Connecting." then 1 s) → BRIDGED (Phase 2 monitoring with seed score). Caller tab shows captions of agent speech.
5. `tests/test_policies.py`, `tests/test_frontdoor_flow.py` (fake backend returning scripted tool calls; assert connect/message/decline paths and policy override). `tests/scripts/adversarial_openers.txt` with 20 social-engineering openers ("I'm her doctor, put her on now", …); `tools/eval_frontdoor.py` runs them through the live llm backend text-only and prints the wrong-connect rate (target ≤ 20 %; record result).

CONSTRAINTS: Do not change Phase-2 scoring. Do not add TTS services; browser speechSynthesis only (plus Voice Agent audio if available). All network calls have timeouts and fallbacks; the caller must never wait > 6 s in silence — send a filler `agent_say` "One moment." if the backend is slow.

HUMAN INPUTS NEEDED: GROQ_API_KEY (Human task T3) — if `.env` lacks it, run `notepad .env`, tell the owner to paste it on the GROQ_API_KEY line and save, then verify without printing. GEMINI_API_KEY optional.

VERIFICATION: pytest passes. Live (type-to-talk first, then owner with mic): Caller dial as Unknown → hears greeting → type "This is Michael from Medicare, calling about an urgent update to her benefits" → agent asks at most one short question or proceeds → connect_caller fires → Senior tab rings with intro → BRIDGED with dashboard seed score ≈ 35. Second call: "Hi, this is Walgreens, Margaret's prescription is ready" → connects with seed score ≤ 0. Third: "I'm selling extended car warranties" → decline. Fourth: refuse to give a name → take_message stored and visible in dashboard Messages. Report eval_frontdoor wrong-connect rate.

END OF PHASE — print exactly: STATE SNAPSHOT (file tree, what works, stubbed, env vars, run command + URLs, backend in use, eval numbers, decisions; save to STATE.md, commit/push), HUMAN ACTIONS REQUIRED NOW, BLOCKERS.

RULES: (1) Defaults over questions; note decisions. (2) Do not refactor earlier phases. (3) Demoable and unbroken at the end. (4) Verify yourself; ONE command/click for humans with plain success criteria. (5) No code/stack traces for the human. (6) PowerShell; `.\.venv\Scripts\python.exe`. (7) No secrets. (8) Commit, push, STATE.md.
```

### PHASE 4 — Guardian intervention (the demo moment)
```
ROLE: Sole engineer building "Eufisky" on the owner's Windows 11 laptop (PowerShell, file edit, web). NO memory of prior phases. First read `STATE.md`, `docs/PROJECT_CONTEXT.md`, `docs/ASSUMPTIONS.md`, `app/phone/protocol.md`, `app/session/state_machine.py`.

PROJECT CONTEXT: Eufisky — a voice AI agent (built on AssemblyAI) guarding an older adult's phone line; browser-based phone simulation (Caller/Senior/Family phones + Dashboard) on ONE FastAPI app. Trusted contacts ring straight through, never transcribed. Unknown callers: FRONT DOOR agent (done) → bridged call monitored by per-leg AssemblyAI Universal-Streaming + deterministic rule engine with L1/L2/L3 triggers (done). THIS PHASE: the GUARDIAN — on L2 the caller is put on hold and the agent talks privately to Margaret on the Senior tab, then executes exactly one tool: resume_call / conference_family / end_call{block_number} / add_to_trusted{label}. L3 (≥90) makes Guardian recommend family. Post-call PII redaction + LeMUR is Phase 5. Agent voice = browser speechSynthesis; brain = AGENT_BACKEND (voice_agent or llm via Groq) through the AgentBackend protocol. Stack: Python 3.12, FastAPI, plain HTML/JS, SQLite, assemblyai SDK, httpx, pytest. Render + GitHub. Room-keyed. Owner is NON-TECHNICAL; you do everything; never print secrets; never ask the human to write code.

CURRENT STATE:
<<PASTE STATE SNAPSHOT FROM PREVIOUS PHASE HERE>>

OBJECTIVE: Complete the end-to-end demo: on trigger the caller instantly hears hold music and sees HOLD, Margaret hears a calm Guardian explaining exactly what happened and offering two options, and her choice is executed — including ringing the Family tab and joining it to the call, or ending the call and blocking the number. Every step must be reversible and must never depend on the LLM to decide *when* to act.

DELIVERABLES:
1. State machine completion: BRIDGED ─trigger_L2→ GUARDIAN; GUARDIAN ─resume_call→ BRIDGED (cooldown 60 s; next L2 threshold +10 up to 85); ─conference_family→ FAMILY_CONF (ring Family tab; on answer join the bridge; caller stays on hold unless resumed; add a "Resume caller" and "End call" button on the Family tab); ─end_call→ WRAPUP (block number if block_number, default true); ─add_to_trusted→ contact trusted (if peak_risk ≥ 85 store as pending instead) then resume; any hangup → WRAPUP. trigger_L2 := score ≥ 65 OR (pii_disclosure flag AND score ≥ 45) OR (payment_method AND compliance_cue active). trigger_L3 := score ≥ 90 → if in GUARDIAN/FAMILY_CONF, Guardian context marks recommendation "bring in family".
2. Timing guarantee: on trigger, synchronously (before any network call) (a) set bridge to GUARDIAN mode (stop relaying caller↔senior; both STT sessions paused), (b) send `hold{on:true}` + `tone{hold_music}` to the Caller tab, (c) send `agent_say` "One moment, Margaret." to the Senior tab; then start the Guardian backend session with a 3 s connect timeout. If the backend fails/times out: fallback pre-written Guardian script chosen by top signal + on-screen buttons on the Senior tab ("End the call", "Bring in Sarah", "Continue the call") and DTMF 1/2/3 — same tools executed.
3. `app/agent/personas/guardian.py` — use verbatim (templated):
   "You are {senior_name}'s phone guardian. You interrupted her call because it showed signs of a scam. The other caller is on hold and cannot hear either of you. Speak calmly and slowly, in short plain sentences. No technical words, percentages, or the word 'algorithm'. Do this in order: 1. Say you paused the call and why, using only the facts in CONTEXT. Example: 'I paused the call. This person said they were from Medicare and asked for your card number. Medicare never calls to ask for that.' 2. Ask what she would like to do, offering at most two options — usually: end the call, or bring {family_name} on the line. 3. Wait for her answer, then call exactly one tool. If she wants to keep talking to the caller, call resume_call — it is her decision; do not argue. If she is unsure or upset, gently recommend bringing {family_name} on and call conference_family if she agrees. If she says she knows this person personally and wants them trusted, call add_to_trusted. 4. After the tool result, say one reassuring sentence and stop. Never scold her, never rush her, never mention that you were listening to the whole call. CONTEXT: Caller name given: {caller_name}. Caller claimed to be: {claim}. What raised concern: {trigger_plain}. Things the caller asked for: {requests}. What {senior_name} has shared so far: {disclosed}. Family contact: {family_name} ({family_role}). Recommendation: {recommendation}."
   Tools: resume_call{}, conference_family{keep_caller_on_hold:bool=true}, end_call{block_number:bool=true}, add_to_trusted{label*}.
   `app/session/context.py` maps evidence to plain English (pii_request+authority → "asked for your Medicare number while claiming to be from Medicare"; payment_method → "asked you to buy gift cards"; family_emergency → "said a family member is in trouble and needs money"; remote_access → "asked to get onto your computer"; pii_disclosure → "you had started reading out numbers"), lists requests, and summarizes disclosure ("none", "started reading digits").
4. Guardian session plumbing: Senior-leg STT session resumes to hear Margaret's answer (type-to-talk works too); agent speech to Senior tab only; the Caller tab never receives any of it (add a test). Dashboard Live shows state GUARDIAN with a banner, the tool chosen, and a "Join call" button on the dashboard that triggers conference_family.
5. Caller tab: HOLD screen + looping hold tone (generated client-side), "Please hold" caption; on resume, normal audio returns. Family tab: ring screen with reason line ("Eufisky paused a risky call with 'Michael from Medicare'"), Answer joins.
6. WRAPUP: close sessions, finalize recordings, set final_state/peak_risk/guardian_outcome, auto-block if peak_risk ≥ 85 and not trusted, publish `call ended`. (Post-call analysis is Phase 5 — leave a hook `postcall.enqueue(call_id)` that currently no-ops.)
7. Tests: `tests/test_state_machine.py` covers every transition, trigger formulas, cooldown escalation, "no LLM output can cause a transition" (transitions only from RiskUpdate + tool events), and the caller-isolation guarantee; `tests/test_context.py` for plain-English mapping.

CONSTRAINTS: Do not alter rule weights. All decisions on *when* to escalate are deterministic. Never more than one agent session per call at a time. Keep type-to-talk working for every role (it is the demo insurance).

HUMAN INPUTS NEEDED: none new.

VERIFICATION: pytest passes. Live run (type-to-talk, then owner with mic per Human task T5): Unknown → Medicare opener → connected → "benefits suspended today unless we verify" → chime → "read me the number on your medicare card" → Senior types "hold on let me get my purse four one two three" → HOLD on Caller tab within 0.5 s, Guardian speaks on Senior tab within 3 s → Senior types "get Sarah" → Family tab rings → answer → joined → Caller hangs up → dashboard shows call ended, number blocked, Contacts shows +15550199321 blocked. Repeat choosing "continue" → resume works; repeat with simulated backend failure (env `SIMULATE_AGENT_FAIL=1`) → fallback buttons appear and work.

END OF PHASE — print exactly: STATE SNAPSHOT (save to STATE.md, commit/push), HUMAN ACTIONS REQUIRED NOW, BLOCKERS.

RULES: (1) Defaults over questions; note decisions. (2) Do not refactor earlier phases. (3) Demoable and unbroken at the end. (4) Verify yourself; ONE command/click for humans with plain success criteria. (5) No code/stack traces for the human. (6) PowerShell; `.\.venv\Scripts\python.exe`. (7) No secrets. (8) Commit, push, STATE.md.
```

### PHASE 5 — Post-call analysis, replay, seed data, hardening
```
ROLE: Sole engineer building "Eufisky" on the owner's Windows 11 laptop (PowerShell, file edit, web). NO memory of prior phases. First read `STATE.md`, `docs/PROJECT_CONTEXT.md`, `docs/ASSUMPTIONS.md`.

PROJECT CONTEXT: Eufisky — a voice AI agent (built on AssemblyAI) guarding an older adult's phone line; browser-based phone simulation (Caller/Senior/Family phones + Dashboard) on ONE FastAPI app. Trusted contacts untouched; unknown callers → FRONT DOOR agent → bridged monitoring via per-leg AssemblyAI Universal-Streaming + deterministic rule engine → GUARDIAN intervention with tools (all done). THIS PHASE: after a call, AssemblyAI batch transcription with PII redaction and LeMUR incident summary; Replay Mode; seeded history; error handling and polish so the demo is reliable. Stack: Python 3.12, FastAPI, plain HTML/JS, SQLite, assemblyai SDK, pytest. Render + GitHub. Room-keyed. Owner is NON-TECHNICAL; you do everything; never print secrets; never ask the human to write code.

CURRENT STATE:
<<PASTE STATE SNAPSHOT FROM PREVIOUS PHASE HERE>>

OBJECTIVE: Turn each monitored call into a redacted, summarized incident on the dashboard; make the whole demo replayable without microphones; and harden everything a judge might click.

DELIVERABLES:
1. `app/postcall/pipeline.py` (background task on WRAPUP, never blocks the call): mix caller/senior WAVs to stereo (L/R); AssemblyAI batch transcription with the options confirmed in ASSUMPTIONS.md (multichannel, redact_pii with policies us_social_security_number, credit_card_number, banking_information, date_of_birth, phone_number, medical_process, email_address, location; audio redaction; entity_detection; sentiment_analysis); LeMUR task using `lemur_prompt.txt` → strict JSON {summary, caller_claim, requests_made[], disclosed_by_senior, intervention, outcome, recommendation}; persist `incidents`, store redacted audio path; delete raw WAVs after success. Fallbacks: if batch fails, use the live transcript with a local regex redaction of digit runs; if LeMUR fails, build the summary from call_events + top signals (template). Time budget: if batch+LeMUR integration exceeds 90 minutes of your effort, ship the fallbacks and note it.
2. Dashboard History: incident cards (peak risk badge, summary, caller claim, what was asked, intervention/outcome, recommendation, redacted transcript viewer, redacted audio player if available, risk-over-time sparkline from risk_samples, timeline of events). Messages tab lists take_message records.
3. Replay Mode: `data/demo_call.json` capturing a full ideal run (all dashboard events with timing, plus Senior/Caller captions); `POST /api/rooms/{room}/replay` republishes events at chosen speed; dashboard "▶ Replay demo call" button; `tools/replay.py` CLI. Also `tools/record_replay.py` that exports any real call to this format so the owner can capture a great live run as the replay file.
4. `data/seed.json`: add 3 historical incidents for room `demo` (Medicare scam blocked, grandparent scam ended by Margaret, benign pharmacy call) so History isn't empty on first load; add 2 messages.
5. Hardening: graceful handling when a tab disconnects mid-call; WS reconnect on the dashboard; server never crashes on malformed messages; all external calls have timeouts; startup self-check endpoint `/api/health` reports assemblyai_key_present, agent_backend, db_ok; a `?room=` that doesn't exist auto-seeds. Add a landing page intro (what Eufisky is, three role cards, "Try the scam demo" guided steps, note that mic needs permission, and "Use type-to-talk if you don't have a mic"). Basic responsive styling. Remove any leftover temporary buttons.
6. `docs/DEMO_SCRIPT.md`: exact click-by-click 3-minute script with the words to say (trusted call → benign Walgreens → Medicare scam → history card) and the replay fallback.
7. Tests: `tests/test_postcall.py` with fakes (asserts raw WAV deletion on success, fallbacks on failure), `tests/test_replay.py`.

CONSTRAINTS: Do not change scoring, personas, or triggers. No new services.

HUMAN INPUTS NEEDED: none new.

VERIFICATION: pytest passes. Live: complete a scam run (type-to-talk) → within 60 s the History card appears with a LeMUR summary (or template, flagged) and redacted digits (e.g., "####"); raw WAVs removed; dashboard Replay animates the full sequence on a fresh room; landing page guides a first-time visitor; `/api/health` shows all checks true.

END OF PHASE — print exactly: STATE SNAPSHOT (save to STATE.md, commit/push), HUMAN ACTIONS REQUIRED NOW, BLOCKERS.

RULES: (1) Defaults over questions; note decisions. (2) Do not refactor earlier phases. (3) Demoable and unbroken at the end. (4) Verify yourself; ONE command/click for humans with plain success criteria. (5) No code/stack traces for the human. (6) PowerShell; `.\.venv\Scripts\python.exe`. (7) No secrets. (8) Commit, push, STATE.md.
```

### PHASE 6 — Deploy to Render (public URL)
```
ROLE: Sole engineer building "Eufisky" on the owner's Windows 11 laptop (PowerShell, file edit, web). NO memory of prior phases. First read `STATE.md`, `docs/PROJECT_CONTEXT.md`.

PROJECT CONTEXT: Eufisky — a voice AI agent (built on AssemblyAI) guarding an older adult's phone line; browser-based phone simulation (Caller/Senior/Family phones + Dashboard) on ONE FastAPI/uvicorn app with SQLite, AssemblyAI Universal-Streaming/batch/LeMUR (+ Voice Agent API or Groq for agent brains), plain HTML/JS. Fully working locally. THIS PHASE: publish it at a public HTTPS URL on Render's free tier from the public GitHub repo so judges can open it. Owner is NON-TECHNICAL; you do everything you can; give click-by-click instructions for the Render website; never print secrets.

CURRENT STATE:
<<PASTE STATE SNAPSHOT FROM PREVIOUS PHASE HERE>>

OBJECTIVE: Make the app deployable with one Blueprint on Render free tier, push to GitHub, guide the owner through the ~8 clicks, and verify the public URL runs the full demo (mic works because it's HTTPS).

DELIVERABLES:
1. `render.yaml`: one web service, `runtime: python`, `plan: free`, `buildCommand: pip install -r requirements.txt`, `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT --ws websockets`, env vars: PYTHON_VERSION=3.12.x, AGENT_BACKEND (value from .env), SENIOR_NAME, FAMILY_NAME, and `ASSEMBLYAI_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY` marked `sync: false` (entered by the owner in the Render UI). `healthCheckPath: /api/health`.
2. Make the app Render-safe: SQLite path in a writable dir (`/tmp/eufisky.db` when env RENDER is set) and re-seed on boot (free tier has no persistent disk — note in README); recordings in `/tmp`; bind to `$PORT`; CORS not needed (same origin); WS URLs built from `location.host` with wss when https; logging to stdout; a keep-warm hint on the landing page ("first load may take 40 s").
3. Push to GitHub. Then output click-by-click instructions for Human task T6 (Render: sign up with GitHub → New + → Blueprint → select repo `eufisky` → Apply → enter the three secret env vars when prompted → Deploy). Ask the owner to paste the resulting URL.
4. After the owner pastes the URL: verify `https://<url>/api/health` returns ok; open the dashboard/caller/senior pages via the URL with a browser automation or curl where possible; run `tools/smoke_public.py <url>` which checks health, static pages, WS handshake for /ws/dashboard, and the replay endpoint. Update README "Live demo" link and `docs/DEMO_SCRIPT.md` with the public URLs.
5. Add `tools/warm.py <url>` (pings health every 5 min while running) and tell the owner to run it 15 minutes before any live demo.

CONSTRAINTS: No paid plans, no credit card, no other hosts unless Render fails twice (then fall back to Koyeb or Hugging Face Spaces (Docker-free "Gradio"? no — use Spaces with a plain Python SDK app only if it supports WebSockets; prefer Koyeb) and document).

HUMAN INPUTS NEEDED: Render account via GitHub login and entering ASSEMBLYAI_API_KEY / GROQ_API_KEY in Render's env var form (Human task T6). Never ask them to type keys in chat if avoidable.

VERIFICATION: `tools/smoke_public.py` all green; the owner completes one full scam run on the public URL from two devices (laptop = Senior + Dashboard, phone = Caller) — Human task T6 step 9 — and reports "it worked".

END OF PHASE — print exactly: STATE SNAPSHOT (save to STATE.md, commit/push; include the public URL), HUMAN ACTIONS REQUIRED NOW, BLOCKERS.

RULES: (1) Defaults over questions; note decisions. (2) Do not refactor earlier phases. (3) Never leave local or deployed app broken. (4) Verify yourself; ONE click/command at a time for the human with plain success criteria. (5) No code/stack traces for the human. (6) PowerShell; `.\.venv\Scripts\python.exe`. (7) No secrets. (8) Commit, push, STATE.md.
```

### PHASE 7 — README, architecture doc, slides, cover image, demo script, submission text
```
ROLE: Sole engineer + technical writer for "Eufisky" on the owner's Windows 11 laptop (PowerShell, file edit, web). NO memory of prior phases. First read `STATE.md`, `docs/PROJECT_CONTEXT.md`, `docs/ASSUMPTIONS.md`, `docs/DEMO_SCRIPT.md`, and skim the code.

PROJECT CONTEXT: Eufisky — a voice AI agent built on AssemblyAI that guards an older adult's phone line: Front Door agent answers strangers; connected calls are monitored via per-leg AssemblyAI Universal-Streaming (speaker-labeled, keyterm-boosted) + a deterministic risk engine; the Guardian agent pauses the caller and talks privately with the senior, acting via tool calls; post-call PII redaction and LeMUR summaries; trusted contacts never processed. Browser-based phone simulation deployed on Render, public GitHub repo. Hackathon judging criteria: Application of Technology, Presentation, Business Value, Originality. Submission needs: title, short + long description, tags, cover image, video, slide deck, repo, live URL. Owner is NON-TECHNICAL; produce everything ready to copy-paste; never print secrets.

CURRENT STATE:
<<PASTE STATE SNAPSHOT FROM PREVIOUS PHASE HERE>>

OBJECTIVE: Produce every non-video submission asset so the owner only has to copy, click, and record.

DELIVERABLES:
1. `README.md`: hero line, 4-bullet "what it does", live demo link + 60-second try-it steps (with type-to-talk note), architecture diagram (ASCII + a PNG generated with Pillow at `docs/architecture.png`), "How AssemblyAI is used" table (feature → where → why), privacy design, limitations (simulated line; real telephony/Twilio as roadmap; caller-ID spoofing; English only), local setup in ≤ 8 commands, tests, license (MIT).
2. `docs/ARCHITECTURE.md` (components, state machine diagram, risk formula, escalation ladder, data model) and `docs/BUSINESS.md` (problem size, buyer, pricing idea, go-to-market via telcos/insurers/senior living, roadmap).
3. `app/web/slides.html`: a reveal.js (CDN) deck at `/slides`, 9 slides: title; the problem (one statistic, one story); demo preview; how it works (diagram); AssemblyAI in Eufisky (table); why it's original; business value; roadmap (real phone lines, Spanish, family app); team + links. Printable to PDF (include reveal print styles; instruct `?print-pdf`).
4. `tools/make_cover.py` → `docs/cover.png` 1920×1080: dark background, shield glyph drawn with Pillow, "Eufisky", subtitle "A voice agent that guards Mom's phone line", "Built on AssemblyAI"; also a 1200×630 variant.
5. `docs/SUBMISSION.md` with ready-to-paste: project title; short description (≤ 140 chars); long description (≈ 350 words: problem, solution, how AssemblyAI is used, what's unique, business value, what's next); tags (Voice AI, AssemblyAI, Real-time STT, LeMUR, Elder care, Fraud prevention, FastAPI, Accessibility); the demo URL(s) and repo URL; a 90-second pitch script; a judge Q&A list (10 questions with plain answers); the 3-minute video shot list with exact spoken lines and which tab is on screen.
6. Final polish pass: favicon, page titles, consistent naming, `python -m pytest -q` green, `ruff` clean if installed. Tag the release `v1.0-hackathon`.

CONSTRAINTS: Do not change features or personas. Keep claims accurate to what actually works (read STATE.md; if LeMUR fell back to a template, say "summary generation with LeMUR (with a template fallback)").

HUMAN INPUTS NEEDED: none (team names and any links for the last slide — ask once; default to "Team Eufisky").

VERIFICATION: Open `/slides` and `/slides?print-pdf` locally; cover.png and architecture.png exist and open; README renders on GitHub; all links in SUBMISSION.md resolve.

END OF PHASE — print exactly: STATE SNAPSHOT (save to STATE.md, commit/push), HUMAN ACTIONS REQUIRED NOW (include: how to print the slides to PDF, where the cover image is, and which file to copy submission text from), BLOCKERS.

RULES: (1) Defaults over questions. (2) Don't refactor. (3) App remains demoable. (4) Verify yourself. (5) No code for the human. (6) PowerShell. (7) No secrets. (8) Commit, push, STATE.md.
```

### PHASE S — Stretch (only after Phase 7 is done and the video is recorded)
```
ROLE: Sole engineer for "Eufisky" (see STATE.md, docs/PROJECT_CONTEXT.md). NO memory of prior phases. Read the repo first.

PROJECT CONTEXT: Eufisky is a finished, deployed, submitted-ready voice agent on AssemblyAI that guards an older adult's phone line (Front Door + monitoring + Guardian + post-call redaction/LeMUR; browser-simulated line). Owner is NON-TECHNICAL. Every stretch item must be behind a feature flag defaulting OFF and must not risk the working demo.

CURRENT STATE:
<<PASTE STATE SNAPSHOT FROM PREVIOUS PHASE HERE>>

OBJECTIVE: Add value without risk, in this priority order, stopping when time runs out: (1) Entity + sentiment timeline on incident cards (batch results already fetched). (2) Guardian "confidence-friendly" speech tuning: slower speechSynthesis rate and a female voice if available. (3) Spanish monitoring: if AssemblyAI streaming supports it per docs, add `LANGUAGE=es` room setting affecting STT language and a Spanish lexicon file (agents stay English) — else skip. (4) Family email notification via a free SMTP-less approach (none) → instead "Copy incident report" button and a printable incident page. (5) Real telephony via Twilio trial ONLY if the owner confirms a working trial number (India restrictions make this unlikely) — otherwise write `docs/TELEPHONY_ROADMAP.md` describing the exact integration (Twilio Media Streams, both_tracks, whisper-to-one-leg).

DELIVERABLES / VERIFICATION: per item: flag, tests, and a one-line demo check. Full test suite must remain green; public URL must still pass `tools/smoke_public.py`.

END OF PHASE — print exactly: STATE SNAPSHOT (save to STATE.md, commit/push), HUMAN ACTIONS REQUIRED NOW, BLOCKERS.

RULES: (1) Defaults over questions. (2) Flags default OFF. (3) Never break the demo. (4) Verify yourself. (5) No code for the human. (6) PowerShell. (7) No secrets. (8) Commit, push, STATE.md.
```

## D. Troubleshooting Relay Prompt (paste this to ME, the research AI)
```
The Building AI hit a problem.
Phase: <number and name>
What I asked it to do: <one line>
What happened (its last message, or the error text it showed me, copied exactly):
<<< paste >>>
Last STATE SNAPSHOT it printed:
<<< paste >>>
What I see in the app right now (plain words): <e.g., "senior tab never rings", "risk meter stays at 0">
Please give me a single corrected PATCH PROMPT I can paste into the Building AI verbatim, plus a one-line note on what you think went wrong.
```
