# 0142. A curated craft reads only its curated rows, stored pieces keep one curated rule, and the generated explainer works within a budget

A craft with a curated dossier keeps its seed claims and seed process archived, not deleted; a
dossier removed from the folder is retired by an explicit step; a curated glossary meaning is the
term's stored summary; one rule says which stored piece is curated; the nightly rebuild rests a
group it tried and spends no more than the day has left; the generated explainer drafts within a
budget, skips a section that states no quantity, may draw a dataset row and says why it added
nothing; a facet finds claims by their discipline; and a ladder numbers only stages a source
orders.

Date: 2026-11-22. Status: accepted (the lead's debt lane brief "curated import, stored pieces and
generated explainers", and the owner's decision of 2026-11-22 to retire the seed rows of crafts
with curated dossiers). It amends [decision 0053](0053-curated-dossier-import.md) (the import),
[decision 0033](0033-knowledge-pieces-and-reuse.md) (the nightly rebuild),
[decision 0055](0055-generated-explainers.md) (the builder's wait) and
[decision 0090](0090-reused-and-curated-sections-enriched.md) (item 2, which piece is curated). The
contracts are `docs/contracts/curation.md` (The import), `docs/contracts/science.md`,
`docs/contracts/explainer.md` (Generated explainers as built; the stream's `trail`),
`docs/contracts/craft-page.md` (Readers' or curated), `docs/contracts/research.md` (the nightly
piece rebuild) and `docs/contracts/retrieval.md` (`facets`).

| For | Read |
|---|---|
| The import it amends | [decision 0053](0053-curated-dossier-import.md) |
| The stored pieces and rebuild it amends | [decision 0033](0033-knowledge-pieces-and-reuse.md) |
| The generated explainer it amends | [decision 0055](0055-generated-explainers.md) |
| The curated-piece rule it replaces (item 2) | [decision 0090](0090-reused-and-curated-sections-enriched.md) |
| The page merge that told curated pieces by their claims first | [decision 0096](0096-reader-question-pieces-join-their-craft-page.md) |
| Retiring a dossier also removes its places, GI record, prices and workforce rows (amends item 2) | [decision 0171](0171-imports-keep-approvals-and-differences-settle.md) |
| The debt it clears and what it leaves | [TECH_DEBT.md](../TECH_DEBT.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Twelve debt entries of the 2026-11-22 register and one finding of the live Khurja test
(answer 504968ea-49cc-469c-88f9-205a2ea90e8a: two sections' simulation builders each ran 150 s and
added nothing) were left to this lane. The register's entry on seed rows waited on the owner, who
decided on 2026-11-22 that a curated craft's seed rows are retired: archived, never deleted, read by
no page, search or answer, and restorable. Five choices had real alternatives.

## Decision

1. **Retiring seed rows is a status and a mark, done by a reversible migration, the seed and the
   import.** A seed claim (marked by the seed's own review event, `seed import <id>`) about a
   curated craft's concepts or their edges becomes `SUPERSEDED`, with a review event that keeps
   the status it had; the craft's `Seed process` gets `Process.archivedAt`, which every reader of a
   craft's processes filters (`models.science.live_process`). Migration 0067 does it for the rows
   on production and its downgrade restores each claim to the status its retirement event kept and
   clears the mark; `seed_claims` and `import_curation` run the same step after they write, so a
   later seed or a newly curated craft never shows them again. Moving the rows to an archive table
   was refused: it deletes them from the tables the seed would write them back to. Seed concepts,
   edges and passages stay: they are structure and source text, and no claim of theirs is shown.
2. **A removed dossier is retired by name, never by the deploy.** The folder is the database's
   export, so a craft curated over MCP and not yet exported has no file; retiring every craft whose
   file is missing would undo that work. `import_curation --retire <slug>` refuses while the file is
   present, then supersedes the curated claims, marks the overview pieces stale, archives the
   curated process, deletes the `CuratedCraft` row and restores the seed rows the dossier retired.
3. **One curated-piece rule, from the claims.** A piece is curated when it has no answer id and
   every claim it cites is curated (`piece_reuse.curated_piece`); supersession, reuse order, Expert
   floors and the craft page all use it, so a reader's piece whose answer was deleted is superseded
   and shown as a reader's. A new column marking curated pieces was refused: the claims already say
   it, and a column could drift from them.
4. **The generated explainer works within a 60 s budget inside a 75 s wait, and records why it
   added nothing.** Its model calls draft within `SIMULATION_BUDGET_SECONDS` (60 s, the figure
   decision 0055 first gave one code-writing call), a redraft starts only when the time left is at
   least what the first draft took, and the registry waits 75 s (was 150 s), under the expert
   panel's 90 s. A section whose facts state no figure, offer no dataset row and whose concept plays
   no reaction asks no model. Every builder's outcome, blocks shown and seconds are recorded on the
   answer row under `plan.builds`, since the research trail is streamed and not kept; a new trail
   group was refused as a change to the client's contract for a diagnostic. Dataset rows are offered
   only from the datasets the section's blocks already cite, for the craft's first mapped district,
   and an explainer resting on them alone is refused.
5. **Ladders number only ordered stages, and the process route marks the others.**
   `ProcessStageView.ordered` is `false` for a stage no source orders and left out otherwise, so the
   golden files and the client's strict shapes stay as they are; the ladder offers the composer only
   ordered stages, marks an unordered stage it holds `unnumbered` (the field the craft page's ladder
   already carries, so the client draws it unnumbered), and refuses a stored ladder that numbers an
   unordered one, so the composer is never offered a stage without a stated order and its prompt
   needs no change.

Smaller rules follow the entries' own plans: a curated glossary meaning becomes the term's English
`STORED` summary from the curated claims every dossier names for its key; `GiRegistration`, never
written, is dropped by migration 0067 and the catalogue's GI year comes from `CraftGiRecord`; a
facet also reads the scope's claims filed under the discipline its concept types belong to; the
nightly rebuild stamps `KnowledgePiece.rebuildTriedAt` on a group it rebuilt or found empty and
leaves it a week, and holds each rebuild to the smaller of its depth's cap and the day's remainder;
every block sent with a reuse mark gets its piece's `FOUND` trail entry.

## Consequences

- On production migration 0067 retires the seed rows of the curated crafts that have them; from
  `backend/app/data/seed_claims.json` these are five crafts (Bagh Prints of Madhya Pradesh, Bagru
  Hand Block Print, Kutch Ajrakh, Machilipatnam Kalamkari, Sanganeri Hand Block Printing): 916
  concept claims (all `PROPOSED` in the seed), each with one new review event, and five seed
  processes holding 58 stages. Their 330 edge claims were already `WITHDRAWN` and are untouched.
- The migration refuses to drop `GiRegistration` if it holds a row, so a hand-written row is moved
  to `CraftGiRecord` before it is lost.
- An explainer that needed more than 60 s is not shown; `plan.builds` shows how often, which is the
  measurement the register's redraft entry now waits on.
- The client's strict shapes do not yet know `ProcessStageView.ordered`; no screen reads
  `/crafts/{slug}/process` today, and a client that does must accept the field.
- Answers still cannot grow a craft's process: the stages they find carry a planner's names, and
  the register now names the review-screen route that is left.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/db/test_seed_retirement_db.py`, `backend/tests/db/test_knowledge_pieces_db.py`,
`backend/tests/answering/test_reuse_enrichment.py`, `backend/tests/answering/test_piece_rebuild.py`,
`backend/tests/answering/test_builder_spend.py`, `backend/tests/answering/test_block_builders.py`,
`backend/tests/db/test_builder_record_db.py`, `backend/tests/simulations/test_simulation_budget.py`,
`backend/tests/ledger/test_reused_block_trail.py`, `backend/tests/db/test_facet_discipline_db.py`
and `backend/tests/science/test_ladder.py`.
