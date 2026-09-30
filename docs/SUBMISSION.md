# Eufisky hackathon submission

## Project title

Eufisky: Private Help for Risky Calls

## Short description

Eufisky screens unknown callers and privately helps older adults handle risky calls, with live AssemblyAI voice agents.

## Long description

Adults aged 60 and older reported nearly $2.4 billion in fraud losses in 2024, according to the FTC. This figure covers all fraud. Phone impersonation calls illustrate one part of the problem: a stranger creates urgency, claims authority and asks an older adult to share private details or send money.

Eufisky is a voice AI prototype that helps during the conversation. Trusted contacts ring directly and bypass transcription and recording. Unknown callers first meet Front Door, a voice agent that asks who they are and why they called. If the call connects, Eufisky monitors the caller and senior through separate audio streams with fixed speaker labels.

AssemblyAI powers Front Door and the private Guardian conversation through the Voice Agent API. Universal Streaming transcribes each connected audio leg. Keyterm prompting includes names, ordinary call purposes and scam vocabulary. A deterministic policy combines speaker-specific evidence, including urgency, authority claims, requests for private information, payment methods and compliance cues, into a decaying 0-100 risk score. The score represents a heuristic, not a probability that a caller is fraudulent.

At 40, the senior hears a private nudge. At 65, or earlier for defined sensitive-disclosure or compliance rules, Eufisky holds the caller and starts Guardian. The senior can resume, invite family into a private conference, end the call or trust the caller. At 90, Eufisky recommends family involvement. These reversible choices aim to preserve the senior's autonomy.

After microphone calls, AssemblyAI batch transcription requests PII redaction for text and audio. The current LLM Gateway generates an incident summary with a deterministic template fallback. Recorded call events ground actions and outcomes. The family dashboard shows evidence, transcripts and state changes. Typed calls use local numeric masking and have no audio recording.

Recent voice fixes preserve capture samples, smooth PCM playback and wait for speech completion before automatic hangup. Verification includes 89 Python tests, four JavaScript audio checks and a hosted Chrome microphone test using synthetic English speech. Human-accent recognition, noisy-room performance and scam false-positive rates remain unbenchmarked.

The initial buyer hypothesis is an adult child supporting a parent. A $9-15 monthly family subscription needs demand and cost validation. Today's public prototype simulates phone calls in a browser. Next steps are human voice evaluation, real telephony and caller identity verification. Possible later partners include telcos and senior-living operators.

## Technologies and tags

AssemblyAI, Voice Agent API, Universal Streaming, PII Redaction, LLM Gateway, Voice AI, Elder Care, Fraud Prevention, FastAPI, SQLite, Accessibility

## Links to paste

- Live prototype: https://eufisky.onrender.com/
- Pitch deck: https://eufisky.onrender.com/slides
- Pitch PDF: https://eufisky.onrender.com/static/pitch/Eufisky-hackathon-deck.pdf
- Editable PowerPoint: https://eufisky.onrender.com/static/pitch/Eufisky-pitch.pptx
- Public repository: https://github.com/adib-cyber007/Eufisky
- Deployment platform: Render
- Team: Team Eufisky
- Video link: upload the included Eufisky-demo.mp4 to YouTube as Unlisted, then paste its share link.

## Media ready to upload

- Cover: Eufisky-submission-cover.png, 1920 x 1080 (16:9).
- Deck: Eufisky-hackathon-deck.pdf, nine slides.
- Editable deck: Eufisky-pitch.pptx. Three-minute speaking notes are inside each slide.
- Video: Eufisky-demo.mp4, approximately 1 minute 43 seconds and 2.7 MB.

The included narrated video demonstrates prerecorded Replay and a preloaded sample report. It identifies the browser simulation. It does not demonstrate a live microphone conversation. For a stronger presentation, use the live voice recording plan below.

## Additional information for judges

Open the live prototype and select Try judge Replay for an isolated saved scenario. For microphone testing, start a new room and open the Caller and Senior phones. Use headphones and allow microphone access. On Render's free tier, allow the service to wake before recording. The demo uses simulated browser phone lines. Real carrier routing and verified caller identity are roadmap work. Default-off stretch features should remain off for the submission.

## Final upload checklist

