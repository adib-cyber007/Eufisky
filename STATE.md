# STATE SNAPSHOT

Phase 6 repository preparation is complete on `main`; public deployment verification is waiting for the owner to create the free Render service and return its URL. The owner's manual frontend restyle remains preserved: `backup-restyle-2026-09-07` points exactly to commit `c450729`. `STATE_after_phase0.txt` remains untouched and untracked.

Deployment-ready behavior:

- `render.yaml` defines exactly one Render Blueprint web service using Python 3.12.14 and the free plan. It installs `requirements.txt`, starts `uvicorn app.main:app --host 0.0.0.0 --port $PORT --ws websockets`, and uses `/api/health` for health checks.
- Render receives non-secret defaults for `AGENT_BACKEND=voice_agent`, `SENIOR_NAME=Margaret`, and `FAMILY_NAME=Sarah`. `ASSEMBLYAI_API_KEY`, `GROQ_API_KEY`, and `GEMINI_API_KEY` are private `sync:false` prompts; no secret value is committed or printed.
- When Render sets `RENDER`, SQLite uses `/tmp/eufisky.db` and call/redacted recordings use `/tmp/eufisky-recordings`. The demo database is created and seeded during every fresh process startup. Local development continues to use `data/eufisky.db` and `data/recordings`.
- The incident-audio endpoint accepts only the project data directory or the configured recording directory, so `/tmp` audio works without weakening path traversal protection.
- The app remains same-origin and the existing browser clients select `wss://` automatically when the page uses HTTPS. No CORS configuration or separate service is required. Uvicorn logs to the Render service log stream.
- The landing page calmly warns that the first free-host load after a quiet period may take about 40 seconds.
- `tools/smoke_public.py <url>` checks health/database readiness, landing/Caller/Senior/Family/Dashboard pages, a Dashboard WebSocket handshake, the Replay endpoint, risk/transcript/state/tool events, and replay completion.
- `tools/warm.py <url>` checks health every five minutes so the free service can be warmed about 15 minutes before a demo.

Verification completed before deployment:

- Full suite: `68 passed` with `.\.venv\Scripts\python.exe -m pytest -q`.
- Local public-smoke simulation: health, all five pages, Dashboard WebSocket, Replay endpoint, every required replay event type, and completion passed.
- Local warmer one-shot: `READY`.
- Python compilation, Blueprint contract tests, `git diff --check`, and the explicit Render path check passed.
- The three test warnings are non-failing dependency/cache warnings; they do not affect application behavior or deployment.

Files changed for Phase 6 preparation: `render.yaml`, `app/runtime_paths.py`, `app/db.py`, `app/main.py`, `app/phone/calls.py`, `app/postcall/pipeline.py`, `app/web/index.html`, `tools/smoke_public.py`, `tools/warm.py`, `tests/test_deployment.py`, `README.md`, and `STATE.md`.

Environment variables: Render supplies `PORT` and `RENDER`; Blueprint fixes `PYTHON_VERSION=3.12.14`, `AGENT_BACKEND=voice_agent`, `SENIOR_NAME=Margaret`, and `FAMILY_NAME=Sarah`; the owner enters `ASSEMBLYAI_API_KEY`, `GROQ_API_KEY`, and `GEMINI_API_KEY` only in Render's private form. Never paste those values into chat.

Local run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Local pages: `http://localhost:8000`, `/caller?room=demo`, `/senior?room=demo`, `/family?room=demo`, `/dashboard?room=demo`; health: `/api/health`.

# HUMAN ACTIONS REQUIRED NOW

1. Open `https://dashboard.render.com` and choose **Sign in with GitHub**. Success means the Render dashboard opens; do not choose a paid plan or add a card.
2. Click **New +**, then **Blueprint**. Success means Render asks for a Git repository.
3. Find the GitHub repository **adib-cyber007/Eufisky** and click **Connect**. Success means Render detects `render.yaml` and previews one service named `eufisky` on the **Free** plan.
4. Keep the displayed service plan set to **Free**, then enter `ASSEMBLYAI_API_KEY`, `GROQ_API_KEY`, and `GEMINI_API_KEY` into Render's private secret fields. Copy the values from the laptop's existing `.env`; never send them in chat. Success means each field is filled but its value is hidden.
5. Click **Apply** or **Deploy Blueprint**. Success means one Python web service begins building; if Render asks for payment or a card, stop and report that screen instead of continuing.
6. Wait for the service status to become **Live**. The first build can take several minutes. Success means the Events/log area says the deploy is live and the service header shows an `https://...onrender.com` URL.
7. Open that URL once and allow about 40 seconds if it is waking. Success means the Eufisky landing page appears.
8. Paste only the public `https://...onrender.com` URL back into this chat. Do not include any API key.

# BLOCKERS

Public deployment does not exist yet, so public health/page/WebSocket/Replay checks, the README **Live demo** link, public links in `docs/DEMO_SCRIPT.md`, and the required owner two-device test cannot be completed yet. The only needed input is the deployed public Render URL after the eight safe free-tier actions above. Render must fail twice before any fallback host is considered.
