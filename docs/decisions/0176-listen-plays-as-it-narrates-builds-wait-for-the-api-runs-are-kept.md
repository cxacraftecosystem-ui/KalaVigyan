# 0176. Listen plays as it narrates, the admin build waits for the API main needs, evaluation runs are kept, and the Gemini voice is a fixture

Listen and the film start on the first narrated block, the lede of a whole answer, and the rest is
made while it plays; an Admin's Start a build waits, as the deploy workflows do, until the API runs
every change `main` makes to it; each finished answer-quality, weekly retrieval and release-check
run keeps its summary where the admin report reads it; and the paid check's Gemini read-aloud is
the speech adapter's fixture.

Date: 2026-11-23. Status: accepted (the lead's follow-ups brief of 2026-11-23, follow-ups lane,
after decisions 0170, 0173, 0174 and 0175). It amends [decision 0035](0035-listen-and-voice-switched-off.md)
(what Listen's limit counts, when it answers), [decision 0140](0140-voice-and-listen-kept-true.md)
(the narration lease, now renewed), [decision 0154](0154-ai-media-and-film-scores-kept-true.md)
(the film, which plays before its narration is whole), [decision 0161](0161-listen-falls-back-a-node-counts-admins-see-hidden-facts.md)
(the fallback, now decided on the first block, and the Gemini voice heard),
[decision 0170](0170-review-over-mcp-staged-and-pages-refreshed-now.md) (the evaluations report)
and [decision 0173](0173-a-release-that-keeps-serving-and-its-way-back.md) (the web built only on
the API it calls, now from the admin button too). The contracts are `docs/contracts/voice.md`
(Listen), `docs/contracts/explainer.md` (Film mode; Listen), `docs/contracts/frontend.md`,
`docs/contracts/nightly-upkeep.md` (Schedule; Routes), `docs/contracts/knowledge-api.md` (Admin
reports) and `docs/contracts/retrieval.md` (Evaluation).

| For | Read |
|---|---|
| Listen, its cache, its seconds and its limit | [decision 0035](0035-listen-and-voice-switched-off.md) |
| The lede first and the narration lease | [decision 0140](0140-voice-and-listen-kept-true.md) |
| The film's score and the paid checks | [decision 0154](0154-ai-media-and-film-scores-kept-true.md) |
| The Gemini voice and the voice a script names | [decision 0161](0161-listen-falls-back-a-node-counts-admins-see-hidden-facts.md) |
| The admin reports over MCP | [decision 0170](0170-review-over-mcp-staged-and-pages-refreshed-now.md) |
| `api_ready.sh`, the gate the deploy workflows build through | [decision 0173](0173-a-release-that-keeps-serving-and-its-way-back.md) |
| The film control's 300 s wait on production | [decision 0175](0175-production-checks-read-what-the-page-shows.md) |
| A field the web reads ships with its web shape | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **Listen made every block before it answered.** `GET /api/answers/{id}/listen` narrated every
  missing block in the one request, three text-to-speech calls at a time; a new 63-sentence answer's
  first Listen took 99.6 s on production (release 37c0f9bb), and since `NARRATION_VERSION` 3 every
  stored narration is made once more, so every reader meets that wait once per answer. The film
  waited on the same request, which is why its production control waits up to 300 s (0175).
- **The admin button skipped the API gate.** Decision 0173 made both deploy workflows call the
  Vercel hook only through `api_ready.sh`, which diffs the commit the API runs (`/health`'s
  `release`) against `main` over the Backend checks push paths. The settings hub's Start a build
  (`POST /api/site/build`) still called the hook directly, so it could build a site whose pages
  need an API change not yet live. The box holds no GitHub token and the release tarball holds only
  `backend` and `infra/deploy`, not the workflow that lists those paths.
- **No evaluation run was kept where the server reads.** Decision 0170's evaluations report gave
  floors with `measured: null`: both evaluation workflows print their report and upload it as an
  artifact. The first schema's `EvalRun` table (suite, commit, status, budget, cost, summary,
  times) was never written by any code.
