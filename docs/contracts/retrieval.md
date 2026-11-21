# Stored-knowledge retrieval contract

How stored claims (T1) and stored passages (T2) are found for a question, how their vectors are
made, stamped and renewed, and how retrieval is measured. Decisions 0008 and 0101 (item 10 and
build step 3). Code: `app/retrieval/`, the contract types in `app/research/retrieval.py`, the
seat search in `app/services/seat_search.py`, the seed passages in
`app/services/claim_seed_passages.py`, migration `0043_embedding_stamps`.

## The search

`KnowledgeRetriever.search(KnowledgeQuery) -> KnowledgeHits`. Two implementations:
`StoredKnowledgeSearch(session, *, embed, english=None)` on one session and
`SessionScopedSearch(sessions, *, embed, english=None)`, which opens a session per search.

- `KnowledgeQuery {craftSlug | null, text, mode, facets[], fields[], chunkAcls, limit}`. A craft
  scope reads the craft's concepts and its family's shared concepts; `craftSlug` null reads every
  visible concept. Modes set the statuses and levels read (`MODE_CLAIM_STATUSES`,
  `MODE_CLAIM_LEVELS`); only the modes whose policy holds tier `T2` read passages.
- `fields` keeps the claims filed under one of the fields (as their field or a secondary field)
  and the claims with no field yet; passages follow the claims kept. An empty tuple reads every
  field.
- `chunkAcls` is the reader's passage access (`chunk_acls_for(reader)`); restricted chunks and
  sources and withheld field recordings are never read.

### Ranking

- Claims: three rankings of at most `RANKING_DEPTH` (30) each, fused by reciprocal rank fusion
  (`score = sum(1 / (60 + rank))`, ties by best single rank, then id):
  - full text: the search words' distinct Latin terms of 3 or more characters ORed through
    `to_tsquery('english')`; the first `LEXICAL_CANDIDATES` (400) matches by `ts_rank_cd` are
    then ordered by the rarity of the terms each holds: a term weighs `ln(1 + n / n_t)`, where `n`
    is the number of candidates and `n_t` the number holding the term, so a claim holding the
    question's rare word (settled, bacteria, a person's name) outranks claims that only repeat the
    craft's name or a name every claim carries; ties by `ts_rank_cd`, then id;
  - vector: exact cosine distance between the embedded question and the scoped claims whose
    vector was made by the embedding route's current model (see Stamps); a claim with no vector,
    or with another model's, ranks by text and entities alone;
  - entities: claims on scoped concepts (or edges touching them) named in the search words by a
    name of 4 or more characters, longest name first. A concept is named by its whole name, by its
    native head before ` (` and by the gloss inside the parentheses (`Syahi (fermented iron
    black)` is named by "syahi" and by "fermented iron black"), and by the label, aliases and
    local names of every glossary term linked to it (`TermConcept`).
- Passages: full text and vector as above, fused in two separate lists of at most `limit` each:
  corpus passages, and the passages of field recordings (`Source` of a `FieldRecording`). A
  craft's many corpus passages therefore never crowd an artisan's recorded words out of the
  hits. `KnowledgeHits.chunks` holds both lists merged by score, so up to twice `limit` rows.
- The question is embedded as `task: search result | query: <text>`, claims as
  `title: none | text: <text>`, passages as `title: <source title> | text: <text>`.

### Questions without Latin words

The search words are the question itself unless it has no Latin term of 3 or more characters.
Then, when the search was built with an `english` rendering (`EnglishRendering`, an
`async (text) -> str`), the search words are that rendering; the vector is still made from the
question as asked. The answer pipeline (`services/answer_store.build_answer_pipeline`) passes
`english_question` of decision 0023, so a direct caller with Hindi, Gujarati or any other
non-Latin question gets a full-text and entity ranking in English. A question with any Latin
word makes no model call. A failed rendering leaves the question as asked (decision 0023's
rule). The rendering and the question's vector are both made before the search takes a
connection.

### Expert seats

`seat_query(ask, brief)` searches the seat's own fields: `fields` is the seat's `SeatBrief.fields`
(the Historian reads `HISTORY` and `OVERVIEW`, the Chemist `CHEMISTRY`, `PROCESS`, `MATERIALS`
and `HEALTH`), so the search is filtered by field, not only worded by it. The words are the
answer's English question (`PlanRequest.english_question`, else the question), the craft name,
the seat label and the field titles.

## Stamps

Every stored vector carries the model that made it.

- Columns (migration `0043_embedding_stamps`): `Claim.embeddingModel`, `Chunk.embeddingModel`,
  `Craft.embeddingModel` (for `descriptorEmbedding`), `varchar(120)` like `RoutePolicy.model`,
  and `Craft.descriptorHash` (SHA-256 hex of the descriptor text the vector was made from).
- The current model is `kv_embedding_model()`: the model of the first enabled `EMBED` route
  (by ordinal) whose provider is enabled. Python reads it as
  `retrieval/stamps.current_embedding_model()`.
