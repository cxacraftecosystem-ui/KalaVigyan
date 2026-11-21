# 0020. Voice UI: the voice dock on /ask and the craft page

Voice is a dock on `/ask` and the craft page, not a dialog, offered only when the server says so and
run by one controller over injected adapters with the ElevenLabs client SDK. Its transcript cites,
relay is push to talk, and client tools are checked again against what the browser holds.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0014 Contracts for process science, region profile, voice and media](0014-science-region-voice-media-contracts.md) |
| The review that fixed it | [0022 Voice spend fails closed, a filtered style hint, region sources and one home per rule](0022-batch-3-review-fixes.md) |
| The contracts it names | [voice.md](../contracts/voice.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0014 fixed the voice contract (`docs/contracts/voice.md`): availability in
`GET /api/answers/config`, the voice notice and consent, `POST /api/voice/session` answered by
transport (`AGENT`, ElevenAgents over WebRTC with a server-minted token; `RELAY`, speech to text,
our pipeline and text to speech, the default until lane 0017's spike), the four client tools, the
transcript and the relay turn stream. PLAN 10 and 14 ask for a voice orb on `/ask` and the craft
page, consent before the first session, client tools re-validated in the browser, the on-screen
transcript linked to the same citations, and the voice button hidden when ElevenLabs is not
available. PLAN 0 and the owner rules bind: every fact on screen cites, no gap admissions or
how-it-works copy, a control that cannot work is hidden, guards fail closed. Lane 0017 builds the
routes at the same time, so the client is built against the contract and its golden files.

## Decision

1. **A dock, not a dialog.** The voice UI is a non-modal panel docked bottom right (full width
   above the bottom island on a phone, `z-40`, the dock rung). The craft page's tools act on the
   page behind it (open the Process tab at a stage, open the Region tab), which a modal would
   cover. `VoicePanel` stays the mount point with its props; it gains `availability` and an
   optional `host` (the stages the page drew, `showOnMap`, `openStage`). It is loaded with
   `next/dynamic` and mounted only when voice is offered.
2. **When voice is offered.** `voiceOffered` is true only when the parsed availability is
   configured with a transport and a language, at least `MIN_START_SECONDS` (30) remain (or the
   allowance is unlimited), and the browser can carry the transport: `getUserMedia`,
   `RTCPeerConnection` and `AudioWorkletNode` for `AGENT`; `MediaRecorder` recording one of
   `RELAY_AUDIO_TYPES` for `RELAY`. Otherwise the Voice button is not rendered. Browser support is
   read through `useSyncExternalStore` with a server snapshot of "none", so the server and first
   client render agree. The config's `voice` block is parsed by `voiceAvailabilityShape`; a block
   off the contract (today's backend still sends `{configured, languages}`) hides voice and is
   logged with the failing path, so the hide is loud in the console and never a guess.
3. **One controller, injected adapters.** `lib/voiceCall.ts` (`VoiceCall`) owns the phases (idle,
   consent, starting, live, ending, ended, failed), the call timer (`maxDurationSeconds`), ending,
   and tool re-validation. Transports are `RelayTransport` (`lib/voiceRelay.ts`) and
   `AgentTransport` (`lib/voiceAgent.ts`); the browser pieces are adapters passed in: the API
   (`lib/voiceSession.ts`), ElevenLabs (`lib/elevenLabsAgent.ts`, the only module that touches
   the SDK), the recorder and speech player (`lib/voiceDevice.ts`) and the media options. The
   React hook only subscribes (`useSyncExternalStore`) and calls `begin`/`dispose`, so the unit
   specs drive whole calls with fakes, which there is no React renderer to do otherwise.
   Closing the dock ends the session; the teardown waits one task so a strict-mode remount keeps
   the same call instead of opening a second (one live session per user); leaving the page
   (`pagehide`) ends it at once with `keepalive`.
4. **ElevenLabs client SDK.** `@elevenlabs/client` 1.36.1 (latest stable, pinned exactly; MIT),
   not `@elevenlabs/react`: the controller needs plain callbacks, and the React package is a
   wrapper over the same client. It is imported dynamically inside the adapter, so LiveKit loads
   only when an `AGENT` call starts. The adapter passes the conversation token, `webrtc`,
   `textOnly: false`, the four client tools and callbacks, and nothing else: no agent id,
   overrides, dynamic variables, extra body or user id (the contract's "token only"). The SDK
   then sends only its `source_info`.
5. **Client tools are re-checked against what the browser holds.** Each call is parsed by
   `clientToolCallShape` (anything off the contract is ignored) and then held: `show_on_map` only
   for the session's craft; `open_stage` only for a stage the page drew; `show_sources` only for
   an answer in the transcript; `offer_image` only for a drawn stage that `GET /media/options`
   offers an image today (fetched once per session; a failure offers nothing). In `AGENT` a call
   arrives from the SDK and again in the transcript's `actions`; the SDK path pre-pays its
   signature so the transcript does not repeat it, and an SDK call that cannot be held yet (its
   answer not in the transcript) is applied from the transcript when it is. In `RELAY` a turn's
   actions are applied when its `done` arrives, once the answer is in the transcript. Each turn
   also shows its held actions as buttons (Sources, Map, the stage name) so they can be run again;
   on `/ask`, which draws no map, Map is a link to the craft's Region tab. `offer_image` reveals
   the stage on the craft page, where lane 0021 draws the image button; it has no button of its
   own.
6. **The transcript cites.** Turns come from our server only: in `RELAY` from the turn stream
   (the reducer builds exactly the stored `VoiceTurnView`, pinned against the transcript golden);
   in `AGENT` from `GET /voice/session/{id}/transcript`, read after each agent reply and once at
   the end. ElevenLabs' agent text is never shown, because it carries no citations; the user's
   own words from the agent's speech to text are shown until the transcript turn replaces them.
   Sentences reuse the answer view's `SectionBlock` and citation chips; one numbering covers the
   call; the Sources list is the answer view's `SourcesList` (now with `idPrefix`, `compact` and
   `flashIds`); `show_sources` scrolls to it and flashes the answer's sources (`useRevealRow`,
   `fr-flash-row`, whose outline survives reduced motion). A turn with no cited sentence shows the
   server's spoken reply muted, as the text answer shows `not_enough_evidence` verbatim.
7. **Relay is push to talk.** The first recording starts with the session; the orb sends, a reply
   plays from `speechPath`, and pressing during a reply stops it and listens. A recording stops at
   `maxTurnSeconds`; one over `maxAudioBytes` is refused in a sentence; an empty one is dropped.
   The recorder takes the first type the session accepts that the browser records and labels the
   upload with the bare type (never `;codecs=`). The upload is named by the naming convention:
   `KalaVigyan_Voice-Session_<IST date>_<HHMM>_<Craft>_Recording.<ext>`. No silence detection:
   an open microphone that sends itself would bill seconds the learner did not mean to spend.
8. **States and copy.** Consent shows the notice (title, Markdown body) with Agree and start or
   Not now; the version accepted is the notice's own, remembered for the page so a second call
   does not ask again; a 403 with `X-Voice-Consent-Required` returns to consent. The orb carries
   the state in a word under it (Connecting…, Tap to talk, Listening · tap to send, Thinking… or
   the server's status, Speaking) as well as its ring, so reduced motion loses nothing; the level
   halo follows the microphone or the agent's voice only when motion is allowed. Server refusals
   (409 live session, 429 no time left, 403 unverified email) are shown verbatim; a microphone
   refusal becomes "Allow the microphone to talk."; a dropped call is "The call dropped." with Try
   again. The header shows the call time left (`formatClock`, spoken as `spokenClock`).
9. **CSP.** The pinned SDK's WebRTC path connects only to LiveKit at
   `wss://livekit.rtc.elevenlabs.io` (read from its `utils/location.js` and
   `WebRTCConnection.js`; with a token it never calls `api.elevenlabs.io`); livekit-client 2.24.1
   validates a failed join and checks reachability over `https://` on the same host (its region
   lookup is for `*.livekit.cloud` only). The CSP gains
   `connect-src 'self' https://accounts.google.com/gsi/ wss://livekit.rtc.elevenlabs.io
   https://livekit.rtc.elevenlabs.io`: `'self'` for the `/api` proxy and relay audio, Google
   Identity's documented source, Turnstile needing none (Cloudflare's CSP reference). A unit spec
   reads the SDK's own host constants so an upgrade that moves them fails. The SDK loads its audio
   worklets from `blob:` URLs, which a future `script-src` must allow or replace with
   self-hosted worklets (`workletPaths`).

## Consequences

- Voice stays hidden until lane 0017 sends the contract's availability block from
  `/answers/config`; nothing else on the client waits for it.
- The dock, orb and microphone paths have not run in a browser; the controller and transports are
  covered with fakes. Both are in `docs/TECH_DEBT.md`, as are the worklet CSP and the image button.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
