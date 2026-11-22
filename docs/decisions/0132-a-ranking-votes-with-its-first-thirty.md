# 0132. A ranking votes with its first thirty; deeper finds only fill the rerank pool

Each of a search's rankings still reads 60 deep, so the reranker has its pool, but only its first 30
items vote in the fused order. An item no ranking places in its first 30 follows every item one does.

Date: 2026-11-22. Status: accepted (the lead, on the release check that stopped the round 7 release
on 2026-11-22; within the owner's go-ahead of 2026-11-22 to finish the round). It amends
[decision 0125](0125-reranking.md). The contract is `docs/contracts/retrieval.md`, Ranking.

| For | Read |
|---|---|
| The pool it amends | [decision 0125](0125-reranking.md) |
| The check that found it | [decision 0126](0126-measurement-that-grows.md) |
| The ranking rule | [retrieval.md](../contracts/retrieval.md), Ranking |
| The fusion weighted by a measured file (amends the fusion) | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0125 deepened every ranking from 30 to 60 so a reranked search could send 60 fused facts to
Voyage, and expected searches without reranking to be otherwise unchanged. The release check of
decision 0126 scored the release on the production knowledge base and stopped it: recall at 5 on the
hand-written questions fell to 0.795 against a floor of 0.82, while the live release's code scored
0.922 on the same vectors. In nine of the missed questions the expected fact ranked first in both the
full-text and the vector ranking and fell to 6th to 16th: facts that only mention the craft's
concepts appear deep in all three rankings (for example at 37, 10 and 6), and three deep votes
(0.040) outweigh two first places (0.033). The fused order is what a search without reranking
returns (the evaluation, the facet coverage, the enrichment) and what a reranked search keeps when
the rerank fails.

## Decision

1. **The first 30 vote.** `fusion.reciprocal_rank_fusion` sums `1 / (60 + rank)` over each item's
   ranks within `VOTING_DEPTH` (30) as its vote, and sorts by the vote, then by the sum over every
   rank, then by best single rank, then by key. The first 30 of a 60-deep ranking are the 30-deep
   ranking the fusion read before decision 0125, so the voted order is the order measured then.
2. **Deeper finds fill the pool.** An item found only below rank 30 keeps its place in the
   candidates after every voted item, so a reranked search still sends up to 60 facts.
3. **The score is unchanged.** A hit's `score` stays the sum over all its ranks, as the evidence
   readings use it.

## Consequences

- On the production knowledge base the hand-written questions score recall at 5 of 0.936 and mean
  reciprocal rank of 0.707 (the live release scored 0.922 and 0.708 on the same vectors, and 0.87
  and 0.69 before the titled vectors), so the release check passes.
- A search's fused order no longer lets breadth of shallow mentions beat a fact two rankings place
  first; the reranker still sees the deep candidates.
- The rankings' depth (`RANKING_DEPTH`, 60) and the pool (`RERANK_POOL`, 60) are unchanged.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/retrieval/test_fusion_and_text.py`.
