# 0170. An Admin's AI stages review decisions a person confirms, and an Admin refreshes changed pages now

An Admin or Master Admin signed in through their AI client with a `review` scope reads the review
queue and admin reports and stages decisions and source corrections; nothing is applied until a
person confirms the batch on the Review page in one click. An Admin refreshes the pages that changed
now, from the settings hub or over MCP, one job at a time with the night.

Date: 2026-11-23. Status: accepted (owner, 2026-11-23, the MCP review and page refresh lane; the
owner chose that the AI's decisions are staged and that nothing reaches readers until a person
confirms; the lead added the admin reports and staged source corrections the same day). It amends
[decision 0101](0101-knowledge-architecture-for-every-craft.md), item 15 (who holds `review`);
[decision 0111](0111-fewer-mcp-tools.md) (a seventh tool group, listed only with `review`); and
[decision 0119](0119-nightly-refresh-of-changed-pages.md) (the night is no longer the only refresh
and shares one lock with an Admin's). The contracts are `docs/contracts/mcp-oauth.md` (Scopes and
roles; Tokens), `docs/contracts/review-queue.md` (Staged over MCP), `docs/contracts/nightly-upkeep.md`
(Refresh pages now) and `docs/contracts/knowledge-api.md` (the tool table; Small schemas; Admin
reports).

| For | Read |
|---|---|
| Who held `review` before, and the scopes it amends | [decision 0101](0101-knowledge-architecture-for-every-craft.md), item 15 |
| The tool groups and the list's budget | [decision 0111](0111-fewer-mcp-tools.md) and [decision 0159](0159-places-kept-reviews-filed-and-mcp-kept-small.md) |
| The night's refresh of changed pages | [decision 0119](0119-nightly-refresh-of-changed-pages.md) |
| The client and audit of each MCP call | [decision 0150](0150-mcp-activity-and-box-logs.md) |
| How the web reads a field or kind it does not know | [decision 0151](0151-a-release-the-live-side-can-read.md) and [decision 0167](0167-answer-leftovers-kept-true.md) |
| The queue's kinds and decisions | [decision 0159](0159-places-kept-reviews-filed-and-mcp-kept-small.md) and [decision 0169](0169-mcp-follow-ups-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Admins review on the site, one card at a time, while an AI client could read the queue's quotes,
re-read its sources with `read_source` and propose decisions faster. An AI that applies decisions
itself would let any instruction hidden in a contributed statement or a quoted page act on the
knowledge, so the owner chose staging. The `review` scope already existed (Professor and above) but
only showed review tasks in `list_open_work`. Publishing also waited for the night: the night
rebuilds stale snapshots and stored documents and refreshes the changed pages (decision 0119), and
the only manual control, Start a build, rebuilds the whole site through the Vercel hook. The
contributors' `tools/list` held 61,316 of its 61,440 bytes of input.

## Decision

1. **`review` is an Admin's, given fresh.** A token holds `review` only while its account has
   `REVIEW_CONTRIBUTIONS` (Admin, Master Admin) and two-step verification on
   (`oauth_rules.may_hold`, read on every call); a person gives it only when their session also
   proved them within the last 15 minutes, read from the session token's `iat`, which a sign-in, a
   password change and a two-step change set (`Grantor.may_grant`). Fifteen minutes is long enough to
   sign in and then add the server in an AI client, and short enough that a session left open on a
   shared machine cannot give it. A Professor's connection keeps its other scopes and no longer
   holds `review`; Professors review on the site as before. A password, two-step or role change, a
   suspension or Sign out everywhere ends the whole connection, `review` with it, and Connected apps
   then no longer lists it; a listed connection shows the scopes its next token holds.
2. **Review tokens are short.** An access token holding `review` lives 15 minutes, not an hour, and
   `review` ends 8 hours after the consent (a working day): a refresh after that leaves it out and
   the connection goes on with its other scopes (`live_scopes`, `access_token_seconds`).
3. **Four admin tools, listed only with `review`.** `review_queue`, `stage_reviews`, `refresh_pages`
   and `admin_reports` form the `admin` group; `tools/list` leaves them out for a token without
   `review` (`mcp_tool_base.listed_to`), so the contributors' list stays 22 tools and 61,316 bytes of
   input. An Admin's list has its own budget, 26 tools and 68 KB of input (66,576 bytes and 74,893 in
   all when measured). Each tool also checks the account's role itself. One read tool lists and opens
   items (an `open` argument, as `get_page` takes `parts`) rather than two; a source is re-read with
   the contributors' `read_source`, not a copy.
4. **The server never applies what an AI proposes.** `stage_reviews` takes 1 to 20 decisions, each
   the item's kind and id, an action the Review page allows (with re-filing under a craft or a
   family's science) and a reason of at least 12 characters, and stores them as a staged batch
   (`StagedReview`, `StagedReviewItem`: who, which connection, token and client name as
   `McpToolCall` keeps them, when, each decision and a label), changing nothing else. Each decision
   is checked by running the Review page's own decision service for that account inside a savepoint
   that is rolled back (`staged_review_apply.dry_run`), so the rules are the same code
   (`fact_move_problem`, one's own item, the kind's actions, re-filing), not a copy that could drift.
   A refused decision says why; the call stages the rest. The tool's description and reply say that
   nothing is published until a person confirms. A prompt injection can therefore at most place a
   decision, with its reason and the client that proposed it, in front of an Admin.
