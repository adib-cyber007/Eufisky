# Eufisky business case

## The problem

Adults aged 60 and over reported **$2.4 billion in fraud losses in 2024**, four
times the reported total in 2020. The same FTC report found that median
individual loss from phone-originated fraud was $2,210, and phone calls were
the leading contact method for people 80 and over.
[Source: FTC, Protecting Older Consumers 2024–2025](https://www.ftc.gov/system/files/ftc_gov/pdf/P144400-OlderAdultsReportDec2025.pdf).

Call blocking helps when a number is already known to be dangerous. It is less
useful when a spoofed or newly created number reaches a senior and a persuasive
caller gradually introduces urgency, authority, secrecy, or payment demands.
That in-call gap is where Eufisky intervenes.

## Buyer and user

The protected user is an older adult who wants to keep answering the phone
without learning a new app. The first buyer is an adult child caring for a
parent aged 70 or older. Channel buyers can include:

- mobile and landline carriers that want a family-safety add-on;
- insurers seeking fewer fraud losses and higher member retention;
- senior-living operators standardizing resident safety;
- banks and credit unions extending scam prevention beyond transaction alerts.

## Pricing idea

These are hypotheses for validation, not current offers:

| Package | Pricing hypothesis | Intended buyer |
|---|---:|---|
| Family | $9–$15 per protected line per month | Adult children |
| Family Plus | $19 per month for two protected lines and multiple guardians | Households |
| Partner | $2–$5 per covered member per month at volume | Telcos, insurers, banks |
| Senior living | Per-resident annual contract with pooled usage | Operators |

Usage economics are attractive because trusted contacts bypass AI processing.
The paid workload is concentrated on unknown calls rather than every minute on
the line. Actual pricing depends on telephony, inference, support, and fraud
operations costs measured in a production pilot.

## Go to market

1. **Family pilots:** recruit adult children through caregiver communities and
   senior-safety nonprofits; measure activation, unknown-call completion,
   intervention acceptance, and false-positive rate.
2. **Senior-living pilot:** install on a small resident cohort with staff and
   family escalation; publish an anonymized safety and usability report.
3. **Insurer or bank partnership:** offer Eufisky to higher-risk members and
   compare reported scam incidents, loss avoidance, and support contacts.
4. **Telco distribution:** integrate at the network edge as an opt-in family
   safety feature, using carrier call authentication and billing.

The sales story is not “AI answers every call.” It is “trusted people remain
private, while unfamiliar callers receive focused, explainable protection.”

## Business value

- **Prevention before payment:** intervention occurs while pressure is building,
  before a card number, transfer, or remote-access step is completed.
- **Family leverage:** one guardian can support a parent without listening to
  ordinary conversations.
- **Explainable operations:** evidence phrases, speaker labels, thresholds, and
  tool actions create a reviewable incident trail.
- **Channel differentiation:** telcos and insurers can add a visible safety
  service instead of another generic blocklist.
- **Accessible adoption:** the senior continues using a familiar phone-call
  interaction; the family receives the dashboard.

## Roadmap

### Next: production phone line

Connect Twilio or a carrier media-stream API, map caller and callee legs to the
existing streaming adapters, and whisper Guardian audio only to the protected
leg. Add STIR/SHAKEN attestation signals, durable encrypted storage, accounts,
consent, audit logging, rate limits, and production observability.

### Then: broader household coverage

- Spanish screening, risk lexicon, Guardian prompts, and incident summaries.
- A family mobile app for contacts, alerts, live conference invitations, and
  incident review.
- Household-specific keyterms such as doctors, pharmacies, utilities, and
  family names.
- Partner administration for senior living, insurers, banks, and telcos.

### Later: measured intelligence

Use opt-in, redacted incident outcomes to tune lexicon weights, test additional
languages, and evaluate false negatives and false positives. Preserve the
deterministic action layer so a model suggestion never becomes a call-control
action without an allowed tool and an auditable rule.

## Success measures

Pilot evaluation should track scam attempts interrupted before disclosure,
Guardian acceptance, family conferences, false interventions per 100 unknown
calls, median response latency, trusted-call bypass rate, and cost per protected
line. The goal is safer autonomy—not maximum call blocking.
