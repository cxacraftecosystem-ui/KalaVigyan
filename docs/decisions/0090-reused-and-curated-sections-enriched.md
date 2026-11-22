# 0090. Reused and curated sections are enriched like researched ones

Curated sections are the Expert floor and stay current, and a reused or curated section is enriched
like a researched one, a rebuilt reaction player replacing the stored one. Expert reaches every
stored field, builders reach more fields, and the ledger keeps decision 0080's rules.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| Which piece is curated, by its claims (amends item 2) | [decision 0142](0142-curated-crafts-read-only-curated-rows.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked "explain how Ajrakh works in the most complete comprehensive exhaustive detailed
description manual from all the angles ..." twice at Expert depth (answers ef92a342 and 2ec5df92)
and judged the result "not upto the mark, no interactive pieces, no chemical breakdown apart from
one compound name, no wow moments at all". Both answers were the curated dossier's craft-page
overview reused word for word: the question names no glossary term, so every field fell back to
the craft's topic key, the key the curated overview is stored under at `EXPERT` depth, and no
field was researched or composed. Reused sections ran only the seven `rebuilt_on_reuse` builders
and never a ladder; reused prose kept the dossier's own term marks, so no concept graph and a thin
quiz; the understanding chose seven fields although the dossier holds claims in eleven; "works",
"politics" and "geography" cued nothing, so the process came last; and one molecule per section was
the limit. The claim ledger was not a cause: no other block was ever built for it to drop.

A first version of this decision also loosened the ledger (cards and expert takes dropping repeated
text only) and rebuilt every reused section's builders one section after another. Its review found
that re-asking showed two identical reaction players (and in Postgres one more on every ask), that
the loosened ledger brought back the word-for-word and restated repeats decision 0080 removed, that
a Basic or Detailed answer on a curated craft waited for each reused section's slowest builder in
turn, and that the curated overview was superseded by the first Expert answer for good. This text
is the corrected decision.

## Decision

1. **Curated sections are the Expert floor.** At `EXPERT` a reused group whose craft pieces no
   answer made is not reused as settled (`services/reuse_enrichment.expert_floors`). Its blocks are
   placed and streamed first, re-marked with the answer's glossary, and the field is researched as
   a deepening of them (`SectionContext.floors`, `floor_deepening`): the composer's sentences whose
   claims the floor already cites are left out, the composed heading replaces the fallback, and
   the builders run over the floor and the new blocks together. Each floor is sent before its
   section waits for a research slot (`SECTION_CONCURRENCY`), and a failure while sending it stops
   that section alone. A section whose floor shows something is not researched again on the web
   for composing nothing new. The kept group holds copies of the floor (reuse mark cleared) beside
   what was built.
2. **Curated pieces stay current.** An answer's keep never supersedes a piece no answer made
   (`piece_store._supersede`, and the test store the same way), so the craft page, the district
   page and compare keep reading them and they serve reuse again once the answer's group goes stale.
   Reuse takes a group an answer made before a curated group of the same field
   (`research/piece_reuse.answered_first`), so the next ask, at any depth, reuses the richer group
   and an Expert ask is floored only while no answer has built on the curated pieces.
3. **A reused section is enriched like a researched one.** `BlockBuilders.for_reuse(shown, depth=)`
   runs every builder of the field whose kind the group does not already show, and the
   `rebuilt_on_reuse` ones whatever it shows, except that the generated explainer and the expert
   panel, the two longest model calls, run on reuse only at Expert (`BuilderEntry.reused_from`).
   Every reused section's builders start at once, before the headings are awaited; the placed
   blocks of all of them are sent, then each section's additions in reading order. A reused
   `PROCESS` section without a stored ladder is led by one built from the stored stages whose claims
   its blocks cite (`reuse_enrichment.reused_ladder`, no model call). Placed blocks are term-marked
   again (`placed_section`).
4. **A rebuilt reaction player replaces the stored one.** The reaction player is rebuilt on every
   reuse from the process rows (no model call), so stored players pick up what decision 0088 added;
   its entry `replaces_stored`, so a reused group's stored player is left out of the placed blocks
   and of the copies and the rebuilt one takes its place. A reused group is kept again only when it
   gained a storable block it does not already store (`Placed.stores`, by kind and by content with
   sentence ids and term marks set aside, `knowledge_pieces.shows_alike`): a rebuilt player equal to
   the stored one keeps nothing, so nothing is inserted, superseded or embedded again.
