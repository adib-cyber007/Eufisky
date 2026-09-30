# Eufisky submission assets

Prepared September 30, 2026 for the [AssemblyAI Voice Agent Hackathon](https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon). Assets only: no entry was submitted and nothing was uploaded or published in this preparation step.

## Upload-ready files

| File | Purpose |
| --- | --- |
| `submission-copy.txt` | Copy-ready title, descriptions, tags, links, and judge instructions |
| `submission-fields.json` | The same core fields in structured form |
| `Eufisky-cover.png` | 1920 × 1080 cover image, 16:9 |
| `Eufisky-pitch-deck.pdf` | 10-slide presentation |
| `Eufisky-demo.mp4` | 4:56 narrated video, 1280 × 720, H.264/AAC, approximately 6.4 MB |
| `Eufisky-demo.srt` | English captions; also embedded as a selectable video subtitle track |
| `narration.txt` | Editable narration script |
| `Eufisky-pitch-deck.html` | Offline editable deck; arrow keys advance slides |
| `Eufisky-dashboard.png`, `Eufisky-replay.png`, `Eufisky-history.png` | Additional prototype screenshots |

The video uses Microsoft Zira Desktop synthetic narration. Its interface segment records the local browser prototype running the built-in scripted Replay at 2× speed. The slide illustrations and narrated pitch describe the implementation; the video does not establish that hosted AssemblyAI services were exercised. Captions follow the narration approximately and may need enabling in the player.

## Requirements mapping

The event requests a title, short/long descriptions, technology/category tags, cover, video, slides, repository, demo platform, and application URL. All corresponding assets or copy are included. The short description is 207 characters; the long description is 357 words. The [general delivery guide](https://lablab.ai/delivering-your-hackathon-solution) requests a 16:9 PNG/JPG cover, an MP4 of at most five minutes, and a PDF presentation. This package meets those formats. Team, account, and video hosting details remain outside this assets-only scope.

The shared guide contains an IBM Bob report reference that is absent from this AssemblyAI event's own requirements. It has not been treated as an AssemblyAI requirement. Event-specific instructions should govern any later submission.

## Evidence captured during preparation

- Local automated suite: **85 passed**, with two dependency deprecation warnings. Command: `.venv/Scripts/python.exe -m pytest -q --basetemp=tmp/submission/pytest-20260930 --tb=short`.
- Public smoke script passed health/database, pages, dashboard WebSocket, and the Replay event story for `https://eufisky.onrender.com`.
- Offline rules evaluation: 60 constructed scam scripts reached L2 intervention; 40 benign scripts did not reach L1 or L2. These are deterministic fixture checks, not representative accuracy or loss-prevention estimates.
- PDF exported and all ten rendered pages visually inspected. Browser slide overflow check returned no overflowing text boxes.
- MP4 verified at 296.454 seconds, 6,393,671 bytes, 1280 × 720, H.264 video, AAC audio, and embedded English subtitles. A frame from the encoded Replay segment was visually inspected.

## Honest scope for judges

Eufisky is an English-first browser phone simulation; optional Spanish monitoring does not mean localized Spanish agent conversations. Real Twilio/carrier integration is future work. Consent controls need further hardening, including negative/ambiguous commands. Authenticated households, caller identity, privacy lifecycle controls, and representative audio evaluations remain prerequisites for a real-world pilot. Batch PII processing does not imply every raw recording, log, or transcript has been redacted. Do not enter real personal data into the public prototype.

The pitch maps to the event's four judging dimensions: technology integration, clear presentation, business value hypotheses, and private intervention as the product's differentiating focus. It makes no claims of commercial traction, prevented losses, production readiness, or live latency measurements.

## Links

- [Public browser demo](https://eufisky.onrender.com/?room=demo)
- [Public source repository](https://github.com/adib-cyber007/Eufisky)
- [Hackathon event and judging criteria](https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon)
- [Submission delivery guide](https://lablab.ai/delivering-your-hackathon-solution)

No application code was changed for this assets-only preparation. Existing workspace changes were preserved.
