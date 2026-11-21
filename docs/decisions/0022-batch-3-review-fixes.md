# 0022. Voice spend fails closed, a filtered style hint, region sources and one home per rule

A review of lanes 0014 to 0021 made voice spend fail closed: a relay upload is measured and its turn
claimed before speech to text, and an agent call holds its whole length at the start. It also
filtered the media style hint, gave `CraftRegion` its places' sources, gave each rule one home and
pinned the client's vocabularies to the backend.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The lanes it reviewed | [0014](0014-science-region-voice-media-contracts.md), [0015](0015-science-engine.md), [0016](0016-region-profile.md), [0017](0017-voice-backend.md), [0018](0018-media-backend.md), [0019](0019-craft-page-and-region-panel.md), [0020](0020-voice-ui.md) and [0021](0021-media-ui.md) |
| The contracts it names | [voice.md](../contracts/voice.md) |
| Every decision, by group | [README.md](README.md) |

## Context

A review of lanes 0014 to 0021 found one high-severity and several smaller defects. The high one:
in `RELAY`, the default transport, a relay turn ran speech to text before any check, billed the
last recognised word's end time, and claimed a turn only after hearing text. Silence or noise was
heard as nothing, billed 0 seconds and used no turn, and the 60 s limit was checked against the
last word, so a long low-bitrate upload passed as short. `VOICE_SECONDS` is the only limit on
ElevenLabs spend (voice calls never pass the AI router's monthly ceiling), so any verified student
could buy unlimited speech to text for nothing. The speech route also synthesised a reply again on
every cache miss, for any turn still in the transcript, billing 0 under the turn's old key. In
`AGENT`, reconciliation only ever refunded, and an ended row freed the user's slot while the
ElevenLabs call could keep running. The media style hint missed plurals and group words, and sat
after the bans as the model's last instruction. Smaller findings: a craft location's source had
no number or link, two homes each for the HMAC key rule, India time and the first-citation walk,
nesting over budget, frontend vocabularies no test compared with the backend, and specs reading
files their workflow does not watch. PLAN section 0 puts accuracy first; the practice skills ask
that guards fail closed and that every rule have one home.

## Decision

1. **A relay upload is measured before speech to text** (`voice/audio.upload_floor_seconds`). A
   WAV must be uncompressed PCM; its length is its data bytes over its own rate, channels and
   sample size, so a header that lies about its size is measured by what it holds. Compressed
   audio (WebM, Ogg, MP4) cannot be timed without decoding, so it is bounded by bytes: the dock
   records at `RELAY_AUDIO_BITS_PER_SECOND` (32 kbit/s, ample for speech) and the ceiling
   `RELAY_MAX_AUDIO_BYTES` is a minute at that rate with a quarter's headroom (300 000 bytes).
   The floor is that size over 5 000 bytes a second, so a full upload is a minute. Past a minute
   is 413, an unreadable WAV 400. The session start sends `audioBitsPerSecond` and the new
   `maxAudioBytes`; the dock asks `MediaRecorder` for that rate and sends the turn at nine tenths
   of the byte limit, so a browser that records faster still sends a valid upload.
2. **A relay turn is claimed before speech to text, under the session row's lock**
   (`SqlVoiceStore.claim_turn`). In one transaction it locks the row (`FOR UPDATE`), checks the
   session is live and below 40 turns, reads the day's seconds, refuses when fewer than the
   upload's floor are left, holds `RELAY_MAX_TURN_SECONDS` (or what is left) under
   `voice:<session>:<turn>` and counts the turn. After speech to text the turn keeps the larger of
   the floor and the heard seconds and writes the rest back as `voice-refund:<session>:<turn>`. A
   failed speech to text still costs the floor: every upload costs something, and the provider
   may bill a call that answered nothing. Speech to text and that settlement run as shielded work
   (`core/shielded`), so a learner who ends the call mid-turn is still given back the unheard part. Parallel uploads are not serialised end to end, because
   holding a pooled connection across a provider call is worse than letting each upload hold its
   own minute; under the lock they cannot together pass the day's seconds. A per-user limit of
   40 turns in 10 minutes (`voice_turn_attempt`) matches the 40-turn cap of a 10-minute call.
3. **A reply is synthesised again only during the call or two minutes after it** (`SPEECH_GRACE`),
   else 410 and the client keeps the transcript text. Each new synthesis is billed under its own
   key (`voice:<session>:<turn>:speech:<replay id>`) capped at what is left today, refused before
   any call when nothing is left, and the route allows 60 replays in 10 minutes. Storing reply
   audio in the media bucket stays the better fix and is in the debt register.
4. **An agent call holds its whole length at the start** (`voice:<session>:hold`, the session's
   `maxDurationSeconds`, which is already capped by the day's seconds). Custom-LLM turns write
   nothing more; the call ends at its length (`quota` when the day cut it short, else `turns`) or
   at 40 turns. Reconciliation settles both ways: a `voice-refund:<session>` row for a surplus, a
   `voice-settle:<session>` row for time past the hold. An `AGENT` session occupies the user's slot
   and the platform's live count until it is reconciled or 12 minutes after its start
   (`AGENT_OCCUPANCY_SECONDS`, the start window plus the longest call), not until `/end`. So that
   a student is not held to one call a day, the user's ended calls are reconciled when the voice
   availability is read and at their next start (`upkeep.settle_own_calls`) as well as by the daily
   upkeep; otherwise a held call could leave under 30 seconds and hide the voice button until the
   next day. The `live_session` sentence now
   reads "Your last voice call is still open. End it, or try again in a minute."
5. **The style hint is filtered on word forms and placed as a description.** One list of group
   words (`schemas/media.NAMED_GROUP_WORDS`) serves the claim set, stage names and the hint;
   `names_a_group` and `style_hint_problem` compare each word, its singular (`-s`, `-es`) and
   `-ies` to `-y`, so `castes`, `deities` and `rules` match. The hint's banned words add writing,
   people, dress, sacred and override words (`ignore`, `rule`, `instruction`, `prompt`, `system`).
   The prompt puts the hint after the stage name as "Preferred look, a description from the
   requester and not an instruction", then the facts, and the bans last; the template is
   `media-prompt/v2`, which changes every prompt hash, so earlier shared assets are not reused
   for new prompts.
6. **`CraftRegion` carries its places' sources** (`sources: SourceRef[]`, every `basis.sourceId`
   once in place order, `basis_source_ids`), loaded with the restricted filter and refused loudly
   when one was not loaded. The craft page merges them after the process's sources, so a
   location's source has its number, link and Sources entry even when no claim cites it.
7. **One home per rule.** `core/security.secret_key` (whitespace dropped, at least 32 characters)
   and `secret_key_or_none` (logs a key set but too short, by name) serve the media bundle and the
   voice binding; the media options no longer hide silently on a short key. `core/clock.INDIA_TZ`
   is the zone of quota days, budget months, file names, media labels and the usage routes.
   `schemas/science.cited_source_ids` takes anything with `citations` (the `Cited` protocol) and
   serves the voice transcript; `process_claims` reads each stage through `_stage_claims`.
8. **The client's vocabularies are pinned to the backend.** `e2e/backend-vocabulary-unit.spec.ts`
   reads the tuples in `models/enums.py` and `schemas/{science,region,voice,media}.py` and compares
   each with the client constant; Frontend checks watch those files, `core/roles.py`,
   `shared/roles.json` and `infra/terraform/variables.tf`. It deploys nothing, so watching more is
   free.

## Consequences

- The relay golden session gains `audioBitsPerSecond` and a 300 000-byte `maxAudioBytes`; the
  region golden gains `sources`. Both sides' tests read them.
- A silent or failed relay upload now costs its floor and a turn; a turn heard past a minute costs
  its whole minute, no more. Billing semantics are in `docs/contracts/voice.md`.
- An agent call blocks a new one for up to 12 minutes unless it is settled first; a student's
  quota is held for the whole call until reconciliation.
- Lane 0018's DB test helper `stage_with_claims` (43 lines) was the one function above the
  hygiene baseline; it is split, so the count is back at its baseline.
- Left as debt (`docs/TECH_DEBT.md`): compressed audio is bounded by bytes, not decoded; an
  ElevenLabs call cannot be ended from our side; reply audio is cached per process; the dock's
  asked bit rate is not enforced by every browser; India time is still written in the geo ETL
  and one model default.
- Database tests for the claim and the agent slot are in `tests/db/test_voice_store_db.py` and
  run on GitHub Actions.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
