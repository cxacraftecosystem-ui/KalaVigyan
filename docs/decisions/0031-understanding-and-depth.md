# 0031. Understanding the question, and depth by role

One understanding step works out the craft or crafts from the question and never blocks: a wrong
guess is one tap to change, and a model failure is not the question's failure. Depth by role
replaces the reader's mode choice, with caps per depth and one home for the spend refusal.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| What superseded part of it | [0093 No caps for now: every AI cap defaults to none, and every call asks for its model's documented maximum output](0093-no-caps-for-now.md): its cap values; the code paths stand |
| The contract it was built to | [0030 The explainer contract](0030-explainer-contract.md) |
| The review that fixed it | [0038 Phase A review fixes](0038-phase-a-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

`docs/plans/answer-experience.md` (owner-approved, section 8 final) makes a craft optional: the
app works out the craft or crafts from the question and proceeds, a wrong guess is one tap to
change, and an answer can be for any craft (sections 1, 2.3 step 1). Depth replaces the reader's
choice of mode: Basic for students, Detailed for researchers and professors, Expert for admins and
master admins, anyone may switch (section 2.4). Owner decision O3 and the owner's rule of
2026-11-17 remove every cap from Master Admins and give everyone else a per-answer cap per depth
in the AI budget. Decision 0030 fixed the `understood` event, the depth table and
`UNCAPPED_ROLES` as data; this lane builds the step, the route, the caps and the any-craft path.
Before it, an ambiguous question stopped with pills, an unknown craft stopped with an error,
`DEEP` needed `ASK_DEEP`, and the monthly ceiling refused and degraded every role alike.

## Decision

1. **One understanding step, on the PLAN route.** `planner/understanding.ModelUnderstander` runs
   the craft resolver, then one structured call on the existing `PLAN` route (Gemini Flash Lite
   first, labelled "Plan and craft choice" since the first migration), so no task, enum value or
   route is added and the Settings hub already governs it. The reply names the listed craft the
   question is about (an enum of the resolver's slugs, or empty), crafts the question names that
   are not listed (at most three), the fields it touches (the `DISCIPLINES` vocabulary, which is
   also a section's discipline and a piece's facet) and the experts to seat (`EXPERT_SEATS`). The
   question and every listed craft reach the model only inside untrusted blocks. The schema uses
   only `type`, `enum`, `items`, `properties`, `required` and `additionalProperties: false`, so
   every route's structured output accepts it (finding 8a.1); counts are enforced on our side.
2. **Never blocking.** A slug the reader chose is kept (an unknown slug is still "No craft has that
   address"). `anyCraft` answers for any craft and keeps the detected crafts as offers. A clear
   winner stands whatever the model says. An ambiguous question proceeds with the model's pick
   among the candidates, else the best match, and offers the rest. A question naming no known
   craft resolves each name the model gives through the same resolver: a clear winner is chosen,
   other matches are offered, and nothing found means any craft. A model never adds a craft that
   is not a `Craft` row.
3. **The model failing is not the question failing.** An unusable reply or a failed call leaves
   the resolver's understanding (`basis: RESOLVER`, no fields or seats, logged). A spend refusal
   keeps the router's own words (`refusal`): the answer then comes from stored findings for the
   chosen craft (the stored-only `VERIFIED` path, which needs no model call for a Latin-script
   question), or, for any craft, shows the refusal. This keeps "verified answers from stored
   knowledge still work" true now that readers no longer pick a mode.
4. **`understood` replaces `match` in the flow.** It is the first event: the chosen craft (or none),
   the offers, the effective depth and the language. The `RESOLVING` status is no longer sent, so
   nothing precedes it; the `match` event stays in the vocabulary for the contract golden only and
   `stream.match_event` is removed. The understanding is stored on `Answer.understanding`
   (migration `0013_answer_understanding`), so the expert seats wait there for the panel of
   phase B.
5. **Any craft runs end to end.** `PlanRequest`, `RetrievalPlan`, `KnowledgeQuery`,
   `KnowledgeHits`, `ComposeRequest`, `ResearchSummary` and `ClaimWriteBack` take a null craft.
   Stored search then reads every visible concept (`retrieval/statements.EVERY_CRAFT`); queries
   are not anchored to a craft name; the planner and composer see `ANY_CRAFT_LINE` in place of the
   craft block; written claims hang on shared concepts (no craft, no sub-category) with an empty
   craft in the dedupe key. Without this, every live-evidence sentence of an any-craft answer
   would have no claim to cite and would be dropped.
6. **Depth.** The request carries `depth` (default the role's); `mode` is gone from the request
   and `ASK_DEEP` from the capabilities, since every known role may ask at every depth and an
   unknown role at none (403). The understanding applies `effective_depth` with the model reply's
   `degraded` flag, so past the degrade mark Expert becomes Detailed for capped roles. Each depth
   carries a research budget within its mode: Basic 2 queries and 5 documents, Detailed 4 and 10
   (Hybrid's), Expert 8 and 20 (Deep's); `research_budget(mode, depth)` takes the smaller of the
   depth's and the mode's, so a degraded Expert answer keeps Hybrid's limits.
7. **Caps.** `AI_ANSWER_CAP_USD` in the AI budget holds a cap per depth (starting at $0.25 Basic,
   $0.50 Detailed, $1.00 Expert, to be raised once real costs are measured, owner O3). One
   `providers/budget.AnswerSpend` per answer travels in the `Principal`; `reserve` checks the
   estimate against what the answer has held and spent, holds it in the same synchronous step,
   and the router settles or releases it, so parallel calls of one answer cannot pass the cap
   together. A depth without a cap leaves nothing to spend (fails closed).
   `UNCAPPED_ROLES` moved to `core/roles` (one home for budget and depth): for a Master Admin
   `evaluate` allows everything (per-answer, per-call, daily, media, monthly) and `degrades` is
   false, while the `UsageEvent` is still written, so Usage shows the spend. The budget update
   refuses a daily cap for Master Admins. Every other role keeps today's ceiling rules.
8. **One home for the spend refusal.** `core/errors.SPEND_REFUSAL_KIND` and `spend_refusal(error)`
   replace the `"ceiling"` literals in the router, the media router and jobs, the coverage job and
   the answering service.

## Consequences

- An ambiguous or unknown craft no longer stops the reader; the pills of the old screen are gone
  with `match` (the asking screen, decision 0036, reads `understood`).
- Comparison questions detect several crafts, but phase A chooses one and offers the others; the
  `compare` block (phase D) researches each.
- The cap is set by the asked depth, not the degraded one; the degraded answer spends less anyway.
- Any-craft claims are reachable only by any-craft searches until a craft-scoped search also reads
  shared concepts. These, and the remaining items, are in `docs/TECH_DEBT.md`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
