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
