# 0133. The evaluation scores what answers read

Every evaluation question is asked twice, in the fused order and in the reranked order every answer
reads; a restatement folded into a hit counts as that hit; the floors name each question set's floors
per order; a rerank that fails during an evaluation warns and never passes; the question writer keeps
a second-language question only in its language's script; the first generated set is committed; and
the answer floors are re-based to the judge that now judges.

Date: 2026-11-22. Status: accepted (the lead, on the live measurements of release db09b9e7 on
2026-11-22; within the owner's go-ahead of 2026-11-22 to finish the round). It amends
[decision 0125](0125-reranking.md) and [decision 0126](0126-measurement-that-grows.md). The contracts
are `docs/contracts/retrieval.md`, Evaluation, and `docs/contracts/answer-eval.md`, The floors.

| For | Read |
|---|---|
| The reranked order it now scores, and the evaluation it left unreranked (amended here) | [decision 0125](0125-reranking.md) |
| The question sets, the floors and the release check it amends | [decision 0126](0126-measurement-that-grows.md) |
| The fused order's voting depth | [decision 0132](0132-a-ranking-votes-with-its-first-thirty.md) |
| Scoring, the floors and the release check | [retrieval.md](../contracts/retrieval.md), Evaluation |
| The answer floors | [answer-eval.md](../contracts/answer-eval.md), The floors |
| Every decision, by group | [README.md](README.md) |

## Context

Every answer search reranks its fused candidates with Voyage `rerank-3` (decision 0125), but the
evaluation asked its questions without reranking, so the release check and the weekly run measured a
path no reader gets. A reranked search also folds a restatement into the hit it restates
(`corroboratingIds`), which the scorer did not read. Measured on the production knowledge base on
2026-11-22 (release db09b9e7), each question asked for 20 facts:

| Set | Fused recall at 5 / MRR | Reranked recall at 5 / MRR |
|---|---|---|
| Hand-written, 78 | 0.936 / 0.707 | 0.987 / 0.982 |
| Generated, English, 58 | 0.414 / 0.296 | 1.000 / 0.855 |
| Generated, other languages, 111 | 0.982 / 0.910 | 0.991 / 0.950 |

The reranked figures count a hit when the expected fact is the hit or among its restatements. As the
runs score the generated file in the fused order, the release sample (41 English questions, two per
craft) scored recall at 5 of 0.439 and MRR of 0.297, and the weekly whole set (169) 0.787 and 0.700.
The fused order is weak on paraphrased English questions: the full-text and named-concept rankings
find words the question shares with many facts and outvote the vector ranking, which places the
expected fact in its first three for 52 of 55 such questions. The reranker repairs it.

The first generated set (run 44993519051 of `eval-questions.yml`: 169 questions, model
`claude-haiku-5-5`, seed 20261122) kept one Bengali and one Telugu question written in Devanagari:
the writer's only test of a second language was a letter outside ASCII. The answer floors (judge and
rubric 0.85) were set from the 2026-11-21 baseline (judge 0.936, rubric 0.911), judged entirely by
Gemini 4 Argon, because Claude refused the judge's schema until `be1a5ee`; answer-quality run
44994632550 on release db09b9e7 (13 answers before its 5 US dollar cap) was judged throughout by
Claude Opus 5.5 (13 `EVAL_JUDGE` calls on `claude-opus-5-5`, all OK): judge 0.815, rubric 0.969.

## Decision

1. **Both orders, one embedding.** `evaluation.evaluate_golden` asks each question twice, without and
   with `rerank`, and returns a `SetReport` of two `RetrievalReport`s, `reranked` (primary: what
   answers read) and `fused` (what a failed rerank keeps). `eval_runs.scored` searches through one
   `SessionScopedSearch` given the reranker, as `services/answer_store` builds the answer retriever,
   and `prefetched_embedder` embeds each question once for both asks. `EvalTools.rerank` is
   required; `app.scripts.eval_retrieval` passes `providers/rerank_router.router_reranker()`.
