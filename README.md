# Eufisky

Eufisky is a browser-based simulation of a voice AI agent that guards an older adult's phone line. The repository is currently at **Phase 1**: the runnable FastAPI phone system, contact routing, browser audio bridge, and dashboard shell are complete. Phase 0 capability probes are retained as prerequisites for later phases.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000> and <http://localhost:8000/api/health>.

See `STATE.md` for the current handoff snapshot and `docs/PROJECT_CONTEXT.md` for the complete product contract.