- **The Gemini voice was heard.** Paid run 45164894170 recorded `gemini-3.8-flash-tts` answering the
  documented interaction: a 24 kHz mono 16-bit WAV in the last `audio` block of the `model_output`
  step (`mime_type` `audio/wav`), 5.44 s for 81 characters, with the media wire's `Api-Revision`
  header accepted. Its ElevenLabs narrations, sent with parentheses for square brackets, spoke the
  parenthesised words in 1.32 s (English) and 1.12 s (Hindi).

## Decision

1. **The ask waits for its first block only.** `voice/listen_making.first_block_made` takes the
   leases of the blocks it misses (the first block before the rest), and, when it holds any, admits
   the making (decision 6), holds the seconds of all of them at once and starts making them in the
   API process (`ShieldedWork`), three parts at a time, the first block first. The request awaits
   only the first block; the answer lists the blocks narrated from the first up to the first one not
   yet stored as `tracks`, every later block as `pending`, and `pollAfterSeconds` (3) exactly when
   blocks are pending. A block another ask is making is `pending`, not waited for, unless it is the
   first; the first, held elsewhere, is waited for each second until the lease seen lapses, then
   taken over, or 503 while a renewed lease still covers it. A later block whose making fails is
   left unstored and its lease freed, so the next ask makes it again. Per-block reads (an ask per
   block) were refused: every block would be a request through the limit, the hold and the
   explainer read, and the blocks would be made one at a time instead of three.
2. **The hold and the voices are unchanged.** One hold per ask that makes anything, under
   `listen:<requestId>:<voice>:hold`, settled once every block it made is made or failed; no model
   call is added and the day's allowance and the voices are those of decisions 0035 and 0161. The
   fallback is decided on the first block: an own-service failure there stops the rest of that
   voice's making, settles it and reads the script with the next voice, as before. An ask may name
   `voice`; it is then read by that voice alone (503 when it is not offered), which is how a poll
   continues a script without mixing voices.
3. **Leases are renewed while a block waits or is read.** The making renews each of its unfinished
   blocks' leases every 30 s (`LEASE_RENEW_SECONDS`, a quarter of the 120 s lease,
   `object_lease.renew_lease`), so a block queued behind others is never taken over by the reader's
   own polls; a maker that dies stops renewing and its leases lapse within 120 s.
4. **The web plays what it has and asks for the rest.** `ListenScript` gains `pending?` and
   `pollAfterSeconds?`, both optional on the web (`lib/listen.ts`) and checked together, so the web
   reads an older backend's script, and the production web ignores them before it knows them
   (decision 0151). One feed, `components/answer/useListenScript.ts`, serves the dock and the film:
   it asks again with the script's voice every `pollAfterSeconds` while blocks are pending, at most
   100 times, keeps the tracks it holds (their links stay valid an hour) and adds the new ones
   (`extendedScript`), and stalls with a message when a poll fails or answers another voice or
   order. The dock plays on; at the end of what is narrated it says "Preparing the next part…"
   (`afterTrack`) and fails with Try again only if the feed stalled. A film scene whose block is
   pending holds at its start (`filmStep` ignores the clock there, `filmWaits`) and says it is
   preparing that scene's narration.
5. **The film control's 300 s stays a ceiling.** The film is ready as soon as the lede is narrated,
   so the production control (`FILM_READY_MS`) should rarely wait long; it is left as it is.
6. **The limit counts makings, not asks.** The 30 in 10 minutes of `listen_attempt` is taken only by
   an ask that starts a making (`api/listen_deps.making_admission`), as the film score's limit is
   (decision 0154); a cached reading and a poll that starts nothing are never refused. A making the
   limit refuses frees its leases and holds nothing.
