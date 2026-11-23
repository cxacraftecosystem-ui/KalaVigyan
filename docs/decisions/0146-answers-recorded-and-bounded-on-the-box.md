# 0146. An answer is recorded whole, routed and capped by what it understood, and never crowds out a sign-in

Every answer runs under a request id and keeps its sentences, citations and streamed steps; the
nightly upkeep adds the cost that settles after it finishes; the understanding call has its own
route; a degraded answer is held to the cap of the depth it runs at; a call cut off by anything
but a provider failure is settled at its estimate; research holds at most the database pool less
two connections; daily allowances are a setting; the figure post-check reads converted
quantities and element formulas; and the stream drops the vocabulary nothing sends.

Date: 2026-11-22. Status: accepted (the lead's debt-clearing brief of 2026-11-22, research runtime
lane, after the live Khurja test of answer 504968ea-49cc-469c-88f9-205a2ea90e8a and post-deploy run
45004523731). It amends [decision 0012](0012-answer-stream-end-to-end.md) (the answer rows and the
retired events), [decision 0013](0013-review-fixes-quotes-licences-scope.md) (the figure check),
[decision 0031](0031-understanding-and-depth.md) (the understanding's route and the answer cap),
[decision 0093](0093-no-caps-for-now.md) (where daily allowances live),
[decision 0135](0135-write-backs-filed-under-the-craft-they-name.md) (an answer's cost) and
[decision 0139](0139-sources-and-providers-reach-outside-services-once.md) (the `AiTask`
re-export). The contracts are `docs/contracts/research.md` (the answer stream, the answering
service, understanding), `docs/contracts/backend.md` and `docs/contracts/frontend.md` (the AI
budget), `docs/contracts/nightly-upkeep.md` and `docs/contracts/infra.md`.

| For | Read |
|---|---|
| The answer stream whose gaps it closes | [decision 0012](0012-answer-stream-end-to-end.md) |
| The figure check it widens | [decision 0013](0013-review-fixes-quotes-licences-scope.md) |
| The understanding and the depth caps | [decision 0031](0031-understanding-and-depth.md) |
| The caps set to none for now | [decision 0093](0093-no-caps-for-now.md) |
| The cost an answer records | [decision 0135](0135-write-backs-filed-under-the-craft-they-name.md) |
| The provider layer and its routers | [decision 0139](0139-sources-and-providers-reach-outside-services-once.md) |
| The early lede that shows stored findings first | [decision 0077](0077-lede-headings-and-question-order.md) |
| An answered call settles at its cost whatever cuts its caller off | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| An answer that stops before it finishes is marked stopped and keeps its cost | [decision 0167](0167-answer-leftovers-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The debt register held twelve entries about how an answer runs on the box. While an Expert answer
researched Khurja Pottery on the one API process, the post-deploy check's sign-in took more than
60 s: the answer's seats, readers and builders held the five connections of the process's pool,
and a sign-in waited for one. The answer's row kept the cost settled when it finished, so work
that outlived it went uncounted, and an answer outside a request recorded none. The understanding
ran on the `PLAN` route, so Usage could not tell it from planning; a degraded Expert answer was
held to Expert's cap; and a call that raised anything but a provider failure left its estimate
held for the rest of the answer. Daily allowances were a code table while `QuotaPolicy` rows sat
unread, and the AI budget had no screen. The stream still listed `RESOLVING`, `match`, `section`
and `sentence` and re-exported the citation shapes; `AnswerSentence`, `AnswerCitation`,
`AnswerTrace` and `LiveCandidate` were never written; and the figure check read digits and digit
formulas only.

## Decision

1. **Research leaves two connections to short requests.** The asking routes build their answer on
   `core/db.research_sessionmaker()`: the same engine, but every session holds a slot of one
   `ResearchGate` per process sized `pool_size + max_overflow - SHORT_REQUEST_CONNECTIONS` (2, at
   least one slot). Seats, readers, builders and write-backs all open their sessions through it, so
   one answer, or two, never take the connections a sign-in or a page read needs. A task already
   holding a slot opens a nested session without a second one, so a write-back that stamps an
   embedding cannot deadlock. We chose a gate on sessions over a second pool: a second pool would
   need more pooler connections than the box's budget, and a gate on fan-out would have to know
   every place research spawns work.
2. **The release check probes sign-in beside an Expert answer.** After each backend deploy only
   (`E2E_SIGN_IN_PROBE`), the post-deploy check starts one fresh Expert answer with the E2E
   account, waits for its research to begin, signs in twice and fails when one takes more than
   10 s, then closes the answer. It spends one partly researched Expert answer per backend deploy,
   never on the hourly or pull-request runs.
3. **Every answer has a request id and its later cost.** `answer_question` and `answer_understood`
   run inside `core/logging.kept_request_id("answer")`, keeping the HTTP request's or the
   rebuild's id and opening `answer-<id>` otherwise; `Answer.requestId` stores it (migration 0071).
   The nightly upkeep sets an answer of the last seven days to its request's summed
   `UsageEvent.costUsd` where they differ (`services/upkeep_costs`). The voice turn's own `Answer`
   rows are the voice service's and record neither.
4. **The understanding is routed and reported apart.** `AiTask.UNDERSTAND` ("Understand the
   question") joins the research text tasks with `PLAN`'s default routes, and migration 0071 copies
   the stored `PLAN` routes to it, so nothing changes until an admin reorders it; `PLAN` is now
   "Plan research". The answer's `AnswerModels.understand` makes the call.
5. **The cap follows the depth the answer runs at.** `AnswerModels.follow_depth` (the answer's
   `AnswerSpend.follow`) is called with the understanding's effective depth before research, so a
   degraded Expert answer is held to Detailed's cap, on every path (asked, follow-up, rebuilt).
6. **A cut-off call is settled at its estimate.** `router.run` reserves, calls and settles in
   separate steps; anything but a provider failure (a bug, a cancellation, a timeout) settles the
   usage `CANCELLED` at its estimate, shielded, and moves the answer's hold to spent at the same
   estimate (`router.settle_abandoned`), as the media router already settled its usage. The
   provider may have billed a call we did not see finish, so the spend is counted, never lost;
   releasing the hold instead would let the answer spend past its cap on a call already paid. The
   rerank and media routers use the same function.
7. **Daily allowances are a setting.** `core/daily_allowances` reads `QuotaPolicy.perDay` through
   one loader (`None` unlimited, a role without a row unlimited, an unknown role the student's) and
   the code table is gone. Every allowance decision reads a process copy that
   `providers/quota.used_today` refreshes when older than 30 s, so the voice and media call sites
   keep their signatures. `PUT /settings/ai-budget` takes `dailyAllowances`, and the AI budget
   screen (`/admin/budget`, Master Admin only, the two-step code to save) edits every cap and
   allowance with an empty field as no cap.
8. **An answer keeps what it showed.** At its finish the answer writes one `AnswerSentence` row per
   shown sentence (the lede as section 0, each section by its order, open questions marked, a
   sentence at a level the store cannot hold left out), its `AnswerCitation` rows (a claim, claim
   source or source that is not stored left null), and one `AnswerTrace` row per `status`, `trail`
   and `paced` event the stream sent, with its milliseconds since the stream opened. `LiveCandidate`
   is dropped with `Answer.liveCandidateIds` and `AnswerCitation.liveCandidateId`: live research
   writes back what it cites (decision 0011), and a sentence citing evidence not kept is dropped, so
   no answer holds an unfiled candidate. A stored-only answer (the budget refused the
   understanding) keeps no row, as the MCP ask already says: it spends nothing and shows stored
   claims only.
9. **An answer reads and cites public passages only.** The planner's stored search reads `PUBLIC`
   chunks whoever asks, and a quoted citation's `context` is its stored passage only when that
   passage is `PUBLIC` and not restricted: an answer is kept as pieces, shared by link and read by
   others, so passing a researcher's `RESEARCHER` access through, as the register proposed, would
   leak closed text into them. [Decision 0144](0144-stored-passages-as-evidence.md), item 4, holds an
   answer's stored pack to `PUBLIC` passages for the same reason.
10. **Stored findings come first through the lede.** A section's prose is still sent whole after its
    write-back, so the claim ledger admits each sentence once; the stored-claim sentences reach the
    reader before any write-back in the early lede (decision 0077), written from stored findings
    while the sections research.
11. **The figure check reads quantities and element formulas.** `unsupported_figures` reads each
    number with a unit (`research/stated_figures.UNIT_WORDS`) and supports it by the same number
    in its cited texts, as before, or by a cited quantity of the same dimension that converts to it
    at the sentence's precision through the one Pint registry (60 °C by 140 °F, 2 km by 2000 m); a
    run of element symbols with a two-letter one (NaCl, CuO) is a formula, while capital acronyms
    (WHO, NHS) are not. Number words and a number whose unit changed stay with the composer's
    stance checks (`research/sentence_support`: `NUMBER_WORD`, `UNIT_CHANGED`), which already read
    them; repeating them here would refuse a sentence twice and hold the curated component units
    to words their facts state as digits. The local Indian units move to `research/local_units`, so
    the registry no longer reads the quote rules through `research/measures`. `figures_in` and
    `numbers_in` are unchanged.
12. **The stream says only what is sent.** `RESOLVING`, `match`, `section`, `sentence` and
    `shared/answer-stream.golden.sse` are gone; the citation shapes are imported from
    `research/citations` only; and `services/ai_providers.py` is deleted.

## Consequences

- Migration `0071_understand_and_answer_rows` adds `AiTask` `UNDERSTAND` with the `PLAN` routes
  copied, adds `Answer.requestId` with its index, and drops `LiveCandidate` and its `LiveTier` type;
  its downgrade restores them and folds `UNDERSTAND` usage back into `PLAN`. The schema tests now read
  a later migration's `drop_table` and its `ENUM_REMOVALS`.
- Usage shows the understanding on its own line from the first answer after the release.
- An answer holds three research sessions at once on a five-connection pool; more wait for a slot
  instead of the pool's 30 s timeout.
- Each answer adds one statement per sentence batch, citation batch and trace batch to its finish.
- A sentence naming an element formula its quotes do not hold is dropped, and one stating a
  quantity its quote gives in another unit is kept.
- The voice turn's `Answer` rows record no cost or request id; their file belongs to the voice
  service, which writes them.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/test_research_gate.py`,
`backend/tests/test_router_abandoned.py`, `backend/tests/test_understand_task.py`,
`backend/tests/test_answer_routes.py`, `backend/tests/answering/test_answer_records.py`,
`backend/tests/answering/test_answer_rows.py`, `backend/tests/answering/test_citation_contexts.py`,
`backend/tests/planner/test_stored_passage_acls.py`, `backend/tests/research/test_stated_figures.py`,
`backend/tests/research/test_stream.py`, `backend/tests/test_roles.py`,
`backend/tests/db/test_daily_allowances_db.py`, `backend/tests/db/test_answer_rows_db.py`,
`backend/tests/db/test_late_costs_db.py`, `backend/tests/db/test_understanding_route_db.py`,
`frontend/e2e/ai-budget-unit.spec.ts`, `frontend/e2e/answer-stream-golden-unit.spec.ts` and
`frontend/e2e/release/sign-in-probe-unit.spec.ts`.
