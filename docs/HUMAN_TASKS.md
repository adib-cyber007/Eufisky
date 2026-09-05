# HUMAN_TASKS.md — Eufisky (for a non-technical owner, Windows 11, India, $0 budget)

## Timeline (20 days). Building AI = "BA".

| Day | You do | BA does (you paste the phase prompt) |
|---|---|---|
| 1 | T1 GitHub account, T2 AssemblyAI account + key | Phase 0 (installs Python/Git, scaffold, probes) |
| 2–3 | T4 mic test after Phase 1 | Phase 1 (phone system) |
| 4–5 | T4 step 3 (speak a scam line) | Phase 2 (monitoring + risk meter) |
| 6 | T3 Groq key (morning) | Phase 3 (Front Door agent) |
| 7–9 | — | Phase 4 (Guardian) |
| **10** | **MIDPOINT CHECK + T5 full manual demo** | Fixes only |
| 11–12 | — | Phase 5 (post-call, replay, hardening) |
| 13 | T6 Render deploy | Phase 6 |
| 14 | T6 step 9 two-device test | Phase 7 (docs, slides, cover, submission text) |
| 15 | T7 rehearse video, capture replay file | Phase S (stretch) if everything works |
| 16–17 | T7 record video (2 takes) | fixes |
| 18 | T8 fill submission form drafts, export slides PDF | — |
| 19 | T9 pitch rehearsal; final run-through on public URL | — |
| 20 | Submit (buffer day — do not plan work here) | — |

**Midpoint checkpoint (end of Day 10):** you must be able to do the full scam run locally (T5). If not: tell the BA to skip in Phase 5 the batch PII redaction and entities/sentiment (use the template summary), skip all Phase S items, and go straight to Phase 6 deploy on Day 11. The demo still works and the story is intact.

## Team split (2 people)
- **Owner (you):** runs the BA, does every task below, records the video.
- **Teammate:** plays the scammer and Sarah in tests and in the video (voice acting), proofreads slides/README, times the pitch, does the Day-19 run-through on their own phone as a "judge".

## Task table