2. **A folded restatement is the same fact found.** A hit is its claim and its `corroboratingIds`;
   recall at 5 and 20 and the reciprocal rank count a fact found at the first hit that holds any of
   its claims. The fused order folds nothing, so it scores as before. The judge of misses reads the
   reranked order and asks only about a first hit that holds no expected claim; its decisions widen
   both orders' facts.
3. **Floors per set and order.** `floors.json` becomes version 2: `retrieval{set: {reranked:
   {recallAt5, meanReciprocalRank}, fused: {...}}}`. `eval_floors.parse_floors` migrates version 1 by
   putting each set's floors on the fused order, the only order version 1 measured, and refuses any
   other version. The release check scores its sample as its own set, `releaseSample`, because one
   fused floor cannot serve both a sample of paraphrased English questions (0.439) and the whole set
   with its other languages (0.787); `generated` is the weekly run's whole set. Each floor is the live
   number above less 0.05, rounded down to two places:

   | Set | Reranked recall at 5 / MRR | Fused recall at 5 / MRR |
   |---|---|---|
   | `handWritten` | 0.93 / 0.93 | 0.88 / 0.65 |
   | `generated` (169: the 58 and 111 weighted, reranked 0.994 / 0.917) | 0.94 / 0.86 | 0.73 / 0.65 |
   | `releaseSample` (41) | 0.95 / 0.80 | 0.38 / 0.24 |

   The sample's reranked floors use the reranked figures of all 58 English questions, since the 41's
   own were not measured apart; its fused figures (0.439, 0.297) sit close to the 58's (0.414, 0.296).
4. **A failed rerank warns.** The search keeps the fused order when the rerank fails (decision 0125,
   item 5), so a reranked ask whose hits carry no `relevanceScore` is counted as fallen back
   (`evaluation.kept_fused_order`). Its set reports those questions as `fellBackToFused`, its reranked
   floors are not compared, and the run warns: the release check exits 2 (`WARNED`, the release goes
   on) and the weekly run's outcome is `warned`, which leaves the floor issue as it is. A broken
   fused floor still stops a release.
5. **The cost stays visible.** A run makes one Voyage call per question it asks (about 60 short
   documents, about 0.0002 US dollars at list price), reserved and settled by the rerank router like
   every model call; the weekly report prints `searchSpentUsd`, what its query embeddings and reranks
   spent under the request id `eval-search-<run>`.
6. **The question writer checks the script.** A second-language question is kept only when at least
   half of its letters are in its language's script (`research/translation.written_in`, the rule the
   translation post-check uses, with the script of `ANSWER_LANGUAGE_SPECS`); a question kept from the
   previous set is held to the same rule on reuse, so the two Devanagari questions leave at the next
   regeneration and their facts keep their English questions.
7. **The first generated set is committed** byte for byte from run 44993519051 as
   `backend/app/data/eval/generated/retrieval_questions.json`, never edited by hand.
8. **The answer floors follow the judge.** The judge changed from Gemini to Claude, a stricter judge,
   so its baseline is re-measured: the judge floor is 0.815 less 0.05, rounded down, 0.76. The rubric
   rose with round 7's fixes, so its floor rises to 0.969 less 0.05, rounded down, 0.91.

## Consequences

- The release gate and the weekly run now measure the order readers get, and still guard the fused
  order a failed rerank leaves.
- Each run asks every question twice and reranks it once; the release check's 180 seconds now cover
  119 questions and 119 Voyage calls at four at a time.
- A Voyage outage or a refused spend during a release is a warning, not a stopped release, as a
  failed embedding route already was.
- The fused order's weakness on paraphrased English questions is recorded as debt, cleared by weighting
  the vector ranking or fusing by learned weights, measured on the generated English questions.
- The generated set's two Devanagari questions stay in the committed file and its floors until the
  next regeneration drops them.
- The CI floors of the stand-in embedder (`tests/db/test_retrieval_eval.py`) stay on the fused order.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/retrieval/test_evaluation.py`,
`test_eval_floors.py`, `test_release_check.py`, `test_miss_judging.py`, `test_question_writing.py`,
`test_question_generation.py`, `test_eval_workflows.py`, `backend/tests/answering/test_answer_floors.py`,
`backend/tests/db/test_measurement_db.py` and `backend/tests/db/test_retrieval_eval.py`.
