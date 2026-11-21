# 0033. Stored knowledge pieces and reuse

Every finished block is stored as a knowledge piece and reused when its facet and a topic key
derived from data match, checked again at read time and failing closed. A claim change marks pieces
stale through a trigger, a newer piece supersedes the older one, and a nightly job rebuilds.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| What amended it | [0096 Every piece built for a reader's question joins its craft's page, whoever asked](0096-reader-question-pieces-join-their-craft-page.md): stored pieces served only to answers |
| The contract it was built to | [0030 The explainer contract](0030-explainer-contract.md) |
| The review that fixed it | [0038 Phase A review fixes](0038-phase-a-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

`docs/plans/answer-experience.md` section 2.2 (owner-approved, section 8 final) stores every
finished block as a knowledge piece so the next relevant answer reuses it: looked up by craft,
facet and topic key, then by embedding similarity; reused when facet and topic match, its depth is
at least the asked depth and every claim it rests on is still visible and not retracted; streamed
first and marked "From earlier research" with its date; research runs only for facets without a
reusable piece, or for all when the reader asks for fresh research. A retraction or a level change
stales the pieces resting on the claim, the next answer rebuilds them, and a nightly job rebuilds
stale pieces for the most-asked crafts. Structured parts also land in their natural homes: process
stages in the science tables. Decision 0030 fixed the piece model, the content hash, topic keys,
the reuse rule and the staleness vocabulary; decision 0032 built the sections and their blocks.

## Decision

1. **Table.** `KnowledgePiece` (migration `0015_knowledge_pieces`) holds the contract's fields
   with CHECK constraints over `BLOCK_KINDS`, `DISCIPLINES` and `EXPLAINER_DEPTHS` (the pattern of
   `0012_images_and_terms`, not new Postgres enum types), `claimIds` as `uuid[]` with a GIN index,
   `sourceIds` as `text[]`, both non-empty, and `embedding` (1536, no ANN index: candidates are
   filtered by craft, facet and topic first, so the few that remain are ordered exactly). RLS is
   on and the public roles revoked, as for every table.
2. **Staleness is a trigger on `Claim`.** `kv_stale_resting_pieces` sets `staleSince` on every
   piece whose `claimIds` hold the claim when its status moves into a hidden status (`DRAFT`,
   `REJECTED`, `RETRACTED`), or its level, text or sensitivity changes, or it is deleted
   (`PIECE_STALE_CHANGES`). Today no route retracts or reviews a claim; the review lane, the
   seeds, operators and any later writer are all covered without having to remember a call. A
   test checks the migration's lists against `models/enums` and `research/retrieval`, and DB
   tests check each change (and that filling a vector does not stale anything).
3. **Reuse is checked again at read time, failing closed.** A piece is reused only when every
   claim it rests on is visible now (`knowledge_view.claims_by_id`), still carries every citation
   the block shows, at the level the block shows (`research/piece_reuse.visible_as_cited`), and a
   stored `process_ladder` still passes `science/ladder.ladder_problems` against the craft's
   process rows. A piece row that no longer validates as a `KnowledgePiece` is logged and skipped.
4. **Topic keys come from data, never from a model.** Each facet has one namespace
   (`research/piece_topics.FACET_NAMESPACES`: `PROCESS` is `process`, `CHEMISTRY` `reaction`,
   `GEOGRAPHY` `water`, ...). The subjects are the glossary terms the question names (the
   server's `TermMarker` over the craft's glossary, the craft's own name left out), else for the
   place facets (`GEOGRAPHY`, `GEOLOGY`, `CLIMATE`) the craft's districts, else the craft's slug:
   "Why does alum fix alizarin in Ajrakh?" is `reaction:alizarin+alum`, "How is Kutch Ajrakh
   made?" `process:kutch-ajrakh`, and Kutch Ajrakh's water `water:kachchh` (the golden piece). A
   question naming different terms gets a different topic, so a stored alizarin block never
   answers an indigo question; the same question asked again finds its piece. The question is read
   as written, so a question in an Indian script matches only the glossary's local names; no extra
   model call renders it first.
5. **A section is reused whole.** The unit of reuse is the set of pieces one answer stored for one
   facet (its ladder and its prose), placed ladder first, and refused whole when any of them fails
   the rule. Among several reusable sets the one whose piece is nearest the question's embedding is
   chosen (cosine distance over the stored vectors; ties and missing vectors keep the newest). The
   embedding call is made only when more than one set qualifies.
6. **Stored as built, in English, with their own sentence ids.** The answer keeps each section's
   English blocks (`SectionOutcome.built`) and stores every block that cites claims and sources
   (`prose`, `process_ladder`). Sentence ids are renumbered `p<piece id prefix>.<n>` when stored, so
   a reused block placed next to newly built ones never shares a sentence id (Listen highlights by
   sentence id), and the content hash stays the same wherever the piece is placed, which also keeps
   Listen's narration cache shared across answers. Piece ids are derived from the answer and block
   ids, so storing is idempotent. `images` blocks rest on illustrated claims, not citations, and
   cannot be pieces under the 0030 contract; their pictures stay stored as `MediaRef` rows.
7. **Supersession.** A newly stored piece supersedes every earlier current piece of the same
   craft, facet, topic and kind whose depth is at most its own, stale or not; a fresh-research
   answer therefore replaces what it bypassed, and a Basic piece gives way to an Expert one but
   never the reverse.
8. **Stream and flow.** After the sections are known and before planning, the answering service
   asks the piece store; reused sections stream first (a `trail` `FOUND` per piece with its
   `storedAt`, `section_started` in `WRITING`, their sources, the placed blocks translated like
   any block, `section_done READY`), then only the open sections start `RESEARCHING` and share the
   depth's budget. `AskRequest.fresh` (default false) makes the lookup reuse nothing; the explainer
   offers "Research again" once an answer that showed earlier research is done. Answers for any
   craft neither reuse nor store pieces (no craft to key them by).
9. **New cited stages.** When a `PROCESS` section's prose cites claims on the craft's own
   `PROCESS_STAGE` concepts and the craft has no stored process at all, those concepts become one
   process (`Live research process`, variant `live_research`) with stages in the order the section
   first cites them (the model orders, the server fills names and links from the concept rows),
   under an advisory lock per craft, so the craft page's Process tab and later ladders use them. A
   craft that already has a process is left unchanged: where a new stage sits among stored stages
   is not something any source has stated. Withdrawn by decision 0038: the order of a whole new
   process is not stated by any source either, so answers no longer write process rows.
10. **Nightly rebuild.** `app/scripts/rebuild_pieces` runs in the Coverage enrichment workflow
    before the enrichment, under the same `ENRICHMENT_DAILY_BUDGET_USD`: its model calls are
    tagged `enrichment-rebuild-<id>`, so the day's spend counts them. It lists stale, unsuperseded
    pieces of the 10 crafts most asked about by signed-in readers in the last 30 days
    (`services/piece_rebuild.stale_groups`) and answers each stored question again for its facet,
    at its depth, with fresh research and the asker's name withheld, as a system principal held to
    the depth's per-answer cap; it stops when less than the reserve is left or spend is refused.

## Consequences

- A second ask of a covered question on a covered craft and facet costs one understanding call
  and no research; Listen of a reused block hits the narration cache.
- Topic keys are strict: a rephrasing that names other glossary terms researches again (accuracy
  over speed); the debt register lists what would widen matching.
- Pieces store no follow-ups. Since decision 0039 an answer made only of reused sections offers
  the stored follow-ups for the headings its pieces' claims do not cover, and a reused section
  gets pictures searched from its blocks' claims, as a researched one does.
- Items left below standard are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
