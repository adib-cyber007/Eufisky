# Eufisky architecture

Eufisky is one FastAPI service that simulates a protected phone line in browser
tabs. A `room` query value isolates each demo group. The system treats routing,
risk scoring, and safety actions as deterministic application logic; voice
models can speak and request registered tools, but cannot change call state by
free-form text.

## Components

| Component | Responsibility | Important boundary |
|---|---|---|
| Caller, Senior, and Family pages | Capture microphone audio or typed speech, play bridged or agent audio, and show call state | PCM16 mono, 16 kHz travels over the phone WebSocket; typed input follows the same call logic |
| Family Dashboard | Shows transcript, evidence, score, transitions, incidents, contacts, and Replay | Receives events only for its room |
| Phone router | Classifies caller ID, owns call lifecycle, bridges audio, applies hold, and rings family | Trusted calls bypass AI processing |
| Front Door agent | Asks unknown callers who they are and why they are calling | Can request only `connect_caller`, `take_message`, or `decline` |
| Streaming adapter | Opens one AssemblyAI Universal Streaming session for each connected leg | Separate caller and senior sessions create deterministic speaker labels |
| Risk engine | Matches speaker-specific phrases and digit patterns, decays evidence, and emits a 0–100 score | No LLM decides the score |
| Safety state machine | Turns score thresholds and registered tool calls into hold, chime, resume, conference, or end actions | Agent speech alone cannot transition state |
| Guardian agent | Speaks privately with Margaret while the caller is on hold | Can request only `resume_call`, `conference_family`, `end_call`, or `add_to_trusted` |
| Post-call pipeline | Mixes channels, requests batch PII redaction, generates an incident summary, and deletes raw recordings | Summary generation uses AssemblyAI's LLM Gateway with a deterministic template fallback |
| SQLite store | Persists contacts, calls, evidence, transcripts, incidents, messages, and room settings | Render uses temporary storage for this demo |

## Runtime data flow

```text
Browser phones                         FastAPI                       Providers

Caller ─────┐                     ┌─ caller-ID router
Senior ─────┼── /ws/phone ───────┤
Family ─────┘   JSON + PCM16      └─ call lifecycle / audio bridge
                                          │
                  trusted ────────────────┼──── private bridge; no AI
                                          │ unknown
                                          v
                                   Front Door agent ───────────> Voice Agent API
                                          │ connect
                            ┌─────────────┴─────────────┐
                            v                           v
                    caller stream               senior stream ──> Universal Streaming
                            └─────────────┬─────────────┘
                                          v
                              deterministic risk score
                                          │
                         score 40 / L2 rule / score 90
                                          v
                           safety state machine + Guardian ─────> Voice Agent API
                                          │
                                          v
                         batch redaction + summary generation ──> AssemblyAI
                                          │
                                          v
               Dashboard <── /ws/dashboard events <── SQLite incident history
```

## Call state machine

```text
IDLE
 ├─ trusted caller ───────────────────────────────> DIALING_SENIOR
 ├─ blocked caller ───────────────────────────────> WRAPUP
 └─ unknown caller ─> SCREENING
                       ├─ take_message / decline ─> WRAPUP
                       └─ connect_caller ─────────> DIALING_SENIOR

DIALING_SENIOR ── answer ─> INTRO ─> BRIDGED
                                      │
                                      ├─ score >= 40: senior-only chime; remain BRIDGED
                                      └─ L2 trigger: caller held ─> GUARDIAN
                                                                  ├─ resume / trust ─> BRIDGED
                                                                  ├─ conference ─────> FAMILY_CONF
                                                                  └─ end ────────────> WRAPUP

BRIDGED / GUARDIAN / FAMILY_CONF ── hangup ─> WRAPUP ─> POST_CALL ─> DONE
```

Only an explicit, registered tool event can apply an agent-requested action.
The per-call agent-session registry also enforces that Front Door is fully
closed before Guardian can open.

## Risk formula

For time `t`, the engine calculates:

```text
score(t) = clamp(
  round(seed
        + Σ [weight(hit) × 2 ^ (-age_seconds / half_life_seconds)]
        + Σ active_combo_bonus),
  0, 100
)
```

Phrase matching uses a rolling 12-word window per speaker. Repeated identical
evidence within two seconds is suppressed. Each signal family keeps at most its
three newest active hits, and a hit is discarded after eight half-lives.

| Signal family | Speaker | Weight | Half-life |
|---|---:|---:|---:|
| Authority impersonation | Caller | +20 | 120 s |
| Urgency | Caller | +15 | 60 s |
| Secrecy | Caller | +25 | 120 s |
| Payment method | Caller | +30 | 180 s |
| PII request | Caller | +25 | 120 s |
| Remote access | Caller | +30 | 180 s |
| Family emergency | Caller | +25 | 120 s |
| Threat | Caller | +20 | 90 s |
| Compliance cue | Senior | +15 | 60 s |
| PII disclosure pattern | Senior | +40 | 300 s |
| Benign context | Caller | −20 | 180 s |

Three combination bonuses preserve context: +15 when two of authority,
urgency, and a PII request are active; +20 for payment plus urgency; and +25
when PII disclosure is active with either a PII request or authority claim.
The score and its supporting phrase-level evidence are published together.

## Escalation ladder

| Level | Trigger | Deterministic action |
|---|---|---|
| L1 — nudge | First score at or above 40 | Play a soft chime and “Eufisky is listening” to Margaret only |
| L2 — intervene | Score at or above 65; or senior PII disclosure with score at least 45; or payment method plus senior compliance cue | Hold the caller and start a private Guardian conversation |
| L3 — recommend family | Score at or above 90 | Recommend bringing Sarah into Guardian or family-conference state |

After a resume or trust action, L2 has a 60-second cooldown and its numeric
threshold rises by 10, capped at 85. This prevents an immediate intervention
loop while preserving PII and payment/compliance safeguards.

## Data model

```text
rooms
  ├── contacts        trusted / blocked / pending routing identities
  ├── calls           one lifecycle record and peak risk
  │    ├── call_events          states, levels, tools, and call events
  │    ├── risk_samples         time, score, and active signals
  │    ├── transcript_segments  speaker, time, text, and finality
  │    └── incidents            summary JSON, redacted text/audio, provenance
  └── messages        screened caller messages and callback numbers
```

The `calls` record stores classification, Front Door and Guardian outcomes,
recording paths, final state, and peak risk. `incidents.analysis_source` says
whether the report used the provider summary or template fallback; the
transcript source is kept with incident analytics.

## Deployment

One Render web service runs Uvicorn and serves pages, REST, WebSockets, and
static assets from the same HTTPS origin. The production demo stores SQLite and
recordings under Render's temporary `/tmp` filesystem, reseeds the demo room on
a fresh instance, and uses secure WebSockets automatically. This is appropriate
for judging, not durable production storage.
