# 0040. No connection held across a model call

No caller holds a pooled database connection while it waits on a model or an embedding call, after
the first production run of phase A exhausted the pool. A test records each session's queries and
commits to keep it so.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contracts it names | [backend.md](../contracts/backend.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The first production run of phase A (E2E run 43993673874) failed both known-answer questions with
"Something went wrong while answering". The server log shows `QueuePool limit of size 5
overflow 0 reached, connection timed out, timeout 30.00` from `router.load_routes`, reached from
`StoredKnowledgeSearch.search` inside a section's coverage check. Answers now run up to four
sections at once (decision 0032). Each section's stored search ran its first query, which checks a
connection out of the pool, and then embedded the question through the router, which needs a
second connection. Four sections, plus the answer's own work, held all five connections while each
waited for one more, so every section timed out together and `/api/answers/config` waited 25 s
behind them. Writing back a section's research (`indexing._fill`) and the craft resolver's
semantic step had the same shape.

`DATABASE_CONNECTION_LIMIT` stays 5 with no overflow: both API colours and the box scripts share
the Supabase session pooler, so a larger pool would trade this failure for the pooler's own limit.

## Decision

1. A caller never holds a pooled connection while it waits on the router. `app.core.db.
   release_connection(session)` commits a read-only session, which returns its connection; the
   session checks one out again on its next query.
2. `StoredKnowledgeSearch.search` embeds the question before its first query.
3. `indexing._fill` releases the connection before each embedding call, so writing back research,
   storing knowledge pieces and the nightly embedding job hold none while embedding.
4. `DatabaseCraftResolver._semantic` releases the connection before it embeds the question.
5. `tests/retrieval/test_connection_release.py` records each session's queries, commits and
   embedding calls and fails if an embedding call comes while a connection is held; all three
   failed before this change.
6. Every production E2E action is bounded at 30 s (`actionTimeout`). The craft tab click and the
   menu button click, which the screen check opens on every page, record why a click is refused (the
   page not answering a script, the tab moving, or what covers its centre, and Playwright's call
   log). Every screen step is bounded at 120 s. When a step overruns and the page no longer runs
   a script, the run pauses it through the Chrome debugger it attached at the start and records
   the stuck call frames with the code around each, or says the main thread is stuck outside
   script; the remaining screens of that width are skipped and the report is still written (plan
   finding 8a.3). `e2e/stuck-page-unit.spec.ts` spins a page forever and checks the stack names
   the spinning function. The debugger's `Debugger.pause` is sent without waiting for its reply,
   which only comes once the page resumes.

## Consequences

- The rule is in `docs/contracts/backend.md` under the AI router.
- `fill_descriptor_embeddings`, run only by the nightly script with nothing in parallel, still
  holds its connection while embedding.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
