# 0044. Region story and map layers

The `region_story` and `map_layer` blocks are built through the block builder registry: the model
only chooses, a dataset value is cited or not shown, and no river data means no story. Map layers
come from the layer route's own computation, and region pieces are reused across crafts.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0042 Phase B contract: place, matter and the expert panel](0042-phase-b-contract.md) |
| The review that fixed it | [0050 Phase B review fixes](0050-phase-b-review-fixes.md) |
| What amended it | [0153 Rivers are named from Wikidata then OpenStreetMap, groundwater comes from the India data portal, a region place shows its headline values, and the geo ETL fails every gap it can see](0153-rivers-named-groundwater-loaded-and-region-values-chosen.md): a river's name from the river names datasets |
| A current stored story placed by the builder, place claims as steps, layers by glossary term and any district set stored | [decision 0160](0160-place-builders-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Lane 0044 of phase B (`docs/plans/answer-experience.md`, decision 0042) builds the `region_story`
and `map_layer` blocks through the block builder registry. Their fields and validators were fixed
by decision 0042, the river data and tracer by decision 0043, and their renderers by decision
0048. Owner rules bind: every fact the reader sees cites a source or a dataset row; numbers,
districts, coordinates, river paths and dates come from claims or datasets, never from a model,
which may only choose and order; real geometry with the boundary caption on every map; untrusted
text only inside untrusted blocks; no connection held across a model call (decision 0040). Region
pieces are cross-craft, keyed by basin or district (decision 0042 point 8), and this lane wires
that slot into storing and reuse.

## Decision

1. **Two registry entries.** `region_story` for `GEOGRAPHY` sections (20 s, one plan-model call)
   and `map_layer` for `GEOLOGY` and `CLIMATE` sections (8 s, no model), from
   `services/place_builders.py`. A geography section's story already carries its layers as pills,
   so it gets no separate map. Both kinds join `BUILT_BLOCK_KINDS` on both sides in this change:
   their builders and their renderers (decision 0048) are now both present.
2. **What a story is offered** (`services/place_offers.region_offer`, one short session before
   the model call): the craft's districts are its cited `CraftLocation` district places that have
   a polygon (`region_records.district_places`, the region route's own places); the rivers are
   `river_store.rivers_crossing` of those districts, now ranked by the crossing reach's Strahler
   order, then its mean discharge, then upstream area, at most 3 (`REGION_RIVERS_MAX`), each traced
   with the 0043 tracer (a broken network is logged and that river not offered); district names
   and states come from the district register (`AdminDistrict`, `AdminState`); the layers are the
   registry layers in the water, climate, soil, geology and terrain facets with a stored value in
   a craft district (`map_layer_store.district_layers`), with their dataset rows.
3. **The model only chooses.** One call (`composer/region_story.choose_region_story`) gets the
   rivers (order, discharge and the districts they reach, as data), the districts, the layers and
   the statements, each inside an untrusted block, and answers refs only: one river or none, at
   most 8 steps (a statement ref and a district ref or none), at most 4 layers. The server builds
   everything shown (`services/region_story.region_story_block`): steps are the section's cited
   fact-level claims as stored, with their visible citations; a step whose ref is not a statement
   is dropped, a claim is shown once, and a step placed in a district the story does not list, or
   in one its sentence and quotes do not name, keeps its claim without a district (decision 0050:
   the district a model attaches to a fact must be stated by that fact, decision 0042 point 4). The river's reach ids and districts are the trace's; the story's
   districts are the river's in path order, then the craft's others.
4. **Datasets are cited, or the value is not shown.** The story cites `DR_DISTRICT_SHAPES` (without
   that row there is no story), `HYDRORIVERS_1_0` with a river (without that row the story is told
   without its river) and the dataset row of each chosen layer (a layer whose row is missing is
   left out). The district values themselves reach the reader through the layer route the pills
   read, never through the block.
5. **No river name.** HydroRIVERS names no river, so naming a traced path after a word in a claim
   would be a model's identity claim about a path. The builder sends `name` null and the client
   labels the course generically; the contract keeps the field for a named dataset later
   (`docs/TECH_DEBT.md`). The phase B fixture's name stays as a shape example.
6. **No river data, no story.** Until the Geo ETL's `riverlines` load (`river_store.rivers_loaded`
   finds no basin) the region story builder adds nothing and logs it once per answer (the registry
   is built per request); it never fails the section. Map layers do not wait for rivers.
7. **Map layers come from the layer route's own computation.** `section_map_layer` picks, in
   registry order, the section's facet layers (`geo/section_layers.SECTION_LAYER_FACETS`), putting
   first the layers whose subject words (`LAYER_SUBJECTS`, whole words) the section's sentences
   name, and keeps the first with a value in a craft district; `map_layer(layer_values(...))`
   gives its version, title, dataset row and boundary row exactly as `GET /api/map/layers/{layer}`
   answers, and only the craft's districts with a value are highlighted. A map layer cites no claim
   and is never a piece.
8. **Region pieces are stored and reused across crafts.** `piece_store._pieces` stores every block
   in `piece_slot`'s slot, so a story is a piece with no craft, topic `<namespace>:basin-<mainRiv>`
   or `<namespace>:lgd-<code>+...` (`knowledge_pieces.region_topic`); a key over 200 characters is
   not stored. When a facet's section is reused, the lookup also reads the current region stories
   keyed by the basins crossing the craft's districts or by those districts
   (`services/region_pieces.region_story_pieces`), drops one whose river no longer follows the
   stored reaches (`river_store.stored_trace_problems`: the path's reaches and any reach flowing
   into its source), and `piece_reuse.with_region_story` adds the one that passes the reuse rule as
   a cross-craft piece, preferring the story kept with that section, else the newest. A researched
   section builds its own story, which supersedes the stored one of its basin.

## Consequences

- Readers see region stories after the deploy and the Geo ETL `riverlines` load; map layers at
  once, from the stored district values.
- Tests: the Kachchh story from fixture reaches through the real tracer (equal to the phase B
  fixture's story but unnamed), a step with no claim dropped, a missing dataset row dropping its
  value, no river data adding no block and logging once, layer choice by subject words, the map
  layer equal to the fixture's, reuse of a stored region piece (pure, through the answer flow and
  on Postgres), and on GitHub Actions the offer's ranking and traces, the section map and the stored
  piece's slot, reuse and refusal once its river changes (`tests/place/`, `tests/db/test_place_db.py`).
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
