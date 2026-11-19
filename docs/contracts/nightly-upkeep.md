# Nightly upkeep and the nightly static build (decision 0101, items 5 and 11)

Every night the database looks after what it already holds, then the web app is rebuilt from it:
quotes are re-verified against their sources, live open sources are archived before their links
rot, orphaned research concepts are swept, MCP client registrations that never signed anyone in are
removed, the monograph sections and components and the craft
page snapshots whose facts moved are rebuilt, and one production build pre-renders the craft pages
from those snapshots onto the CDN. Answers stay live. Every step is bounded per night by a named
constant, so a night's work and its load on other sites are known in advance.

Last reviewed: 2026-11-20.

## Schedule

| What | Where | When |
|---|---|---|
| The upkeep and the build trigger | `.github/workflows/nightly-upkeep.yml` (GitHub Actions, run on the box through SSM like Coverage enrichment) | 23:45 UTC every day (05:15 IST), after Coverage enrichment (22:17 UTC, at most 67 minutes) |
| The same run by hand | the workflow's Run workflow button, with `dry_run` to report only | any time |
| The build alone | an Admin's Start a build on the admin settings page (`/admin`), or `POST /api/site/build` | any time, at most once in 10 minutes |

The workflow runs `python -m app.scripts.nightly_upkeep` as the `kalavigyan` user with the box's
`.env`; the job fails when the report's `ok` is false, and the report is printed in the run's log.

## The steps, in order, and their bounds

| Step | Module | Bound (constant) | Records |
|---|---|---|---|
| 1. Re-verify quotes | `services/upkeep_quotes.py` | `QUOTE_SOURCES_PER_NIGHT` = 50 sources; a source is due again after `QUOTE_RECHECK_AFTER` = 30 days | `ClaimSource.quoteCheck` (`PASS`/`FAIL`) and `checkedAt`; `SourceUpkeep` (outcome, failures, problem) |
| 2. Archive sources at risk | `services/upkeep_archive.py`, adapter `sources/wayback_save.py` | `ARCHIVES_PER_NIGHT` = 10; a failed save is retried after `ARCHIVE_RETRY_AFTER` = 30 days | `SourceUpkeep.archiveUrl`, `archivedAt`, `archiveTriedAt` |
| 3. Sweep orphaned concepts | `services/orphan_concepts.py` | `ORPHANS_PER_NIGHT` = 500; a concept stands at least `ORPHAN_MIN_AGE` = 7 days | `AuditLog` action `upkeep.orphans_reported` with the ids reported |
| 3a. Remove abandoned MCP client registrations | `services/upkeep_clients.py` | `ABANDONED_CLIENTS_PER_NIGHT` = 1,000, oldest first; a client is abandoned `ABANDONED_CLIENT_AGE` = 30 days after registering | the `OAuthClient` rows deleted (their unexchanged codes go with them) |
| 4. Reload monographs | `services/upkeep_pages.py` through `services/monograph_load.py` | `MONOGRAPHS_PER_NIGHT` = 20, a window that rotates by night | `ArticleSection`, `KnowledgePiece` (only what changed) |
| 5. Rebuild stale craft pages | `services/upkeep_pages.py` through `services/craft_page_snapshots.py` | `PAGES_PER_NIGHT` = 60, oldest snapshot first | `CraftPageSnapshot` |
| 5a. Refresh the field work | `services/open_work_refresh.py` | every subject, once | `TaskReservation.ending` `COMPLETED` for a live reservation of a `MISSING_FIELD` or `THIN_FIELD` task no longer open (`open-work.md`) |
| 6. Trigger the site build | `services/site_build.py` | one deploy-hook call | `AuditLog` action `site_build.triggered` |

The orchestration is `services/nightly_upkeep.py` (`run_nightly_upkeep`, and the read-only
`plan_nightly_upkeep` behind `--dry-run`).

### 1. Quotes

- **Which sources:** every source with an `https://` address cited by at least one claim, never
  checked first, then the longest unchecked; a source checked within 30 days waits.
