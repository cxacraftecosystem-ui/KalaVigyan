# 0173. A release keeps the site serving and its way back open, a colour takes traffic only once it reaches its database, the web builds only on the API it calls, the fetcher runs as a user of its own, and every provider call ends and settles

A release that retried its migration starts the live colour again before it seeds; a release that
stops before its switch points the idle slot back at the release it held, and a plain rollback
promotes only a release that has served; every new colour, a restart's included, must answer
`/health/ready` before nginx switches to it; a release stops itself before SSM's limit through the
same clean-up as any failure; the web app builds only when the API that `main`'s head needs is the
one answering; the fetcher runs as a dynamic user that cannot see the API's process; Gemini's
calls are bounded; a cut-off vision screen settles at its estimate; and one unreadable artisan
transcript no longer stops the retention purge.

Date: 2026-11-23. Status: accepted (the lead's brief for the release and infra fix lane, from the
adversarial review of the whole codebase on 2026-11-23: eight confirmed findings and one
uncertain one). It amends [decision 0007](0007-web-search-and-fetcher.md), the fetcher sandbox,
which now runs as a user of its own. The contract is `docs/contracts/infra.md` (CI; Liveness and
readiness; Migrations; Fetcher); the RUNBOOK's Deploy and Roll back say how to use it.

| For | Read |
|---|---|
| The fetcher sandbox it amends | [decision 0007](0007-web-search-and-fetcher.md) |
| Every migration readable by the release before, which lets the old colour serve again after one | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| A cut-off call settled at its estimate | [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) |
| The pooler sessions each process may hold | [decision 0163](0163-limits-kept-by-choice-and-a-register-that-only-shrinks.md) |
| How a release migrates, seeds, checks and switches | [infra.md](../contracts/infra.md), Migrations and Seeds |
| Every decision, by group | [README.md](README.md) |

## Context

- **A retried migration left the site down.** After three failed `alembic upgrade` tries,
  `blue_green.sh` stopped the live colour to free its pooler sessions and tried five more times;
  when one passed, nothing started the live colour again, so nginx proxied to a stopped port
  through the seeds, embeds, page rebuild and retrieval check, 20 to 35 minutes. The watchdog
  restarts only running units.
- **A plain rollback promoted the release that had just failed.** `cmd_release` pointed the idle
  slot at the new release before it migrated, and nothing pointed it back; `rollback` with no
  argument started whatever that slot held and promoted it on `/health`, which never touches the
  database. The RUNBOOK said the previous release was still there.
- **Every gate read `/health`.** The switch, the in-place restart that a same-commit Deploy backend
  run takes, `release.sh`'s last check and the CloudFront smoke all passed a colour whose
  `DATABASE_URL` was wrong.
- **A web-only push shipped the frontend of an API that was not live.** Deploy web app diffed only
  its own push's range, but the deploy hook builds the head of `main`, which holds the frontend of
  every earlier push, including one whose API was still in Backend checks or failed there. Deploy
  backend's last step built `main`'s head the same way.
- **The fetcher could read every secret.** It ran as `kalavigyan`, the user of the API, worker and
  queue, which load the full `.env`; a process can read `/proc/<pid>/environ` of its own user, so
  `InaccessiblePaths` and the `FETCHER_`-only `fetcher.env` kept nothing from code running in it.
- **The release could outlive its SSM command.** The command runs with `executionTimeout` 2700 s
  and SSM kills the process group, which skips the EXIT trap that restarts the workers, the
  fetcher, the queue and a stopped live colour. The last 25 Deploy backend runs took 11 to 17
  minutes; run 45157344139 spent 14 minutes on the box with its page rebuild cut at its 480 s
  budget. The bounded steps before the switch can take 2,100 s, and the rest are unbounded: a
  migration has no lock timeout, so one waiting on a lock the serving colour holds waits until SSM
  kills it. The mechanism is real and the margin thin, so the finding was taken as real.
- **A stalled Gemini call held its provider's slot forever.** `genai.Client` had no timeout, and
  the router holds the provider's semaphore for the whole call; Gemini is the only embedding route.
- **A cut-off vision screen left its reservation unsettled**, so its spend counted for 15 minutes
  and then as nothing, against decision 0146's rule.
- **One unreadable artisan transcript stopped the purge.** `_closed` opened each lapsed
  conversation's transcript with no per-row guard, so an `InvalidInput` ended the upkeep before
  `purge_due`, every day, as the same row came back.

## Decision

1. **The live colour serves again as soon as the migration passes.** `migrate_serving` keeps the
   three-then-five tries and the stop between them, and `serve_again` starts the stopped colour and
   waits for `/health` before the seeds. Decision 0151's rule that every migration is readable and
   writable by the release before makes this safe; it is what the release does when the first try
   passes.
2. **A stopped release puts its slot back, and a plain rollback promotes only a release that has
   served.** `begin` records what the idle slot held before anything changes it, and the exit of
   any run that did not switch (a release, a rollback, a restart) points it back. `promote` already
   writes `.released` into a release it switches to; `rollback` with no argument refuses a slot
   whose release lacks it and names what the slot holds, so even a slot a killed run left behind is
   never promoted by accident. A named rollback goes where it is told.
