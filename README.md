# Eufisky
<img width="2109" height="746" alt="image" src="https://github.com/user-attachments/assets/2dddae12-1674-4098-9360-aa055403bc54" />

Eufisky is a browser-based simulation of a voice AI agent that guards an older adult's phone line. Trusted callers remain private; unknown callers are screened, monitored by speaker-separated AssemblyAI streaming, and paused for a private Guardian intervention when deterministic scam signals rise. Afterward, personal information is redacted and the family receives a plain-English incident report.

The current build includes the full phone-room demo, seeded dashboard history and messages, post-call batch analysis with reliable local fallbacks, and a microphone-free Replay Mode.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000> and follow the guided steps. The direct demo pages are `/caller?room=demo`, `/senior?room=demo`, `/family?room=demo`, and `/dashboard?room=demo`. The health check is <http://localhost:8000/api/health>.

On the dashboard, click **▶ Replay demo call** for a complete no-microphone run. See `docs/DEMO_SCRIPT.md` for the exact three-minute presentation, `STATE.md` for the current handoff snapshot, and `docs/PROJECT_CONTEXT.md` for the product contract.

If a family is worried that an urgent legitimate caller could be filtered into a message, open **Dashboard → Settings** and turn on **Always ring me first, even for calls that look risky**. It defaults OFF to preserve the safer standard demo. When ON, Front Door still screens callers, but its score-based connection override is skipped; calls it attempts to connect ring Margaret and remain protected by the unchanged live monitoring and Guardian intervention.

## Deploy on Render for free

The repository contains one `render.yaml` Blueprint for one free Python web service. In Render, choose **New + → Blueprint**, connect this GitHub repository, enter the requested secret environment variables in Render's private fields, and apply the Blueprint. Do not paste API keys into chat or commit them to Git.

The hosted demo uses Render's temporary `/tmp` storage for SQLite and call recordings. The demo room is reseeded whenever a fresh service instance starts, and hosted changes or recordings can disappear after a restart, redeploy, or idle spin-down. That is intentional for this demonstration build. The site is same-origin, automatically uses secure WebSockets on HTTPS, and needs no separate CORS setup.

A free service can sleep while unused. Its first page load may take roughly 40 seconds. About 15 minutes before presenting, keep this running in PowerShell and press `Ctrl+C` after the demo:

```powershell
.\.venv\Scripts\python.exe tools\warm.py https://YOUR-SERVICE.onrender.com
```

After deployment, verify the full public HTTP, WebSocket, and Replay path with:

```powershell
.\.venv\Scripts\python.exe tools\smoke_public.py https://YOUR-SERVICE.onrender.com
```
