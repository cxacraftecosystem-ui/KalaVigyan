# 0152. An answer reads a craft's matter once and shows each card, molecule and what-if once, matter blocks cite every value they show, and the science seed deletes what it no longer plans

The matter builders of one answer share one read of the craft's process rows; the claim ledger
shows one what-if per stage and pair of choices as it already shows one card per material and one
molecule per compound; a reaction step carries its cited ΔH and a material card cites its
compound's PubChem record; the glossary seed takes local names its claims state; a missing 3D
conformer is asked again after 90 days; the compound lookup holds no connection while PubChem
answers; the science seed deletes its own rows it no longer plans, seeds tools and a stage's own
role, and cites a thermal-analysis paper for kaolinite; and a disposed molecule leaves no listener
behind.

Date: 2026-11-23. Status: accepted (the lead's debt-clearing brief, lane matter, molecules,
reactions and the science engine). It amends [decision 0015](0015-science-engine.md) (the seed and
the kaolinite constant), [decision 0045](0045-reactions-materials-molecules.md) (one read per
builder, a kept miss kept for good, fields fixed until a new version),
[decision 0049](0049-matter-and-expert-renderers.md) (the listeners 3Dmol.js keeps) and
[decision 0056](0056-what-if-lab.md) (one what-if per section). The contracts are
`docs/contracts/explainer.md` (the matter kinds, Once per answer, Matter builders as built, the
conformer route) and `docs/contracts/science.md` (Envelope, Where the values come from).

| For | Read |
|---|---|
| The science engine and its seed | [decision 0015](0015-science-engine.md) |
| The matter blocks and their builders | [decision 0045](0045-reactions-materials-molecules.md) |
| The matter renderers | [decision 0049](0049-matter-and-expert-renderers.md) |
| The what-if lab | [decision 0056](0056-what-if-lab.md) |
| One claim, one rendering per answer | [decision 0080](0080-claim-ledger.md) |
| No connection held across a slow call | [decision 0040](0040-no-connection-held-across-a-model-call.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The debt register held seventeen entries on this area (sections 0015, 0045, 0049 and 0056). Each
was checked against the code on 2026-11-23. Some had moved: the claim ledger already kept one card
per material and one molecule per CID across sections (decisions 0080, 0090) without a test of it;
`ReactionStep` had gained its conditions additively; the Kutch Ajrakh, Bagh, Bagru, Sanganeri and
other dossiers had brought their own reactions. 3Dmol.js 2.5.5, the latest release on npm, still
adds its `document.body` and `window` listeners as fresh `bind` results it keeps no reference to.

## Decision

1. **One read of a craft's matter per answer.** `BuildAsk.matter` is a `craft_matter.MatterReads`:
   one read per craft, behind a lock, so builders that ask together wait for the one read, and a
   read cut off by its builder's wait is read again by the next to ask. `BlockBuilders.for_answer`
   makes one per answer and `added` gives it to every section's ask; a registry not made for an
   answer gives each ask its own. The reaction, card, molecule, what-if, supply-map and
   generated-explainer builders read through it. The zoom story builder, another lane's file this
   round, still reads alone (`docs/TECH_DEBT.md`).
2. **Repeats across sections are the ledger's.** Sections build at once, so a builder cannot know
   what another section is building; the stream's ledger, which admits every block of the answer
   in order, is the one answer-wide record. It keeps one what-if per choice: a what-if at the stage
   of one shown that sets two of the same options (`WHAT_IF_SHARED_OPTIONS`) side by side is left
   out, while another input of that stage, or the same options at another stage, is shown. Cards
   and molecules were already kept once (decision 0080); their tests now prove it across a
   chemistry and a materials section.
3. **New fields are optional, not new versions.** `ReactionStep.deltaH` (`StepEnergy {kjPerMol,
   claimId}`, the reaction view's ΔH, only from a claim the step cites, re-checked against the rows
   on reuse) and `MaterialCardBlock.sourceId` (the compound's `COMPOUND_RECORD`, only with a CID,
   cited directly like the molecule's) are left out of the JSON when absent, as decision 0088 did
   for the step's conditions, so a stored player or card keeps its content hash and still
   validates. The web shapes accept both in the same change; the step shows "Reaction energy"
   with a real minus sign and the card cites its record beside the formula through the one
   `SourceChip`. The craft page's chemistry cards cite the records their molecules already cite.
4. **Local names a claim states.** The glossary seed adds to a material, tool or stage term the
   names its concept's seed claims state after "locally known as", "known locally as", "locally
   called" or "called locally": a quoted name whole, otherwise the run of words of four letters or
   more that are no ordinary English word (the SCOWL list), and only when one of the six words
   before the phrase is a word of the term's own name, so "Turners locally known as Kharadiyas
   carve the blocks" gives the blocks no name. Claim texts only: the quotes are OCR'd GI pages
   ("Tumers", "?eela Karna").
5. **A conformer miss is asked again after 90 days** (`CONFORMER_MISS_RECHECK_DAYS`); a kept
   conformer never is. If that second ask fails, the kept miss stands and answers 404, and the next
   request asks again; a CID never asked still fails as before.
6. **The compound lookup holds no connection while PubChem answers.** It reads in one short
   session, asks with none open, and writes in a second that re-reads each row `FOR UPDATE`; a row
   changed meanwhile, or whose CID another compound took, is left for the next run.
7. **The science seed deletes what it owns and no longer plans**, in the transaction of its upsert:
   stage materials, reactions and conditions on its own stages, citations and readings of its
   reactions and conditions, materials of its material and tool concepts that nothing uses, and
   compounds whose id is the seed id of their name's slug that nothing names. A compound's key is
   therefore the slug of its name, so the seed can recognise its compounds after their key has left
   the file. A seeded stage's tools are stage materials with role `TOOL` on a `Material` of kind
   `OTHER`, as a dossier stores them; a material's `stageRoles` gives a stage its own role only
   where that stage's cited quote states it (Machilipatnam's myrobalan, brushed on as the yellow at
   the second printing, is a dye there).
8. **Kaolinite dehydroxylation is 400–700 °C**, quoting Izadifar et al. (2020, Clays and Clay
   Minerals 68, 319–333, CC BY 4.0): "Dehydroxylation of kaolinite commonly occurs between 400 and
   700°C". The Wikipedia claim of a 550–600 °C onset stays a seeded claim and is no constant. PLAN 7
   and the contract say 400–700 °C.
9. **A disposed molecule removes its listeners.** The adapter watches `document.body` and `window`
   while `createViewer` runs (`moleculeViewer.heldListeners`), keeps each listener the viewer adds,
   puts `addEventListener` back as it was, and `dispose` removes them.
10. **The renderers are seen running in the dark and by touch.** The release controls open Kutch
    Ajrakh and Bagru on a dark 390 px touch phone and check the species cast's contrast with axe,
    the molecule canvas left clear over the page's well, and Explore by tap and one-finger drag.

## What follows

- The register's entries on these points are deleted; what is left is named there: the zoom
  story's own read, the crafts still without a cited reaction or temperature, curated
  alternatives, condition and water inputs, and out-of-envelope readings in the review queue.
- A source stating a reaction's ΔH can now reach the player through the reaction's
  `deltaHKjMol` and `deltaHClaimId`; none is stored yet, so no golden shows `deltaH` and its three
  fields join `backend/tests/contracts/unshown_fields.json` (decision 0151) until one does.
