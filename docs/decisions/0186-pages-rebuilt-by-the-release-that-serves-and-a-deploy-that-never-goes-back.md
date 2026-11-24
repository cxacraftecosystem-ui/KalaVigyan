# 0186. Stored pages are rebuilt only by the release that serves them, a deploy never moves production back, and the migrated database is read under the release production serves

A release rebuilds its stale pages and stored documents only after its switch, once the old
colour has stopped, and a rollback rebuilds them with the release it goes back to right after its
own switch; Deploy backend refuses a commit that does not come after the release `/health` names;
and Backend checks reads the migrated database under the models of the release production serves
as well as under its base, through one script that reads `/health` for every workflow.

Date: 2026-11-24. Status: accepted (the lead's brief for the release lane, from the adversarial
review of the whole codebase on 2026-11-24, workflow wf_af6bcf74-937: three confirmed findings).
It amends [decision 0173](0173-a-release-that-keeps-serving-and-its-way-back.md) (how a release
seeds, switches and rolls back, and how the web build reads the API's release) and
[decision 0151](0151-a-release-the-live-side-can-read.md) (the release before's probe). The
contract is `docs/contracts/infra.md` (CI; Migrations; Seeds; Stored pages); the RUNBOOK's Deploy
and Roll back say how to use it.

| For | Read |
|---|---|
| The release that keeps serving and its way back, which this amends | [decision 0173](0173-a-release-that-keeps-serving-and-its-way-back.md) |
| Every migration readable by the release before, and its probe, which this amends | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| The field whose arrival showed the fault, `CitedSource.kind` | [decision 0183](0183-the-shared-template-draws-the-approved-page.md) |
| How a release migrates, seeds, switches and rebuilds pages | [infra.md](../contracts/infra.md), Migrations, Seeds and Stored pages |
| Every decision, by group | [README.md](README.md) |

## Context

- **The release before read documents in the new shape.** `blue_green.sh`'s `seed()` ran
  `rebuild_pages` before the retrieval check and the switch. `rebuild_stale_documents` marks the
  new page code (`pages.documentCode`) and writes every stale generated document again, and
  `load_monograph` stores each authored `MonographDocument`, in the new release's shape. Decision
  0183 added `CitedSource.kind`, which `source_ref` sets on every source, so every rebuilt body
  carried `sources[*].kind`. While the release before still served, its
  `page_translation_serving.page_in_language` validated such a body with its own
  `MonographContent`, whose `ContractModel` forbids unknown keys, so a read whose page-text index
  lagged the document, and every translated read, ended in the catch-all handler's 500. The old
  colour could not rebuild them back: `rebuilds_here` compares the newer fingerprint. A release
  the retrieval floor stopped would leave them so until the nightly upkeep, and a rollback to an
  earlier release met the same bodies.
- **The probe read the wrong release before.** Backend checks probed `github.event.before` on a
  push to `main`, the previous head whether or not it ever shipped. Backend checks cancels a run
  when its branch moves on and Deploy backend runs only after a successful one, so a push whose
  checks were cancelled, or whose deploy failed, never served, and production would go from the
  release before it straight to the next push, whose probe had checked models production never
  ran.
- **An older successful run shipped over a newer release.** Deploy backend checked out
  `workflow_run.head_sha` and released it with no comparison with the live release; only
  `blue_green.sh` refused the release already served. Re-running an older Backend checks or
  Deploy backend run would ship older code: with an older migration head, `alembic upgrade head`
  fails on the unknown revision, and after three tries `migrate_serving` stops the live colour
  for five more, so the API would be down for one to two minutes; with the same head, older code
  and dossiers would ship and the smoke step, which expects the commit it shipped, would pass.

## Decision

1. **A release rebuilds its pages after its switch.** `rebuild_pages` leaves `seed()`;
   `cmd_release` runs it after `start_and_promote` (the old colour is stopped there) and before
   `refresh_served_pages`. Until the switch every stored body stays as the live release wrote it,
   a release stopped before its switch leaves them so, and the new colour reads the older shape
   because a field a release adds to a stored body has a default. The web build still follows the
   rebuild, since Deploy backend starts it only after the release on the box ends.
2. **A rollback rebuilds with the release it goes back to.** `cmd_rollback` runs
   `rebuild_pages "$target/backend"` after its switch and before `refresh_served_pages`: the
   rolled-back code marks its own page code and writes every stale body in its own shape. The
   switch stays first, so a rollback is still instant.
3. **A time-out after the switch keeps the new release.** A release that reaches its `--within`
   limit while it rebuilds pages has handed over, so its clean-up starts nothing old again; the run
   fails and the nightly upkeep rebuilds what is left.
4. **Deploy backend ships only a commit after the release production serves.** Its checkout takes
   the whole history, and its step *Refuse a commit older than the release production serves*,
   right after the release is named and before AWS is touched, runs
   `.github/scripts/release_order.sh descends "$SHA"`. The commit `/health` names must be `$SHA`
   (a re-run, which starts it again on the current environment) or its ancestor
   (`git merge-base --is-ancestor`); an older or a sideways commit is refused, naming
   `kv-blue-green rollback` as the way back. A commit this repository does not hold is refused.
   When `/health` names no commit (no answer, CloudFront's 403, an unnamed release) the deploy goes
   on with a warning: an API that cannot be read is one a deploy may have to repair, and the
   commit cannot be shown older than nothing.
5. **The migrated database is read under every release before.** The probe step runs
   `release_order.sh before "$BASE_REF"`, where the base is the push's previous head on `main` and
   `main` otherwise, and loops over what it names: the commit `/health` names, then the base when
   it is another commit. When `/health` names none, only the base is read, as before.
6. **One read of `/health`.** `release_order.sh live` is the one read of the commit the API
   names, used by `descends`, `before` and the web build gate `api_ready.sh`, which read it
   inline before. Backend checks now also runs on a pull request that changes `deploy-backend.yml`,
   `.github/actions/**` or `.github/scripts/**`, since its tests read them.

## Consequences

- Between the switch and the rebuild reaching a page, the new colour serves the older copy of each
  stale stored document (a field a release adds has a default) and builds a stale snapshot on its
  first read; nothing returns 500 for a shape it does not know.
- A rollback still leaves a window: until its rebuild reaches a page (at most about 16 minutes),
  the release it went back to may refuse that page's newer body. Closing it needs every reader of
  a stored body (`page_translation_serving`, `monograph_document.stored_document`, `page_english`)
  to validate with unknown keys ignored, which protects only the releases that ship it; that
  backend change is outside this lane and left to the lead.
- Production never runs older code through Deploy backend. An older release is served only with
  `kv-blue-green rollback`, and a secret is applied by re-running the newest Deploy backend run.
  A refused run changes nothing in Parameter Store, S3 or on the box.
- When production and the base differ, shard 1 probes two releases and takes a few minutes more.
  A pull request whose migration the release production serves cannot read fails until
  production serves one that can, which is the order it must ship in anyway.
- The probe still loads rows, labels and required columns only: a dropped trigger that only
  re-marks a value, or a stored JSON body, is outside it; item 1 keeps stored bodies away from the
  release before instead.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/deploy/test_blue_green.py` (which release serves while each step runs, a stopped
release, a rollback and a time-out after the switch), `backend/tests/test_deploy_page_order.py`,
`backend/tests/deploy/test_release_order.py` (the release order against a real history, and both
workflows' calls), `backend/tests/deploy/test_web_build_gate.py` and
`backend/tests/contracts/test_watched_files.py`.
