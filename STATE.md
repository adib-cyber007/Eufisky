# STATE SNAPSHOT (save to STATE.md, commit/push)

Default-off stretch phase completed on 2026-09-09.

Eufisky remains a deployed, submission-ready browser phone-line simulation at
https://eufisky.onrender.com. The proven submission path is unchanged: trusted
contacts bypass AI processing; unknown calls use Front Door, separate caller
and senior AssemblyAI streams, deterministic risk scoring, private Guardian
intervention, and redacted post-call reports.

Added without enabling anything in the submitted demo:

- A privacy-safe entity and sentiment timeline for existing batch results.
  Only organization values display; all other entity values and digit runs are
  redacted again before reaching the browser.
- Confidence-friendly Guardian browser speech at rate 0.82, with a preferred
  English female system voice when available. Other agent speech stays at the
  existing rate and voice.
- Optional Spanish monitoring using AssemblyAI Universal-3.5 Pro Streaming's
  documented `language_codes=["es"]` bias and a Spanish risk lexicon with the
  exact English policy's weights, decay, caps, and combinations. Front Door and
  Guardian continue speaking English.
- Copy incident report and a clean printable incident page, both sourced only
  from the existing redacted report data.
- `docs/TELEPHONY_ROADMAP.md`, specifying a gated Twilio Media Streams and
  Conference design with `both_tracks` monitoring and a private Guardian stream
  to the senior leg. No Twilio dependency or runtime path was added because no
  working trial number was confirmed.

Safety controls:

- `FEATURE_INCIDENT_INSIGHTS`, `FEATURE_GUARDIAN_VOICE_TUNING`,
  `FEATURE_SPANISH_MONITORING`, `FEATURE_INCIDENT_EXPORT`, and the reserved
  `FEATURE_TWILIO_TELEPHONY` all default OFF.
- `.env.example` uses `0`; `render.yaml` explicitly uses `"false"` for every
  stretch flag; the public `/api/features` endpoint confirms all five are OFF.
- Per-item tests and one-line demo checks are recorded in
  `docs/STRETCH_FEATURES.md`.

Verification completed:

- Full suite: **82 passed** (up from 77), with only pre-existing dependency and
  pytest-cache warnings.
- All changed JavaScript files passed `node --check`; Python compilation and
  `git diff --check` passed.
- Local default-off browser check confirmed no timeline, export actions, or
  Spanish control appears. The complete local smoke test passed.
- Local opt-in browser check confirmed timeline rendering, Spanish room-setting
  save/restore, report copying, and the printable redacted layout.
- The post-deploy public smoke test passed health/database, Landing, Caller,
  Senior, Family, Dashboard, Slides, secure Dashboard WebSocket, Replay, and the
  complete event story.
- Stretch implementation commit `391e4d8` is pushed to `origin/main`.
- Release tag `v1.0-hackathon` remains the original submission checkpoint at
  `564e8c6`; the default-off stretch work is intentionally subsequent.

One pre-existing local edit to `app/web/slides.html` remains unstaged and was
deliberately excluded from both stretch commits.

# HUMAN ACTIONS REQUIRED NOW

1. Create the slide PDF: open
   https://eufisky.onrender.com/slides?print-pdf in Chrome or Edge, press
   Ctrl+P, choose **Save as PDF**, set **Landscape**, set **Margins** to
   **None**, enable **Background graphics**, and save.
2. Upload `docs/cover.png` as the 1920x1080 submission cover. Use
   `docs/cover-1200x630.png` only if the destination requests a social-card
   size.
3. Copy the title, descriptions, tags, URLs, pitch, and judge answers from
   `docs/SUBMISSION.md`.
4. Record the video by following the timestamped table and exact spoken lines
   in `docs/SUBMISSION.md`; no additional script writing is needed.

No stretch-feature configuration is required for submission; keep the flags
OFF.

# BLOCKERS

None. Real telephony is intentionally roadmap-only until the owner confirms a
working Twilio trial number and verified destinations.

## Voice reliability update — 2026-09-30

Fixed fractional sample loss in browser resampling, microphone muting during
PCM playback, per-chunk playback gaps, stale audio after confirmed interruption,
and automatic hangup cutting off system speech. Closing lines now wait for the
correct phone's playback acknowledgement, with a bounded timeout. Voice Agent
uses accuracy mode with adaptive pacing, recognition context and Guardian names;
runtime disconnects switch to the existing STT/text fallback. STT only commits
finalized words, accepts transcript-only turns and ignores duplicate turn ends.
Keyterms are balanced across benign, senior and scam vocabulary within the cap.

Checks: 89 Python tests and 4 dependency-free Node audio checks pass; JavaScript
syntax and diff whitespace checks pass. A public synthetic-voice baseline
reproduced "pharmacy delivery" being transcribed as "farm delivery" and routed
the call successfully. The same audio will be checked after deployment. No new
dependency or feature flag is required. Local AssemblyAI credentials are absent;
provider integration checks use the hosted service in isolated test rooms.

Checkpoint: commit/push this coherent voice fix to origin/main (already
authorized), then verify the deployed assets, speech recognition and call closure.
