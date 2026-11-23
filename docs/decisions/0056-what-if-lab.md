# 0056. The what-if lab's builder

The what-if lab's builder offers one input per block, a stage's materials that stored data relates
as alternatives, and assembles each outcome on the server from cited relationships. The model only
chooses, a hypothesis is labelled as one, and every block is checked against the rows when built and
when reused.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| What amended part of it | [0140 Voice and Listen hold their state in the bucket, bill what they hear and read the lede first](0140-voice-and-listen-kept-true.md): a hypothesis outcome is not read aloud |
| The contract it was built to | [0054 Phase C contract: generated explainers, the what-if lab, zoom, timelines and film mode](0054-phase-c-contract.md) |
| The review that fixed it | [0061 Phase C review fixes](0061-phase-c-review-fixes.md) |
| What amended part of it | [0152](0152-matter-read-once-and-the-science-seed-kept-true.md): One what-if per stage and pair of choices in an answer |
| Every decision, by group | [README.md](README.md) |

## Context

Plan section 4 feature 5 and decision 0054 point 8 fixed the `what_if` block: one input per block,
each option's outcomes stored claims relating it to a result or a stored reaction of its compound,
an option without one unknown. The renderer is decision 0059's. Nothing built one. Owner rules
bind: every outcome is a cited stored claim, a model only chooses, untrusted text stays inside
untrusted blocks, no connection is held across the model call (decision 0040), and builders spend
only from the answer's headroom (decision 0050).

## Decision

1. **A builder in the registry.** `services/what_if_builder.WhatIfBuilder` is the `what_if` entry
   of `BLOCK_BUILDERS` for process, chemistry and geography-and-water sections (`WHAT_IF_FIELDS`),
   waiting 20 s for two short reads and one plan-model call. It is listed after the expert panel,
   in `PIECE_BLOCK_ORDER` order. The kind does not join `BUILT_BLOCK_KINDS` here: decision 0059
   point 1 leaves that to the review (0061), so until then `from_registry` does not start it.
2. **An input is a stage's materials that stored data relates as alternatives.** The craft's
   process rows (`craft_matter`) group each stage's materials by role; a group is a candidate
   only when a sentence of the section names one of its materials (`first_naming`: its name, a
   glossary term's label, alias or local name, or a marked term). Within a group, two materials
   are alternatives when a fact-level `CONTRASTS_WITH` relation claim joins their concepts, or
   when a stored text names both with an alternative word between them
   (`research/alternatives.alternatives_named`: `or`, `instead`, `rather`, `versus`, `replaced`,
   `superseded`, `substituted`, ... within three words, a comma list joining a run). The texts
   are the stage's name and the fact-level claims of the stage, of every material used at it, of
   the options' concepts and of the section. Each joined part of two or more materials is an
   input, at most four, in order of first mention; an input has at most six options. Co-ingredients
   ("clay, millet flour and lime") are never offered as alternatives.
3. **Outcomes are assembled by the server from cited relationships.** For each option, in this
   order and at most eight: the relation claims on an edge touching its concept whose relation is
   one of `OUTCOME_RELATIONS` (decision 0054's `CONTRASTS_WITH`, `AFFECTED_BY`, `DEPENDS_ON`,
   `ENABLES`, `PRODUCES`, widened here to `CAUSES`, `PREVENTS`, `MODIFIES` and `REQUIRES`, which
   state effects as directly), by that order; then the fact-level claims on its concept; then the
   claims a stored reaction holding its compound cites through a linked passage and that name the
   option or the compound, with `reactionId`. A claim is offered once per option. One short
   session (`services/what_if_evidence`) reads the relation and concept claims after the process
   rows and before the call; `USES` edges are not outcomes.
4. **The model only chooses.** One plan-model call (`composer/what_if`) answers
   `{input, changed, options[{option, outcomes[]}]}` by ref; every stored text (question, section
   title, stage, option names, statements) is inside untrusted blocks and the server's lines carry
   only refs, the relation and whether a statement is a hypothesis. The server keeps the chosen
   input's options in its own order: an option with no offered outcome is unknown and always shown
   with none, whatever the reply gives it; a known option keeps the offered refs the reply lists for
   it (at most three, each once) and is left out when none is left; an outcome ref that is not one
   of that option's stored claims is dropped. A reply listing an option of another input changes two
   inputs at once and is refused whole (`two_inputs_changed`). The input's words (`changed`) are the
   model's, at most 80 characters, and every content word must be a stem the input's stage, role,
   option names or offered statements use; the block's validators then refuse an unstated figure.
   Fewer than two options, or no option with an outcome, adds nothing. Options are always stored
   materials (`materialId`); the builder never makes a glossary or unstored option.
5. **A relationship that is a hypothesis is labelled as one.** A relation claim or a reaction's
   claim at `HYPOTHESIS` may be an outcome; its sentence keeps the stored level, so the reader sees
   the Hypothesis badge (`ExplainerSentence` now marks `HYPOTHESIS` beside Verified and Reviewed,
   decision 0037 point 5 widened). A hypothesis about the option itself (a concept claim) is never
   offered. `WhatIfBlock` checks its outcomes with `blocks.require_findings` (stored levels, each
   sentence once) instead of `require_facts`; this relaxes decision 0054's "facts only" for this one
   kind, as PLAN section 0 keeps evidence levels as labels. No stored version-1 payload changes
   meaning: every payload valid before is valid now.
6. **Re-checked against the rows when built and when reused.** `science/what_if_check.what_if_problems`
   refuses a block whose stage is not stored, whose material option is no longer a stored material
   of the craft, is renamed or is no longer used at the stage, whose reaction outcome's reaction is
   not stored, holds no compound of the option or is cited through no linked passage, or that has a
   glossary option (which the rows cannot re-check). The builder runs it after building, and
   `piece_store` runs it on reuse beside ladders and players (`WhatIfBlock` in `PROCESS_BLOCKS`,
   `process_problems` now public so the seam is tested). The piece is the section's slot.
7. **Small shared changes.** `quotes.spans_in_key` gives every whole-word occurrence of a name
   (`occurs_in_key` shares its pattern); `builder_evidence.known_claim` is a stored claim view at
   any level with its citations (`known_fact` is it at fact levels).

## Consequences

- Nothing a reader sees changes until the review joins `what_if` to the built kinds. After that,
  a process, chemistry or water section that names a stage's material shows one what-if when the
  craft's stored data relates that material's alternatives, at the cost of one plan-model call
  from the answer's headroom (Master Admins uncapped). Kutch Ajrakh's red dyeing offers madder,
  synthetic alizarin and, once curated, al root (unknown).
- Tests reproduce the fixture's madder and alizarin options from the seeded rows and a reply
  written to the published structured-output shape, and check that an outcome without a claim is
  dropped, an option without evidence is unknown, two inputs at once are refused, a hypothesis
  relationship is labelled, the input's words are its texts', and stored blocks are refused once
  their rows change. Database tests (marked `db`) read the seeded relationships and rebuild the
  fixture's options from the seeded database.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
