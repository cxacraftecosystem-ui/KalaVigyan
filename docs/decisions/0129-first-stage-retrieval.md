# 0129. The stored search finds the right facts as the knowledge grows

Each claim's vector now carries its craft, concept and field; the words of a question reach the
glossary's other names for them; facts are searchable in the request that writes them; and a
question about no single craft reads the vector indexes instead of scanning every claim.

Date: 2026-11-22. Status: accepted (owner, 2026-11-21: "yes, run all five lanes and the retrieval
lanes"; on the embedding model: "skip it, it is fine", so the vectors stay on Gemini Embedding 2).
The contract is `docs/contracts/retrieval.md`, The search, Stamps and Embedding runs.

| For | Read |
|---|---|
| The contract it changes | [retrieval.md](../contracts/retrieval.md) |
| How stored knowledge was first searched | [0008](0008-stored-knowledge-retrieval.md) |
| The rerank stage that follows this first stage | [0125](0125-reranking.md) |
| How retrieval is measured | [0126](0126-measurement-that-grows.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The first stage (full text, vector and entity rankings, fused) decides which facts the reranker and
the seats ever see. Four faults would grow with the knowledge, towards 500 crafts and 150,000
claims:

- A claim was embedded as `title: none | text: <text>`. "It is then washed in the river." carried
  no craft, stage or field, so its vector sat as near to every craft's washing as to its own.
- The full-text query dropped every word under 3 letters. "GI" never reached it: on the live
  measurement the POLICY field's recall at 5 was 0.4, with three GI questions missed. Nor did the
  glossary's other names: "siyahi" never found "syahi".
- A fact written outside a release and the daily run waited up to a day for a vector: a term
  summary's write-back and a structure item written into a page had none, so the vector ranking
  could not find them.
- A question about no single craft ranked every visible claim by an exact distance scan, slow at
  150,000 claims, while the HNSW indexes built on `Claim.embedding` and `Chunk.embedding` in the
  first migration went unused.

And the seats of one section now search the same words, so an answer embedded one question once per
seat.

## Decision

1. **Vectors with their context.** A claim is embedded as
   `title: <craft> · <concept> · <field> | text: <text>`, the sub-category or the category standing
   for the craft on a shared or family concept; passages keep their source's title. The stamp
   becomes the model and a recipe, `gemini-embedding-2#ctx1`, in SQL (`kv_embedding_model()`,
   redefined by migration `0061_embedding_recipe`) and in Python (`stamps.EMBEDDING_RECIPE`, a test
   keeping both equal). The rankings read every vector of the current model whatever its recipe, so
   they never go blind; the embedding runs renew the vectors of an older recipe after the missing
   ones and another model's, oldest first. A vector written without a stamp (a gate's, a test's)
   takes the model alone, since only the indexing writes the recipe's text. A dispatch-only
   workflow, `embed-knowledge.yml`, lets the lead renew everything in one go after the release:
   about 2.6 million tokens, near 0.52 US dollars, on the knowledge of 2026-11-22.
2. **The glossary reaches the words search.** The full-text query keeps a question's words of 2
   letters after its longer ones, and a short word counts only when it names a glossary term. Every
   word that names a term matches the term's other names too, as one slot of the ORed query, so the
   rarity weighting is unchanged: "GI" finds "geographical indication", "siyahi" finds "syahi", and
   a short word no term names is left out.
3. **Searchable when written.** A term summary's write-back, a structure item written at once and
   one approved from the review queue are embedded in the same request with the writer's own
   embedding route; a failed embedding never undoes the write, and the daily run catches up. A
   proposed fact already keeps its duplicate gate's vector. A just-written row is embedded only
   when it has no vector of the current model; renewing an older recipe is left to the runs.
4. **Questions about no single craft use the indexes.** With `craftSlug` null, the vector ranking
   orders by the HNSW index (the nearest eight vectors per wanted hit, then the claim conditions,
   then exact distance), with `hnsw.iterative_scan = relaxed_order` and `hnsw.ef_search = 200` set
   for the transaction. Production runs pgvector 0.8.2, read on 2026-11-22. A craft's scope keeps
   its exact scan.
5. **One embedding per text for an answer.** The answer pipeline's embedder keeps each vector for
   the answer's life, keyed by the stamp and the text, and shares one still being made; nothing is
   kept across answers.

## Consequences

- Every claim and passage vector is embedded once more after the release (passages only for the
  stamp, since their text is unchanged). Until then the rankings read both recipes.
- The write-back of an answer still embeds its claims through its duplicate gate; those vectors
  carry the model alone and are renewed by the runs, so no request pays twice.
- Restatements collapse by vector only between vectors of one stamp (`rerank.py` compares the full
  stamp), so for a day after the release fewer restatements of mixed recipes are joined.
- The knowledge view, the category knowledge and the component library rank by the same
  glossary-aware words.
- The hand-written questions are kept as they are (decision 0126); five already ask about GI, and a
  transliteration question waits for the glossary to hold a pair the live facts use.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/retrieval/test_first_stage.py`,
`test_stamps.py`, `test_statements.py`, `backend/tests/knowledge_writes/test_written_vectors.py`,
`backend/tests/db/test_first_stage_db.py`, `test_retrieval_stamps_db.py` and
`test_term_write_back_gates_db.py`.
