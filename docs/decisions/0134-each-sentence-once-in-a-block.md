# 0134. A block says each sentence once, and the judge reads it as a reader does

The items one sentence backs (a supply map's materials, a measure's quantities, a market's prices, a
timeline's point and route, a signature figure's facts, a ladder's stages, an expert panel's
differences) are drawn together under that sentence, which is said once; the answer evaluation's
judge reads each block's sentences once in the same way.

Date: 2026-11-22. Status: accepted (lead's round 7 brief, sentence-once lane, from the answer-quality
run 44994632550). The contracts are `docs/contracts/explainer.md` (Block renderers, Each sentence
once) and `docs/contracts/answer-eval.md` (The judge).

| For | Read |
|---|---|
| The ledger rule that lets a story block repeat a sentence within itself | [0127-coherent-answers.md](0127-coherent-answers.md) and [explainer.md](../contracts/explainer.md), One claim, one rendering |
| The evaluation that found it | [answer-eval.md](../contracts/answer-eval.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The judge of run 44994632550 (13 answers on production, 2026-11-22) flagged repeated sentences in 10
of 13 answers. Two mechanisms were confirmed in the stored payloads. A supply map's builder gives
every material link the sentence that names it, and the view grouped links by material, removing a
repeated sentence only within one material: one sentence naming six materials of Jaipur blue pottery
showed five times, once under each material it backed (answer af3f7ac2, `s2.supply.1` to `.5`). A measure's builder makes a row
per stated quantity, each with its sentence: a sentence stating two depths at Ajrakhpur showed twice
(answer d9674645, `p4a920ce999d3.1` and `.2`). The judge reads `cited_sentences`, every copy, so it
saw the same repeats. A survey of every other kind whose items carry a sentence found the same
fan-out in the market prices (one claim stating two prices), the timeline (a point and a route from
one claim), the indigo vat (both forms from one claim, several contents from one claim; the golden
figure itself has both), the firing (a temperature and an atmosphere from one claim), the process
ladder (one claim linked to two stages) and the expert panel (one view differing from two seats).

## Decision

1. **The view groups, the block keeps its items.** The stored blocks are unchanged: each item still
   carries its sentence, so the ledger, translation, citation numbering and every stored payload
   stay as they are. Each view draws the items one sentence backs together and says the sentence
   once.
2. **A sentence is its English words.** Two copies are one sentence when their `original` (a
   translated sentence's English) or text is equal (`sentenceGroups.sentenceKey`,
   `BlockBase.shown_sentences`), since copies of one claim carry distinct ids and may be translated
   apart.
3. **A supply map joins materials through any shared sentence.** Materials are one row when they
   share a sentence directly or through another material (`joinedBy`), so a sentence is said once
   even when two materials rest on overlapping sentences, not only identical ones. The heading names
   the materials in order in sentence case, "a, b and c", lowering a later name only where the
   sentences write it in lower case, so a proper name ("Multani matt") keeps its capital. A pin is a
   place: each placed origin has one number, in reading order, wherever it is listed.
4. **A figure reads in order.** A signature figure that cannot merge its parts (the vat's three
   frames) keeps each part's title and says a sentence only where it first appears; facts sharing a
   sentence are one fact with their labels joined by " · ".
5. **The judge reads what a reader sees.** `judge_message` reads `shown_field_sentences`; the
   judge's criteria, prompt and schema are unchanged, and the rubric's counts still read every
   sentence the blocks carry, so its scores do not move with this change.

## Consequences

- A supply map like Jaipur's draws the materials of the head potter's notes as one row with the
  sentence once (the unit spec's "Quartz stone, kach (glass), sajjt (borax), katira (gum) and
  Multani matt"); the Ajrakhpur measure draws both depths beside one sentence.
- A supply pin's numbering follows the list, not the order of the links, and a place two rows list
  is one pin.
- `what_if` options and `concept_graph` nodes may still share a sentence, since only one option or
  node shows at a time.
- The rubric's sentence density still counts a repeated copy (debt register, round 7).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`frontend/e2e/sentence-once-unit.spec.ts`, `frontend/e2e/sentence-once-figures-unit.spec.ts` and
`backend/tests/research/test_shown_sentences.py`.