- Every writer stamps. The writers in `retrieval/indexing` and the descriptor fill set the stamp
  explicitly; triggers (`Claim_embedding_stamp`, `Chunk_embedding_stamp`,
  `Craft_descriptor_stamp`) stamp any other write (the write-back gates, proposals, tests): a
  vector written without a stamp, or changed while its stamp stayed, takes the current model; a
  cleared vector clears its stamp (and a craft's hash).
- A claim or passage whose text changes in place loses its vector and stamp in the same
  statement, whichever path changed it: the curation import's claim updates
  (`services/curation_claims.write_claims`), the testimony erasure
  (`services/testimony_claims`), re-chunking (`retrieval/indexing._apply`) or any later writer.
  The next embedding run gives it a new one.
- The migration stamps the vectors stored before it with the route's model at that moment;
  `gemini-embedding-2` is the only catalogue model that can run `EMBED` and has been since the
  foundation.

## Embedding runs

- `embed_pending(session, embed, *, batch_size=50, deadline=None)` embeds the visible claims and
  unrestricted passages with no vector or another model's stamp (missing first), then the
  knowledge pieces with no vector, in batches of `EMBED_BATCH` (50), at most `EMBED_RUN_ROWS`
  (20,000) rows of each kind a run. With a `Deadline` it starts no batch once the time is
  spent; each batch is committed, so a stopped run keeps what it did. It returns
  `EmbeddedCounts {claims, chunks, pieces, complete}`.
- `embed_written(session, embed, *, claim_ids, source_ids)` applies the same rules to the rows a
  write just stored.
- `services/craft_resolver.fill_descriptor_embeddings(session, embed, *, batch_size, deadline)`
  embeds a craft's descriptor (name, local name and aliases joined by `; `) when it has no
  vector, another model's stamp, or a `descriptorHash` that differs from the hash of its
  descriptor text now, so a craft whose aliases change is embedded again. The resolver's
  semantic step reads only descriptor vectors of the current model.
- Scripts: `python -m app.scripts.embed_knowledge [--seconds N]` and
  `python -m app.scripts.embed_craft_descriptors [--seconds N]` print a JSON report
  (`{ok, model, claims, chunks, pieces, complete}` and `{ok, filled}`), or
  `{ok: false, error}` and exit 1 when the embedding route fails.

### On every release

`infra/deploy/blue_green.sh` runs, after the seeds, the curated import and the craft sync,
`embed_craft_descriptors` and then `embed_knowledge`, each with `--seconds $EMBED_SECONDS`
(240) inside `timeout` of that plus `EMBED_GRACE` (60). Their reports are logged; a failure, a
time-out or a down embedding route is a warning and the release goes on. What is left is
embedded by the next release or the daily Coverage enrichment run.

## Stored passages of the corpus imports

The seed import (`app.scripts.seed_claims`) keeps the verbatim passages it quotes as chunks of
their sources (`claim_seed_passages.store_seed_passages`): every quote whose upstream check
passed (`quoteCheck` `PASS`), once per source, with every locator it was cited at joined by
`; `, `PUBLIC` (the same words are already shown as the claim's quote), language `en`. A
source that already has chunks (an earlier run, or a document live research stored) is left as
it is, so a second run stores nothing. `ClaimSource.chunkId` is not set, so citation access is
unchanged. The passages are searched like any corpus passage and embedded by `embed_knowledge`.

The Wood Handbook is cited by the inferential-system seed (FPL-GTR-190, 2010) by chapter title,
with no quote; the repository holds no text of that edition, so it has no passages.

## Evaluation

- The golden list (`app/data/eval/retrieval_questions.json`, version 1, read by
  `retrieval/golden.golden_questions()`): 77 questions over 21 crafts and the shared
  block-printing science, covering all sixteen fields. Each question names the field it asks
  about (`field`) and, sometimes, the field filter it is asked with (`fields`). Each entry of
  `expected` is one fact the answer needs: a claim, or a list of every stored claim that states
  that fact (the knowledge base often holds a seed claim and the curated claims that restate it),
  any one of which counts. Claims are named by seed key (`seed-...`) or claim id, read from each
  craft's public export on 2026-11-21. `test_evaluation` checks the counts, that every name is a
  seed key or a claim id, and that every seed key is a seeded concept claim of the named craft in
  an allowed field.
- `retrieval/evaluation.evaluate_golden(retriever, golden, *, claim_id, present=None)` asks each
  question in `HYBRID` mode for 10 claims and reports recall at 5 (the share of a question's
  facts with any of their claims in its first five, averaged), mean reciprocal rank (of the first
  claim of any fact) and recall by field, with the facts each question missed (`a or b`).
  Expected claims not visible in the database are reported as absent and not scored; a fact
  whose claims are all absent is dropped.
- `tests/db/test_retrieval_eval.py` seeds the claims and passages, embeds them with a hashed
  bag-of-words embedder (deterministic, no network), scores the questions with a seeded claim
  (at least the 22 seed-keyed ones) and asserts recall at 5 of at least 0.9 and a mean
  reciprocal rank of at least 0.7; a change that lowers either below its floor fails.
- `python -m app.scripts.eval_retrieval` runs the list against the live database with the
  embedding route and prints
  `{ok, questions, recallAt5, meanReciprocalRank, absent, misses, recallByField}`.

## Not built

- Knowledge pieces carry no stamp; a piece's vector is filled when missing only.
- The candidate gates' neighbour search (`services/candidate_store`) and the piece store's reuse
  distance compare vectors without reading the stamp.
- The HNSW indexes on the vector columns are unused by the exact craft-scoped scan.
- Wood Handbook passages wait for the cited edition's text.
