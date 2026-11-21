# 0012. The answer stream end to end

`POST /api/answers/stream` runs end to end through one answering service: a producer and a queue,
progress from inside research, citations read back from the database after write-back, and no
session held across a model call. Not enough evidence is its own event, and `VERIFIED` answers make
no model call.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| The review that fixed it | [0013 Quote strength, open licences, one craft scope and scoped embedding](0013-review-fixes-quotes-licences-scope.md) |
| The contracts it names | [research.md](../contracts/research.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The resolver (0004), planner (0009), composer (0010) and write-back (0011) existed, but
`POST /api/answers/stream` answered `VERIFIED` only, from stored claims, built every event in the
route and collected them before sending, so no heartbeat could be sent and nothing reached the
learner while research ran. PLAN section 0 asks for live research written back with citations,
every sentence cited, and accuracy over speed; PLAN section 12 limits deep research to
researchers and above; the stream contract (`docs/contracts/research.md`) already named the
`status` steps and the 60-second heartbeat.

## Decision

1. **One answering service, the route stays thin.** `services/answering.answer_question(ask,
   pipeline, emit)` runs resolve, then either the stored path (`VERIFIED`) or plan, research,
   compose, keep, and render (`HYBRID`, `DEEP`). Its collaborators are one `AnswerPipeline`
   (`resolve`, `research`, `compose`, `store`) so the whole flow runs in tests with fakes and the
   real ones are wired in one place (`services/answer_store.build_answer_pipeline`). The route
   checks the capability and the ask window, builds the pipeline with the asker's `Principal`
   (so the router's per-role daily cap and the monthly ceiling apply to every model call), and
   streams.
2. **Producer and queue.** `research/stream.event_stream(produce)` runs the producer as a task
   that validates each event (`event_frame`) and queues the frame; the response reads the queue
   and sends `HEARTBEAT_FRAME` whenever nothing was sent for `HEARTBEAT_SECONDS`. Closing the
   response cancels the producer. This is the one place the heartbeat lives, and events reach
   the learner as they are produced.
3. **Progress from inside research.** `ResearchPlanner.research(request, *, progress=)` reports
   `SEARCHING_STORED`, `RESEARCHING` (query count) and `READING` (evidence count, only when there
   is any). The answering service owns the user-facing words (`status_message`), so copy has
   one home and the planner stays free of it.
4. **No session across a model call or the stream.** The service opens short sessions from the
   session factory: one per resolve, one per stored search (`retrieval.hybrid.
   SessionScopedSearch`), one to keep the answer, one to read citations. The request-scoped
   session of FastAPI is not used by the stream, which runs after the route returns.
5. **Citations come from the database after write-back.** The contract's `Citation` names a
   claim and a source. Live evidence has neither until it is written back, so the service keeps
   the answer first: an `Answer` row (question, mode actually run, craft, plan, tiers), then
   `store_live_research` with that answer id, then `sentence_claim_ids` maps each composed
   sentence to its stored claims plus the claim written for it (by the write-back plan's
   per-sentence dedupe keys, `WriteBackPlan.sentence_keys`). Citations and sources are then
   read with `knowledge_view.claims_by_id`, the same builder the stored path uses. A sentence
   whose claims have no visible citation is dropped; its level is the weakest stored level of
   its claims, and a hypothesis-level sentence is an open question.
6. **Not enough evidence is its own event.** `not_enough_evidence {message}` carries
   `not_enough_evidence_message(summary)`, so the client can show an empty state (with "Research
   it live" after a `VERIFIED` question) instead of an error. `error` stays for failures.
7. **Modes and quotas.** `VERIFIED` and `HYBRID` need `ASK_STANDARD`, `DEEP` needs `ASK_DEEP`
   (`core/roles.CAPABILITY_MIN_ROLE`); a role without the capability gets 403 before any work,
   an unknown role is refused (fails closed). `/answers/config` lists the modes the asker may
   use, `HYBRID` first by default. Spend limits are the router's (per-role daily USD cap, monthly
   ceiling, degrade to `HYBRID` past 80%); a `ceiling` refusal is shown in the router's own
   words. The ask window (30 per 10 minutes) is unchanged. No new per-question count quota was
   invented: PLAN section 12 gives none.
8. **`VERIFIED` makes no model call.** It reads `VERIFIED` and `REVIEWED`, `APPROVED` claims
   (`MODE_CLAIM_LEVELS`, `MODE_CLAIM_STATUSES`) and lists them as cited sentences, so it keeps
   working when the monthly ceiling is spent. The asker's name is a withheld search term in the
   researched modes.
9. **`services` may import `composer`.** The pipeline builder constructs `ModelComposer` and
   uses `compose_request`; `composer` imports only `research`, `core` and `models`, so no cycle
   follows. Recorded in `tools/hygiene/layers.py` and the bindings.
10. **Shared fixtures for the seam.** `shared/answer-stream.research.golden.sse` and
    `shared/answer-stream.not-enough.golden.sse` are written by hand; the backend test runs the
    real flow (real composer, write-back plan, renderer and frames, fake model, store and
    research) and must produce them byte for byte, and the frontend spec parses and reduces the
    same files.

## Consequences

- A researched answer is visible only after write-back. Accuracy over speed (PLAN section 0):
  every live citation then points at a stored claim and source the learner can open later.
- A client that disconnects cancels the work, including a write-back in progress (the
  transaction rolls back). Recorded in `docs/TECH_DEBT.md`.
- `AnswerSentence`, `AnswerCitation` and `AnswerTrace` rows are not written yet; the `Answer`
  row carries the plan, tiers and cited claim ids.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
