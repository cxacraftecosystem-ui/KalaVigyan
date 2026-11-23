# 0165. An answer's spend is counted as settled, its asked fields are the ones the question asks, and an expert difference is told once

The answer evaluation stops and reports on what its calls settled, never on a reservation's
estimate; an answered call settles at its cost whatever cuts its caller off and while the session
pooler is briefly full; the understanding says which of its fields the question itself asks; an
expert panel does not differ again over two readings the page already said; and the judge reads a
panel's mirrored difference once, as the reader's differ card shows it.

Date: 2026-11-23. Status: accepted (the lead's answer-regression brief of 2026-11-23, from
answer-quality run 45112746194 on release 1ab422fe against run 44994632550 on release db09b9e7). It
amends [decision 0120](0120-grounded-sentences.md) (differences exempt from the repeat rule),
[decision 0134](0134-each-sentence-once-in-a-block.md) (the judge reads what a reader sees),
[decision 0138](0138-answers-composed-from-the-asked-fields.md) (`Understanding.asked`) and
[decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) (how a call is settled). The
contracts are `docs/contracts/answer-eval.md` (Spend, The judge), `docs/contracts/research.md` (the
understanding), `docs/contracts/explainer.md` (One claim, one rendering) and
`docs/contracts/backend.md` (AI router).

