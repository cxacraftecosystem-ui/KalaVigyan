# 0108. An approved structure proposal becomes a curated fact of its dossier

A structure proposal carries one piece of structure and the fact that states it, is reviewed as
structure, and becomes a curated fact of its dossier when approved. The dossier export follows the
database.

Date: 2026-11-20. Status: accepted (round 6, structure writes; the owner asked that contributors
deliver everything through MCP). Builds on decisions 0053 (the database is the source of truth and
the dossiers its export) and 0101 (contributions through the gates).

| For | Read |
|---|---|
| What amended it | [0111 Twenty-one MCP tools in six groups, with small schemas](0111-fewer-mcp-tools.md): the tools it names; its gates and contracts stand |
| What amended it | [decision 0162](0162-unused-craft-page-chapters-retired.md): an approved glossary term's shared entry and an approved reaction's science row are written at approval |
| What it builds on | [0053 Curated dossiers are imported on deploy and served as one craft page](0053-curated-dossier-import.md): the database as the source of truth and the dossiers as its export |
| What it builds on | [0101 One knowledge architecture for every craft: facts, sections, components, monographs](0101-knowledge-architecture-for-every-craft.md): contributions through the gates |
| Every decision, by group | [README.md](README.md) |

## Context

The structure a craft page draws (a stage's after and why, native names, reactions, botanical
names, glossary terms, conflicts, open questions and the GI record) entered only by bulk import of
a dossier. Contributors through MCP and the Knowledge API need a way in that keeps the page and
its dossier export consistent.

## Decision

1. **One proposal, one piece of structure, one stating fact.** `propose_structure` and
   `POST /api/knowledge/structure` take a piece of a curated craft's or family's page and the fact
   that states it. The checks run in order: STATED (every name, colour and number the piece gives
   is in one of its quotes), then the QUOTES and SOURCE gates, after the piece is checked against
   the dossier's models and the page (unknown stage or material, a name the page already has, a
   conflict with what it holds).
2. **Reviewed as structure.** Proposals wait in the STRUCTURE kind of the review queue for a
   Professor or above; a Professor's own proposal is written at once.
3. **Approval writes a curated fact.** Approval locks the page, re-checks it (409 when the page
   moved on) and writes the stating fact as a curated fact of the dossier: the next C key, the
   CuratedClaim marker, its quotes recorded as found by curation, and the structure row the page
   reads. The proposal keeps the proposer's channel in its origin. A source already kept by
   another dossier is copied into this dossier's own row, and approval is refused with 409 when that
   page is named by its DOI.
4. **The export follows.** Exporting the dossier writes the new fact, its quote and its source; a
   later import of that export moves the quotes onto the import's own source row.

## Consequences

- A categories page takes no structure proposals yet (crafts and families only; a craft without a
  curated page is refused with 422).
- An approved glossary term has no shared glossary entry (`termKey` stays null), and an approved
  reaction gets no stored science row, until the dossier is exported and imported again.
- Approval, hiding and retraction refresh the signed-out pages at once through the web app's
  revalidation route (`WEB_REVALIDATE_SECRET`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-20; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
