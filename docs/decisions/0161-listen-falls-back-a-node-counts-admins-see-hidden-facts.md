# 0161. Listen falls back to the Gemini voice by sentence, a shared-science node counts and pages its crafts, admins see the hidden facts, and the smoke measures the dock's bit rate

When ElevenLabs cannot read, Listen reads with the Gemini voice and highlights the sentence being
read; the script says which voice read it. A shared-science node says how many crafts share its
term and a route pages on through them. The Settings hub shows the night's count of facts readers
cannot see. The browser smoke records a dock turn and checks its bit rate lets a minute fit. The
first paid check's replies become fixtures: ElevenLabs is sent no square brackets, a Gemini JPEG is
stored as the PNG every reader expects, and an image's tokens are priced by modality.

Date: 2026-11-23. Status: accepted (the lead's debt-clearing brief, screens and stream lane; the
Listen fallback approved by the owner on 2026-11-22: "when ElevenLabs is down or refuses, Listen
reads aloud with the Gemini voice and highlights by sentence only"). It amends
[decision 0035](0035-listen-and-voice-switched-off.md) (who reads Listen, its offer, its cache id
and its ledger keys, what ElevenLabs is sent), [decision 0064](0064-quiz-compare-and-shared-science.md)
(a node's crafts) and [decision 0018](0018-media-backend.md) (the image a job stores and its cost),
on the lead's add-on of 2026-11-23 after the paid check (run 45112123057).
The contracts are `docs/contracts/voice.md` (Listen; Relay turns), `docs/contracts/explainer.md`
(Listen; concept graph), `docs/contracts/learning.md` (Shared-science explorer) and
`docs/contracts/nightly-upkeep.md` (Routes).

| For | Read |
|---|---|
| Listen as ElevenLabs reads it | [decision 0035](0035-listen-and-voice-switched-off.md) |
| The lede first, hypotheses unread, the lease and the marks store | [decision 0140](0140-voice-and-listen-kept-true.md) |
| The explorer and its node | [decision 0064](0064-quiz-compare-and-shared-science.md) |
| The count of hidden facts | [decision 0149](0149-a-fact-readers-can-see.md) |
| The dock and how it is checked | [decision 0020](0020-voice-ui.md) |
| The paid check that will see the Gemini voice run | [decision 0154](0154-ai-media-and-film-scores-kept-true.md) |
| The media backend whose stored image and cost it changes | [decision 0018](0018-media-backend.md) |
| Who reads, and how | [voice.md](../contracts/voice.md), Listen |
| Every decision, by group | [README.md](README.md) |

## Context

Four debt entries were open on 2026-11-23. Listen was hidden whenever ElevenLabs did not answer
(`listen.languages` empty), because only ElevenLabs gives word timings. A shared-science node
listed at most 100 of the crafts sharing its term and did not say how many there were, so a term
such as alum or indigo looked shared by exactly 100. The night counted the approved facts readers
cannot see (decision 0149), but only the night's report and an admin route showed it. The dock asked
`MediaRecorder` for 32 kbit/s and sent a turn at nine tenths of 300,000 bytes; no run had measured
what a browser records.

The Gemini speech page (read on 2026-11-23, the Interactions API) documents `gemini-3.8-flash-tts`
reading a `user_input` text block with `response_format {type: audio}` and the voice in
`generation_config.speech_config`, answering a RIFF WAV of 24 kHz mono 16-bit PCM in the last
`audio` block of the `model_output` step. It reads text as a verbatim transcript, takes no language
code, lists 30 prebuilt voices and over 130 languages: English, Hindi, Bangla, Tamil, Telugu,
Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi and Assamese among the answer languages, and
not Urdu. It gives no timings.

## Decision

1. **Voices, tried in order.** Listen holds an ordered tuple of voices (`voice/listen_voices.py`):
   `ElevenLabsVoice` when the key is set and ElevenLabs answers its probe, then `GeminiVoice` when
   `GEMINI_API_KEY` is set. A request reads with the first voice that speaks the explainer's
   language; when that voice fails with an `ExternalFailure` of its own service (down, refused, off
   its shape), the request is read again by the next voice. A failure of anything else (the
   bucket, a refused hold) ends it, so the bucket failing is not paid for twice, and the day's
   allowance refuses before any voice speaks. The whole script is one voice, never a mix, and
   `ListenScript.voice` names it (`ELEVENLABS` or `GEMINI`). Trying the probe first was kept, so a
   request does not wait on an ElevenLabs that is known to be down; the cost is that ElevenLabs
   audio cached before an outage is not served during it, and the Gemini voice reads those blocks
   once.
2. **Sentences, read one at a time and joined.** The Gemini voice reads each sentence of a part as
   its own request and joins their PCM into one WAV per part (`voice/read_aloud.py`), so each
   sentence's start and end are exact from the samples before it: `ListenTrack.sentences
   [{sentenceId, start, end}]` with `words` empty. Reading a whole part and spreading its time over
   the sentences by length was refused: it would invent timings. One track per sentence was
   refused: each would reload the audio element, and the contract keeps one track per part. A part
   whose sentences come back at different sample rates, or audio that is not mono 16-bit WAV, fails
   as off the shape. WAV, not MP3, because the box would have to encode with `ffmpeg` on every
   request; a part costs about three times the bytes.
3. **The same rules for what is read and what is billed.** Both voices read `spoken_blocks`: the
   lede first, then each block's cited sentences, hypotheses unread. Both hold the estimate at 1,000
   characters a minute under the reader's `VOICE_SECONDS` and settle to the audio (an MP3 by its
   bytes at 128 kbit/s, a WAV part by its seconds rounded up). The ledger keys carry the voice
   (`listen:<requestId>:<voice>:hold`, `listen-refund:<requestId>:<voice>`,
   `listen-settle:<requestId>:<voice>`), so a fallback holds and settles its own rows: a voice that
   fails bills only the audio it made. The cache id takes the voice's model, so each voice keeps
   its own narration; ElevenLabs' cache ids are unchanged.
4. **The offer names its voice.** `/answers/config` `listen {languages, voice?}` lists the answer
   languages any offered voice reads and names the first: all thirteen with `ELEVENLABS`, the
   twelve without Urdu with `GEMINI` alone, `{languages: []}` with none. The web accepts `voice` and
   `sentences` as optional, and a track timed by sentences marks the sentence being read with no
   word (`lib/listen.trackMark`, `lib/listenMarks`, `lib/filmScenes`), so the page and the film
   highlight by sentence. The read-aloud is a method of the existing Gemini media wire
   (`GeminiMediaWire.read_aloud`), billed to the reader's seconds as ElevenLabs narration is, and
   not routed through the AI router, which has no task for one fixed voice model.
5. **A node counts its crafts and a route pages them.** `ConceptNode.craftCount` is how many crafts'
   own claims name the term for this reader (optional, left out only by a node stored before it
   existed). `GET /api/shared-science/{termKey}/crafts?craft=&offset=` answers `ConceptCraftsPage
   {schemaVersion, termKey, label, craftCount, offset, crafts (1 to 100), sources}` in the node's
   order, its sentences numbered on from the node's. The page is cut from the same in-memory list
   the node is, since a craft's place depends on which of its claims the reader may see; paging in
   SQL was refused, as pages would come out uneven. Show all N reads every later page in order,
   as the field voices list does, and numbers the pages' sources after the answer's own.
6. **The hidden facts on the Settings hub.** A Facts readers cannot see card for Admins lists each
   craft's hidden facts by reason, the crafts with unexplained facts first and then the most
   hidden, under one line saying when the night counted. Crafts are named by their address, which
   is what the report holds; reading the catalogue for names was refused as a second request for
   an admin card.
7. **The dock's bit rate is measured where a browser runs on every pull request.** The browser smoke
   (`frontend/e2e/voice-rate.smoke.spec.ts`) drives the real dock on `/design/voice` with Chromium's
   fake microphone, reads the uploaded file out of the form, decodes its length in the page and
   fails above 36,000 bit/s, the rate at which a minute fits under nine tenths of `maxAudioBytes`.
   Chromium's `audio/webm` measured 28,269 bit/s at desktop and 28,245 bit/s at phone width for the
   asked 32,000 (2026-11-23). The production voice check runs only after a release, so it was not
   the place to measure.

8. **The paid check's replies are fixtures.** The recorded English and Hindi narrations (their
   audio cut to its first 4,096 base64 characters, as no test plays it) replace the hand-written
   narration fixture, the recorded image interaction (its thought signature cut, its 1K JPEG
   replaced by a 32 pixel JPEG) replaces the hand-written image fixture, and the run's
   `paid_checks_report.json` sits beside the voice fixtures. `eleven_v4` is kept: it was accepted and
   its alignment spelled both texts. It spoke 882 and 765 characters a minute; the hold keeps the
   documented 1,000 and the settle adds the rest within what is left, since the rate differs by
   language and the settle already bills the audio.
9. **ElevenLabs is sent no square brackets.** In Hindi, `eleven_v4` gave `[कई चरणों में]` 0.075 s, five
   milliseconds a character, while English spoke `[in several stages]` in 1.44 s: Hindi read the
   brackets as an audio tag and skipped the cited words the page highlights. `ElevenLabsVoice`
   sends each square bracket as a parenthesis, one character for one, so the alignment still
   indexes the shown text; `NARRATION_VERSION` becomes 3 so no narration made with brackets is
   served again. Dropping bracketed text was refused: it is cited. The paid check now narrates the
   text as Listen sends it and reports the parenthesised words' seconds.
10. **A Gemini image is stored as PNG.** Gemini answered `image/jpeg` where the job, its file names
    and the web's media shape expect `image/png`, so every job would have failed its output check.
    `media/output.checked_output` converts a JPEG to PNG from its pixels
    (`research/image_intake_pixels.converted`, metadata dropped) and refuses any other type.
    Storing JPEG was refused: the web refuses any media type but PNG and MP4, and a backend
    sending JPEG before the web accepted it would break every media view for the release's
    minutes. Asking the API for PNG was refused: no documented request field was seen.
11. **An image's tokens are priced by modality.** The reply gives `output_tokens_by_modality`
    (1,120 image tokens of 1,389 output tokens). `AiModel.media_price_per_mtok` holds the media rate
    (Gemini 3.1 Flash Image $60, Nano Banana 2.1 $30 a million) and `price_per_mtok` the text and
    thinking rate ($3 and $7.50), from the Gemini pricing page read on 2026-11-23;
    `budget.token_cost(..., media_tokens)` bills the image tokens at the media rate and the rest at the
    text rate, every output token at the media rate when the reply gives no breakdown, and an admin
    override may set `media`. The recorded call costs $0.068036, not $0.08334.

## Unverified

1. That the Interactions API serves `gemini-3.8-flash-tts` speech in the documented shape when a
   request carries the media wire's `Api-Revision` header; no request has reached Gemini. The
   paid check's `gemini_speech` step reads one sentence and parses it as Listen does.
2. That angle brackets in a cited sentence are read as text and not as an inline speech tag
   (the page documents tags such as `<short pause>`).
3. Safari's recorded rate for `audio/mp4`; no runner has Safari.
4. That `eleven_v4` reads a parenthesis in Hindi as text, and its alignment in the eleven other
   answer languages.

## Consequences

- Listen is offered while ElevenLabs is down, in twelve languages, read sentence by sentence.
- A Gemini part is a WAV of about 48 KB a second; a whole Expert answer read by Gemini is several
  megabytes in the bucket, aged out after a year by the narration lifecycle rule.
- The Listen ledger keys changed form; no code reads them, and Usage sums the seconds.
- A node and the explainer's concept graph carry `craftCount`; the shared-science and phase D
  goldens carry it, and `shared/learning.shared-science.golden.json` gains the `crafts` page.
- The goldens `shared/listen.script.golden.json` (now with `voice`),
  `shared/listen.script-sentences.golden.json` (new) and `shared/naming-golden.json` (a WAV
  narration name) changed with this record.
- Every narration is made again once, under version 3.
- A stored stage illustration is a PNG converted from Gemini's JPEG, larger than the JPEG.
- An image job's recorded cost falls by the text tokens' share (about a fifth for the recorded call).
- No migration, no new table, no new dependency.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/voice/test_listen_fallback.py`, `test_read_aloud.py`, `test_listen.py`,
`test_listen_routes.py` and `test_narration.py`, `backend/tests/media/test_gemini_speech.py`,
`backend/tests/research/test_shared_science_nodes.py`,
`backend/tests/contracts/test_learning_exports_contract.py`,
`backend/tests/learning/test_learning_routes.py`, `backend/tests/db/test_learning_views_db.py`,
`frontend/e2e/listen-contract-unit.spec.ts`, `listen-marks-unit.spec.ts`, `film-mode-unit.spec.ts`,
`learning-renderers-unit.spec.ts`, `learning-contract-unit.spec.ts`, `hidden-facts-unit.spec.ts`,
`voice-rate-unit.spec.ts` and `voice-rate.smoke.spec.ts`, and for the paid check's replies
`backend/tests/voice/test_recorded_narration.py`, `test_elevenlabs.py`,
`backend/tests/media/test_gemini_media.py` and `test_views.py`.
