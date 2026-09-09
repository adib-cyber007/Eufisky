# Real telephony roadmap

Status: **not implemented**. `FEATURE_TWILIO_TELEPHONY` is reserved and defaults
to off. Do not enable or build this path until the owner confirms that a Twilio
trial number can receive the intended calls and call the verified senior/family
destinations in the relevant country.

## Target call topology

Use a Twilio Conference as the switchboard, with separate participants for the
unknown caller, senior, and optional family member. Persist Twilio `CallSid`,
`ConferenceSid`, participant labels, and `StreamSid` beside Eufisky's call ID.
Keep trusted-contact routing on a direct, unmonitored Twilio `<Dial>` path.

For an unknown caller:

1. Twilio posts the inbound webhook to `/twilio/voice`. Validate the
   `X-Twilio-Signature`, normalize the caller ID, create the Eufisky call, and
   return a bidirectional `<Connect><Stream>` for the Front Door exchange.
   The app receives the caller's inbound track and sends Front Door audio back
   as base64, headerless 8 kHz `audio/x-mulaw` frames.
2. When Front Door chooses `connect_caller`, close that stream and update only
   the caller Call resource to new TwiML. The new TwiML starts a unidirectional
   `<Start><Stream track="both_tracks">` and then joins the named Conference.
   Dial the verified senior number as a second labeled Conference participant.
3. Pass the Eufisky call ID and leg label as nested Stream custom parameters;
   Twilio Stream URLs do not accept query parameters. `/ws/twilio-media`
   accepts `connected`, `start`, `media`, `mark`, and `stop` messages. The
   `both_tracks` media track field separates caller inbound audio from the
   outbound senior-side conference mix.
4. Decode the base64 8 kHz mono mu-law payload, convert it to signed PCM16, and
   resample to 16 kHz. Feed each track into its own existing `STTStream`; keep
   Eufisky's rule engine, state machine, dashboard events, post-call processing,
   and block policy unchanged.

## Guardian: private whisper to one leg

At level 2, set the caller Conference participant to `hold=true` with a calm
hold URL. Then redirect only the senior's `CallSid` to a private bidirectional
`<Connect><Stream>` controlled by Eufisky. This temporarily removes the senior
from the public Conference while leaving the caller on hold. The private stream
receives Margaret's speech and plays Guardian audio only to her; the caller can
hear neither direction.

Map Guardian tools as follows:

- `resume_call` / `add_to_trusted`: redirect the senior Call back to the same
  Conference, wait for its participant status callback to report connected,
  then release the caller's hold.
- `conference_family`: create an outbound participant for the verified family
  number, keep the caller held, return Margaret to the Conference after family
  answers, and let the family controls decide whether to resume or end.
- `end_call`: complete the caller participant and senior private stream, end
  the Conference if empty, and run the existing wrap-up/block path.

Twilio also exposes Conference participant coaching (`coaching=true` with
`callSidToCoach`) where only the coached participant hears the coach. That is a
good fit for a human support participant. For Eufisky's generated Guardian
audio, the temporary private bidirectional senior stream is the explicit
whisper-to-one-leg boundary and is easier to test for caller isolation.

## Endpoints and durable fields

Add these only inside the disabled telephony package:

- `POST /twilio/voice`: inbound routing and Front Door TwiML.
- `POST /twilio/status`: idempotent call/participant lifecycle updates.
- `POST /twilio/hold`: minimal hold-music TwiML.
- `WSS /ws/twilio-media`: screening, monitoring, and private Guardian media.
- Durable fields: Eufisky call ID, caller/senior/family `CallSid` values,
  `ConferenceSid`, `StreamSid`, stream purpose, and last processed sequence.

Use Twilio sequence numbers and status-event IDs to reject duplicates and late
events. A reconnect may resume monitoring only when the Eufisky state and all
Twilio identifiers still match. Otherwise, fall back to a safe message and end
the unknown call rather than bridging it unmonitored.

## Security, privacy, and failure policy

- Keep Account SID, Auth Token/API key, and phone numbers in secret environment
  variables. Never put them in URLs, custom parameters, logs, or the repository.
- Validate `X-Twilio-Signature` on HTTP callbacks and the signed WebSocket
  upgrade. Accept WSS on port 443 only and enforce Twilio's documented message
  schema, payload size, and monotonic sequence numbers.
- Announce monitoring/AI use as required by the caller's jurisdiction. Preserve
  the current trusted-contact promise by never starting a Media Stream on the
  direct trusted path.
- Close every stream and AssemblyAI session on `stop`, call completion, timeout,
  or disconnect. If Guardian isolation cannot be confirmed, end the call; never
  reconnect the caller while the private stream is active.

## Trial gate and acceptance checks

Proceed only after the owner confirms all three facts: a Twilio trial number is
active, the senior and family numbers are verified trial destinations, and a
real inbound plus outbound call succeeds in the intended country. Then test on
a separate branch with `FEATURE_TWILIO_TELEPHONY=1`; never replace the browser
demo until all checks pass.

Required automated checks: webhook signature rejection, trusted calls create no
stream, `both_tracks` speaker mapping, mu-law conversion/resampling, duplicate
sequence suppression, caller hold before Guardian audio, zero Guardian frames
on the caller leg, resume ordering, family join, disconnect cleanup, and a full
browser regression. Final acceptance is one real benign call and one scripted
scam call with the caller audibly held during Margaret's private Guardian turn.

## Official references

- Media Streams overview: https://www.twilio.com/docs/voice/media-streams
- `<Stream>` and `both_tracks`: https://www.twilio.com/docs/voice/twiml/stream
- Media message format and 8 kHz mu-law audio: https://www.twilio.com/docs/voice/media-streams/websocket-messages
- Conference participants, hold, and coaching: https://www.twilio.com/docs/voice/api/conference-participant-resource
- Updating an active Call with new TwiML: https://www.twilio.com/docs/voice/api/call-resource