7. **The admin build waits for the API `main` needs.** `services/web_build_gate.refuse_ahead_of_api`
   asks GitHub's public REST API, with no token and nothing named but the repository, for the newest
   Backend checks run on a push to `main`, and builds only when that run's commit is the API's own
   `RELEASE` or an ancestor of it (`compare/<commit>...<release>` answering `identical` or
   `ahead`). Backend checks runs on a push to `main` exactly when the push changes the Backend
   checks paths, so GitHub applies the one list `api_ready.sh` reads; the server keeps no copy of it.
   An API that names no release, or no such run, refuses (409, saying why), and GitHub failing is
   502; nothing is built in either case. Diffing `release...main` on the server was the
   alternative: it needs the path list, which lives only in the workflow, so it would be a second
   copy kept equal by a test. Dispatching Deploy web app needs a token the box does not hold, and
   no secret is added. Between a push and GitHub creating its run (seconds) the gate cannot see the
   push; the deploy workflows' gate has the same window between its check and Vercel's clone.
8. **Each finished run keeps its summary in `EvalRun`.** The first schema's unused table is reused,
   not a second one made: migration `0094_eval_run_summaries` (after `0097_chunk_kinds`, round 7's
   head when it merged) adds `fresh` (default false) and
   `floorsHeld` (null when the floors were not compared), allows `suite` only `ANSWERS`,
   `RETRIEVAL` and `RELEASE_CHECK`, and indexes `(suite, finishedAt)`. `eval_answers` and
   `eval_retrieval` (weekly and `--release`) store kind, start and finish, the release commit, the
   settled spend (the release check's searches now tagged and measured too), the cap, the mean of
   each measure and every floor check (`summary`, version 1) through `services/eval_run_store`; a
   store that fails is reported as `storeError` in the printed report and never fails the run. The
   release commit is `RELEASE`, which the callers now export from the release's `release.env`
   (`answer-quality.yml`, `retrieval-eval.yml`, `blue_green.sh`), as the API's units do. The
   evaluations report lists the latest run of each kind, then each floor with the value the latest
   run measuring it found (`measuredBy`). The full report stays the workflow's artifact.
9. **The Gemini read-aloud is a fixture.** `backend/tests/media/fixtures/speech_completed.json` is
   the recorded interaction, its audio cut to its first 4,096 base64 characters (the WAV header
   kept, so its declared length still reads 5.44 s); the adapter's test parses it as Listen does and
   times its sentence from the samples, and `providers/gemini_media.py` needed no change. The run's
   ElevenLabs replies and report join the voice fixtures (`narration_parenthesised*.json`,
   `paid_checks_report_run2.json`) and prove the parentheses are read in both languages.

## Consequences

- A whole answer's first Listen answers in the time of its lede; the rest is made while it plays.
  A reader who closes the page does not stop the making; a restart of the API process does, and the
  next ask makes what is left.
- Polls read the explainer and every block's manifest each time, every 3 s while blocks are pending.
- The register's two Listen voice entries become one, on the languages and the angle brackets still
  unheard.
- Production needs migration 0094 (the release runs it) and, for the evaluation's release commit,
  nothing more: the next release's `release.env` and the next run supply it.
- The admin build calls GitHub's API at most once a press, within GitHub's 60 unauthenticated
  requests an hour per address.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/voice/test_listen_progressive.py`, `test_listen.py`, `test_listen_fallback.py`,
`test_listen_routes.py`, `test_narration_lease.py` and `test_recorded_narration.py`,
`backend/tests/media/test_gemini_speech.py`, `backend/tests/upkeep/test_site_build_gate.py` and
`test_site_build_routes.py`, `backend/tests/mcp/test_admin_reports.py`,
`backend/tests/test_eval_run_summaries_migration.py`, `backend/tests/db/test_eval_runs_db.py`, and
`frontend/e2e/listen-pending-unit.spec.ts` and `film-mode-unit.spec.ts`.