- **How:** the page is fetched through the fetcher (`sources/fetcher_client.py`, the same limits
  as live research) and each stored quote is looked for in its text with the curation matcher
  (`curation/matching.py`, built on `research/quotes.py`): case, typographic dashes and quotes,
  soft hyphens and line breaks are folded.
- **Verdicts:** found is `PASS`; not found in a complete text is `FAIL`; not found in a text the
  fetcher cut short (`truncated`) is left as it was. Both set `checkedAt`.
- **A fetch that fails** changes no quote. A refusal (robots, content type, size, an address the
  fetcher will not read) records `REFUSED` and its reason; a failure (gone, unreachable, rate
  limited) records `FAILED` with its kind and status and adds one to `failures`, which returns to
  0 at the next good fetch. `failures` is the link-rot signal.
- **A night when the fetcher itself is away** blames no source: when every one of at least
  `FETCHER_OUTAGE_MIN` = 3 due sources failed as unreachable with no HTTP status, nothing is
  recorded, the report says `fetcherUnavailable`, and the run is not `ok`. The night's results are
  written together at the end of the step.

### 2. Archives

- **At risk:** an `OPEN` source (sensitivity), with an `https://` address that is not already a
  Wayback address, no DOI (a DOI is a persistent identifier), no archived copy (neither
  `Source.externalIds.archivedUrl` from curation nor `SourceUpkeep.archiveUrl`), whose last fetch
  succeeded (only a live page is worth saving). Most recently seen alive first.
- **How:** `GET https://web.archive.org/save/<url>` (the Save Page Now endpoint, anonymous); the
  snapshot is the redirect's `Location` or the `Content-Location`, and is kept only when it
  matches the curation Wayback pattern (`curation/parts.WAYBACK_SNAPSHOT_PATTERN`).
- A source whose sensitivity is not `OPEN` (`ATTRIBUTE_REQUIRED`, `RESTRICTED`) is never sent to a
  public archive.

### 3. Orphaned concepts

A concept is an orphan when all of these hold:

- it was written by live research (`originRef` is `live_research`); curated concepts
  (`curation:...`), seeded ones and any other origin are never removed;
- it is at least 7 days old;
- no claim is about it (`Claim.subjectType = 'CONCEPT'`), no concept edge starts or ends at it,
  and no process stage, material, registered component (`KnowledgePieceSubject`) or glossary term
  (`TermConcept`) links to it.

Report first, then delete: a night lists every orphan it finds and records the new ones in the
audit log; the next night removes only those an earlier night reported that are orphans still.
The delete re-checks the rule in the same statement, so a concept linked in between is kept.
Artisan testimony concepts keep their own removal (`services/testimony_claims.drop_orphans`).

### 3a. Abandoned client registrations

An MCP client registered more than 30 days ago that never completed a sign-in (no `OAuthGrant`, so
no token) is deleted; the delete re-checks the rule in the same statement, so a client that connects
in between is kept. A client with a connection, even an expired or revoked one, stays: Settings and
the audit still name it (`mcp-oauth.md`).

### 4 and 5. Pages

- Monographs (today Kutch Ajrakh, `scripts/build_monograph.SERVED_FOLDERS`) are reloaded from
  their content; `load_monograph` writes a new section version only for a field whose sentences
  changed and rewrites only components whose content hash changed. Their static HTML is built
  from git (`build_monograph`), not here.
- Every other curated or snapshotted craft is stale when a variant has no snapshot, an older
  schema or a stamp other than the current one (`craft_page_stamp.page_stamp`, which moves with
  the craft's facts, pictures, places and the release). The oldest stale pages are rebuilt.

### 6. The build

One `POST` to the Vercel deploy hook starts a production build of `main`. The build pre-renders
`/crafts/{slug}` for every slug of `GET /api/site/pages` (except the static monograph) and keeps
each page for a day (`revalidate = 86400`); any other craft renders on its first visit and is kept
the same way. Signed-in readers still load their own variant in the browser, and answers are
never cached. A change that must reach readers who are not signed in before the next night (a
hidden piece, a retracted claim) is published by an Admin's Start a build. The admin control refuses a second build within 10 minutes (429 with
`Retry-After`); the nightly run always triggers.

