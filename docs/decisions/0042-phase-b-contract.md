# 0042. Phase B contract: place, matter and the expert panel

Phase B's contract fixes version 1 of the place, matter and expert panel kinds: references instead
of copied geometry, datasets cited as rows, a model that only chooses and orders, and reactions from
the science engine. Builders and renderers are registries, called once from the sectioned flow.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The lanes built to it | [0043](0043-river-lines-tracer-and-monthly-rain.md), [0044](0044-region-story-and-map-layers.md), [0045](0045-reactions-materials-molecules.md), [0046](0046-expert-panel.md), [0047](0047-seasons-and-supply.md), [0048](0048-place-renderers.md) and [0049](0049-matter-and-expert-renderers.md) |
| The contracts it names | [explainer.md](../contracts/explainer.md), [region.md](../contracts/region.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase B of `docs/plans/answer-experience.md` ("Place and matter", owner-approved, section 8 final)
builds the river story, map layers, the reaction player, material cards, 3D molecules, the
expert panel, seasons and supply. Decision 0030 declared these kinds with provisional fields so
phase A could fix the envelope; none was ever produced, stored or drawn. Phase B runs as parallel
lanes with fixed numbers: 0043 river lines, tracer and monthly rainfall data, 0044 region story
and map layers, 0045 reactions, materials and 3D molecules, 0046 expert panel, 0047 seasons and
supply, 0048 place renderers, 0049 matter and expert renderers, 0050 review fixes. The practice
skills ask for the interface they share to be agreed and built first, pinned on both sides by
fixtures. Phase A's lessons bind: no connection held across a model call (0040), every fact
cited, numbers and places from claims or datasets only.

## Decision

1. **Version 1 is fixed now, not reinterpreted.** The phase B kinds keep `version: 1` with their
   final fields, because no version-1 payload of them exists anywhere (the built guard refused
   them since 0030). From here a field change is a new version.
2. **References, not copied geometry.** A region story carries the river's HydroRIVERS reach ids
   in path order, its outlet (`mainRiv`, the basin key) and the districts it reaches in path
   order, plus cited steps; the client draws the river from one basin TopoJSON served by
   `GET /api/rivers/{mainRiv}` and the districts from the district shapes it already loads. A
   map layer names its registry layer and version; values come from the layer route.
3. **Datasets are cited as rows.** A block drawn from a dataset carries the dataset rows it rests
   on (`DatasetRef`, the region contract's dataset shape, moved to `research/datasets.py` with the
   PLAN 8 caption so the block validators can check the caption word for word). Map layers and
   molecules cite no claim and are therefore never knowledge pieces; they are rebuilt each time.
4. **A model only chooses and orders.** Per kind the contract says which values the server fills
   (from stored rows, the district register, HydroRIVERS, CHIRPS, PubChem, Wikidata, the
   glossary) and what a model may choose (which claims, which offered basin, which offered layer,
   the order of steps). Names a model chooses (a river name, a supply origin, a material word)
   must be stated by a cited sentence or its quote (`blocks.named_in`). Season rows show only
   months or seasons their sentence or quotes name (`research/calendar`), because a month mapped
   from "monsoon" would be a model's number.
5. **Reactions are the science engine's.** `ReactionSpecies`, `mhchem_equation` and
   `reaction_level` moved from `schemas/science.py` to `research/reactions.py` (their four
   importers switched), so a reaction step rebuilds its equation from its species and recomputes
   its level from its citations, failing closed like the Process tab.
6. **Experts differ is stated by both seats.** An expert view's difference with another seat
   rests each side on its own claims and its own sources; within a section the other seat must
   give the mirrored difference (same claims, swapped), and an agreement must be mutual
   (`expert_pairing_problems`, checked by `ExplainerSection`). The client draws one card per pair
   (`expertsDiffer`). The 18 seats are data in `research/expert_panel.py` (label, brief, source
   kinds, fields); a seat speaks in the sections of its fields; depth seats 2, 4 or 6 to 10
   (`DepthPolicy`, unchanged).
7. **One map of where a kind keeps its sentences.** Each block model declares `SENTENCES`;
   `cited_sentences`, the payload walk used by translation and term marking
   (`explainer.payload_sentences`, `with_payload_sentences`) and the piece sentence ids all read
   it, so a later kind is translated, marked and stored without new code.
8. **Region pieces are cross-craft.** A region story is stored with no craft, its topic the
   facet's namespace and `basin-<mainRiv>`, else `lgd-<code>` per district
   (`knowledge_pieces.piece_slot`); every other phase B piece keeps its section's slot. Lane 0044
   wires the slot into storing and reuse.
9. **Builders are a registry, called once from the sectioned flow.** `services/block_builders.py`
   holds `BLOCK_BUILDERS` (empty). An entry names the later-phase kind it adds, the fields
   (disciplines) it may add to, a factory over `BuilderTools` (sessions, live sources, the plan and
   compose models) and its wait (8 s by default like pictures, at most 60 s for a model call).
   After a section's prose and ladder are checked, its builders start together while those blocks
   are sent; their blocks are marked, translated and sent after them and before the pictures, and
   kept as pieces. A builder that fails, times out, makes another kind, carries a reuse mark,
   cites a source it did not return or makes a kind not yet built adds nothing; the section is
   never failed by one. Lanes add entries only; `answer_sections.py` holds the one call.
10. **Renderers are a registry.** `components/answer/blockRenderers.ts` maps each kind to one
    renderer; a kind without one is not drawn. The phase A kinds are entered.
11. **Built stays a guard.** `BUILT_BLOCK_KINDS` stays phase A. A kind is added to it, on both
    sides in one change, by the lane that completes it (builder and renderer both present); a
    test then requires a builder entry (server) and a renderer (client) for every built kind.
12. **PubChem records get stable ids.** `link_compounds` stores a new record source under
    `uuid5(ID_NAMESPACE, "pubchem-record:<cid>")` (`record_source_id`), so a molecule's citation
    resolves the same way in every database; records stored earlier keep their ids.
13. **Fixture.** `shared/explainer.phase-b.golden.json` holds every phase B kind for Kutch Ajrakh
    built from seed claims and sources, the seeded science rows (reactions, Alum, compounds), the
    LGD register, the region golden's layer and dataset rows and the geo ETL catalogue's
    HydroRIVERS row. The river's reach ids and outlet are placeholders, listed under
    `placeholders`, until lane 0043 loads HydroRIVERS. The alizarin CID is PubChem's (the recorded
    adapter response).

## Consequences

- The lanes build to `docs/contracts/explainer.md` (phase B) and `docs/contracts/region.md`
  (rivers); their fixtures and tests must keep `explainer.phase-b.golden.json` reproducing.
- Nothing a reader sees changes: the registry is empty and the kinds are not built.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
