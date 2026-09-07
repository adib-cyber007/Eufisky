# Eufisky submission kit

Everything below is ready to paste. The only asset still requiring a human is
the recorded demo video.

## Project title

Eufisky — A Voice Agent That Guards Mom's Phone Line

## Short description

Eufisky screens unknown callers, detects scam pressure live, and privately helps an older adult before personal details leave the call.

## Long description

Phone scams do not become dangerous when a number appears on screen. They
become dangerous during the conversation, when a persuasive stranger creates
urgency, claims authority, asks for private information, and guides an older
adult toward a payment. Adults aged 60 and over reported $2.4 billion in fraud
losses in 2024, according to the FTC.

Eufisky is a voice AI agent that guards an older adult's phone line. Trusted
contacts ring straight through and are never transcribed. Unknown callers first
meet a Front Door agent that asks who is calling and why. If the call connects,
Eufisky monitors the caller and senior through separate audio legs, preserving
a reliable speaker label for every transcript segment.

AssemblyAI is the voice layer throughout the experience. The Voice Agent API
powers Front Door screening and the private Guardian conversation. Universal
Streaming transcribes each connected leg in real time, with keyterm prompting
for names and scam phrases. A deterministic engine—not an opaque model
verdict—combines speaker-specific evidence such as authority claims, urgency,
payment methods, PII requests, and senior compliance cues into a decaying
0–100 risk score.

At score 40, Margaret hears a private nudge. At 65, or earlier when sensitive
disclosure and compliance rules fire, the caller is put on hold. Guardian then
speaks privately with Margaret and can resume the call, bring in her daughter,
end the call, or trust the caller through explicit tool calls. At score 90,
Eufisky recommends family involvement.

After an unknown call, AssemblyAI batch processing requests PII-redacted text
and audio. A LeMUR-style prompt through AssemblyAI's current LLM Gateway creates
a plain-English incident summary, with a deterministic template fallback if
the provider is unavailable. The family dashboard ties transcript, evidence,
risk, state changes, and actions into one explainable timeline.

What makes Eufisky different is the moment and manner of intervention: it acts
inside the call, distinguishes who said what, pauses the stranger, and gives
the senior a calm, reversible choice without monitoring trusted conversations.
The first buyer is an adult child; distribution can expand through telcos,
insurers, banks, and senior-living operators. Today's public demo is a
browser-based phone simulation. Next comes real telephony, Spanish support,
stronger caller identity, and a family app.

## Tags

Voice AI, AssemblyAI, Real-time STT, LeMUR, Elder care, Fraud prevention, FastAPI, Accessibility

## Links

- Live demo: https://eufisky.onrender.com/?room=demo
- Family dashboard: https://eufisky.onrender.com/dashboard?room=demo
- Slide deck: https://eufisky.onrender.com/slides
- Printable slides: https://eufisky.onrender.com/slides?print-pdf
- API health: https://eufisky.onrender.com/api/health
- Public repository: https://github.com/adib-cyber007/Eufisky
- Cover image, 1920×1080: docs/cover.png
- Social cover, 1200×630: docs/cover-1200x630.png

## 90-second pitch

Older adults reported losing 2.4 billion dollars to fraud in 2024. Call
blocking helps only when a number is already known. The most dangerous moment
comes later—when a convincing stranger says your Medicare benefits end today
and asks you to read the number on your card.

Eufisky guards that moment.

Trusted contacts ring straight through and are never processed. Unknown
callers meet a Front Door voice agent. If a call connects, Eufisky sends the
caller and the senior to separate AssemblyAI Universal Streaming sessions, so
every live word keeps a reliable speaker label. Keyterm prompting sharpens
names and scam language.

An explainable rule engine scores urgency, authority claims, payment requests,
private-data requests, and the senior's response. At the first threshold,
Margaret hears a private nudge. When risk rises, Eufisky pauses the caller and
Guardian speaks privately with her. Through explicit tool calls, Guardian can
resume, bring Sarah into the call, trust the caller, or end it.

Afterward, AssemblyAI batch processing requests PII redaction, and a LeMUR-style
summary through the LLM Gateway creates a plain-English incident report, with a
template fallback.

Eufisky is not another blocklist and not an opaque scam classifier. It is a
speaker-aware, reversible intervention inside the call, designed to preserve
both safety and dignity. Today it is a browser phone simulation. Next: real
phone lines, Spanish, and a family app.

## Judge Q&A

### 1. Is this a real phone service?

Not yet. The public build is a browser-based simulation of Caller, Senior,
Family, and Dashboard devices. Real carrier integration through Twilio or
telco media streams is the next engineering milestone.

### 2. What exactly does AssemblyAI do?

AssemblyAI powers the two conversational agents, real-time transcription on
separate caller and senior streams, keyterm prompting, post-call batch
transcription and PII redaction, and LeMUR-style structured summary generation
through the current LLM Gateway.

### 3. How do you know who said each phrase?