5. **Confirmation is one click by a person.** The Review page lists the open batches ("Proposed
   through <client> by <admin>"); an Admin unticks, changes an action, reason, filing or source
   field, and confirms the selected items in one request. Each is checked again and applied through
   the same decision services the web's routes use, in its own savepoint, so one refused item leaves
   the others applied; each applied item keeps its decision's own audit with the confirming person
   as actor, and `review.staged_applied` names the batch, the client and the proposer. Any Admin
   may confirm, the proposer included: the click is the person's act.
6. **What stays on the site.** Testimony and contributed pictures are not offered over MCP: they
   hold people's own voices, words and pictures, whose consent covers KalaVigyan's reviewers and not
   a third party's model.
7. **Bounds.** At most 100 staged items per Admin per India day (five full calls): more than a day's
   careful confirming, and a runaway client stops there. A batch expires three days after it was
   staged, long enough for a weekend, short enough that a queue item has not moved underneath it.
8. **Source corrections are staged the same way.** `SOURCES` corrects a source's title, authors,
   year, journal (`containerTitle`) or kind, a title only when it is a work's title and an author
   never a file's producer; `SOURCES_DIFFER` clears a fact's sources-differ mark. Confirmed, they
   audit as `source.retitled` (the action `scripts/retitle_sources` already writes), `source.corrected`
   and `review.sources_differ_cleared`, and refresh the pages citing them.
9. **Admin reports are read where they are kept.** `admin_reports` reads, a page at a time and
   capped, coverage and the night's hidden facts per craft, the write-back filing report, the junk
   titles and producer authors, MCP activity (without the per-connection rows that name accounts),
   settled AI spend by day and task, and the evaluation floors, through the services the routes and
   scripts already use. No stored evaluation run exists for the server to read: the workflows print
   to SSM and upload artifacts, so the report gives the floors with `measured: null`. Keys, routes,
   roles, settings, Zenodo, deletions and anything that spends money stay out of MCP.
10. **Refresh pages now builds on the night's steps.** Refresh pages now on the settings hub and
    `refresh_pages` over MCP start one background job in the API process (`ShieldedWork.start`) that
    rebuilds the stale snapshots and stored documents within the night's bounds (60 pages, 200
    documents) and 8 minutes, then refreshes the changed pages through `/api/revalidate`, as the
    night and every decision already do; it adds no parallel path and starts no Vercel build.
    `PageRefreshJob` is the lock: a partial unique index allows one running job, and the night takes
    the same lock for its page steps or, while an Admin's job runs, leaves them to it. A job still
    running 15 minutes after it began (90 for the night's) is taken as stopped. The cooldown is 10
    minutes after the last Admin-started refresh, as for a build; the Master Admin's every page
    (every stale page and document without bounds, then every page the site lists) is once a day,
    after a confirmation on the web, and not offered over MCP. Confirming a batch starts a refresh of
    exactly the pages its items touched, or, while another job runs, sends them to the site at once.
    The worker process was the alternative home, but its layer may not import the services.
11. **No model is called by a refresh.** A snapshot is built from stored rows, a stored document from
    published sections, and a refresh is an HTTP call to the web: the model cost per page is nothing.
    Each refreshed page is rendered again on Vercel at its next visit, which is why the default
    refreshes only what changed.

## Consequences

- Migration `0093_staged_reviews_refreshes` adds `StagedReview`, `StagedReviewItem` and
  `PageRefreshJob`, row-level security on and no grants to `anon` or `authenticated`; its parent is
  round 7's head `0092_readings_layers_categories`.
- A Professor who connected with `review` before this release loses only the review tasks of
  `list_open_work` over MCP.
- A refresh runs in an API process: a restart stops it, and the next start, 15 minutes later, marks
  it failed; the night rebuilds whatever it left.
- The evaluation report reads floors only until the evaluation workflows store their runs where the
  server can read them; the lead decides whether they should.
- The web shapes of the two new payloads ship with them (`lib/stagedReviewContract.ts`,
  `lib/sitePagesContract.ts`); the production build leaves out a staged item of a kind it does not
  know, as the Review page does (decision 0167).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in the contracts named above. Its rules are tested by
`backend/tests/mcp/test_oauth_rules.py`, `backend/tests/db/test_review_scope_db.py`,
`backend/tests/mcp/test_tool_budget.py`, `backend/tests/mcp/test_review_tools.py`,
`backend/tests/mcp/test_staged_contract.py`, `backend/tests/db/test_staged_reviews_db.py`,
`backend/tests/db/test_page_refresh_db.py`, `backend/tests/mcp/test_admin_reports.py`,
`backend/tests/db/test_admin_reports_db.py` and the web's unit specs of the staged batches and the
refresh card.
