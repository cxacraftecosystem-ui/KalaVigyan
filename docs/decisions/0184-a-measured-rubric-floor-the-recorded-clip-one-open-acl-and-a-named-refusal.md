# 0184. The rubric floor rises to a measured whole run, the recorded clip is the video fixture, every reader's chunk ACL is `PUBLIC` alone, and a refused agent turn names its check

The answer rubric floor is raised to the first whole answer-quality run measured under decisions
0168 and 0174; the replies of the one paid Gemini clip replace the documented video fixtures; the
field transcripts' `SIGNED_IN` chunks are folded into `PUBLIC`, so every reader reads one ACL; and
a custom-LLM request the voice binding refuses is logged with the check that refused it.

Date: 2026-11-24. Status: accepted (the lead's release after decisions 0182 and 0183; the owner
approved the paid clip on 2026-11-23 and the voice check window on 2026-11-24). It amends
[decision 0147](0147-time-market-and-figures-kept-true.md) (the rubric floor),
[decision 0179](0179-transcript-windows-a-chunk-kind-linked-shared-concepts-and-one-paid-clip.md)
(the `SIGNED_IN` label and the clip's fixtures) and
[decision 0017](0017-voice-backend.md) (the custom-LLM binding). The contracts are
`docs/contracts/answer-eval.md` and `docs/contracts/retrieval.md` (Floors),
`docs/contracts/field-voices.md`, `docs/contracts/research.md` and `docs/contracts/craft-page.md`
(chunk ACLs) and `docs/contracts/voice.md` (the binding, point 5).

| For | Read |
|---|---|
| The floors and how they are set | [decision 0126](0126-measurement-that-grows.md) |
| The rubric's shown-once count and the floor it set | [decision 0147](0147-time-market-and-figures-kept-true.md) |
| The quantities table and the everyCited share the run measured | [decision 0168](0168-a-table-under-a-said-sentence-and-python-within-budget.md), [decision 0174](0174-a-confirmed-downgrade-and-answers-that-fit-and-repeat-nothing.md) |
| The window kind and the paid clip step | [decision 0179](0179-transcript-windows-a-chunk-kind-linked-shared-concepts-and-one-paid-clip.md) |
| Why a label is dropped only a release later | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| The voice binding | [decision 0017](0017-voice-backend.md) |
| What is left | `docs/TECH_DEBT.md`: A Gemini clip's first frame and its safety block are not yet seen live; ElevenLabs behaviour not yet verified |
| A turn that races the bind, and the refused header's shape | [decision 0189](0189-lost-media-counted-a-recording-kept-with-its-row-refunds-on-the-hold-day-bands-as-read-and-a-bind-awaited.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **The rubric floor waited on a measured run.** Decision 0147 set `rubricMean` at 0.82, the
  lowest mean its shown-once count could give on run 44994632550, less 0.05, and decision 0174
  left it there until a whole run measured the shown quantities table and the everyCited share.
  Answer-quality run 45230293916 on release aa85ff4c asked and answered all 24 questions at rubric
  0.930 and judge 0.807 for $2.33, and its floors were applied (`floorsApplied: true`).
- **The clip was made once.** Paid check run 45259180160 made one 8 s `gemini-omni-1.2-flash`
  clip: 1280×720, 40 s to finish, 46,336 video tokens, counted at seven cents a second ($0.56),
  and `DELETE /v1beta/interactions/{id}` answered 200 `{}`. The finished interaction held
  `user_input`, `thought` and `model_output` steps, where the documented fixture held one
  `model_output`, and its usage named 941 thought tokens outside `total_output_tokens`, which a
  clip priced by the second does not bill. The clip came with a sound track although the prompt
  asked for none (`silentAsAsked: false`); the pipeline still stored it (`pipelineStores: true`).
- **`SIGNED_IN` was kept a release.** Decision 0179 stopped writing it but kept it in
  `OPEN_CHUNK_ACLS` and kept migration `0097_chunk_kinds`' insert trigger for the release before,
  which still wrote it. That release is gone: decision 0179 has been live since dd006e13.
- **The agent turn was refused unseen.** With the voice call switched on, ElevenLabs reached
  `POST /api/voice/llm/v1/chat/completions` and was answered 401, and the paid check heard no reply
  (`conversation_initiation_metadata` then 52 pings). `authorised_session` refuses for four
  reasons with one message, by design (the caller learns nothing), and logged none of them, so the
  box's logs could not say which one failed.

## Decision

1. **The rubric floor is 0.88.** `answers.rubricMean` in `backend/app/data/eval/floors.json` is the
   run's 0.930 less 0.05, rounded down. The judge floor stays 0.76: the run's 0.807 less 0.05
   would round down to 0.75, and a floor only rises.
2. **The recorded replies are the video fixtures.** `backend/tests/media/fixtures` holds the
   run's start (`video_started.json`), first open poll (`video_polling.json`), finished
   interaction (`video_completed.json`, the clip's base64 cut to the small two-track MP4 of
   `tests/media/mp4_builder.py` and the thought signature cut to 64 characters) and the delete
   reply (`video_deleted.json`). `gemini_media` and `MEDIA_OUTPUT` read the recorded shapes as
   they are, so neither changes. The audio rule of `MEDIA_OUTPUT` was checked on the recorded clip
   itself: `media/mp4.without_audio` removed its one `soun` track, and all 17 video chunk offsets
   moved by the 2,070 bytes removed and still point at the same bytes.
3. **Every reader's chunk ACL is `PUBLIC`.** Migration `0100_signed_in_chunks_public` sets every
   `SIGNED_IN` chunk to `PUBLIC` (their kind stays `WINDOW`) and drops the trigger
   `Chunk_kind_window_mark` with its function. `OPEN_CHUNK_ACLS` is `("PUBLIC",)`,
   `SIGNED_IN_CHUNK_ACL` is gone, and `EVERY_CHUNK_ACLS`, what a `READ_RESEARCHER_QUOTES` holder
   reads, is `PUBLIC` and `RESEARCHER`. The PostgreSQL type `ChunkAcl` keeps its `SIGNED_IN`
   label, which no row holds and no reader reads, and so does `CHUNK_ACLS`, the model's copy of the
   type, since `tests/test_app_and_schema.py` holds the model to every label its migrations
   declare: the release before binds it in
   `Chunk.acl IN (...)` while the new colour starts, so dropping it now would fail that release's
   every read, and dropping it later means recreating the type, which rewrites the `Chunk` table and
   rebuilds its vector index under an exclusive lock, for no reader's gain. `OpenEnum` reads the
   label as text if it ever met one.
4. **A refused agent turn names its check in the log.** `authorised_session` logs one warning, `a
   voice agent turn was refused at the <check> check: <why>`, with the check one of
   `REFUSAL_CHECKS` (bearer, conversation header, session record, binding) and the why a fixed
   phrase (no authorization header, not a bearer, no bearer or session key configured, a different
   bearer; the header's length; no session holds the conversation, its purpose or transport, ended
   or past its hard end, its turn count; the nonce or conversation does not match). It never logs a
   bearer, key, nonce or conversation id. The reply is still the one 401 `unauthorized`.
5. **The fetcher and web search are seen on the box.** On release dab903fd (2026-11-24),
   `kv-fetcher` answered `/health` 200, fetched and read one HTML page (191,259 bytes, 6,379
   characters of text) and one PDF (13,264 bytes), and its unit's memory peaked at 236 MB against
   `MemoryMax` 768 MB; `WebFetch` held 212 rows, the newest written by an answer that evening. One
   SearXNG and one Brave web search and one image search of each were recorded on the box as
   `backend/tests/sources/fixtures/{searxng,brave}_{search,images}.recorded.json` (results cut to
   five and eight): the adapters read five https web pages from each search, and keep seven of
   Brave's eight pictures and six of SearXNG's, leaving out those another site serves. The
   synthetic fixtures stay for the cases no live reply shows (an empty reply, no web block, long
   ids). SearXNG reported its own Brave engine rate-limited and DuckDuckGo behind a CAPTCHA, so its
   hits came from its other engines.

## Consequences

- The next answer-quality run fails below 0.88 and keeps the issue `Answers fell below their floor`
  open until a whole run passes.
- The register entry "Gemini video not yet seen live" is rewritten to what is still unseen: the
  `image` input that would make a stage image the clip's first frame, and a safety block. The
  entry "The rubric floor waits on a run that shows the quantities table" and the entry "The
  `SIGNED_IN` chunk ACL is read by everyone" are deleted.
- The two write-back entries are deleted on the filing report run on production on 2026-11-24
  (`python -m app.scripts.write_back_filing` on release 1e366637): all 75 approved write-backs with
  no `CandidateCheck` row are among the 171 the lead reviewed on 2026-11-23 under the owner's
  approval of 2026-11-22, and the 20 of them today's rule would file elsewhere carry that review's
  KEEP ruling; the 19 facts answer 504968ea-49cc-469c-88f9-205a2ea90e8a wrote are all decided (12
  rejected, 1 retracted, 6 approved, each filed where today's rule files it). The five facts still
  filed elsewhere are `IN_REVIEW`, waiting in the review queue as every gated write-back does.
- The entry "Web search and fetcher: recordings and the box" is deleted on item 5. The register
  holds 42 entries.
- Readers read exactly the rows they read before: every window was readable by everyone through
  `SIGNED_IN`, and is now through `PUBLIC`. Searches that pass no reader's ACLs still read windows
  only when they name `WINDOW`.
- After this release the voice check is run again with the call switched on for the owner's window,
  and the kv-api log names the check to fix; the entry "ElevenLabs behaviour not yet verified"
  stays until a turn is answered.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/answering/test_answer_floors.py`, `backend/tests/retrieval/test_eval_floors.py`,
`backend/tests/media/test_gemini_media.py`, `backend/tests/db/test_chunk_kinds_db.py`,
`backend/tests/field_voices/test_citing_rules.py`, `backend/tests/voice/test_pack_access.py`,
`backend/tests/voice/test_agent_turn.py`, `backend/tests/sources/test_web_adapters.py` and
`backend/tests/sources/test_brave_images.py`.
