# 0154. AI media and film scores kept true: one making per score, scores timed by what was heard, page copies, and paid checks under a cap

A film score is made once under a lease, answered 202 while it is being made, timed by the
narration readers heard and cued by the facets its blocks store; old clips leave the bucket; the
worker says it is alive; AI pictures get a page copy and are shared on the craft page with two
professors' sign-off for a named cluster; and the paid checks the owner approved run from one job
that cannot pass US$5.

Date: 2026-11-23. Status: accepted (the lead's debt-clearing brief, media-and-film lane, from the
debt register of 2026-11-22). It amends [decision 0018](0018-media-backend.md),
[decision 0058](0058-elevenlabs-music-sound-image-video.md),
[decision 0060](0060-zoom-timeline-and-film-renderers.md) and
[decision 0096](0096-reader-question-pieces-join-their-craft-page.md). The contracts are
`docs/contracts/media.md`, `docs/contracts/explainer.md` (Film mode) and
`docs/contracts/craft-page.md`.

| For | Read |
|---|---|
| The media backend it amends (heartbeat, holds, refunds, page copy, sharing) | [decision 0018](0018-media-backend.md) |
| The score it amends (timing, the cue table, one making, 202) | [decision 0058](0058-elevenlabs-music-sound-image-video.md) |
| The film renderer it amends (the gain on iPhones and iPads) | [decision 0060](0060-zoom-timeline-and-film-renderers.md) |
| The AI media on the craft page it builds | [decision 0096](0096-reader-question-pieces-join-their-craft-page.md) |
| No connection held across a model call | [decision 0040](0040-no-connection-held-across-a-model-call.md) |
| The paid checks chosen one by one, and one Gemini clip made when a run names it | [decision 0179](0179-transcript-windows-a-chunk-kind-linked-shared-concepts-and-one-paid-clip.md) |
| The film playing before its narration is whole | [decision 0176](0176-listen-plays-as-it-narrates-builds-wait-for-the-api-runs-are-kept.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The register held 21 entries for AI media, film scores and their checks. Most were code left
below its own contract; six waited on calls nobody had paid for. On 2026-11-22 the owner approved
paid live checks up to US$5 in total ("Yes, up to $5 total"): one English and one Hindi narration,
one short music bed, one agent turn and one Gemini image, each reply recorded as a test fixture.
The keys are only in GitHub secrets and Parameter Store, and the ElevenLabs key is restricted to
the box's address.

## Decision

1. **One making per score, answered 202 while it runs.** A score is planned (scenes, hash, bed),
   served when a stored manifest matches the plan, and otherwise made under an S3 lease at
   `media/score/<answerId>/<language>/lease.json` (600 s), so two asks never both pay. The lease is
   the narration's, made generic in `voice/object_lease.py`; no database connection is held across
   the calls (decision 0040). The route waits 45 s; a making still running, or one another ask
   holds, answers 202 `FilmScoreMaking` and the client asks again every 5 s, at most 60 times.
   The rate limit counts only asks that start a making. A worker job queue for audio was the
   alternative; the lease and shielded work give the same result without a second queue.
2. **The bed is cut from what was heard.** When Listen has stored the narration of every spoken
   block for the reader's voice and language, scenes last as long as those parts; otherwise the
   character estimate stands. A stored score whose bed is shorter or longer than the plan is made
   again (clips are content-addressed, so the cues are reused).
3. **Cues follow stored facets (`film-score/v2`).** A ladder is cued by the facet most of its
   stages' types share (tools, water, fire; ties to the first), a region story only when it holds a
   river; prose gets none, because nothing stored says what a prose block is about. The hash now
   carries the prompt version and each scene's facet.
4. **Old clips leave the bucket.** S3 lifecycle cannot tell whether a manifest names a clip, so
   the worker's daily sweep marks each clip no manifest names (`unnamed.json`) and deletes the
   folder 90 days later; a manifest naming it again, or a making reusing it, lifts the mark.
5. **The worker says it is alive.** It writes `AppSetting` `worker.heartbeat` every 60 s, which the
   options and job routes read (silent more than 5 minutes: no kind offered, no job queued), and
   pings systemd's watchdog (`Type=notify`, `WatchdogSec=300`), which restarts a hung worker. The
   API watchdog stays for the API slots.
6. **Spend.** A refund row is dated to its job's creation, so a unit returns to the day that spent
   it; the worker renews a queued job's hold once a minute when it is older than half the 15-minute
   reservation. `MediaJob.costUsd` keeps the call that made the asset by choice; every call is in
   `UsageEvent`.
7. **Pages own sharing.** On success the worker writes a requester-free copy at
   `media/craft/<sha256>/<fileName>`, sets `MediaAsset.pageKey` (migration `0078_media_page_key`)
   and shares the asset unless it depicts a named cluster; the chapters job copies older assets.
   Shared assets join their craft's chapters as `ai_media` and are read at
   `GET /api/crafts/media/{assetId}`. The craft page's show route records the sign-offs of a named
   cluster: the first professor's keeps it hidden, a second professor's shows it, hiding withdraws
   both. The separate sharing route the client had a contract for, which no screen drew, is retired
   with its client code.
8. **The iPhone volume.** Where the element volume is fixed, the bed and each cue play through one
   Web Audio gain each, created on the reader's first press and loaded with CORS from the bucket;
   elsewhere the element volume stays, so no other browser depends on the bucket's CORS.
9. **India time has one home.** `models/time_zone.INDIA_TZ_NAME` is read by `core/clock` and by
   `Craft.recordedTimezone`'s default. The geo ETL is its own package with no dependency on the
   backend and keeps a fixed +05:30 offset for its run date by choice; India has no daylight time.
10. **Paid checks under a cap.** `.github/workflows/paid-checks.yml` (workflow_dispatch, cap at
    most 5) runs `python -m app.scripts.paid_checks` on the box over SSM, where the keys are. Each
    check is estimated before it is made (narration at $0.30 a thousand characters, a 10 s bed at
    $0.275 a minute, the image at $0.067, the agent turn at $1.50) and skipped when the running total
    would pass the cap; a failed call counts its estimate. Every reply is recorded without request
    headers and kept as the run's artifact with `paid_checks_report.json`, which the lead commits
    as fixtures. The agent turn opens a conversation over the signed WebSocket, binds a Master
    Admin voice session to its conversation id before asking one question, ends the session and
    deletes the conversation. `websockets` becomes a direct dependency (it was locked through
    `uvicorn[standard]`).

## Consequences

- Entries left in `docs/TECH_DEBT.md` wait on that paid run, on calls the approval does not cover
  (a Gemini clip, an ElevenLabs picture), on the invoice, on a person with an iPhone, or on the
  owner's register of community names; the inset frame for places abroad was not done.
- Existing score manifests are made again once (version 2), and existing clips once by their new
  cache ids.
- `kv-worker.service` is installed by the release from its own folder, so a rollback installs the
  matching unit.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/voice/test_film_scenes.py`,
`test_film_score.py`, `test_film_score_making.py`, `test_film_routes.py` and
`test_narration_lease.py`, `backend/tests/test_worker_schedule.py`, `backend/tests/media/test_jobs.py`,
`test_queue.py`, `test_runner.py` and `test_page_media_route.py`, `backend/tests/db/test_media_store_db.py`,
`test_worker_heartbeat_db.py` and `test_craft_ai_media_db.py`, `backend/tests/test_paid_checks.py`,
`backend/tests/test_india_time.py`, and `frontend/e2e/film-mode-unit.spec.ts`,
`explainer-phase-c-unit.spec.ts` and `release/answerControls.ts`.
