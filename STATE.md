# STATE SNAPSHOT

Phase 4 Guardian is implemented on `main`.

- Deterministic transitions now cover `BRIDGED → GUARDIAN → BRIDGED/FAMILY_CONF/WRAPUP`, including a 60-second resume cooldown and +10 L2 threshold escalation capped at 85. L2/L3 formulas and prior rule weights are unchanged.
- L2 immediately detaches both monitoring streams, stops caller/senior relay, sends caller HOLD plus client-generated looping hold music, and says “One moment, Margaret.” before starting the Guardian backend with a three-second cap.
- Guardian uses the required calm templated persona and exactly four tools: resume, conference family, end/block, and trust/pending. Provider failure exposes the same actions through Senior buttons and DTMF 1/2/3.
- Guardian speech/audio is routed only to Margaret. Senior STT and type-to-talk hear her choice. Family conference keeps the caller held while Margaret and Sarah speak privately; Family has Resume caller and End call controls.
- Dashboard Live shows GUARDIAN/FAMILY_CONF, its recommendation and chosen tool, plus a Join call action. Caller has a Please hold screen; Family receives the exact risk reason.
- WRAPUP closes Front Door/Guardian/STT/recording resources, persists final state, peak risk and Guardian outcome, auto-blocks risk 85+ unless trusted, publishes call ended, and calls the Phase-5 no-op `postcall.enqueue(call_id)` hook.
- `add_to_trusted` stores trusted below peak 85 and pending at peak 85+, then resumes the call.
- Type-to-talk remains available for Caller, Margaret, and Sarah. Trusted-call privacy behavior and the verified Front Door path remain intact.

Verification:

- Full suite: `43 passed`.
- Focused rules/state/context/call tests: green. Tests cover every transition, all L2 formulas, L3 recommendation, cooldown escalation, inert non-tool LLM output, caller speech/audio isolation, fallback controls, family private bridge, end/block, auto-block, trust/pending, and slow STT shutdown timing.
- Python compile and all three browser JavaScript syntax checks: green; `git diff --check`: green.
- Rule immutability check: no Phase-4 diff in `app/rules/lexicon.yaml` or `app/rules/engine.py`.
- Live four-WebSocket type-to-talk runs against fresh servers:
  - Family flow: caller HOLD in 36 ms; reason exactly `Eufisky paused a risky call with 'Michael from Medicare'`; Sarah rang/answered; caller hangup persisted WRAPUP, peak 90, Guardian outcome `conference_family`; `+15550199321` blocked.
  - Continue flow: caller HOLD in 37 ms; Margaret resumed the caller; final high-risk block persisted.
  - `SIMULATE_AGENT_FAIL=1`: caller HOLD in 37 ms; fallback controls appeared and the Continue action resumed the caller.
- Browser surfaces are covered by static rendering tests for all required buttons/banner/hold-audio code. Direct browser automation was denied by the host's stale lexicon-only authorization guard; no product failure was observed.

Environment (values hidden): `ASSEMBLYAI_API_KEY`, `GROQ_API_KEY`, and `GEMINI_API_KEY` are set; `AGENT_BACKEND=voice_agent`. `SIMULATE_AGENT_FAIL=1` is an optional demo-only fallback switch and defaults off.

Run locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open `/caller?room=demo`, `/senior?room=demo`, `/family?room=demo`, and `/dashboard?room=demo` at `http://localhost:8000`.

# HUMAN ACTIONS REQUIRED NOW

None.

# BLOCKERS

None. The Phase 4 source is pushed and the local server is running on port 8000.
