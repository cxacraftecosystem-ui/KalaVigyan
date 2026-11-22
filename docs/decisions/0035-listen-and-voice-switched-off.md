# 0035. Listen, and the live voice call switched off

Listen reads finished research aloud in the reader's language with word timings, its audio cached
per piece and language in the private media bucket. The live voice call is switched off.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| What amended part of it | [0140 Voice and Listen hold their state in the bucket, bill what they hear and read the lede first](0140-voice-and-listen-kept-true.md): the lede first, hypotheses unread, the narration lease and lifecycle |
| The contract it was built to | [0030 The explainer contract](0030-explainer-contract.md) |
| The review that fixed it | [0038 Phase A review fixes](0038-phase-a-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Plan section 2.5 (`docs/plans/answer-experience.md`, owner-approved, decision O1 final): voice is
for listening to finished research in the reader's language, with word timings so the text
highlights as it reads; audio is cached per piece and language in the private media bucket, so a
second listener costs nothing. The live voice call stays in the code but is switched off: its
session, custom-LLM and relay routes answer 404 and the voice button is not drawn. Master Admins
have no caps; everyone else listens within the daily `VOICE_SECONDS` of `core/roles`. The one
ElevenLabs adapter is `providers/elevenlabs.py` (decision 0017). The explainer UI lane (0037) wrote
its client against a draft of the script shape (`frontend/lib/listen.ts`) while this lane ran.

## Evidence

Read on the ElevenLabs documentation on 2026-11-17:

- `elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps`: `POST
  /v1/text-to-speech/{voice_id}/with-timestamps`, query `output_format` (default
  `mp3_44100_128`) and `enable_logging` (false is zero retention, enterprise only); body `text`,
  `model_id`, `language_code` (ISO 639-1), `previous_text`, `next_text`, `previous_request_ids`,
  `next_request_ids`, `voice_settings`, `seed`, `apply_text_normalization`. The answer is
  `{audio_base64, alignment {characters[], character_start_times_seconds[],
  character_end_times_seconds[]}, normalized_alignment {...}}`; `alignment` covers the text as
  sent, `normalized_alignment` the normalised text. A streaming twin is
  `/v1/text-to-speech/{voice_id}/stream/with-timestamps`.
- `elevenlabs.io/docs/overview/models`: model selection names `eleven_v4` for quality and for
  "content creation ... audiobooks & video narration" and `eleven_v4_turbo` for real-time; the
  character limits table gives `eleven_v4` 10,000 characters (about 10 minutes) and lists no limit
  for v4 Turbo; the v4 family speaks 90+ languages, all thirteen answer languages among them, and
  takes ISO 639-1 `language_code`. `elevenlabs.io/v4`: "A single generation supports up to 10,000
  characters"; bracketed audio tags such as `[pause]` are read from the text; SSML is disabled.
- `elevenlabs.io/docs/overview/capabilities/text-to-speech`: split long text into segments and
  pass previous and next text for natural prosody between them.

## Decision

1. **Endpoint and model.** `ElevenLabs.narration(text, *, voice_id, language, previous_text,
   next_text)` posts to `/v1/text-to-speech/{voice_id}/with-timestamps` with `NARRATION_MODEL`
   `eleven_v4` (the documented narration model, 10,000 characters a generation) and
   `output_format` `mp3_44100_128`, and returns `TimedSpeech {audio, starts, ends}`: one start and
   end per code point of the text sent. It reads `alignment`, not `normalized_alignment`, because
   only the text as sent can be underlined. The alignment must spell the text exactly; a mark of
   several code points (an Indic syllable) times each of them; lengths that differ, times out of
   order within a mark, audio that is not base64 or over 8 MiB are off the documented shape and
   fail loudly. Text past `NARRATION_MAX_CHARACTERS` or a language outside `TTS_LANGUAGES` (the v4
   family's list, decision 0025) is refused before any request. The call waits up to 90 s.
2. **What is read.** Listen reads the cited sentences of each block, in reading order: prose
   sentences, then a ladder's stage sentences stage by stage; pictures, stage names, section
   titles and labels are not read, so everything heard is a cited fact. A sentence is spoken in
   the explainer's language when it is translated, else in English (a sentence whose translation
   failed stays English on screen, decision 0023), each language in its own request.
3. **Parts.** A block's sentences are grouped into parts of at most `PART_CHARACTERS` (2,000,
   about two minutes, well within the 10,000 limit and the 90 s wait), whole sentences only, one
   language each; neighbouring parts' text goes as `previous_text` and `next_text`. Composer
   sentences are at most 600 characters and translations 1,000, so a longer sentence is refused.
