# 0119. The night refreshes only the pages that changed

The nightly upkeep no longer starts a production build of the site. After rebuilding stale page
snapshots and stored documents, it asks the web to refresh exactly the pages whose content moved,
and a night that changed nothing sends nothing.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21, on Vercel's usage: "the daily rebuild only
happens for stale pages, right? No cost for the existing pages, right?"). The contract is
`docs/contracts/nightly-upkeep.md`, step 6.

| For | Read |
|---|---|
| The contract it changes | [nightly-upkeep.md](../contracts/nightly-upkeep.md) |
| How pages are refreshed when a fact moves | [knowledge-writes.md](../contracts/knowledge-writes.md), Pages follow their facts |
| Every decision, by group | [README.md](README.md) |

## Context

The nightly upkeep rebuilt only stale snapshots, at most 60 a night, and since polish B only stale
stored documents. It then called the Vercel deploy hook every night, whatever it had found. A
production build makes a new deployment, and a new deployment starts with an empty page cache. So
every craft page that is rendered on demand (all but the few the build pre-renders) was rendered
again on its first visit the next day, whether or not anything on it had changed. That cost function
time, cache writes and origin transfer for every page every day, on a plan whose limits the round's
own test traffic was already pressing. Pages already refresh as their facts are written (the
revalidation route), and a release builds the site anyway.

## Decision

1. **No nightly build.** `app.scripts.nightly_upkeep` never calls the deploy hook. Releases and an
   Admin's Start a build are the only builds.
2. **The changed pages are collected.** `PagesReport.changed_owners()` names the crafts whose
   monograph sections or components were written (step 4), the crafts whose snapshot changed
   (step 5), and the subject of every stored document rebuilt as changed or removed.
3. **Only those are refreshed.** `page_revalidation.nightly_refresh` sends them through the existing
   `/api/revalidate` route in batches of at most 40 targets. Nothing is sent when nothing changed.
   An unset `WEB_REVALIDATE_SECRET` is reported and is not a failure; a refused batch makes the
   night's `ok` false and names its pages.
4. **The flag follows the step.** `--no-build` became `--no-refresh`, and the report's `build` entry
   became `refresh {ok, pages, refreshed, unrefreshed[], reason?}`.

## Consequences

- An unchanged page is never re-rendered by the night. It is re-rendered when its facts change, when
  its day-long cache expires on a visit, or when a release ships.
- A page whose snapshot waits beyond the night's bound of 60 is refreshed on the night it is rebuilt,
  as before.
- `site_build.nightly_site_build` and its test are gone. `trigger_site_build`, the admin route and its
  throttle are unchanged.
- With every change now reaching its page on the night it is rebuilt, the craft pages' time-based
  window (`revalidate = 86400`) is only a backstop and can be lengthened in a later change.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/upkeep/test_page_rebuilds.py`
and `backend/tests/test_page_batches.py`.
