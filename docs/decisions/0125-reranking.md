# 0125. Stored facts are reranked, and relevance decides when stored knowledge is enough

The searches an answer rests on (the expert seats and the stored pack) fuse a wider pool of
stored facts, ask Voyage `rerank-3` through the AI router to order them by relevance to the
question, give each fact one slot however often it is restated, and judge stored knowledge by the
best relevance score instead of by how many rankings found a fact.

Date: 2026-11-22. Status: accepted (owner, 2026-11-21: "yes, run all five lanes and the retrieval
lanes"; on the model: "use the model of your recommendation, the voyage one"; embeddings stay on
Gemini Embedding 2: "skip it, it is fine"). The contracts are `docs/contracts/retrieval.md`
(Reranking) and `docs/contracts/backend.md` (AI router); the migration is `0060_reranking`.

| For | Read |
|---|---|
| The rerank stage, the pool and the collapse | [retrieval.md](../contracts/retrieval.md), Reranking |
| The route, its spend and its adapter | [backend.md](../contracts/backend.md), AI router |
| When an answer's retrieval is judged low | [open-work.md](../contracts/open-work.md), Each answer's verdict |
| The fusion this builds on | [0008](0008-stored-knowledge-retrieval.md) |
| The low-retrieval rule this replaces where scores exist | [0113](0113-questions-become-work.md) |
| Only the first 30 of each ranking vote in the fused order (amends this record) | [decision 0132](0132-a-ranking-votes-with-its-first-thirty.md) |
| The evaluation scores the reranked order too (amends this record) | [decision 0133](0133-the-evaluation-scores-what-answers-read.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Retrieval fused three rankings (full text, vector, named concepts) of 30 claims each by reciprocal
rank fusion. Fusion rewards agreement between rankings, not relevance: a fact that repeats the
question's craft name and sits near its vector can outrank the one fact that answers it, and five
restatements of one curated fact (the seed claim and the curated claims that restate it) can fill
five of a seat's twelve slots. The answer's verdict called retrieval low only when no stored fact
beat what one ranking alone can score (1/61), so a fact that merely ranked in two lists counted as
knowledge, and live research and the open-work gaps it feeds were not asked for when stored
knowledge did not answer.

## Decision

1. **Voyage `rerank-3` is a routed task.** `AiProvider.VOYAGE` and `AiTask.RERANK` join the
   catalogue and the Postgres enums (migration `0060_reranking`, which also seeds the Provider row
   and the one RERANK route, ordinal 1, `rerank-3`). `providers/voyage_p.VoyageAdapter` is one
   httpx adapter: `POST /v1/rerank {query, documents, model, truncation: true}` with the key as a
   bearer, a 15 s timeout, one wait for a 429's `Retry-After` of at most 2 s, statuses mapped to the
   shared kinds, an answer off its contract refused, the key never logged. The key is
   `VOYAGE_API_KEY`, read from Settings or a managed key (format-checked only; Voyage offers no
   key-check endpoint this adapter relies on).
2. **Spent like every other call.** `providers/rerank_router.RerankRouter` reserves each call's
   estimate with `router.reserve` and settles it with `router.settle`, so the answer's
   `AnswerSpend`, the role's day and the monthly ceiling govern it. The estimate counts tokens as
   Voyage does, query tokens times documents plus every document (each `len // 3`), at $0.05 per
   million; the settlement uses Voyage's `usage.total_tokens`. A route without a key reserves
   nothing. The answer pipeline gives the router the answer's own principal (`AnswerModels.rerank`),
   not the optional headroom, since the core searches need it and a call of 60 facts costs about
   $0.0002.
3. **A wider pool, reranked once.** `statements.RANKING_DEPTH` rises from 30 to 60. A search with
   `rerank` true sends its first 60 fused facts (`RERANK_POOL`), titled like the vectors' template
   (`title: <craft>, <concept>, <field> | text: ...`), and the search words in one call, after its
   session turn and with no connection held, and keeps the rerank order. Each hit carries
   `relevanceScore`. The seats and the stored pack ask for it; the facet coverage does not, since
   it reads which facts the full-text ranking found.
4. **One fact, one slot.** In rerank order, a fact whose text folds to the same words as a kept
   fact, or whose vector lies within cosine similarity 0.97 of one, joins it as a corroborating id;
   the first `limit` distinct facts are kept. 0.97 and not 0.95: merging two different facts loses
   one from the answer, while missing a restatement only spends a slot, and exact restatements are
   already caught by their folded words, so the vector test only needs to catch close rewordings.
5. **Never in the way.** No reranker, a failed call, no key or a refused spend leaves the fused
   order, with the collapse, and one warning per search. The answer never waits on or fails for
   the reranker.
6. **Relevance decides when stored knowledge is enough.** `services/answer_gaps.retrieval_low`
   calls a section's retrieval low when its stored pack's best `relevanceScore` is below
   `ANSWERING_RELEVANCE` (0.5), and falls back to the fused rule (best fused score at most 1/61)
   when no fact carries a score. The documentation's guidance: Voyage gives no threshold and does
   not call its scores calibrated; its reranker page's example scores the document that answers
   the question 0.94140625 and the related documents that do not 0.28515625 and below. 0.5
   separates the two with room on both sides; it sits below their midpoint (0.61) so that a fact
   the reranker judges a partial answer still counts as stored knowledge, and an answer is judged
   low only when no stored fact comes near answering it. The golden questions' scores are measured on the first retrieval evaluation run with the
   reranker (`retrieval-eval.yml`, run by the lead; this machine runs no network calls), and the
   threshold is revisited with them in a later record if the answered and unanswered questions do
   not fall on either side of it.

## Consequences

- Seats and the stored pack hold distinct facts in order of relevance; a restated fact is cited
  once and its restatements travel with it as `corroboratingIds`.
- An answer whose stored facts only share its words is judged `LOW_RETRIEVAL` and becomes an open
  gap, so live research and contributors are asked for what the knowledge base lacks.
- Each reranked search adds one Voyage call (about 60 documents, a few thousand tokens) and three
  short router transactions. The usage ledger shows list price; Voyage's first 200 million tokens
  are free and are not modelled.
- Searches without `rerank` (the facet coverage, the evaluation, the coverage enrichment, direct
  callers) read 60-deep rankings and are otherwise unchanged; the evaluation floors (recall at 5 at
  least 0.9, mean reciprocal rank at least 0.7) still hold for the fused order.
- The lede's search (`services/lede_evidence.lede_query`) does not ask for reranking yet; it is a
  one-field change for the lane that owns it.
- The Provider row's `maxConcurrency` (8) is recorded as for every provider, but the rerank router
  does not take the chat router's per-provider semaphore: one answer's seats are its only
  concurrent callers.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/test_voyage_adapter.py`,
`backend/tests/test_reranking_catalogue.py`, `backend/tests/retrieval/test_rerank.py`,
`backend/tests/retrieval/test_rerank_search.py`, `backend/tests/answering/test_answer_readings.py`,
`backend/tests/db/test_reranking_db.py` and `backend/tests/db/test_rerank_search_db.py`.