| For | Read |
|---|---|
| The repeat rule's exemption for differences | [decision 0120](0120-grounded-sentences.md) |
| The judge reading each block's sentences once | [decision 0134](0134-each-sentence-once-in-a-block.md) |
| The asked fields and the budget they steer | [decision 0138](0138-answers-composed-from-the-asked-fields.md) |
| A cut-off call settled at its estimate | [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) |
| The quantities table this run measured | [decision 0147](0147-time-market-and-figures-kept-true.md) |
| The per-process connection budget that keeps the pooler from filling | [decision 0163](0163-limits-kept-by-choice-and-a-register-that-only-shrinks.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Run 45112746194 (cap 5 US dollars) answered two questions before "the spend cap was reached";
run 44994632550 (same cap) answered 13. Its first question, the Ajrakh indigo one, reported 2.3355
spent against 0.2726 before, and the water and climate one 0.4751 against 0.1436; their rubric fell
from 1.0 to 0.8 and from 0.867 to 0.667. The production rows, the two answers whole, their routes,
the box's stderr and a read-only probe of piece reuse showed six things.

1. **The eval counted an estimate.** The first question's `UsageEvent` rows settled 1.052073. One
   more row, a Sonnet `COMPOSE` call of the s1 simulation builder at 04:36:06, stayed `RESERVED`
   at its estimate of 1.283412, since an answered call is estimated at the model's 128,000 output
   tokens (decision 0093). The model had replied; settling failed because the session pooler was
   full (`EMAXCONNSESSION`, 30 clients), the builder failed, and `router.tagged_spend` counted the
   fresh reservation: 1.052073 + 1.283412 = 2.3355. After two questions the run counted 2.8106,
   leaving 2.19 of the cap, under the 2.50 a question reserves; it had settled 1.527222.
2. **The cache was cold, once.** The old indigo answer reused ten pieces stored on 2026-11-17 for
   four of its five sections (three Opus compose calls, 0.27 with the judge). Nine of the ten were
   marked stale at 19:39:49 on 2026-11-22 by the claim trigger of migration 0017, when claims they
   cite left the visible set (1 to 17 each) during the release that carried decision 0142's
   archive of a curated craft's seed claims; a reused group needs every piece current, so the new
   answer composed all five sections: ten Opus `COMPOSE` calls (130,975 input and 11,561 output tokens, 0.755),
   eleven Sonnet builder calls (0.149), live research and two write-back judges on the Opus
   `EVAL_JUDGE` route (0.119). The new answers stored 29 Detailed pieces, every one reusable now.
   A call cost what a cold section cost before (13,000 to 15,000 input tokens on Opus, 0.06 to
   0.11); production's first `COMPOSE` route has been `claude-opus-5-5` since 2026-11-17, so
   Detailed composes on Opus by that setting, while the code's default is Sonnet.
3. **Every listed field was asked.** The understanding's reply lists every field an answer draws
   on, the asked ones first, and `asked_fields` took the whole list as asked: the indigo reply's
   PROCESS, CHEMISTRY, MATERIALS, OVERVIEW and GEOGRAPHY, the water reply's GEOGRAPHY, CLIMATE,
   PROCESS, OVERVIEW and SOCIETY. Decision 0138's ranking and its half-sentence cap on unasked
   fields never applied, so SOCIETY, thin for Kutch Ajrakh, was researched live with five fetches
   and PROCESS showed its whole ten-stage ladder in a water and climate answer.
4. **A difference repeated the ladder.** The indigo answer's PROCESS ladder said "Stage 8 dyes the
   cloth in indigo for 10 to 15 minutes ..." and "Clifford records a natural indigo vat ...", and
   the CHEMIST and ARTISAN views differed over exactly those two claims, mirrored in both views:
   three copies for the judge, two for the reader.
5. **The quantities table was built once and dropped.** No section of the indigo answer cites three
   quantities in digits; the water answer's PROCESS built one that the claim ledger dropped, since
   every row's sentence was a ladder sentence already shown word for word.
6. **The rubric fell by its new part.** Both falls are the everyCited part decision 0138 sets to 0
   when a shown sentence cites a quote about another craft or a place abroad (2 and 1 such
   sentences: the Barmer centre and Kutch "between the province of Sindh, Pakistan, and mainland
   Gujarat"); the old answers cite the same Barmer and Sindh quotes. ECOLOGY was missed by both
   releases: the field definitions put water, rivers and wells in GEOGRAPHY and ECOLOGY in
   pollution, effluent, waste and sustainability, and neither understanding listed it.

## Decision

1. **The evaluation counts what was settled.** `router.tagged_settled_spend` sums the `costUsd` of
   the tagged rows, a reservation never settled counting nothing; `eval_answers` stops the run and
   reports each question on it. We chose this over counting reservations at a smaller estimate:
   after a question its answer, judge and shielded work have finished, so a row still reserved is a
   lost settlement, not spend in flight, and any estimate of it would be a guess. The budget's
   ceilings keep counting fresh reservations (`tagged_spend`, `current_spend`), failing closed.
2. **An answered call settles at its cost.** `router._settled_answered` runs shielded, so a caller
   cut off by a builder's wait or a timeout while it settles still leaves the row `OK` at its cost,
   and it is tried again after each of `core/pooler.POOLER_RETRY_WAITS` (0.2, 0.5, 1.0 s) while the
   pooler refuses a connection; any other database failure still raises. Decision 0146's estimate
   stays for a call cut off before the model replied.
3. **The understanding says what is asked.** The reply carries `asked`, the fields among its
   disciplines the question itself asks, and the prompt says so and describes ECOLOGY;
   `understanding.question_asked` keeps the reply's `asked` that it also lists, else every field it
   lists, as before. We chose the model's word over the question's cue words: the indigo question
   cues CHEMISTRY alone, though it asks about the vat as much as the dye.
4. **Two readings already said are not told again as a difference.** The claim ledger drops a
   difference from both seats when the page already said both its readings, each by its words or by
   every claim it cites; one reading said in prose still keeps it (decision 0120).
5. **The judge reads a mirrored difference once.** `coverage_answers` reads an expert panel's
   difference once per pair of seats, as the differ card draws it, so the judge and the rubric count
   what the reader sees.

## Consequences

- No migration and no payload change: `asked` is a field of the model's reply, and
  `Understanding.asked` already existed.
- The next run should reuse the 29 stored pieces for its first two questions, so they cost about
  what they did before (0.27 and 0.14); questions whose pieces cite archived claims are cold once
  more, at about 0.5 to 1.05 each.
- A Detailed answer whose understanding marks fewer fields asked researches and writes less in the
  others: no first share of the live budget and at most half the depth's sentences.
- Composing Detailed answers on Sonnet would halve their compose cost; that is the route an admin
  set, not this record's to change. The in-answer write-back judges run on the `EVAL_JUDGE` route's
  Opus; giving them the contribution worker's cheap-then-strong judges is the write-back lane's.
- The quantities table, the off-question part of the rubric and the ECOLOGY expectation of the
  water and climate question are left to the lead after the next run; the table's entry in
  `docs/TECH_DEBT.md` says what would show it.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/db/test_eval_spend_db.py`,
`backend/tests/test_router_settled.py`, `backend/tests/planner/test_understanding_fields.py`,
`backend/tests/planner/test_understanding.py`, `backend/tests/ledger/test_ledger_kinds.py` and
`backend/tests/research/test_shown_sentences.py`.
