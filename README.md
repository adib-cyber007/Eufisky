# Eufisky

Eufisky is a browser-based simulation of a voice AI agent that guards an older adult's phone line. The repository is currently at **Phase 2**: unknown bridged calls have two-leg AssemblyAI streaming, deterministic scam-risk scoring, and a live family risk dashboard. The completed Phase 1 phone system and Phase 0 capability probes remain intact.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000> and <http://localhost:8000/api/health>.

See `STATE.md` for the current handoff snapshot and `docs/PROJECT_CONTEXT.md` for the complete product contract.
