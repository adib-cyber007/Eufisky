# Eufisky 3-minute demo script

## One-minute setup

In PowerShell, from the Eufisky folder, run one command:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Success means PowerShell says `Uvicorn running on http://127.0.0.1:8000` and
`http://localhost:8000/api/health` shows `"ok":true` and `"db_ok":true`.

Open `http://localhost:8000/?room=demo`. From that page, open Caller, Margaret,
Sarah, and the Family dashboard in four tabs. Keep the dashboard visible and use
type-to-talk for the most reliable demo. If you use a microphone, allow the
browser permission prompt first.

## 0:00–0:25 — explain the protection

Show the landing page, then the dashboard.

Say: “Eufisky is a voice AI agent that guards an older adult’s phone line.
Trusted people pass through privately. Unknown callers are screened, monitored
for scam pressure, and paused before personal details leave the call.”

On the dashboard, briefly point to Sarah and Walgreens under **Contacts** and
the three ready-made reports under **History**.

## 0:25–0:45 — trusted family call

1. On **Caller**, choose **Sarah — trusted** and click **Dial Margaret**.
2. On **Margaret**, point out **Trusted — not monitored**, then click **Answer**.
3. In Caller’s type-to-talk box, enter: `Hi Mom, it’s Sarah. I’ll see you at lunch.`
4. Click **Hang up** on Caller.

Say: “Sarah rings straight through. Eufisky does not transcribe or record trusted
calls.”

## 0:45–1:05 — benign pharmacy call

1. On **Caller**, choose **Walgreens — trusted** and click **Dial Margaret**.
2. On **Margaret**, click **Answer**.
3. In Caller’s type-to-talk box, enter: `Hello Margaret, this is Walgreens. Your prescription is ready for pickup.`
4. In Margaret’s box, enter: `Thank you. I’ll collect it this afternoon.`
5. Click **Hang up** on Caller.

Say: “Known services are private too. Eufisky spends AI time only where it adds
protection.”

## 1:05–2:25 — Medicare scam and Guardian

1. On **Caller**, choose **Unknown caller** and click **Dial Margaret**.
2. When Front Door asks who is calling, enter exactly:
   `This is Michael from Medicare, calling about an urgent update to her benefits.`
3. On **Margaret**, click **Answer** when the phone rings.
4. On Caller, enter:
   `Your benefits will be suspended today unless we verify your account.`
5. Point to the dashboard risk meter and the private nudge in the timeline.
6. On Caller, enter:
   `Please read me the number on your Medicare card and your bank account number.`
7. Point out that Caller changes to **On hold** while Margaret hears Guardian
   privately.
8. On **Margaret**, enter: `Please get Sarah.` If the voice agent is slow, click
   **Bring in Sarah**.
9. On **Sarah**, click **Join call**.
10. On Sarah, enter: `Mom, you did the right thing. We can call Medicare ourselves.`
11. On Sarah, click **End call**.

Say: “Two speaker-separated AssemblyAI streams feed a deterministic safety
engine. At the danger threshold Eufisky severs the public bridge first, puts the
caller on hold, and speaks only to Margaret. Sarah joins privately, and the scam
number is blocked.”

## 2:25–3:00 — redacted incident report

1. On the dashboard, click **History**.
2. Click **Refresh** if the new card has not appeared yet; allow up to 60 seconds.
3. Point to the peak-risk badge, plain-English summary, caller claim, requests,
   intervention, outcome, recommendation, risk trace, and safety timeline.
4. Open **View redacted transcript** and point to the hidden digit run such as
   `####`. If redacted audio is available, press Play briefly.

Say: “After the call, AssemblyAI creates a multichannel transcript, removes
personal information from text and audio, and produces a family-readable incident
summary. If either provider step is unavailable, Eufisky clearly flags a local
template fallback instead of leaving the family with nothing.”

## Replay fallback — no microphones or live call required

On the dashboard **Live** tab, choose **2×** and click **▶ Replay demo call**.
The complete screening, risk rise, Guardian intervention, family conference, and
ending animate in about 23 seconds. Narrate the Medicare section above while it
runs. Success means the risk meter crosses all three levels, Caller and Margaret
captions appear, Guardian shows as active, and the safety timeline ends at
**WRAPUP**.
