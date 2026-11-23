# 0045. Reaction player, material cards and 3D molecules

The `reaction_player`, `material_card` and `molecule_3d` blocks are built from one loader of a
craft's matter, with conformers fetched through the PubChem adapter and kept in the private bucket.
Compounds are linked nightly, and pieces of one answer never supersede each other.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0042 Phase B contract: place, matter and the expert panel](0042-phase-b-contract.md) |
| The review that fixed it | [0050 Phase B review fixes](0050-phase-b-review-fixes.md) |
| What amended part of it | [0152](0152-matter-read-once-and-the-science-seed-kept-true.md): One matter read per answer, a conformer miss asked again after 90 days, and optional fields instead of new versions |
| Every decision, by group | [README.md](README.md) |

## Context

Lane 0045 of phase B (`docs/plans/answer-experience.md`, decision 0042) builds the
`reaction_player`, `material_card` and `molecule_3d` blocks through the block builder registry,
for chemistry and materials sections. Their fields and validators were fixed by decision 0042;
every value must come from stored rows, their claims or PubChem, a model may only choose and
order, and no connection may be held across HTTP or a model call (decision 0040). The renderers
are lane 0049's.

## Decision

1. **The builder interface has its own module.** `BuilderTools`, `BuildAsk`, `Built` and
   `BlockBuilder` moved from `services/block_builders.py` to `services/builder_interface.py`.
   The registry imports the builders to list them, so a builder that imported the registry for
   its types would form a cycle; builder modules import the interface, the registry imports
   them. `BLOCK_BUILDERS` and the runner stay where they were.
2. **Only built kinds start.** `BlockBuilders.from_registry` makes builders only for kinds in
   `BUILT_BLOCK_KINDS`. Until a kind's renderer lands its builder would spend database reads,
   PubChem calls and a model call on blocks the registry then drops.
3. **One loader for a craft's matter.** `services/craft_matter.craft_matter` reads, in one short
   session, the Process tab's rows (`process_records`, whose `MaterialRecord` now carries the
   `Material` row id and concept and whose `CompoundRecord` carries its record source), the
   glossary terms linked to each material's concept, every compound of the craft's materials and
   reaction species, and the compounds' PubChem record sources. Builders read it before any model
   or HTTP call.
4. **Reaction player** (`CHEMISTRY`): the craft's shown reactions in process order (process,
   stage ordinal, reaction order), each step built from the Process tab's reaction view
   (`science/reaction_player`), at most 8 (`REACTION_STEPS_MAX`, the ones the section's claims
   cite kept first). The server chooses and orders; no model is asked. `reaction_player_problems`
   re-checks a player against the rows: a reaction that is not stored, a step whose stage, kind,
   label, species, equation or balance differ, or a citation not linked to the reaction refuses
   it, at build time and when a stored piece is reused (`piece_store` checks ladders and players
   together). Version 1 has no conditions or reaction energies; they stay on the Process tab.
5. **Material cards** (`CHEMISTRY`, `MATERIALS`): a material is offered when a section sentence
   marks one of its glossary terms or names it (its name, the term's label, aliases or local
   names), at most 3 per section in order of first mention. Its statements are its own stored
   claims (the stage-use claim and its concept's claims) and the section's cited claims naming
   it, facts only, at most 10. One plan-model call (`composer/material_cards`, every material
   and statement inside untrusted blocks) sorts statements into facts and handling by ref; a ref
   that is not one of that material's statements is dropped, and a card left without a fact is
   not shown. Name and kind come from the `Material`, the role only when every stage use agrees,
   the term from the glossary (the linked term whose label the material's name contains, longest
   first) with its local names once each and its Wikidata id, and the formula and CID only from
   a compound linked to its PubChem record by the compound lookup, so the CID is the formula's
   dataset row. The entry waits 20 s.
6. **Molecules** (`CHEMISTRY`, `MATERIALS`): candidates are the craft's compounds with a CID and a
   stored record source that a section sentence names (the compound's name, a species name, or
   its materials' names and terms), in order of first mention. The first of at most 3 with a 3D
   conformer becomes the one molecule of the section, citing its `COMPOUND_RECORD` source.
7. **Conformers come through the PubChem adapter and are kept in the private bucket.**
   `PubChemAdapter.conformer(cid)` asks PUG REST's canonical
   `compound/cid/<cid>/record/SDF?record_type=3d` through the adapter's paced HTTP (one call per
   0.25 s, under PubChem's five a second), answers `None` on 404, and refuses a body that is not
   that CID's terminated 3D molfile of at most 256 KiB. `ConformerCache` keeps one versioned JSON
   record per CID at `media/molecules/<cid>/conformer.json` (`naming.molecule_key`), holding the
   SDF or `null` when PubChem has none, so neither a hit nor a known miss calls PubChem again.
   `GET /api/molecules/{pubchemCid}/conformer` (signed in) serves the SDF
   (`chemical/x-mdl-sdfile`, private, a week) only for a CID a stored `Compound` holds, 404
   without a conformer, 503 when the bucket or PubChem fails. A builder without the bucket adds
   no molecule. `media_bucket()` moved from `api/media_deps` to `services/object_store` so the
   builder and the routes share one cached store.
8. **Compounds are linked nightly.** `app.scripts.link_compounds` runs in the Coverage enrichment
   job after the vector fills, so seeded compounds gain their PubChem CIDs and record sources
   without a manual run. It makes no model calls, so the job still neither researches nor
   rebuilds through models (commit fdf478c); a molecule needs a linked compound, and no other
   workflow could run it.
9. **Pieces of one answer never supersede each other.** `piece_store._supersede` leaves pieces of
   the same answer alone (`createdFromAnswerId IS DISTINCT FROM`), so a section's several material
   cards are all kept; a later answer's piece still supersedes them.

## Consequences

- Nothing a reader sees changes until lane 0049's renderers add the three kinds to
  `BUILT_BLOCK_KINDS` on both sides; the builders then start.
- Tests: recorded PubChem responses for the conformer and its absence
  (`tests/sources/test_pubchem_conformer.py`), the cache (a hit makes no call), the route, the
  builders (a reaction not in the stored rows is refused, a card fact without a claim is dropped,
  a missing conformer adds no block) and the registry seam (`tests/matter/`); database tests on
  GitHub Actions for the loader, the guard, reuse and supersession (`tests/db/test_matter_db.py`).
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
