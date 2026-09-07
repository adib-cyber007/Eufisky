# STATE SNAPSHOT

Hackathon submission-assets phase completed on 2026-09-07.

Eufisky remains a browser-based phone-line simulation deployed at
https://eufisky.onrender.com. Trusted contacts bypass AI processing. Unknown
callers pass through the Front Door agent; connected caller and senior audio
uses separate AssemblyAI Universal Streaming sessions and a deterministic risk
engine; the Guardian speaks privately with the senior through explicit tool
actions. Post-call processing requests batch PII redaction and generates a
LeMUR-style incident summary through AssemblyAI's current LLM Gateway, with a
deterministic template fallback. The product limitations remain explicit: the
demo is not real telephony, caller ID can be spoofed, and voice/risk support is
English only. Twilio or carrier integration is roadmap work.

Submission assets now included:

- `README.md`: product overview, four-point feature summary, live demo and
  60-second try-it path, type-to-talk guidance, ASCII and PNG architecture,
  AssemblyAI feature map, privacy, limitations, seven-command local setup,
  tests, and MIT license.
- `docs/ARCHITECTURE.md`: components, state machine, exact decaying-risk
  formula, escalation ladder, and data model.
- `docs/BUSINESS.md`: FTC-sourced problem framing, buyers, pricing hypothesis,
  channel strategy, business value, metrics, and roadmap.
- `app/web/slides.html`: nine-slide Reveal.js deck served at `/slides`, with
  Reveal's bundled print rules plus Eufisky print styling for `?print-pdf`.
- `docs/SUBMISSION.md`: copy-ready title, 135-character short description,
  364-word long description, tags, URLs, 90-second pitch, 10 judge Q&As, and an
  exact three-minute video script/shot list.
- `docs/cover.png` (1920x1080), `docs/cover-1200x630.png` (1200x630), and
  `docs/architecture.png` (1600x900), reproducible with the Pillow scripts in
  `tools/`.
- Consistent page titles, `app/web/static/favicon.svg`, and root `LICENSE`.

Verification completed:

- `python -m pytest -q`: 77 passed. `ruff` was not installed, so its conditional
  check was not applicable.
- Python compilation and HTML parsing passed.
- Both generated cover sizes and the architecture image were opened and
  visually inspected; all labels fit their canvases.
- Local `/slides` and `/slides?print-pdf` returned HTTP 200. Browser inspection
  confirmed all nine slides, working Reveal navigation, a dark title slide, and
  a dark print-PDF preview.
- The deployed smoke test passed health/database, Landing, Caller, Senior,
  Family, Dashboard, Slides, secure Dashboard WebSocket registration, Replay
  risk/transcript/state/tool events, and completion.
- Every URL in `docs/SUBMISSION.md` returned HTTP 200 after deployment.
- Submission-assets commit `35c0959` is pushed to `origin/main`. The final
  closeout commit is pushed and tagged `v1.0-hackathon`.

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

# BLOCKERS

None. All non-video submission assets are generated, verified, deployed,
committed, pushed, and release-tagged.
