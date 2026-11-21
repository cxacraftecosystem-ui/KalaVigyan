# 0004. The craft resolver

The craft resolver finds a question's craft in memory from exact, fuzzy (rapidfuzz), family and
place signals that keep interpretable scores, and embeds the question only when no lexical winner
emerges. A single candidate below the accept rule is ambiguous, and a failed embedding is shown as
an error, never hidden.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| Every decision, by group | [README.md](README.md) |

## Context

PLAN 5.2 describes the matcher: normalise, exact, `pg_trgm` fuzzy at 0.45, semantic on
`descriptorEmbedding`, reciprocal-rank fusion with a place boost, then accept at 0.85 with a
0.15 margin, a family answer, or a model choice. The research contract (decision 0002) fixed
the types (`CraftResolver`, `CraftResolution`) but not the algorithm. The answer stream until now
matched whole aliases in the question and returned the longest match. Building it raised
choices the plan leaves open, and the import rules (`LAYER_IMPORTS`) decide where each part can
live.

## Decision

1. **Homes.** The pure index (`services/craft_index.py`) and the pure ranking
   (`services/craft_matching.py`) take plain records and return contract models, so every rule
   is tested without a database. `services/craft_resolver.py` is the database shell: it loads
   the index, keeps it in a `CraftIndexStore` the app owns (`app.state.craft_index`, five
   minutes; no module-level cache), and runs the pgvector query. `services` may not import
   `providers`, so the query embedding is passed in as a `TextEmbedder`;
   `providers/embedding.router_embedder` is the one adapter that embeds through the AI router.
   `knowledge_view.match_aliases`, `alias_rows` and their module cache are deleted.
2. **Fuzzy in Python, not `pg_trgm`.** The owner's item names rapidfuzz, and the index (about
   1,400 keys for the 455 master crafts plus synced crafts) fits in memory; one question takes
   about a millisecond. `FUZZY_MIN_SIMILARITY` moves from 0.45 to 0.85: 0.45 was calibrated for
   trigram similarity, and with `ratio` it let 88 unrelated crafts into "What mordant is used in
   dyeing cotton?". At 0.85 one typo in a word of five letters or more still matches (`ajrak`
   to `ajrakh` 0.91, `kalamkri` 0.94, `dokra` to `dhokra` 0.91) and question words do not.
3. **Scores, not reciprocal ranks.** Rank fusion gives scores that cannot be compared with the
   absolute accept rule (0.85, margin 0.15). Each signal keeps an interpretable score: exact
   kinds fixed (name 1.0, alias and merge 0.97, shared spelling 0.95, so a curated alias
   outranks a shared code spelling), fuzzy `0.95 * ratio`, family `0.7 * ratio`, semantic
   `0.8 * cosine`. Fuzzy can resolve a clear typo; family and semantic alone never can. A
   second kind of signal agreeing adds 0.05.
4. **Containment.** An exact hit inside a longer exact hit is dropped, and fuzzy, family and
   place matching use only the words no exact hit explains. Otherwise "Kutch Ajrakh" would also
   raise every craft with the alias "Ajrakh" and never resolve. Place words are hints, not
   names: they are not fuzzy-matched against craft names.
5. **Family.** Many crafts carry only a qualified name (`Bastar Dhokra`, `Bengal Dokra`), so
   "dhokra" matched nothing. A distinctive token of at most 8 crafts gives a `FAMILY` reason.
   Words that name a kind of craft (`weaving`, `embroidery`, `painting`...) are listed in
   `GENERIC_TOKENS` and never form a family; the list is a judgement to extend as match cases
   are collected.
6. **Region.** A boost that only adds cannot separate two crafts that share an alias. When the
   question names a place and at least one candidate is practised there, scores become
   `0.8 * score + 0.2` for candidates in that place and `0.8 * score` for the rest. When no
   candidate is practised there, nothing changes, so a single exact match is not lost because
   the learner named another state.
7. **Semantic only when needed.** The query is embedded only when the lexical ranking has no
   clear winner and some craft has an embedding, so a named craft costs nothing. The craft
   side embeds the name, local name and aliases (`descriptor_text`), as the owner's item says
   ("craft name+alias embeddings"). `app/scripts/embed_craft_descriptors.py` fills missing
   ones; scripts may now import `providers` (`LAYER_IMPORTS`), since scripts are entry points
   like the API.
8. **One candidate is AMBIGUOUS.** The contract had `AMBIGUOUS` at 2-5 candidates, which left a
   single sub-threshold candidate (a family hit, or a typo in a short name) nowhere but `NONE`.
   It is now 1-5: the web client already renders any number of pills, and a one-pill "Which
   craft?" is better than asking the learner to name the craft again. Contract, stream model
   and tests changed together.
9. **Failures.** A failed embedding is not hidden: the stream sends one `error` event ("Finding
   the craft failed just now...") and `done`; the log keeps the detail.

## Consequences

- The weights and thresholds are named constants in `craft_matching.py` and `craft_index.py`;
  PLAN 5.2's gate (300 match cases, top-1 at least 95%) is what should tune them, and is not
  built yet (`docs/TECH_DEBT.md`).
- Semantic matching returns nothing until `embed_craft_descriptors` has run against the
  production database; no workflow runs it yet (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
