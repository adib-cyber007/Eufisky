# STATE SNAPSHOT

This patch is complete on `main`. The owner's manual restyle is preserved in commit `c450729` (`wip: manual restyle before patch`), and safety branch `backup-restyle-2026-09-07` points to that exact commit. `STATE_after_phase0.txt` remains untouched and untracked.

What now works:

- Contacts: all existing REST operations were diagnosed independently before frontend work (`GET 200`, `POST 201`, `PATCH 200`, `DELETE 204`). The styled Dashboard now adds a contact with a visible Trusted/Blocked choice; shows clear trusted/blocked/pending badges; supports Trust, Block, Untrust, and Unblock actions; confirms before Delete; updates immediately; and shows an auto-block reason plus a History link when a phone-matched incident exists.
- Screened-call visibility: every Front Door `take_message` or `decline` outcome emits exactly one `notice{t_ms,kind,caller_label,purpose,callback_number}` to Margaret's phone and exactly one to the Dashboard. Margaret receives a calm queued, dismissible visual banner and soft sound without speech synthesis. The Dashboard Messages badge increments in real time and clears when Messages is opened.
- Routing setting: Dashboard → Settings contains the single per-room toggle **Always ring me first, even for calls that look risky**. It defaults OFF. ON skips only the score-40 Front Door `connect_caller` override, so the call enters `DIALING_SENIOR`; all monitoring, scoring weights, thresholds, personas, and Guardian behavior remain unchanged.
- Replay: the saved demo still runs end to end. Legacy saved `caption` events are normalized to the live `transcript` WebSocket schema. `tools/record_replay.py` now works when invoked directly, restores seeded risk from `risk_samples`, and derives captions from a seeded incident's redacted transcript when raw segments do not exist. Replay completion is emitted as `status:"completed"`.

Diagnosis/root causes:

- Problem 1: the contact API was already healthy and the restyle retained the contact IDs and script include. The existing JavaScript was functionally incomplete: it only offered Trust/Block, rendered status as plain text, deleted without confirmation, and never joined blocked phones to incidents.
- Problem 2: filtered outcomes persisted/broadcast a Dashboard `message` only for `take_message`; there was no Senior event, no general `decline` notice, no unread state, and no room routing preference.
- Problem 3: the current `data/demo_call.json`, live dashboard selectors, and live call rendering were compatible and the demo replay itself worked. The broken path was historical replay creation: direct script execution could not import `app`, seeded risk samples were omitted, seeded incidents had no raw transcript segments, and exported captions used a legacy event name.

Restyle investigation (`8c36af3..c450729`, `app/web`): 6 files changed, 1,225 insertions and 189 deletions. `caller.html`, `senior.html`, and `family.html` were expanded/reformatted and gained Plus Jakarta Sans, brand marks, and CSS cache version 6 while retaining phone control IDs and `audio.js`/`phone.js`. `dashboard.html` was reorganized into a sidebar/main layout and retained the original live, replay, contacts, messages, and history IDs plus `dashboard.js`. `index.html` gained the same font and stylesheet version. `app.css` received 1,074 changed lines for the new palette, layout, responsive behavior, and component styling. No JavaScript file was part of the manual restyle, and no original script include or required control ID was removed.

Files changed by this functional patch:

- Backend: `app/agent/policies.py`, `app/db.py`, `app/main.py`, `app/phone/calls.py`, `app/replay.py`.
- Frontend: `app/web/dashboard.html`, `app/web/senior.html`, `app/web/static/css/app.css`, `app/web/static/js/audio.js`, `app/web/static/js/dashboard.js`, `app/web/static/js/phone.js`.
- Tools/tests/docs: `tools/record_replay.py`, `tests/test_contacts.py`, `tests/test_settings.py`, `tests/test_frontdoor_flow.py`, `tests/test_policies.py`, `tests/test_replay.py`, `README.md`, `docs/PROJECT_CONTEXT.md`, `app/phone/protocol.md`, `STATE.md`.

Verification:

- Full suite: `60 passed` with `.\.venv\Scripts\python.exe -m pytest -q`.
- Python compilation, JavaScript syntax checks, `data/demo_call.json` parsing, and `git diff --check`: passed.
- Replay CLI: demo file started with 28 events; seeded Medicare history exported and started with 16 events containing risk, transcript, state, level, tool, and call events, peak risk 96.
- Browser: Contact add → Block → Unblock → Trust → Untrust updated immediately; the Delete confirmation appeared and API deletion is covered end to end. A take-message call showed Margaret's notice and Dashboard badge 1 within the live flow, then opening Messages cleared it. With the setting ON, a risky opener rang Margaret, the live dashboard reached risk 100, Guardian held the caller, Sarah joined, and the call ended. A fresh-room 4× replay reached risk 94, all speaker captions, levels 1/2/3, Guardian, family conference, WRAPUP, and “Replay complete.”

No new functionality is stubbed or deferred. Existing provider fallbacks remain intentionally available when external AssemblyAI access is unavailable.

Environment variables (never print values): `ASSEMBLYAI_API_KEY`; `AGENT_BACKEND=auto|voice_agent|llm`; optional `GROQ_API_KEY` and `GEMINI_API_KEY`; optional `SENIOR_NAME` and `FAMILY_NAME`; `PORT` (default 8000). This verification reported the AssemblyAI key present and `AGENT_BACKEND=voice_agent` without exposing secrets.

Run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open `http://localhost:8000`, or directly use `http://localhost:8000/caller?room=demo`, `/senior?room=demo`, `/family?room=demo`, and `/dashboard?room=demo`. Health: `http://localhost:8000/api/health`.

# HUMAN ACTIONS REQUIRED NOW

None.

# BLOCKERS

None.
