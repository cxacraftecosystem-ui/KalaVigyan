# 0140. Voice and Listen hold their state in the bucket, bill what they hear and read the lede first

Listen opens a whole answer on its lede, leaves a hypothesis unread and makes each block once even
when two readers miss it together; narration and reply audio live in the media bucket and age out;
a relay upload is billed by its decoded length and read by `python-multipart`; voice upkeep runs in
the worker; the voice settings have a screen; a voice turn ranks by the stored hybrid search; every
throttled route refuses through one 429; and the voice dock runs in a browser after each release.

Date: 2026-11-22. Status: accepted (the lead's round 7 brief, voice and listen lane, clearing the
debt register's voice, Listen and lede entries). It amends [decision 0017](0017-voice-backend.md)
(upkeep, reply audio, billing, the multipart reader, the pack's ranking),
[decision 0020](0020-voice-ui.md) (how the dock is checked), [decision 0035](0035-listen-and-voice-switched-off.md)
(what Listen reads, its cache and its lease), [decision 0037](0037-explainer-ui.md) (how the word
being read reaches a sentence), [decision 0056](0056-what-if-lab.md) (a hypothesis in Listen) and
[decision 0077](0077-lede-headings-and-question-order.md) (the lede's readers). The contracts are
`docs/contracts/voice.md`, `docs/contracts/explainer.md`, `docs/contracts/learning.md` and
`docs/contracts/frontend.md`.

| For | Read |
|---|---|
| The voice backend it amends | [decision 0017](0017-voice-backend.md) |
| The dock it checks | [decision 0020](0020-voice-ui.md) |
| Listen and the switched-off call | [decision 0035](0035-listen-and-voice-switched-off.md) |
| The explainer view's reading context | [decision 0037](0037-explainer-ui.md) |
| The what-if lab's hypotheses | [decision 0056](0056-what-if-lab.md) |
| The lede | [decision 0077](0077-lede-headings-and-question-order.md) |
| What Listen reads and how it is cached | [voice.md](../contracts/voice.md), Listen |
| Passages a hybrid turn offers and writes back before it speaks them | [decision 0144](0144-stored-passages-as-evidence.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The debt register held thirteen voice and Listen entries on 2026-11-22: claims-only voice packs
ranked by words; voice upkeep riding the coverage enrichment job; relay uploads billed by bytes
over 5,000 a second and settlements counted on the day they were written; claim packs, reply audio
and reachability held per API process; voice settings set in SQL; a hand-written multipart reader;
a dock never run in a browser; two Listen readers paying for one block; narration objects that never
aged out; the 429 shape written out in every throttled route; every sentence re-rendering on each
`timeupdate`; a hypothesis read aloud like a finding; and Listen, film, the quiz and lesson packs
leaving the lede out. The live call is switched off (decision 0035) and nothing has reached
ElevenLabs, so no stored narration or reply audio exists yet.

## Decision

1. **Listen reads the lede first and leaves hypotheses out.** `voice/narration.spoken_blocks`
   reads a whole answer as `explainer_blocks` gives it, the lede first (block `lede`), and one
   section as its own blocks only. A sentence at `HYPOTHESIS_LEVEL` is not spoken: the page shows it
   with its Hypothesis badge, and a spoken "possibly" would need a reviewed phrase in thirteen
   languages (the phrase table is still unreviewed). `NARRATION_VERSION` becomes 2 so no block
   narrated with a hypothesis is served again; nothing was cached under 1.
2. **Film opens on the lede; a whole-answer quiz asks from it; lesson packs wait.** The server's
   scenes start with a `lede` scene (no field, so no cue) and the client draws it as the lede's
   sentences (`lib/filmScenes.ledeScene`) without a heading. `research/quiz.quiz_sentences` puts
   the lede's sentences first when no section is chosen. A lesson pack's title slide would have to
   carry bullets, which changes the slide contract three renderers draw, so lesson packs stay on
   the chosen sections until the owner asks (the debt register keeps that part).
3. **One maker per narrated block.** A request missing a block puts
   `media/narration/<cacheId>/lease.json` with `If-None-Match: *` (`ObjectStore.put_if_absent`).
   A second request that finds a live lease holds no seconds and polls the manifest each second
   until the lease lapses at 120 s; then it makes the block itself, overwriting the lapsed lease.
   The maker deletes the lease after the manifest is stored or the making fails. S3's conditional
   write keeps the lease beside the narration it guards, needs no table, migration or lock held
   across a provider call, and a crashed maker costs at most one wait.
4. **The bucket ages narration and replies out.** Two lifecycle rules: `expire-narration` deletes
   `media/narration/` objects a year after they were written (`narration_days`) and
   `expire-voice-replies` deletes `media/voice-replies/` after a day (`voice_reply_days`). S3 has no
   "not read for a year" rule; a block heard again after a year is narrated once more, which is
   cheaper than a sweep job reading every stored explainer.
5. **Reply audio is kept in the bucket.** `voice/reply_audio.ReplyAudio` keeps each relay and
   artisan reply at `media/voice-replies/<sessionId>/<turnId>/reply.mp3`, so the speech route of any
   API process plays it free; only a reply never kept (text to speech or the store failed) is made
   again, billed under its own key. Without a bucket nothing is kept and an error is logged. Claim
   packs (10 minutes) and the ElevenLabs reachability (1 minute) stay per process by choice: they
   are reads any process repeats cheaply.
6. **A relay upload is billed by its decoded length.** A WAV is measured from its header; any other
   upload is decoded by `ffmpeg` (already on the box) to the null muxer and measured by the last
   `out_time_us` of its progress, because a MediaRecorder WebM carries no duration for `ffprobe` to
   read. An upload decoding past a minute is refused before speech to text is paid. A reconciled
   agent call's refund or settle row is dated to the call's start, so it counts on the call's day.
   Hanging up an agent call from our side waits on the spike.
7. **Forms are read by `python-multipart`.** `api/multipart_form.read_form` feeds Starlette's
   `MultiPartParser` the request stream cut off at its limit, takes exactly one part per named file
   (sent as a file or a field) and one per named text field, and refuses anything else. The new
   dependency is pinned at 0.0.34 in `backend/uv.lock`, written by `uv lock`.
8. **Voice upkeep runs in `kv-worker`.** `app/worker.every_day` runs
   `voice/daily_upkeep.daily_voice_upkeep` at start and every 24 hours beside the media queue, and
   a failed run waits for the next day without stopping the worker; the coverage enrichment job no
   longer runs it and `app/scripts/voice_upkeep.py` is gone. The worker may now import `voice`.
9. **A Master Admin sets the voice settings.** `GET` and `PUT /api/settings/voice` (the
   `MANAGE_ROUTING` capability) show and change `voice.transport`, `voice.max_live_sessions` (0 to
   100) and `voice.voice_id`, each beside its default, audited as `settings.voice_updated`; the
   Settings hub draws them in a Voice calls block. The concurrent-call limit is the owner's to set
   from the plan bought.
10. **A voice turn ranks by the stored search first.** `VoiceRuntime.stored_search` hands a turn the
    same `SessionScopedSearch` the answers use; the pack's claims it ranks (lexical, vector and
    entity, fused) come first and the word ranking fills the rest, so a question in other words
    still finds its claim. The embedding runs inside the turn, which the custom LLM's filler already
    overlaps. T2 passages are not offered, since a spoken sentence is cited only through a claim
    and writing a passage back belongs to the write-back lane.
11. **One 429.** `core/throttle_refusal.too_many_requests` and `refuse_when_throttled` are the
    only way a route refuses a spent limit, with `Retry-After` in whole seconds and none when no
    wait is known. The proposal allowances keep their own 503-or-429 answer.
12. **The word being read lives outside React state.** `lib/listenMarks.listenMarkStore` takes each
    `timeupdate` and keeps the mark object until the word moves; `ExplainerReading.useSentenceListening`
    selects it per sentence with `useSyncExternalStore`, so a time update re-renders only the
    sentence whose word moved and the dock's clock, and the explainer's reading value stays one
    object while it plays.
13. **The dock runs in a browser after each release.** `/design/voice` mounts the real
    `VoicePanel`; `e2e/production/voice.spec.ts` answers the voice routes from the shared goldens
    and drives the notice, a relay turn from Chromium's fake microphone, the reply and the end at
    desktop and phone widths in both themes. No real microphone or ElevenLabs call is needed; the
    agent call waits on the spike.

## Consequences

- Every narration made under version 1 would be made again; none exists.
- Production needs `terraform apply` for the two lifecycle rules (the lead applies it) and `ffmpeg`
  on every API process's machine (`infra/terraform/user_data.sh` installs it).
- A second Listen reader of a block being made waits up to 120 s instead of paying.
- An upload `ffmpeg` cannot decode is refused 400 before speech to text, where the byte floor let it
  through to fail there.
- `/design/voice` is public and `noindex`; opened without the check's route fixtures, the dock
  talks to the switched-off voice routes and shows its failed state.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/voice/test_narration.py`,
`test_narration_lease.py`, `test_film_scenes.py`, `test_relay.py`, `test_audio.py`,
`test_multipart_form.py` and `test_turns.py`, `backend/tests/research/test_quiz.py`,
`backend/tests/test_throttle_refusal.py`, `test_worker_schedule.py`, `test_voice_settings.py` and
`test_object_store.py`, `backend/tests/db/test_voice_store_db.py`, and
`frontend/e2e/listen-marks-unit.spec.ts`, `film-mode-unit.spec.ts`, `voice-settings-unit.spec.ts`,
`voice-dock-board-unit.spec.ts` and `production/voice.spec.ts`.