The app opens a separate Universal Streaming session for each audio leg.
Segments inherit the known caller or senior leg label; Eufisky does not guess
the speaker through diarization.

### 4. Does an LLM decide that someone is a scammer?

No. A deterministic engine scores named, speaker-specific evidence with
documented weights, time decay, combination bonuses, and fixed escalation
rules. Models provide conversation, but only registered tool calls can request
state changes.

### 5. What happens to normal family calls?

Trusted contacts bypass Front Door, transcription, risk scoring, recording,
and post-call analysis. They ring straight through.

### 6. What if Eufisky makes a mistake?

Intervention is reversible. Guardian explains the evidence privately and
Margaret can resume the call or trust the caller. The dashboard also exposes
the phrases and transitions behind the score.

### 7. Can caller-ID spoofing bypass the trusted list?

Yes, caller ID alone is not production-grade identity. The roadmap adds carrier
attestation and stronger identity signals. The demo calls this limitation out
explicitly.

### 8. What happens if AssemblyAI summary generation is unavailable?

The call still completes. The app falls back to the live transcript, locally
redacts digit runs, and creates a deterministic template incident report. The
dashboard records which analysis path was used.

### 9. Who pays for this?

The initial buyer is an adult child protecting a parent. A working pricing
hypothesis is $9–$15 per protected line monthly, with volume pricing for
telcos, insurers, banks, and senior-living operators.

### 10. What did you validate?

The full local suite passes 77 tests. The public smoke test verifies health,
database access, all pages, secure Dashboard WebSockets, Replay evidence,
transcript, state and tool events, and completion. A two-device HTTPS
microphone/voice call also passed.

## Three-minute video shot list

Keep the browser at 100% zoom. Warm the public site first. Use one room value on
every tab, preferably `demo`. If live voice is unpredictable, use type-to-talk
or Replay; both are part of the product.

| Time | Tab on screen and action | Exact spoken line |
|---|---|---|
| 0:00–0:18 | Landing page, then briefly point to “Trusted calls stay private” | “Eufisky is a voice AI agent that guards an older adult's phone line. Trusted people pass through privately. Unknown callers are screened, monitored for scam pressure, and paused before personal details leave the call.” |
| 0:18–0:30 | Family Dashboard, Contacts tab; show Sarah and Walgreens as Trusted | “Unlike a blocklist, Eufisky protects the conversation itself. And unlike always-on monitoring, known family and care contacts are never transcribed.” |
| 0:30–0:42 | Caller tab; choose the unknown Medicare caller and click Dial | “I will play an unknown caller claiming to be from Medicare. Front Door answers before Margaret's phone ever rings.” |
| 0:42–0:57 | Caller tab, type-to-talk | “This is Michael from Medicare about an urgent update to her benefits.” |
| 0:57–1:07 | Caller tab while Front Door connects; switch to Margaret tab when it rings and click Answer | “Front Door identifies who is calling and why. It can connect, take a message, or decline through explicit tools.” |
| 1:07–1:20 | Caller tab, type-to-talk; then switch to Dashboard Live | “Your benefits will be suspended today unless we verify your account.” |
| 1:20–1:34 | Dashboard Live; point to score, caller label, evidence chips, and first level change | “Caller and senior audio go to separate AssemblyAI Universal Streaming sessions, so every word keeps a speaker label. The visible score comes from deterministic rules, not an LLM verdict.” |
| 1:34–1:46 | Caller tab, type-to-talk; return to Dashboard | “Please read me the number on your Medicare card.” |
| 1:46–1:54 | Margaret tab, type-to-talk | “Let me get my purse.” |
| 1:54–2:12 | Margaret tab as Guardian speaks; show Caller tab on hold briefly | “That combination—authority, urgency, a private-data request, and a compliance cue—crosses the intervention rule. The caller is paused while Guardian speaks only to Margaret.” |
| 2:12–2:19 | Margaret tab, type-to-talk | “Please get Sarah.” |
| 2:19–2:31 | Sarah tab; click Join call, then show Dashboard state | “Guardian acts through tools. It can resume, call family, end the call, or trust the caller. Here, Sarah joins without the caller hearing the private check-in.” |
| 2:31–2:45 | End the call; Dashboard History tab, open the newest incident | “After the call, AssemblyAI requests PII-redacted text and audio. A LeMUR-style summary through the LLM Gateway creates this plain-English incident report, with a template fallback.” |
| 2:45–2:55 | Dashboard incident; point to redacted transcript and evidence timeline | “The family sees what happened, which phrases changed risk, what Eufisky did, and whether any sensitive detail was detected—without exposing captured numbers.” |
| 2:55–3:00 | Final slide or landing page | “Eufisky is a steady voice inside the call. Next: real phone lines, Spanish, and a family app.” |

### Recording fallback

If a live call stalls, switch to the Dashboard Live tab, choose **Fast (4×)**,
and click **Replay demo call**. Say: “Replay drives the same transcript,
evidence, risk, state, and tool events without a microphone.” Continue from the
1:20 line.