4. **Timings.** Words are the runs of non-space characters of each sentence; a word starts at its
   first character's start and ends at its last character's end, in seconds to the millisecond, a
   start held at the previous word's start if the provider's times step back. The script gives
   each word its text, not offsets, and the client finds it in the shown sentence after the
   previous word (decision 0030's reason: Python counts code points, the browser UTF-16 units). A
   part lasts the longer of its audio (bytes at 128 kbit/s) and its last word.
5. **Cache.** The cache id is the SHA-256 of `kalavigyan-narration`, `NARRATION_VERSION` (1), the
   model, the voice id and the explainer's language and the block's piece content hash
   (`knowledge_pieces.piece_content_hash`), joined by U+001F: a block placed in another explainer,
   or reused from a stored piece, shares its audio; another voice, model or reading rule is new
   audio. Each part is an `audio/mpeg` object at `media/narration/<cacheId>/<file name>`
   (`naming.narration_key`; `KalaVigyan_Explainer_<date>_<time>_Narration_Part-NN.mp3`), and the
   block's `NarrationManifest` (parts, keys, durations, words) is written last at
   `media/narration/<cacheId>/narration.json`, so a manifest means every part exists. The objects
   live under `media/` because the app's IAM user may only read and write there; they belong to no
   user, so the prefix is `narration`, not a user id. A manifest that does not validate or names
   another cache id is logged and made again. Links are presigned GETs of one hour
   (`NARRATION_LINK_SECONDS`), long enough to listen to an Expert explainer with pauses.
6. **Seconds.** A cache hit costs nothing. Before any speech, the misses' characters are held at
   the documented 1,000 characters a minute as `VOICE_SECONDS` under `listen:<requestId>:hold`,
   in one transaction under a lock on the reader's `User` row; a reader with less left gets 429
   with `Retry-After` until midnight India time and nothing is spoken. After speech the hold is
   settled to the audio's seconds: `listen-refund:<requestId>` for the unused part,
   `listen-settle:<requestId>` for audio past the estimate, capped at what was left. A failure
   bills only the audio made, and the blocks that were made stay cached. Master Admins are never
   refused (`remaining_today` is unlimited) and their seconds still show on Usage. Listen needs
   the `VOICE` capability; it is limited to 30 presses in 10 minutes (`listen_attempt`), Master
   Admins excepted. Misses are spoken three requests at a time.
7. **Route.** `GET /api/answers/{answerId}/listen?language=&section=` reads the reader's own
   explainer, the `Explainer` document sectioned composition (0032) keeps under the answer's
   `payload.explainer` (`EXPLAINER_PAYLOAD_KEY`), refused when its `answerId` is another; another
   reader's answer, an answer without an explainer, another language or a section with nothing to
   read is 404; a malformed section id or language 422; a provider or bucket failure 503 without
   details. It answers `ListenScript {schemaVersion, answerId, language, tracks[{blockId,
   audioUrl, durationSeconds, words[{sentenceId, text, start, end}]}]}`, the shape the client of
   lane 0037 parses; one track per part. `/answers/config` gains `listen {languages}`: every
   answer language the narration model speaks when the bucket, the ElevenLabs key and ElevenLabs
   itself answer, else none, so the client draws no Listen control (hide what cannot work).
8. **The call switched off.** `Settings.voice_call_enabled` (`VOICE_CALL_ENABLED`, default false)
   guards the whole `/api/voice` router (`require_voice_call`): the notice, session start, end and
   transcript, the custom LLM and the relay turn and speech routes answer 404 before anything
   else is read. `/answers/config` sends the hidden `VoiceAvailability`, so the client draws no
   voice button. Nothing is deleted: the code, the tables, the agent provisioning script and the
   daily upkeep (which still purges transcripts) stay. Setting `VOICE_CALL_ENABLED=true` brings back
   the routes and the craft page's Talk dock (`CraftVoice`, which mounts `VoicePanel`); `/ask` has
   no call entry since decision 0036 made its mic dictation (corrected by decision 0038).

## Unverified

1. That `eleven_v4` is served by the text-to-speech endpoints: the models page names the Text to
   Dialogue API for v4 and the v4 page says both streaming and non-streaming endpoints launched
   with it; no call has been made. If it is not, `NARRATION_MODEL` becomes `eleven_v4_turbo`
   (which the relay speech already uses) and the cache id changes with it.
2. That `alignment.characters` spells the text sent code point for code point in every offered
   language; the fixtures follow the documented shape, not captured traffic.
3. That bracketed text in a cited sentence (a quoted `[sic]`, an editorial `[...]`) is read as text
   and not as a v4 audio tag.
4. The real speaking rate per language; the hold uses the documented 1,000 characters a minute and
   settles to the audio.

## Consequences

- Listen works as soon as the bucket and the ElevenLabs key are set and an answer keeps its
  explainer; the voice call stays off until the owner sets `VOICE_CALL_ENABLED=true`.
- Debt (`docs/TECH_DEBT.md`): two readers missing the same block at once both pay for it; no lifecycle
  rule ages narration objects out; the Gemini read-aloud fallback of PLAN 10.6 is not built.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
