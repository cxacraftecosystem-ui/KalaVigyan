# 0126. Measurement grows with the knowledge and alerts when it falls

Retrieval and answers are measured on production by question sets that grow with the data: a
question written for each sampled published fact, misses judged once and remembered, floors kept in
a versioned file that open an issue when one is broken, a retrieval check that stops a release
below the floor, and a craft-matching set built from every craft's names. A drop is caught when it
happens, at 500 crafts as at 20.

Date: 2026-11-22. Status: accepted (owner, 2026-11-21, on the retrieval lanes: "yes, run all five
lanes and the retrieval lanes"). The contracts are `docs/contracts/retrieval.md`, Evaluation, and
`docs/contracts/answer-eval.md`, The floors.

| For | Read |
|---|---|
| The question sets, the scoring, the floors, the release check and craft matching | [retrieval.md](../contracts/retrieval.md), Evaluation |
| The answer floors | [answer-eval.md](../contracts/answer-eval.md) |
| The duplicate gate whose sameness the restatements follow | [knowledge-writes.md](../contracts/knowledge-writes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Retrieval was measured by 78 hand-written questions over 22 crafts (live on 2026-11-21: recall at 5
0.87, mean reciprocal rank 0.69; the weakest fields policy 0.4, botany 0.5, society 0.67). Their
floors (0.9 and 0.7) ran in CI on a hashed bag-of-words stand-in embedder, so they never tested the
real vectors; the weekly live run had no floor and alerted no one; the answer evaluation had no
floor either. Craft matching had no test set at all (the plan asks 300 cases, top-1 at least 95%).
Knowledge now arrives through MCP from many contributors at once, so a set written by hand cannot
keep up with what the search must find.

## Decision

1. **A question per sampled fact.** `app.scripts.generate_eval_questions` samples 20 published
   facts per craft by a seeded hash and asks the cheapest structured route, one call per 25 facts,
   for one question a reader would ask that each fact answers. Code drops a question that reuses
   more than two of the fact's distinctive words, or any it does not name as unavoidable. About one
   fact in five also gets the question in the craft's own language or Hindi. Each question expects
   its fact and the facts the duplicate gate would call the same without a judge. The set is a
   versioned file with a schema, read like the hand-written list, which stays as its own set; a
   regeneration keeps the questions of facts still sampled, so it pays only for new facts. Spend is
   metered by the router and capped (3 US dollars by default).
2. **Scores per set, field and craft, misses judged once.** Each set reports recall at 5, mean
   reciprocal rank and recall at 20 overall, by field and by craft. A generated question whose
   first hit is another fact is judged once by the cheapest route; a fact the judge accepts counts
   as found and joins the question's expected claims in the next revision, one it refuses is
   recorded so it is never asked again.
3. **Floors that alert.** `backend/app/data/eval/floors.json` holds floors per set and for the
   answer means, set at the live numbers less 0.05 (recall at 5 0.82, mean reciprocal rank 0.64;
   judge and rubric 0.85). The generated set has none until its first live run. The weekly
   retrieval run and a whole answer run fail below a floor and keep one issue each,
   `Retrieval fell below its floor` and `Answers fell below their floor`, closed by the next passing
   run. The lead raises the floors.
4. **A release check.** Before traffic moves, `blue_green.sh` scores the hand-written questions and
   two generated English questions per craft, at most 400 in all, with the new colour's code against
   the same database, embedding only, within 180 seconds. Below a floor the release stops; a missing
   set, a failed embedding route or a spent time budget is a warning and the release goes on.
5. **Craft matching.** 1,764 cases are built by code from every craft's name, aliases and names in
   its own script (exact, folded, misspelt by one deterministic edit, partial, and two-craft
   comparisons that must come back ambiguous). CI asks the lexical resolver the exact, folded and
   comparison cases on the seeded crafts and requires 95% of each kind; the live mode scores every
   case with the embedding route.

## Consequences

- The CI floors of the stand-in embedder stay as they were; the live floors now test the real
  vectors, weekly and on every release.
- The generated file is committed by the lead from the generator's or the weekly run's artifact; no
  migration holds it. Until the first one is committed, the release check scores the hand-written
  questions and warns.
- Generated questions in another language are searched as asked, with no English rendering, and
  the report does not yet split the set by language.
- A change to the craft master list or `craft_aliases.json` fails `test_craft_cases.py` until the
  cases are rebuilt with `app.scripts.build_craft_cases`.
- The debt entry "Craft matching has no evaluation set" is cleared.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/retrieval/test_evaluation.py`,
`test_generated_set.py`, `test_question_writing.py`, `test_question_generation.py`,
`test_miss_judging.py`, `test_eval_floors.py`, `test_release_check.py`, `test_craft_cases.py`,
`test_eval_workflows.py`, `backend/tests/answering/test_answer_floors.py`,
`backend/tests/db/test_measurement_db.py` and `backend/tests/db/test_craft_matching_db.py`.