3. **A colour takes traffic only once it reaches its database.** `start_and_promote` waits for
   `/health/ready`; the watchdog and nginx's check right after a switch keep `/health`, since they
   ask whether the process and the proxy answer, and restarting a colour because the database is
   away would not help. A restart (`kv-blue-green restart`, also what a same-commit Deploy backend
   run does) is blue/green: the live release starts on the other colour with the environment as
   rendered now and is switched to only once ready, so a bad secret leaves the old colour serving
   instead of breaking it in place; the idle slot then gets back the release it held. The
   alternative, the in-place restart gated on readiness, would only have turned the run red after
   the outage began. `release.sh`'s last check and the CloudFront smoke read `/health/ready`, and
   the smoke waits until `/health` names the deployed commit.
4. **A release stops itself before SSM would.** `release.sh` passes `blue_green.sh release <sha>
   --within <seconds>`, the time left of `RELEASE_SECONDS` (2700, set once in the workflow, which
   passes it to SSM as `executionTimeout` and to `release.sh` as `SSM_SECONDS`) less a 300-second
   margin, and refuses to start a switch with less than 600 left. `--within` runs the release under
   `timeout --signal=TERM --kill-after=240`: bash runs its EXIT trap on SIGTERM without waiting for
   the step in hand, so the same clean-up as a failure puts the slot, the old colour and the workers
   back, and the SIGKILL lands a minute before SSM's. Raising `executionTimeout` would only move the
   cliff; a TERM trap waits for the running step, up to 960 s; a deadline threaded through each of
   eleven steps would be eleven places to get wrong.
5. **The web builds only on the API it calls.** The API colour reads `RELEASE` from its slot's
   `release.env`, which `release.sh` writes for every release, so `/health` names the commit it
   runs. `build-web-app` runs `api_ready.sh` before the hook: it fetches `main`, diffs the live
   commit against `main`'s head over the Backend checks push paths, and calls the hook only when
   nothing there changed. Deploy web app (push or by hand) and Deploy backend's last step both go
   through it, so a web-only push waits for an earlier API push to ship and Deploy backend does not
   ship a newer API push's frontend; the run says why in a warning. Asking the live API, rather than
   reading the last successful Deploy backend run, also sees a rollback by hand.
6. **The fetcher runs as a user of its own.** `kv-fetcher.service` drops `User=kalavigyan` and
   `Group=kalavigyan` for `DynamicUser=yes`, so systemd makes a user and group for it at each start,
   and adds `ProtectProc=invisible`, so it sees no other user's processes in `/proc`. A different
   user cannot open another's `environ` without `CAP_SYS_PTRACE`, and outside the `kalavigyan` group
   it cannot read `.env` even if `InaccessiblePaths` were lost. PID 1 still reads `fetcher.env` as
   root, and the release tree and interpreter stay world-readable, so nothing else changes and no
   step on the box is needed: the next release installs the unit and restarts the fetcher. A static
   `kv-fetcher` user would need the box's `user_data.sh` and a step by hand; `ProtectProc` alone
   hides only other users' processes, and the API was the same user; `PrivatePIDs` would have kept
   the shared user and group.
7. **Every Gemini call ends.** `GeminiAdapter` bounds a chat to `CALL_SECONDS` (600, the Anthropic
   and OpenAI clients' bound, now one constant in `providers/base`) and an embedding batch to 120 s
   with `asyncio.timeout`; a call that runs out raises a retryable `unavailable` `ProviderError`, so
   the router records it, moves to the next route and leaves the provider's semaphore. The client's
   own `HttpOptions` timeout was not used: it raises the HTTP backend's exception types, which
   depend on whether google-genai picks httpx, httpx2 or aiohttp, and the adapter maps none of them.
8. **A cut-off vision screen settles at its estimate.** `screen_with_vision` settles any exception
   other than a `ProviderError`, a cancellation included, through `settle_abandoned` and re-raises,
   as the router, the rerank router and the media router do.
9. **An unreadable transcript is a failure of its row.** `_closed` reports the conversation and its
   error in the upkeep's failures and goes on, so lapsed conversations close, extractions run, and
   the purge and the expired rejections are cleared; the daily report's `ok` is false while the row
   stays unreadable.

## Consequences

- A release that stops before its switch costs nothing to roll back from, and a migration retry no
  longer takes the site down for the rest of the release.
- A restart takes as long as a colour's start and runs both colours briefly, inside the two slots
  the connection budget already counts. A secret that breaks the database turns the run red and
  leaves the old colour serving on the old environment; the rendered `.env` still holds the bad
  value, so any process that restarts reads it until the secret is fixed.
- A web-only push behind an API push that has not shipped builds nothing until an API push does;
  the hourly "Production is not serving main" check shows the lag. A release built before this
  change names no commit until it is released again; its first Deploy backend writes `release.env`.
- A release that runs out of time may leave a bounded step (an embed, the page rebuild, the
  retrieval check) running in its own process group until that step's own budget ends, as a
  release stopped by its retrieval check already leaves the pages its rebuild wrote.
- Gemini answers that legitimately take longer than ten minutes, or embedding batches longer than
  two, now fail over to the next route.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/deploy/test_blue_green.py`
(which runs `blue_green.sh` on a fake box), `backend/tests/deploy/test_release_wiring.py`,
`backend/tests/deploy/test_web_build_gate.py` (which runs `api_ready.sh` against a real git
history), `backend/tests/test_gemini_stalls.py`, `backend/tests/images/test_picture_vision.py` and
`backend/tests/voice/test_artisan_upkeep.py`.
