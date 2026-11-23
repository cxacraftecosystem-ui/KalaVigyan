# 0064. Quiz, compare and the shared-science explorer

The quiz, compare and the shared-science explorer are built with no model choosing anything: a quiz
is made on request, a comparison is understood and compared per field, and the concept graph follows
the terms a section marks. Reads have sane limits.

Date: 2026-11-18. Status: accepted. Amended by 0070 (a comparison with nothing
cited answers 204; the quiz reads hidden marks) and 0143 (compared crafts named outside the
resolver's list, fields by what a claim is filed under, the stored shared-term summary).

| For | Read |
|---|---|
| What amended it | [0070 Phase D review fixes](0070-phase-d-review-fixes.md): a comparison with nothing cited answers 204, and the quiz reads hidden marks |
| What amended it later | [0143](0143-lessons-exports-and-follow-ups-kept-true.md): compared crafts named outside the resolver's list, fields by what a claim is filed under, the stored shared-term summary |
| What counted and paged a node's crafts | [0161](0161-listen-falls-back-a-node-counts-admins-see-hidden-facts.md): `craftCount` on every node and the crafts route |
| The contract it was built to | [0062 Phase D contract: learning blocks, versions, alerts, lessons, exports and the map](0062-phase-d-contract.md) |
| The contracts it names | [learning.md](../contracts/learning.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0062 fixed the phase D fields of `quiz`, `compare` and `concept_graph` and the
shared-science routes (`docs/contracts/learning.md`); decision 0068 drew the three kinds. This
lane builds them: a quiz made for an explainer from its own cited claims, crafts compared side by
side from stored claims and pieces in a comparison answer and on a compare screen, and the
concept graph of what crafts share, in answers and for researchers. Rules that bind: every fact
cited, a model may only choose and order, guards fail closed, and nothing waits on a model while
a database connection is held (decision 0040).

## Decision

1. **No model chooses anything here.** The contract allowed a model to choose quiz sentences,
   compare rows and graph terms. Fixed server rules choose instead (`research/quiz.py`,
   `research/craft_compare.py`, `research/shared_science.py`, `research/offered_facts.py`), so
   these blocks cost nothing, never touch the router or the reader's caps, are the same for every
   reader and are testable by hand. A fact is ranked by its level, its most reliable source, how
   many distinct sources state it, then its text (`fact_rank`).
2. **The quiz is made on request, never streamed.** `GET /api/answers/{answerId}/quiz` builds it
   from the asker's stored explainer of that answer (every version's answer holds the whole merged
   document), and lesson packs call the same `quiz_block`. A sentence is quizzed only while every
   claim it cites is still shown, so a withdrawn claim is never taught. Questions go round the
   sections in turn, one per sentence and one per term; the key is a marked term of three letters
   or more; distractors are terms marked in other sentences that cite none of the keyed claims and
   that the keyed sentence and its quotes never name, two or three of them, picked walking on from
   the keyed sentence so nearby terms come first. Options are sorted by text (the renderer sorts
   the same way), so the key's place gives nothing away. `quiz` stays out of `BUILT_BLOCK_KINDS`.
3. **A comparison is understood, not guessed.** The understanding reply gains `compare` (the
   listed crafts the question sets side by side, in its order), and `Understanding.compared`
   holds up to three crafts beside the lead craft, which is the first compared one, or the
   reader's pick when it is among them. Ambiguity offers stay offers. `PlanRequest.compared`
   carries them to the builders; research and composition still run for the lead craft only.
4. **Compare is per field.** In an answer each section shows the rows of its own field (at most
   four); the compare route shows every field or the ones asked. Per field: up to three term rows
   for glossary terms at least two crafts share, each cell the craft's best fact naming the term
   (claims about the term's own concepts first), then one row of the field's best remaining fact.
   A row needs two filled cells, so a field with claims on fewer than two sides is not compared; a
   claim is never shown twice. A claim's field is its curated discipline, else its concept type's
   (`services/craft_page.CONCEPT_TYPE_DISCIPLINES`, shared with the craft page); family concepts
   and relations are left out. The first fully visible sentence of a craft's newest current prose
   piece of a field leads that field and carries its `pieceId`.
5. **The concept graph follows the terms a section marks.** A node is a glossary term the answer's
   craft and at least one other craft each back with a cited fact-level claim about their own
   concepts of that term that names it; a craft without one has no edge. The builder adds at most
   four nodes to `CHEMISTRY`, `PHYSICS`, `MATERIALS` and `GEOGRAPHY` sections, in order of first
   mention. The explorer route keeps the contract's 24 nodes and adds `?craft=` to the one-term
   route, so a craft's page lists the others after itself (the fixture's `concept` node).
6. **Sane limits on reads.** The craft explorer scans the first 48 shared terms by label; a term
   reads at most 100 crafts (the focus first, then by name) and three claims per concept, those
   naming the label first, ranked in SQL by a window function; compare reads at most 60 current
   pieces. Every read is one short session with no outside call.
7. **Compare and the concept graph are built.** Their renderers existed (0068), so both joined
   `BUILT_BLOCK_KINDS` on both sides, rebuilt on reuse and never stored: `piece_store.storable`
   leaves out every `UNSTORED_BLOCK_KINDS` block, and both follow `timeline_map` in
   `PIECE_BLOCK_ORDER`.

## Consequences

- After the deploy a comparison question (the understanding model names two listed crafts) shows
  a comparison in each section, and chemistry, physics, materials and geography sections show
  what other crafts share; both read stored rows only. The quiz, compare and explorer routes are
  live for the screens lane (0069): `quizContract.ts`, `compareContract.ts` and
  `sharedScienceContract.ts` name them, with `learning.quiz.golden.json` and
  `learning.compare.golden.json` pinned on both sides.
- No migration and no data run: the glossary links (`TermCraft`, `TermConcept`) the seed and the
  curation import already write are all the explorer needs.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
