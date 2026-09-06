# STATE SNAPSHOT

Phase 6 is deployed at `https://eufisky.onrender.com`. The public application path has passed automated verification; the final landing visibility patch is awaiting redeploy verification and the owner two-device call is still required. The owner's manual frontend restyle remains preserved: `backup-restyle-2026-09-07` points exactly to commit `c450729`. `STATE_after_phase0.txt` remains untouched and untracked.

Deployment behavior:

- `render.yaml` defines exactly one Render Blueprint web service using Python 3.12.14 and the free plan. It installs `requirements.txt`, starts `uvicorn app.main:app --host 0.0.0.0 --port $PORT --ws websockets`, and uses `/api/health` for health checks.
- Render receives non-secret defaults for `AGENT_BACKEND=voice_agent`, `SENIOR_NAME=Margaret`, and `FAMILY_NAME=Sarah`. `ASSEMBLYAI_API_KEY`, `GROQ_API_KEY`, and `GEMINI_API_KEY` are private `sync:false` values; no secret value is committed or printed.
- When Render sets `RENDER`, SQLite uses `/tmp/eufisky.db` and call/redacted recordings use `/tmp/eufisky-recordings`. The demo database is created and seeded during every fresh process startup. Local development continues to use `data/eufisky.db` and `data/recordings`.
- The incident-audio endpoint accepts only the project data directory or the configured recording directory, so `/tmp` audio works without weakening path traversal protection.
- The app is same-origin and browser clients select `wss://` automatically on HTTPS. No CORS configuration or separate service is required. Uvicorn logs to the Render service log stream.
- The landing page contains a dedicated visible warning that the first free-host load after a quiet period may take about 40 seconds. It is separate from the JavaScript-updated room status so it remains visible after page load.
- `tools/smoke_public.py <url>` checks health/database readiness, landing/Caller/Senior/Family/Dashboard pages, a Dashboard WebSocket handshake, the Replay endpoint, risk/transcript/state/tool events, and replay completion.
- `tools/warm.py <url>` checks health every five minutes so the free service can be warmed about 15 minutes before a demo.

Public verification completed:

- GitHub's public deployment record reports the Render environment successful at `https://eufisky.onrender.com`.
- `.\.venv\Scripts\python.exe tools\smoke_public.py https://eufisky.onrender.com` passed health/database, all five static pages, production Dashboard WebSocket, Replay endpoint, all required replay event types, and replay completion.
- Rendered-browser checks passed for the landing page, Dashboard, Caller, and Senior. Dashboard reached **Live connection** and received its initial `IDLE` snapshot.
- A rendered-browser check caught the landing room-status script replacing the cold-start notice; the notice was moved into its own permanent element and covered by a regression test.
- Full suite after the cold-start visibility patch: `68 passed` with `.\.venv\Scripts\python.exe -m pytest -q`.

Phase 6 files: `render.yaml`, `app/runtime_paths.py`, `app/db.py`, `app/main.py`, `app/phone/calls.py`, `app/postcall/pipeline.py`, `app/web/index.html`, `tools/smoke_public.py`, `tools/warm.py`, `tests/test_deployment.py`, `README.md`, `docs/DEMO_SCRIPT.md`, and `STATE.md`.

Environment variables: Render supplies `PORT` and `RENDER`; Blueprint fixes `PYTHON_VERSION=3.12.14`, `AGENT_BACKEND=voice_agent`, `SENIOR_NAME=Margaret`, and `FAMILY_NAME=Sarah`; the owner entered `ASSEMBLYAI_API_KEY`, `GROQ_API_KEY`, and `GEMINI_API_KEY` only in Render's private form.

Public links:

- Landing: `https://eufisky.onrender.com`
- Caller: `https://eufisky.onrender.com/caller?room=test1`
- Senior: `https://eufisky.onrender.com/senior?room=test1`
- Family: `https://eufisky.onrender.com/family?room=test1`
- Dashboard: `https://eufisky.onrender.com/dashboard?room=test1`
- Health: `https://eufisky.onrender.com/api/health`

Warm 15 minutes before a demo:

```powershell
.\.venv\Scripts\python.exe tools\warm.py https://eufisky.onrender.com
```

# HUMAN ACTIONS REQUIRED NOW

1. On the laptop, open `https://eufisky.onrender.com/dashboard?room=test1`. Success means the top-right status changes to **Live connection**.
2. On the laptop, open `https://eufisky.onrender.com/senior?room=test1` in a second tab. Also open `/family?room=test1` in a third tab if you want to exercise the Sarah conference branch.
3. On the phone, open `https://eufisky.onrender.com/caller?room=test1`. Choose **Unknown caller**, turn the mic on, allow the browser microphone prompt, and tap **Dial Margaret**. Success means Front Door greets the caller.
4. Say or type: “This is Michael from Medicare, calling about an urgent update to her benefits.” Success means Margaret's laptop tab rings after screening.
5. Answer on Margaret's tab. On the phone say or type: “Your benefits will be suspended today unless we verify your account. Please read me the number on your Medicare card.” Success means the Dashboard risk rises and Guardian places the caller on hold.
6. On Margaret's tab, choose **Bring in Sarah** or **End call and block**. If using Sarah, answer in the laptop Family tab, then end the call.
7. Open Dashboard → **History** and **Contacts**. Success means the completed call appears and the risky unknown number is blocked.
8. Reply here with exactly: `public two-device test worked` — or describe the one screen where it stopped.

# BLOCKERS

The required owner two-device call has not yet been reported. Phase 6 cannot be marked complete until the final landing-page fix is deployed and reverified, then the owner confirms the public scam run worked from laptop plus phone.