5. **Every stored field at Expert.** The understanding's fields are joined, after them, by every
   field with at least `FIELD_CLAIMS_MIN` (3) visible curated claims for the craft
   (`services/stored_fields`, `AnswerStore.fields`), only at `EXPERT`, only for a model reading,
   never for a follow-up.
6. **Builders reach more fields; craft-level stories are built once.** `seasons` joins `PROCESS` and
   `GEOGRAPHY`, `supply_map` joins `PROCESS` and `ECONOMICS`, `zoom_story` joins `CHEMISTRY` and
   `PROCESS`, `timeline_map` joins `ECONOMICS` and `GEOGRAPHY`. The craft-level stories
   (`claim_ledger.ONCE_PER_ANSWER_KINDS`: region story, seasons, supply map, zoom) are built once per
   answer: an answer's builders share the kinds taken (`BlockBuilders.for_answer`), the first
   section whose builders start builds one, a reused section that shows one takes it, and a builder
   that adds nothing gives it back. The ledger shows each once per answer as well. A timeline and a
   what-if are built from their section's own claims, so each field may show its own.
7. **The ledger keeps decision 0080's rules.** Prose, card facts and expert takes drop a sentence
   whose text or every claim was already shown; a card left with no fact is not shown, whatever it
   names; an "experts differ" pair goes when either view was already shown. Added once per answer:
   one generated explainer per folded concept, and the craft-level stories of point 6.
8. **More molecules.** A section draws up to `MOLECULES_PER_SECTION` (3), one per CID, in order of
   first mention and then, in `CHEMISTRY`, the compounds of every stored reaction of the craft.
9. **Question cues.** "how <the craft> works", "how does <the craft> work" and "how it works" ask for
   the process, so the owner's question leads with it; a bare "work" does not ("How does the GI tag
   work for Ajrakh?" keeps its order). "politic*" cues economics and history; "geograph*" and
   "भूगोल" cue geography. A bare "how" is not a cue: "How does the water of Kachchh shape Kutch
   Ajrakh?" must still lead with its geography.

## Consequences

- The owner's question, rebuilt from the curated dossier with fake model replies and fake builders
  that tell each field's blocks in that field's own words
  (`tests/answering/test_owner_expert_question.py`), leads with the process (its ladder from the
  curated stages first), researches every field on top of the curated prose, covers the stored
  fields the model left out (materials, botany), and shows the ladder, the reaction player with the
  stored equations, one material card, one molecule, the region story, supply map, seasons and zoom
  once each, a generated explainer, a concept graph, one market card for the craft, an expert seat,
  a timeline and a what-if in each field that tells one, and a quiz. The what-if, timeline, supply
  map, seasons, zoom, explainer and expert blocks there are the contract fixtures, not Ajrakh rows:
  in production each shows only when Ajrakh's stored rows support it (the dossier holds no
  relationship claims for a what-if, and two `CLIMATE` claims, below `FIELD_CLAIMS_MIN`, so no
  climate section).
- Asking again reuses the first answer's groups with one reaction player each time, and keeps
  nothing new (`tests/answering/test_owner_asks_again.py`); a stored player that plays less than the
  rows is replaced and kept once.
- A Basic or Detailed answer on a curated craft waits for the slowest builder of its reused
  sections, not their sum, and never for a generated explainer or the panel.
- A craft-level story given back after every other section that could build it has already started
  its builders is not built in that answer; the next answer tries again.
- An Expert answer on a curated craft makes about two model calls per field (plan and compose) and
  each craft-level story's calls once; a floored field is not researched a second time.
- The district page and compare read the newest current prose piece per craft and field, which is
  the answer's copy while it is current and the curated piece again once the copy goes stale.
- The ledger tests of decision 0080 state its rules again (`tests/ledger`): the recorded Indigo
  answer keeps one Indigo card and two expert seats with no repeated sentence.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
