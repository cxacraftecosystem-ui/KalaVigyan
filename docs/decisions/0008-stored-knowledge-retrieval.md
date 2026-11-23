# 0008. Stored-knowledge retrieval

Stored knowledge is retrieved within a craft's scope by two rankings, full text and an exact vector
scan, fused by rank with no similarity floor. What a reader may be shown is defined once in
`research/retrieval.py`, and a failed embedding fails the search instead of falling back to text.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| Knowledge pieces carry their stamp, and the gates and the piece store compare vectors of one model | [decision 0166](0166-pictures-terms-and-stored-pieces-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

PLAN section 6 names two stored tiers that search text: T1, the craft's claims ("SQL over
subject plus hybrid search on claim text"), and T2, corpus chunks ("ported `hybrid.py`; `acl`
and `sensitivity` filtered in SQL"). PLAN section 2 points at
`inferential-system/backend/app/retrieval/hybrid.py`: a Postgres full-text ranking, a pgvector
ranking and a personalised PageRank, fused by reciprocal rank fusion with k = 60. The research
contract (decision 0002) had no retrieval types, `Chunk` has no craft column, and the embedding
protocol lived inside the craft resolver.

## Decision

1. **Contract and homes.** The types are contract types in `research/retrieval.py`
   (`KnowledgeQuery`, `ClaimHit`, `ChunkHit`, `KnowledgeHits`, `KnowledgeRetriever`) next to the
   other lanes' types. The implementation is a new layer `app/retrieval/` (`retrieval ->
   research, core, models`), importable by services, the API and scripts, never the reverse.
   `TextEmbedder` and `checked_vectors` move from `services/craft_resolver.py` to
   `research/embedding.py`, so the resolver and retrieval share one embedding protocol without a
   sideways import; `providers` may now import `research` for it.
2. **What is shown is defined once.** `HIDDEN_CLAIM_STATUSES`, `VISIBLE_SENSITIVITY` and
   `RESTRICTED_SENSITIVITY` move from `knowledge_view` to `research/retrieval.py`, and
   `MODE_CLAIM_LEVELS` / `MODE_CLAIM_STATUSES` state what each mode reads: `VERIFIED` reads
   `VERIFIED` and `REVIEWED` claims with status `APPROVED` (PLAN section 6, "in SQL, never in a
   prompt"); `HYBRID` and `DEEP` read every level and every status but the hidden ones (no
   review gates, PLAN section 0). Whether chunks are read follows `MODE_POLICIES`: only modes
   whose tiers include `T2`.
3. **Craft scope.** A craft's claims are the claims on its concepts and on its sub-category's
   shared concepts (the rule `knowledge_view.craft_concepts` already used), plus claims on edges
   that touch them; the concept must be `OPEN`, the claim `OPEN` and cited by at least one source
   that is not `RESTRICTED`, in SQL before the ranking limit, so hidden rows take no rank. A
   chunk has no craft: a craft's chunks are the chunks of the sources its scoped claims cite,
   within the reader's ACLs (`PUBLIC` unless the caller passes more: the guard fails closed) and
   not `RESTRICTED`. Facet filters narrow both.
4. **Two rankings, not three.** The full-text ranking ORs the question's distinct Latin words of
   three or more characters (at most 40) through `to_tsquery('english')` and orders by
   `ts_rank_cd`, ties by id, as the source module does: an AND query (`websearch_to_tsquery`)
   finds nothing for most natural questions. The vector ranking is pgvector cosine distance.
   The PageRank ranking is not ported: it walks the inferential-system knowledge graph, and our
   concept graph is not yet dense enough to rank with (it can be added as a third ranking
   without changing the fusion). Each ranking takes the best 30 (`RANKING_DEPTH`, the source's
   value), fused by RRF with k = 60 (Cormack, Clarke and Büttcher, SIGIR 2009, and the source
   module); equal scores order by the best single rank, then id, so results reproduce. Claims
   and chunks are fused separately: they are different tiers and the composer treats them
   differently.
5. **Exact vector search.** The vector ranking scans the scoped rows in a `MATERIALIZED` CTE
   and sorts by distance, so the HNSW index is not used. With a filter as narrow as one craft,
   an HNSW scan returns its nearest neighbours first and filters after, which can return fewer
   than 30 rows or miss the craft's rows entirely; accuracy over speed (PLAN section 0). A craft
   has hundreds of rows, not millions.
6. **No similarity floor.** Fusion uses ranks only. A floor would need calibration against the
   known-answer checks; the composer's post-checks drop sentences that the evidence does not
   support.
7. **Embedding text.** Queries are embedded as `task: search result | query: <text>`, stored
   claims as `title: none | text: <text>`, and chunks with their source title: the query prompt
   PLAN section 9 names for gemini-embedding at 1536 dimensions, and the document prompt that
   pairs with it. Both sides of a comparison must use the same model and prompts. `RESTRICTED`
   claims and chunks, and claims with a hidden status, are never sent to an embedding provider.
8. **Chunks.** `chunk_text` packs whole paragraphs up to 1,200 characters, splits a longer
   paragraph at sentence ends and a longer sentence at spaces; the last paragraph of a full chunk
   (when at most 300 characters, the stored quote limit) starts the next one, so a quote across
   a boundary still lies in one chunk. Whitespace is collapsed, as the quote check does. The
   locator is the paragraph range (`para 3`, `paras 3-4`). `replace_source_chunks` updates by
   ordinal, keeps the vector of an unchanged chunk, clears it for a changed one and deletes
   extra ordinals; chunks inherit the source's sensitivity.
9. **Failures.** An unknown craft slug is `InvalidInput`; an embedding failure or wrong vector
   size is `ExternalFailure` from `checked_vectors`; the search does not fall back to text only.

## What follows

- The answering service builds `StoredKnowledgeSearch(session, embed=router_embedder(principal))`
  per request and turns hits into composer candidates (claims) and corpus passages (chunks).
- The claim writer calls `replace_source_chunks` with a fetched `SourceDocument.text` when it
  stores a source, and `app/scripts/embed_knowledge.py` (`embed_pending`) fills missing vectors.
- Stored vectors carry no model stamp (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