## Routes

| Method | Path | Who | Answer |
|---|---|---|---|
| GET | `/api/site/pages` | anyone (public reading limits) | `StaticPages {schemaVersion 1, crafts[slug], categories[slug]}`: crafts with an `OPEN` snapshot by slug, categories in master order; golden `shared/site.pages.golden.json` |
| GET | `/api/site/build` | Admin, Master Admin | `SiteBuildState {configured, lastTriggeredAt, nextAllowedAt}` |
| POST | `/api/site/build` | Admin, Master Admin | 202 `SiteBuildState`; 503 when the hook is not set, 429 within 10 minutes of the last build, 502 when the hook refuses |

The web client parses both shapes with `frontend/lib/sitePagesContract.ts` (spec
`frontend/e2e/site-pages-unit.spec.ts`); the control is `components/admin/SiteBuildCard.tsx`.

## The report

`python -m app.scripts.nightly_upkeep` prints one JSON object and exits 1 when `ok` is false:

```
{ok, quotes {sourcesChecked, fetched, refused, unreachable, quotesPassed, quotesFailed, quotesUndecided,
         fetcherUnavailable},
 archive {archived, archiveFailed},
 orphans {orphansFound, orphansRemoved, orphansReported, orphans[{id, name, type, craftId}]},
 clients {abandonedRemoved},
 pages {monographs[load report], pagesStale, pagesRebuilt, pagesChanged, pagesFailed[]},
 fieldWork {subjects, tasks {MISSING_FIELD, THIN_FIELD}, priorities {HIGH, MEDIUM, LOW}, reservationsClosed},
 build {ok, triggered, reason?}}
```

`ok` is false when a monograph or page failed to rebuild, the fetcher was away or the deploy hook
refused; an unreachable source or a failed archive is expected and only counted. An unset deploy
hook is
reported (`triggered: false`) and is not a failure. `--dry-run` prints `{ok, dryRun, sourcesDue,
sourcesAtRisk, monographs, pagesStale, clientsAbandoned, orphans[]}` and writes nothing.

## What the owner sets

| Name | Where | What |
|---|---|---|
| `VERCEL_DEPLOY_HOOK_URL` | Parameter Store `/kalavigyan/env/VERCEL_DEPLOY_HOOK_URL` (SecureString) | a deploy hook of the Vercel project `kalavigyan` for branch `main` (Vercel, Settings, Git, Deploy Hooks). The address is the secret: it is never printed, logged or returned, and the HTTP client's request log is filtered while it is called |

Then `sudo kv-render-env && sudo kv-blue-green restart` on the box (the nightly job reads the
`.env` at each run; the API reads it at start). Until it is set the upkeep still runs and reports
the build as not triggered, and the admin control says so.

## Commands an operator runs

| Purpose | Command |
|---|---|
| See what tonight would do (writes nothing) | `gh workflow run nightly-upkeep.yml -f dry_run=true`, or on the box `cd /opt/kalavigyan/current/backend && sudo runuser -u kalavigyan -- bash -c "set -a; . /opt/kalavigyan/.env; set +a; exec ./.venv/bin/python -m app.scripts.nightly_upkeep --dry-run"` |
| Run the upkeep now, with the build | `gh workflow run nightly-upkeep.yml` |
| Run the upkeep on the box without the build | the box command above with `--no-build` in place of `--dry-run` |
| Start only the build | Start a build on `/admin` (Admin), or `POST /api/site/build` with an Admin's token |

## Not covered yet

- The web app has no category or family page route today (the API serves them, decision 0078;
  craft pages link to `/categories/<slug>`). `GET /api/site/pages` already lists the categories so
  the route, when it is built, pre-renders from the same list with the same day-long revalidate.
- Coverage gaps turned into research tasks (item 5's third point) belong to open work
  (`list_open_work`), not to this job.