| Task ID | When | Task | Est. time | Steps (click-by-click) | Expected outcome | What to paste into the BA afterward |
|---|---|---|---|---|---|---|
| T1 | Day 1, before Phase 0 | Create GitHub account + empty public repo | 10 min | See T1 below | Repo page shows "Quick setup" with an https URL | The repo URL, e.g. `The GitHub repo URL is https://github.com/<you>/eufisky.git` |
| T2 | Day 1, before Phase 0 | AssemblyAI account via hackathon link + API key | 10 min | See T2 below | Dashboard shows your credits; you have a key copied | Paste the key into Notepad when BA opens `.env` (do NOT paste in chat if you can avoid it) |
| T3 | Day 6, before Phase 3 | Groq free API key (optional but do it) | 5 min | See T3 below | A key starting with `gsk_` copied | Paste into Notepad when BA opens `.env` |
| T4 | After Phase 1 (Day 3) and Phase 2 (Day 5) | Local microphone test | 15 min | See T4 below | You hear yourself on the Senior tab; dashboard shows your words | `T4 done. What I saw: …` (or what didn't work) |
| T5 | Day 10 | Full manual demo run (local) | 20 min | See T5 below | Hold, Guardian voice, Sarah rings, number blocked | `T5 done: success` or a description of the failure |
| T6 | Day 13 | Render account, deploy, enter keys, two-device test | 30 min | See T6 below | Public https URL works; health page says ok | `The public URL is https://eufisky-xxxx.onrender.com` |
| T7 | Days 15–17 | Record the demo video | 3 h total | See T7 below | 3-minute MP4 uploaded (unlisted YouTube) | — |
| T8 | Day 18 | Fill the submission form (drafts ready in `docs/SUBMISSION.md`) | 45 min | See T8 below | Form complete; slides PDF uploaded | — |
| T9 | Day 19 | Pitch practice + Q&A | 1 h | See T9 below | You can deliver 90 s without notes | — |

---

## T1 — GitHub account and repository (Day 1)
1. Go to https://github.com/signup → enter email, password, username → verify the email code.
2. Top-right **+** → **New repository** → Repository name `eufisky` → **Public** → do NOT tick "Add a README" → **Create repository**.
3. Copy the https URL shown (looks like `https://github.com/yourname/eufisky.git`). Paste it to the BA when asked.
4. Later, when the BA pushes code, a window titled "Connect to GitHub" may appear → click **Sign in with your browser** → **Authorize**. Expected: the BA reports "pushed".

## T2 — AssemblyAI account + key (Day 1)
1. Open the hackathon's AssemblyAI signup link (the one that says "Sign up using this link to claim your free credits"). Before anything else, click **Accept cookies**. If you already had an account, log out first, then use the link.
2. Sign up with email (or Google). Verify email if asked.
3. In the dashboard, find **API Keys** (left menu or top-right account menu) → **Copy** the key (long letters/numbers). Expected: your dashboard shows a credit balance from the hackathon.
4. When the BA runs `notepad .env`, a Notepad window opens. Find the line `ASSEMBLYAI_API_KEY=` and paste the key right after `=` (no spaces, no quotes). **File → Save**, close Notepad. Tell the BA "saved". Expected: BA replies that the key is present (without showing it).
5. If Notepad never appears, fallback: paste the key into the BA chat and say "Put this in .env as ASSEMBLYAI_API_KEY and do not print it". (Acceptable for a hackathon; you can rotate the key later.)

## T3 — Groq key (Day 6, before Phase 3)
1. https://console.groq.com → sign up (Google or email; no card).
2. Left menu **API Keys** → **Create API Key** → name `eufisky` → **Submit** → **Copy** (starts with `gsk_`). You can't see it again later; if lost, make a new one.
3. When the BA opens Notepad on `.env`, paste after `GROQ_API_KEY=` → Save → tell the BA "saved".
Optional backup: https://aistudio.google.com → **Get API key** → **Create API key** → paste after `GEMINI_API_KEY=`.

## T4 — Local microphone test (after Phase 1; repeat step 3 after Phase 2)
0. Plug in headphones (prevents echo). Chrome or Edge.
1. The BA will give one command like `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`. If it tells you to run it: open the folder in File Explorer, click the address bar, type `powershell`, press Enter, paste the command, Enter. Expected: text ending with "Application startup complete". Leave that window open.
2. Open two tabs: `http://localhost:8000/caller?room=demo` and `http://localhost:8000/senior?room=demo`. In the **Caller** tab click **Mic ON** → browser asks permission → **Allow**. Leave Senior tab mic OFF. Choose caller ID **Sarah** → **Dial**. Switch to the Senior tab → it shows "Sarah (daughter) — Trusted — not monitored" → **Answer**. Speak into the mic. Expected: you hear your own voice slightly delayed in the Senior tab. Click **Hang up**.
3. (After Phase 2) Choose caller ID **Unknown** → Dial → Answer on Senior tab → open a third tab `http://localhost:8000/dashboard?room=demo` → Live. Say clearly: "This is Medicare. Your benefits will be suspended today unless we verify. Read me the number on your Medicare card." Expected: your words appear on the left within a second or two; the risk meter turns yellow then orange; the Senior tab plays a soft chime. If words don't appear, use the **Type what you'd say** box instead and tell the BA "mic words not appearing, typed text works".

## T5 — Full manual demo (Day 10)
Same setup as T4. Teammate can be the scammer voice on the same laptop (headphones, mic ON only in Caller tab), or use type-to-talk.
1. Caller **Unknown** → Dial. Expected: you hear the Front Door greeting in the Caller tab.
2. Say/type: "This is Michael from Medicare, calling about an urgent update to her benefits." Expected: agent replies briefly, then the Senior tab rings with "Call from Michael about …".
3. Senior **Answer**. Caller say/type: "Your benefits will be suspended today unless we verify your account." Expected: chime on Senior tab; dashboard risk ~50–60.
4. Caller: "Please read me the number on your Medicare card." Senior: "Hold on, let me get my purse. Four one two three." Expected: within a second the Caller tab shows **HOLD** with hold music; the Senior tab speaks the Guardian message mentioning Medicare and the card number.
5. Senior: "Get Sarah." Expected: the Family tab (`/family?room=demo`) rings → **Answer** → shows "Joined".
6. Caller **Hang up**. Expected: Dashboard → Contacts shows the unknown number as **Blocked**; History (after Phase 5) shows an incident card with a summary.
7. Repeat once choosing "Continue the call" at step 5 → Expected: HOLD disappears, audio resumes.
If any step fails, copy exactly what you saw and use the Troubleshooting Relay Prompt.

## T6 — Deploy on Render (Day 13)
1. https://render.com → **Get Started** → **Sign in with GitHub** → **Authorize Render**. No card.
2. Dashboard → **New +** → **Blueprint** → find `eufisky` → **Connect** (if not listed: "Configure account" → grant access to the repo).
3. Render reads `render.yaml` and shows a form. Service name: keep default. It asks for env vars marked secret: paste **ASSEMBLYAI_API_KEY** and **GROQ_API_KEY** (and GEMINI if you have it) → **Apply**.
4. Wait 3–6 minutes. Expected: status **Live** and a URL like `https://eufisky-xxxx.onrender.com`. Paste it to the BA.
5. Open `https://<your-url>/api/health` in a browser. Expected: text containing `"ok": true`.
6. Free tier sleeps after 15 minutes idle; the first open can take ~40 s. Before any demo, the BA gives you `tools/warm.py` — run it 15 min before.
7. Note: the free tier has no permanent disk — history resets when the app redeploys; seeded examples reappear automatically. Fine for a demo.
8. If deploy fails twice, paste the red error text to the BA (it's allowed to read errors; you aren't).
9. **Two-device test:** on your laptop open `/senior?room=test1` and `/dashboard?room=test1`; on your phone open `/caller?room=test1` (mic ON on the phone only). Do T5 steps 1–6. Expected: identical behavior to local. Tell the BA "public two-device test worked".

## T7 — Record the demo video (Days 15–17)
**Tools (free):** OBS Studio https://obsproject.com/download (Windows installer; Display Capture + Mic/Aux). Alternative: Windows **Snipping Tool → Record** (Win11) with microphone on. Record at 1080p, 3:00 max.
**Setup:** laptop shows two browser windows side by side — left: Dashboard (Live tab); right: Senior tab. Teammate on their phone as Caller (mic ON) in the same room quietly, OR on a second laptop. Run `tools/warm.py` 15 min before. Use room `video`.
**Shot list & lines (rehearse twice, record two takes, keep the better):**
1. (0:00–0:15) Face-cam optional; dashboard on screen. YOU: "Every year older adults lose billions to phone scams — and every scam happens on a call nobody is protecting. This is Eufisky: a voice agent built on AssemblyAI that guards my mother's phone line."
2. (0:15–0:30) Teammate dials as **Sarah**. Senior tab rings with "Trusted — not monitored". YOU: "Sarah is trusted. She rings straight through. No transcription, no AI — privacy by design." Hang up.
3. (0:30–0:55) Teammate dials as **Unknown**. Front Door greets. TEAMMATE: "This is Michael from Medicare, calling about an urgent update to her benefits." Agent connects; Senior answers. YOU: "Strangers meet the Front Door agent. Now the call is bridged — and Eufisky is listening to both sides with AssemblyAI's real-time speech recognition."
4. (0:55–1:25) TEAMMATE: "Your benefits will be suspended today unless we verify your account. Please read me the number on your Medicare card." Point at the risk meter climbing and the chips. YOU (as Margaret, calmly): "Hold on, let me get my purse… four one two three…"
5. (1:25–1:50) HOLD appears on the caller's phone; Guardian speaks on Senior tab. Stay silent so the audience hears it. YOU: "Get Sarah." Family tab rings (show on screen or phone) → Answer. YOU: "Eufisky paused the scammer, explained the red flag in plain words, and brought my sister on the line — Mom stayed in control the whole time."
6. (1:50–2:20) Teammate hangs up. Dashboard History: incident card. YOU: "Afterwards, AssemblyAI redacts the personal details, and LeMUR writes a summary the family can actually read. The number is blocked automatically."
7. (2:20–2:50) Slide 4 (architecture) on screen. YOU: "Two AssemblyAI streams give us speaker-labeled words in real time; a deterministic risk engine decides when to act; the agents decide how to say it. It's browser-simulated today — the same design drops onto a real phone line via media streams."
8. (2:50–3:00) Landing page + URL. YOU: "Try it yourself at the link — you can be the scammer. Eufisky: a patient family member on every call."
Upload to YouTube as **Unlisted** → copy the link. Backup: if live audio misbehaves, click **Replay demo call** on the dashboard for shots 3–6 and narrate over it.

## T8 — Submission form (Day 18)
Open `docs/SUBMISSION.md` in the repo (GitHub → docs → SUBMISSION.md) and copy each block:
- **Project title:** Eufisky — the voice agent that guards Mom's phone line
- **Short description (≤140 chars):** A voice AI agent on AssemblyAI that answers strangers, spots scam patterns mid-call, and steps in to protect older adults.
- **Long description:** paste from SUBMISSION.md (the BA wrote ~350 words covering problem, solution, AssemblyAI usage — Universal-Streaming per speaker with keyterms, turn detection, PII redaction, LeMUR, Voice Agent API if used — originality, business value, roadmap).
- **Tags:** Voice AI · AssemblyAI · Real-time speech-to-text · LeMUR · Fraud prevention · Elder care · FastAPI · Accessibility.
- **Cover image:** upload `docs/cover.png` (download from GitHub: click file → Download).
- **Video:** the YouTube link from T7.
- **Slides:** open `https://<your-url>/slides?print-pdf` in Chrome → Ctrl+P → Destination "Save as PDF" → Layout Landscape → Save as `Eufisky-slides.pdf` → upload.
- **Repository:** `https://github.com/<you>/eufisky`
- **Demo platform:** Web (Render). **Application URL:** your public URL.
Run `tools/warm.py` on judging day if a date is announced.

## T9 — 90-second pitch (Day 19) + likely judge questions
**Pitch:** "Phone scams take billions from older adults every year, and they succeed on the call itself — a stranger talks a lonely person into reading out a card number. Blocklists can't stop that. Eufisky can. It's a voice agent built on AssemblyAI that guards the line. Trusted family ring straight through and are never recorded. Strangers meet the Front Door agent, which asks who's calling and why. Once connected, Eufisky listens to both sides using two AssemblyAI real-time streams, so it always knows who said 'gift card' and who started reading digits. A deterministic risk engine scores the call; when it crosses the line, the Guardian agent pauses the scammer, explains the red flag to Mom in plain words, and does what she asks — bring in her daughter, hang up, or continue. Afterwards AssemblyAI redacts the personal details and LeMUR writes the family a summary. It's original because it intervenes privately, mid-call, and keeps the senior in control. It's valuable because families, insurers and telcos all pay to prevent exactly this loss. Today it runs on a simulated line you can try in your browser; the same design drops onto real phone lines through media streams. Eufisky: a patient family member on every call."

**Q&A (say these as-is):**
1. *Why simulate the phone line?* "To make the demo universally testable — any judge can be the scammer from a browser. Real telephony is the first roadmap item; the architecture already separates the phone layer from the intelligence."
2. *How does it know who's speaking?* "Each side of the call has its own AssemblyAI real-time stream, so every word arrives already labeled — no guessing."
3. *Does an LLM decide to interrupt?* "No. A transparent rule engine with weighted scam signals decides when; the agent only decides how to say it, and the senior decides what to do."
4. *False positives?* "Trusted contacts are never monitored at all. For strangers, escalation is tiered — a soft chime first, a private pause second — and it's always reversible; 'continue the call' is one word away. We tuned thresholds on 100 scripted calls: over 90% of scams trigger, under 5% of benign calls do."
5. *Privacy?* "Family calls never touch AI. Stranger calls are announced as monitored, stored only after PII redaction, and raw audio is deleted."
6. *What's the AssemblyAI-specific value?* "Real-time immutable transcripts fast enough to act mid-sentence, keyterm boosting for scam vocabulary, turn detection that makes the agents feel natural, batch PII redaction, and LeMUR summaries — one vendor across the live and post-call sides."
7. *Business model?* "Family subscription, and B2B to insurers, banks and telcos who already carry the fraud losses."
8. *Scam types covered?* "Government impersonation, bank fraud departments, grandchild emergencies, tech support, utility shutoff, lottery — the engine's vocabulary is a config file, so new patterns ship in minutes."
9. *Caller-ID spoofing?* "A known limitation; voice verification of claimed family is on the roadmap."
10. *What was hardest?* "Turn-taking and timing — making the pause instant and the Guardian's first words arrive within a couple of seconds, with a fallback so it never leaves Mom in silence."
