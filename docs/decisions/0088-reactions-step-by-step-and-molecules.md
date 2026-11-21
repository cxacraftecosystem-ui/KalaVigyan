# 0088. Reactions play step by step with their stage, conditions, colours and why; curated CIDs become compounds

Reaction steps carry their stage, conditions and before-and-after colours (only from a cited quote's
own words), with the why as notes at block level, and the web plays the change. Curated PubChem CIDs
become compounds at import, and R01 and R02 stay word equations.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| What amended it | [0095 The craft page becomes a monograph in chapters, public to read, built without a question](0095-craft-page-chapters.md): item 6, for display only |
| Every decision, by group | [README.md](README.md) |

## Context

The owner's Expert question on Kutch Ajrakh showed "no chemical breakdown apart from one compound
name". The reaction player showed a label, species and an equation per step and nothing about
what changes, under which conditions, or what the cloth looks like before and after, although the
stored claims and quotes say it ("At first bright green, the cloth rapidly becomes blue", "kut
develops a deep fast chocolate-black colour", "develops red"). The curated dossiers carry PubChem
CIDs for soda ash, lime, ferrous sulphate, hydros and caustic soda, but the import only looked up
existing `Compound` rows, so those materials had no compound, no formula and no molecule.

## Decision

1. **Steps carry stage, conditions and colours; the player carries notes.** `ReactionStep` gains
   `stage` (the stored stage name), `conditions` (the reaction's and its stage's stated readings,
   the ladder's `stated_condition` rule, at most 4) and `colours` (`StepColour {side, colour,
   stated, citations}`). `ReactionPlayerBlock` gains `notes[{reactionId, sentence}]`: each
   reaction's stored fact claims as cited sentences, each claim once per player, at most 4 per
   step. All are optional and left out of the JSON when empty (`exclude_if`), so a player stored
   before keeps its content hash and still reads.
2. **Notes sit at block level, not in the step.** `SENTENCES` is `(("notes", [(("sentence",
   SENTENCE),)]),)`. The claim ledger drops a story item whose sentence the page already shows and
   drops a list item left with no sentence; with the sentences inside each step a repeated
   explanation would have removed the whole step. At block level a repeated note goes and every
   step stays, with no change to the ledger. Translation and term marking walk the notes.
3. **Colours only from a cited quote's own words** (`science/reaction_colours`): a change ("at
   first [modifiers] C1 ... becomes/turns [pace] [modifiers] C2") gives the before and after
   sides, a result ("develops/gives/produces/yields [a] [modifiers] C") the after side, by the last
   colour word of a compound ("chocolate-black" is black). A colour word used as a name ("indigo
   white is converted into ... indigo blue") or after a negation gives nothing. Twelve colour words;
   the web draws them from the `dye` tokens with their names in text, so no colour carries meaning
   alone.
4. **The web plays the change.** Each step shows its stage, a cloth swatch that fades from the
   stated before colour to the after colour when the step is the open one (still under reduced
   motion), the stated words with their citations, the conditions, "What happens and why" with the
   notes, and marks as "Intermediate" a species one step makes and the next uses (leucoindigo
   between the indigo reduction and oxidation).
5. **Curated CIDs become compounds at import** (`services/curated_compounds`): a CID no compound
   holds becomes a `Compound` named by its first material, with no formula, citing a
   `COMPOUND_RECORD` source for its PubChem page (an existing source for that page is reused); a
   compound without a CID whose name is the material's is left to the lookup instead, so a fresh
   database does not get two rows for the seeded alizarin or indigo. `link_compounds` now also
   reads the record of a compound that has a CID and no formula (`PubChemAdapter.compound`) and
   fills its formula and identifiers, reported as `filled`.
6. **R01 and R02 stay word equations.** The dossier's own sources for R01 (C086) and R02 (C078)
   state the colour change, not formulas; the balanced indigo oxidation is already a stored seed
   reaction of the craft, and R02's product is a colour, and iron-tannate has no single formula.
   Writing formulas into the dossier would state chemistry its sources do not, so the two steps
   keep their names and gain their colours and notes instead.

## Consequences

- The recorded phase B player (`shared/explainer.phase-b.golden.json`) now carries 12 notes, two
  conditions and three colours (green to blue for the oxidation, red for the alizarin lake).
- Old stored reaction players show plain steps until rebuilt; the builder asks no model, so
  rebuilding it on reuse refreshes them at no cost.
- `link_compounds` makes one more PubChem request per curated CID until the formula is filled.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