1. Confirm each team member has registered and joined Team Eufisky on lablab.ai.
2. Open the AssemblyAI Voice Agent Hackathon event and use your team's submission form.
3. Paste the title, descriptions, technologies, repository and demo URLs above. Select the AssemblyAI/voice-agent track offered by the form.
4. Upload the cover and pitch PDF. If the form asks for a deck link, use the public PDF link above.
5. Upload the MP4 to YouTube as Unlisted. Paste the working video URL in the submission form.
6. Preview the submission. Open the video, PDF and prototype in a private browser window to confirm public access.
7. Verify the deadline displayed in the signed-in event form, then press Submit. These materials do not submit the entry automatically.

Organizer checks: title under 50 characters, short description under 255, long description over 100 words, 16:9 cover, video under five minutes and 300 MB. Our video also fits the project's three-minute target. Any event-specific limits in the form take priority.

## Stronger live voice video: three-minute recording plan

Use a fresh room and headphones. Show the actual live app and label prerecorded footage if you use it. If the provider stalls, switch to Replay and say that it is a saved scenario. Do not present typed text as microphone recognition.

| Time | Screen | Spoken line or action |
| --- | --- | --- |
| 0:00-0:20 | Cover slide | “Eufisky helps older adults handle risky calls. It screens unknown callers, then can pause a conversation for private support. This prototype uses browser phones and AssemblyAI.” |
| 0:20-0:45 | Caller phone | Dial. After Front Door asks who and why, say: “I am Michael from Medicare, calling about a benefits update.” Wait for routing. |
| 0:45-1:10 | Senior phone | Answer. Wait for the introduction to finish. Show that the live bridge opens. |
| 1:10-1:40 | Caller and dashboard | Say: “Your benefits will be suspended today unless we verify your account. Please read the number on your Medicare card.” Show evidence and the Guardian state. |
| 1:40-2:10 | Senior phone | Listen to Guardian. Say: “Please bring Sarah into the call.” Show the caller remains held during private family support. If recognition fails, acknowledge it and repeat naturally. |
| 2:10-2:30 | Dashboard | Say: “The senior can resume, invite family, end the call or trust the caller. Trusted calls bypass transcription.” End the test call. |
| 2:30-2:50 | AssemblyAI slide | “AssemblyAI provides voice agents, separate streaming transcription, batch redaction and summaries through the LLM Gateway. Explicit rules decide when to intervene.” |
| 2:50-3:00 | Closing slide | “Our next work is human voice evaluation and real phone integration. Try the browser demo at eufisky.onrender.com.” |

If the new incident report is still processing, say so. Do not substitute a preloaded report while describing it as the result of the just-recorded call.

## Judge Q&A

1. **Is this a real phone service?** The public prototype simulates Caller, Senior and Family phones in a browser. Real carrier integration is next.
2. **Where does AssemblyAI run?** Voice Agent API for Front Door and Guardian, Universal Streaming for connected call legs, batch PII redaction after microphone calls, and LLM Gateway summaries.
3. **How do you identify speakers?** Caller and senior use separate streaming sessions. Labels come from the audio leg, without a diarization claim.
4. **How do you decide a call is risky?** Explicit weighted rules combine speaker-specific evidence and decay. Thresholds trigger intervention. They are not calibrated probabilities.
5. **What if a legitimate call triggers Guardian?** The senior can resume or trust the caller. Families can enable Always ring me first while keeping connected-call monitoring.
6. **What happens to trusted calls?** They ring directly and bypass transcription and recording. Caller-ID spoofing remains a risk until identity verification exists.
7. **Is recognition accurate?** A hosted synthetic-voice regression now recognizes “pharmacy delivery” correctly. Names still need work. Human-accent and noisy-room accuracy have not been benchmarked.
8. **What if AssemblyAI disconnects?** The current session can fall back to the existing STT/text path. Summaries have a deterministic template fallback. Network/provider outages still affect the demo.
9. **How does privacy work?** Trusted calls bypass capture. Microphone-call postprocessing requests PII-redacted text and audio. The prototype still needs a production retention and consent policy before deployment to families.
10. **Who pays?** An adult child is the initial buyer hypothesis. $9-15 per month is a pricing hypothesis. We have not validated paying demand or signed distribution partners.

## Sources

- Official event, Sep 1-30, 2026: https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon
- Required deliverables: https://lablab.ai/guide
- Organizer form guidance: https://github.com/lablab-ai/community-content/blob/main/blog/en/hackathon-guidelines.mdx
- FTC statistic: https://www.ftc.gov/system/files/ftc_gov/pdf/P144400-OlderAdultsReportDec2025.pdf
- Implementation and test evidence: repository STATE.md, docs/ARCHITECTURE.md, docs/BUSINESS.md and docs/HUMAN_TASKS.md, voice fixes d36f679 and f59308a, deployed verification fb63c23.
