# 0163. Nine more limits are kept by choice, the debt register may only shrink, the database tests run in shards, and each process on the box keeps to its own connection budget

Nine more limits leave the debt register for this record, four of them as curation targets and one
as a routine; the hygiene check fails any change that leaves the register with more entries than
its baseline records; the database tests run in three shards; the files over budget that this
lane owned are split with their callers' import paths kept; and every process on the box takes a
connection budget whose sum stays inside the Supabase session pooler.

Date: 2026-11-23. Status: accepted (the lead's clean-up lane brief of 2026-11-23, within the
owner's go-ahead of 2026-11-22 to clear the register "not just for this round, also for all
time"). It is the second record of the kind [decision 0137](0137-limits-kept-by-choice.md) began,
and names it; it amends none.

| For | Read |
|---|---|
| The first record of limits kept by choice | [decision 0137](0137-limits-kept-by-choice.md) |
| What is still below standard | [TECH_DEBT.md](../TECH_DEBT.md) |
| The curation targets these limits leave | [PROGRESS.md](../PROGRESS.md), Curation targets |
| The routine for the places that block filing | [RUNBOOK.md](../RUNBOOK.md), Contributions at scale |
| The rebuilt quiz block | [decision 0062](0062-phase-d-contract.md) |
| Regional measures, prices and GI fields | [decision 0066](0066-local-measures-and-market-gi.md), [decision 0147](0147-time-market-and-figures-kept-true.md) |
| The sandboxed explainer frame | [decision 0061](0061-phase-c-review-fixes.md) |
| Filing by what the source says around a fact | [decision 0136](0136-write-backs-filed-by-their-source.md) |
| The research gate the API's pool is shared with | [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) |
| The connection budget on the box | [RUNBOOK.md](../RUNBOOK.md), Connection budget |
| The third record of limits kept by choice, and the next files split | [decision 0168](0168-a-table-under-a-said-sentence-and-python-within-budget.md) |
| Every decision, by group | [README.md](README.md) |

## Context

On 2026-11-23 the lead's triage of the register found nine more entries that are choices or
curation work, not shortfalls of the code: their own text says nothing in the repository clears
them, or that only curated content or an owner's decision would. Each was read against the code
before it moved. The owner also asked that the register stay cleared for all time, which needs a
check rather than a reminder. And the database tests had grown to 37 to 39 minutes of one job, so
a 40-minute limit cancelled the steps after them and the lead raised it to 60.

## Decision

### The limits kept

Each limit stays until its condition arises; the change that meets the condition removes the
limit and marks its row superseded here.

| Limit | Why it is kept | What would change it |
|---|---|---|
| A reload or a new visit clears a reader's quiz answers and score: no route stores quiz attempts. | Decision 0062 makes a quiz a rebuilt block, and the owner has not asked for scores to be kept. | The owner wanting scores kept (for a class, with the lesson builder): then an attempts route. |
| The craft register's `description` is not shown: `PageCraft` (`backend/app/research/craft_page.py`) has no description, so a craft without a dossier or claims shows only its register facts (category, kind, GI status, states). | It is uncited register text, which the page otherwise never shows as a sentence, and the field is not in the contract. | An owner decision to show it: then `description` on `PageCraft` (model, contract, fixture), drawn beside the register facts and marked as the register's. |
| A fact quoted from a fetched web page keeps the page's researcher-only chunk access (`services/live_source_store.chunk_acl`: a T4 page declares its own licence), so it is withheld from signed-out pages and `get_facts` even once approved. | Publishing it is a licence decision, and a licence the page declares itself is not checked. | A licence decision giving a public chunk access to a quote the gates verified from an openly licensed page. |
| Chromium does not read the `webrtc 'block'` that ends `SANDBOX_CSP` (`backend/app/research/sandbox.py`): it logs "Unrecognized Content-Security-Policy directive 'webrtc'." in every generated explainer and lets a peer connection reach a STUN server, so there the client's `FRAME_GUARD` stops it (no constructor, no nested window, no nested frame; `frontend/e2e/sandbox-frame-unit.spec.ts`), and the production screens walk ignores exactly that console error from `about:srcdoc`. | Browsers that read the directive enforce it, and the guard covers the rest; the directive's support is the browsers'. | Chromium recognising the directive: then the screens walk drops its exception. |
| A `REGIONAL` measure converts only when a stored claim's quote states the factor for a region (owner O5); no seed or curated claim does yet, so only exactly defined units (inch, foot, yard, mile, square foot) convert. The path is built and tested on hand-written quotes (decision 0066), and the region may be named by any name `data/district_other_names.json` lists (decision 0147). | A regional value has to come from a source a curator verifies; inventing one would break O5. | Nothing in the code: the curation target in PROGRESS.md. |
| Ask the map lists a craft for a district only when a cited district or point location places it there; a craft the master list places by its state of practice alone is listed for no district. | Placing a state-level craft in every district of its state would be a claim no source makes. | Nothing in the code: the curation target in PROGRESS.md. |
| Without curated rows, a price is read from a cited claim of the craft only when the claim states exactly one price, one year and one LGD district (`services/market_store.stated_price_offer`, decision 0147); a claim stating two prices, a range of years or two places shows none. | Choosing among several dates or places in one sentence would be a guess. | Nothing in the code: the curation target in PROGRESS.md. |
| Without a curated `market.gi` record, the GI registry fields come from labelled words in GI journal and government claims ("application 183", "Certificate Date 11-05-2011", "Journal Number 37"); a claim phrased otherwise adds nothing, and two claims stating different values give no status. | The registry offers no open API, and a curated record replaces the reading. | Nothing in the code: the curation target in PROGRESS.md. |
| The places that hold or refuse a write-back are word lists: the regions, cultures, other senses and left-out names abroad in `data/places_abroad.json` (its countries held to Natural Earth's sovereign states by a test), and for India the LGD state and district names and the craft index's place labels. Since decision 0136 they are read in a quote's passage and its source's title too, so a district named like a common word can hold a general fact, and a region abroad missing from the list lets one through. | No open gazetteer of regions and cultures is vendored, and a model judging each sentence's places would cost a call per sentence. | Kept true by the routine after each round of live research (RUNBOOK); changed by an open gazetteer of regions and cultures that can be vendored. |

### The register may only shrink

`tools/hygiene_check.py` counts the entries of `docs/TECH_DEBT.md` (its `### ` headings outside
fenced blocks, `tools/hygiene/register.py`) and keeps the count as `registerEntries` in
`tools/hygiene_baseline.json`, whose schema became version 2. A rise fails the check; a fall
passes and says that `--update-baseline` lowers the baseline, which never raises it. The budget
counts stay as they were: each must equal its baseline.

The other choices were the budgets' rule (a fall fails until recorded) and no check. Under the
budgets' rule every lane that clears an entry would rewrite the baseline, and with many lanes
clearing entries in one round every merge after the first would conflict on that line; with no
check, nothing but memory would keep the register from growing again. A change that must add an
entry clears another in the
same change; when none can be cleared, its own decision record says why and raises the recorded
count by hand there, where review sees it.

### The database tests run in three shards

Backend checks runs the migrations and database tests as three jobs, each with its own Postgres
that it migrates and seeds, under a 40-minute limit. `backend/tests/db/conftest.py` reads
`DB_TEST_SHARD=<index>/<total>` and keeps every third test of the collection, starting at its
index (`backend/tests/db/shards.py`), so every shard deals the same collection the same way. The
time sits in a few files whose tests rebuild craft pages or import dossiers at 20 to 40 seconds
each: the first run, which dealt whole files by their test count, took 19, 10 and 7 minutes.
Dealing tests one by one spreads each slow file over every shard with no weights to keep; whole
files by measured seconds would need a weights file that goes stale. A database test therefore
may not lean on another having run first, as the house rules already ask. Every shard seeds,
because the tests read the seeded crafts, claims and districts; the migration round trip, the
dossier import and the release-before check run in the first.

### Files split with their import paths kept

The AI router's records and rules (`providers/route_choice`), its database reads and writes
(`providers/route_store`) and one planned call (`providers/route_call`) left `providers/router`,
which keeps `run`, `reserve` and `settle_abandoned` and re-exports the rest: about ninety modules
and tests import from it, several in other lanes' areas, and the tests replace `load_routes`, `current_spend`,
`settle` and `build_adapter` on it, so the code that calls those names stays where the replacement
is seen. The sign-in routes' shared helpers moved to `api/auth_session`, and their few callers,
none in another lane's area, import them from there.

### Each process on the box keeps to its own connection budget

At 04:36 UTC on 2026-11-23, on release 1ab422fe, the session pooler refused new sessions
(`EMAXCONNSESSION`, 30 clients) while 29 idle sessions had been held for up to 11 minutes, and
4 of 10 public field-voice picture reads that second were refused as uncounted allowances. Every
process read `DATABASE_CONNECTION_LIMIT=12` as a pool it kept, with no overflow, and each also
built two counting engines of 2 kept and 6 overflow (the allowances' and the source paces'):
about a hundred possible sessions against thirty.

Each process now names its role, and the role's budget in `core/connection_budget.BUDGETS` sizes
both of its pools: a main pool that keeps one or two connections and opens the rest only for a
burst, closing them when they are returned, and one counting pool that the allowances and the
paces share. The role is the `KV_PROCESS` every unit already set; a process on the box that
names none, which is how the deploy and SSM run scripts, takes the script budget; off the box an
unnamed process keeps its settings, so tests and laptops are unchanged. The other way, a pool
size in each unit's `Environment=` lines, would leave scripts on the shared `.env`'s figure and
the counting pools unsized. The counting pool stays apart from the main pool because a count
that waits behind long research sessions refuses a reader; sharing one of the two counting
engines was safe, as both run one short statement in their own transaction.

The budgets add up as the lead asked: both API slots of a deploy, the queue, the worker and one
script, at most 26 of the pooler's 30, which leaves 4 for a person's `psql` or the dashboard.
`backend/tests/test_connection_budget.py` reads the units and fails when a unit or a limit would
pass that. The deploy stops the queue and the worker before the slots overlap, so the sum is
above any real peak. The contribution queue runs two gate runs at once, as many as its four main
connections carry at two each (its session and a router call's), and a larger
`CONTRIBUTION_WORKERS` runs only that many, with a warning. An API slot's research gate holds 3 of
its 5 main connections, where it held 10 of 12, and the answer evaluation now builds its answers
through the research gate as the API does, so its parallel sections wait for a slot instead of
for a connection of the script's three.

A connect the pooler refuses for want of room is tried again after 0.2, 0.5 and 1 s
(`core/pooler.connected_session`) by the allowance and pace counts, inside their 5-second limit;
any other failure, and the last refusal, still refuse the call. The lasting cure is the owner's to
give: Small compute holds 90 connections, and raising the pooler in the dashboard lets one change
raise `POOLER_SESSIONS` and the budgets together.

## Consequences

- The debt register holds only work that is open or blocked on something outside the repository,
  and the hygiene check keeps its count from rising.
- The lead lowers the recorded count after a round's merges with `--update-baseline`.
- The slowest database tests show in each shard's `--durations=20` list; when the shards near
  their limit, the number of shards grows.
- A change that meets a row's condition removes the limit and marks the row superseded here.
- A new unit on the box names its `KV_PROCESS` and a budget, or the connection budget test fails;
  two long scripts run one after another.

## How this record is kept true

It is not edited after acceptance except to mark a row superseded: a later choice is a new record
that names this one. It records the choices as taken on 2026-11-23; what the code does today is in
[ARCHITECTURE.md](../ARCHITECTURE.md), the [contracts](../contracts/README.md) and the hygiene
check's own tests (`tools/tests/test_register.py`, `test_check.py`, `test_baseline.py`).

## Later

On 2026-11-23 the owner raised the session pooler from 30 to 45 sessions (Small compute's Postgres allows 90; this project holds only KalaVigyan's database and Supabase's own services). `POOLER_SESSIONS` became 45 and the headroom 5; an API slot may open 10 main connections (8 research slots, against 3 under this record and 10 before it), the contribution queue 8 (4 gate runs at once again), and the busiest box sums to 40.
