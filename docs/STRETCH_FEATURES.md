# Stretch feature controls

Every stretch capability is opt-in. Render and `.env.example` keep every flag
off so the submitted demo continues to use the proven English browser flow.

| Item | Flag (default) | Automated check | One-line demo check |
|---|---|---|---|
| Entity + sentiment timeline | `FEATURE_INCIDENT_INSIGHTS=0` | `test_incident_insights_are_flagged_and_privacy_safe` | Enable the flag, open Dashboard → History, and expand **Entity + sentiment timeline** on a seeded incident. |
| Confidence-friendly Guardian speech | `FEATURE_GUARDIAN_VOICE_TUNING=0` | `test_guardian_voice_tuning_is_guardian_only_and_opt_in` | Enable the flag, trigger Guardian, and hear its slower delivery plus a preferred English female system voice when one is installed. |
| Spanish monitoring | `FEATURE_SPANISH_MONITORING=0` | `test_spanish_monitoring_is_flagged_and_uses_spanish_profile` | Enable the flag, choose Spanish in Dashboard → Settings, then say “Soy de Medicare; su cuenta será suspendida ahora mismo” on the next unknown call and watch risk rise. |
| Copy + printable report | `FEATURE_INCIDENT_EXPORT=0` | `test_incident_export_route_and_browser_contract_are_flagged` | Enable the flag, open Dashboard → History, copy a report, then open its clean printable view. |
| Real telephony | `FEATURE_TWILIO_TELEPHONY=0` | `test_telephony_remains_a_disabled_documented_roadmap` | Leave the reserved flag off and confirm Caller, Senior, Family, and Replay still use the browser-simulated line. |

## Behavior boundaries

- Flags are read when the FastAPI process starts; changing one requires a
  service restart.
- Spanish changes AssemblyAI streaming language bias and the deterministic
  scam lexicon. Front Door and Guardian prompts and speech remain English.
- Insight text is sanitized again for display. Sensitive entity categories and
  digit runs are never exposed by the new timeline.
- Export contains only the existing redacted transcript and incident summary.
- The Twilio flag is reserved and has no runtime effect. See
  `docs/TELEPHONY_ROADMAP.md` for the gated implementation plan.

AssemblyAI verification: Universal-3.5 Pro Streaming supports Spanish and the
documented `language_codes` connection parameter can bias a monolingual session
to `['es']`:

- https://www.assemblyai.com/docs/faq/language-support-for-real-time-transcription
- https://www.assemblyai.com/docs/streaming/getting-started/optimizing-accuracy-and-latency
