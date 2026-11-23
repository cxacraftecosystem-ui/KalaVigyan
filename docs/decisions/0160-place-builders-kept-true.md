# 0160. A geography section reuses a current story, places are keyed and pinned by the register, seasons read what a source states, and the place proofs run on production

The place builders lane of the debt round (2026-11-23): the region story, map layer, seasons and
supply builders, the calendar they read, the stored pieces they key, the stream events and client
state that carry their blocks, the river load and the production run that proves them.

Date: 2026-11-23. Status: accepted (the lead's round 7 brief, place builders lane). It amends
[decision 0033](0033-knowledge-pieces-and-reuse.md) (topic keys of place facets),
[decision 0044](0044-region-story-and-map-layers.md) (a stored story, its steps, its layer and
its key), [decision 0047](0047-seasons-and-supply.md) (season months, supply pins and place
lookups), [decision 0050](0050-phase-b-review-fixes.md) (other names, negation, superseded river
files, the rivers flag) and [decision 0063](0063-follow-ups-versions-and-alerts.md) (a follow-up
that lost a race). The contracts are `docs/contracts/explainer.md`, `docs/contracts/learning.md`,
`docs/contracts/research.md`, `docs/contracts/frontend.md`, `docs/contracts/geo.md` and
`docs/contracts/region.md`; the river load and the production run are in `docs/RUNBOOK.md`.

| For | Read |
|---|---|
| The stored pieces and topic keys it amends | [decision 0033](0033-knowledge-pieces-and-reuse.md) |
| The region story and map layers it amends | [decision 0044](0044-region-story-and-map-layers.md) |
| The seasons and supply blocks it amends | [decision 0047](0047-seasons-and-supply.md) |
| The phase B review fixes it amends | [decision 0050](0050-phase-b-review-fixes.md) |
| The follow-up versions it amends | [decision 0063](0063-follow-ups-versions-and-alerts.md) |
| The river names and reach districts it builds on | [decision 0153](0153-rivers-named-groundwater-loaded-and-region-values-chosen.md) |
| What a reader may see of a fact | [decision 0149](0149-a-fact-readers-can-see.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Twenty-two entries of `docs/TECH_DEBT.md` were open in the lane on 2026-11-23. The geo lane
(decision 0153) had named the rivers, computed each reach's districts in the ETL and left the
phase B fixture's river ids as placeholders. A researched geography section paid a model call for
a story even when a current one was stored; story steps could only repeat the section's prose; map
layers were chosen by an English word list; stories of crafts in more than about 23 districts were
never stored; place pieces were keyed by district name; a season had months only when a quote the
section offered stated them; Indian month names, ranges written with "between" and seasons other
than three were not read; supply origins were pinned through Wikidata alone and asked again for
every map; superseded river files stayed in the bucket; and the production run needed the rivers
flag set by hand. The stored climate quotes of the curated dossiers (read on 2026-11-23) gave the
cases the calendar's rules were measured on.

## Decision

1. **A current stored story is placed by the builder, with its mark.** The region story builder
   reads the craft-less stories of the craft's basins or district set first and places the newest
   that passes the reuse rule (`piece_reuse.usable_region_stories`, shared with the reused-section
   path) with its reuse mark; its registry entry may place pieces (`places_pieces`, as the
   generated explainer's). Such a section spends no model call. A registry path that placed a
   stored block before the builder ran was the alternative; it would duplicate the reuse rule the
   builder already holds the inputs for.
2. **A story's steps may be the craft's stored place claims.** Beside the section's claims (at most
   12) the offer carries at most six of the craft's claims under its place headings (the
   `ENVIRONMENTAL_CONDITION` type the `GEOGRAPHY` field files under), those naming a craft district
   by its register or other name first, then by the question's lexical rank; their sources come back
   with the block.
3. **A map layer is chosen by its glossary term.** `geo/layer_terms.json` holds one term per
   registry layer (label, aliases and any local name a source gives) and `TermMarker` marks the
   section's sentences with them, as answer terms are marked. The terms are a vendored file the
   geo package reads, not `Term` rows: the builder runs synchronously over English sentences and
   needs no query, and a layer's words are reviewed with the registry they belong to.
4. **Place pieces are keyed by district code, and any district set is stored.** A place facet's
   topic names districts `lgd-<code>`; a set too long for a key is keyed by the first 16 hex of the
   SHA-256 of its sorted codes. A story told without a river keeps its codes in
   `KnowledgePiece.districtLgds` (GIN, migration `0083_piece_districts_and_places`); a craft finds
   it only when the set equals its own districts (as the exact key did), and a tapped district finds
   every such story whose set holds it. The migration fills the column for stored stories and
   rekeys stored place pieces from name slugs to codes. A curated place piece keeps the id its
   district name seeded (`curation_overview.piece_id_topic`): the approved Kutch Ajrakh page cites
   its sentences by that id, and an id is an identity, not a lookup key.
5. **A district carries the other names sources use.** `DistrictRef.otherNames` (from the cited
   `data/district_other_names.json`, left out when empty) lets a step about Kutch be placed in
   Kachchh, on both sides of the contract. An other name still does not drop a sentence: "Kutch
   Ajrakh" names the craft, not the district.
6. **A register district is pinned by the register.** A supply origin that is one LGD district is
   placed at the district's stored centroid citing `DR_DISTRICT_SHAPES`; other origins go to
   Wikidata as before. The link gains an optional `districtLgd` and the block optional `datasets`
   rather than a version 2, so a web a release behind lists such an origin without its pin instead
   of refusing the block.
7. **Wikidata's answers are kept, not the choice made from them.** `PlaceLookup` keeps each name's
   candidates and each item's point (or its absence) for 30 days; the choice among candidates is
   made again from the kept answers and each sentence's words. Keying a stored choice by origin and
   context words, with the item's revision, was the alternative; it would ask again for every new
   sentence, and a monthly refresh covers what a revision would tell.
8. **A season or a regional month gets months only from a source.** The calendar reads `between`
   two months and two neighbouring months as spans, `SPRING`, `AUTUMN`, `PRE_MONSOON` and
   `POST_MONSOON` besides the three seasons, "spring" only after a season's lead word and no
   season followed by a year. The national calendar's twelve months and their spellings
   (`calendar_words.REGIONAL_MONTHS`) are read only in month context ("the month of Kartik"), so a
   person or a Saka date spelled alike times nothing, and the table holds no Gregorian months: as
   for local units (owner O5), a regional month or a season takes months only from a quote stating
   them beside it. A region's season calendar enters as an ordinary cited claim under the craft's
   place headings, offered to the seasons builder (`place_claims.place_calendar_claims`). A
   national table of the India Meteorological Department's seasons was the alternative; the
   sources found disagree on winter and the pre-monsoon months, and none could be read verbatim.
9. **The negation window stays; a parser was not added.** In every stored quote where a negation
   stands near a timing, the timing belongs to the negated or purpose clause, not to the claim's
   activity ("so they do not expand in the rainy season" does not time the oiling), so dropping it
   is what a reader should see. The window was widened where the stored quotes showed it fail:
   "rather than", "other than" and "instead of" exclude, a parenthesis no longer ends the clause, and
   a season a point word stands before is a reference. A dependency parse (spaCy) would add a
   dependency and a model to the box for no change in what is shown.
10. **The river load deletes what no basin names.** After the rows are committed the load deletes
    every object under `media/rivers/` that no basin of the load names, with `s3:DeleteObject` on that
    prefix for its role; a lifecycle rule was the alternative, but S3 cannot tell which digest a
    `RiverBasin` row names.
11. **A follow-up that lost a race reloads the stored version.** A `version` whose `basedOn` is not
    the version the follow-up built on marks the state, and once the stream is done the client opens
    the stored version, so the merged blocks show under their stored numbers.
12. **The production run proves the place builders itself.** It counts the river lines loaded when
    the Khari's basin file carries every reach's districts, asks a climate question (failing without
    a seasons block) and a Ganga question for a Varanasi craft (timing its story), and notes each
    region story, seasons block and supply map with its time after its section's first block and
    what it shows. The Ganga question is asked at Detailed depth: the builder and its 20 s wait are
    the same at every depth, and an Expert answer costs a panel more.
13. **The phase B fixture draws the loaded Khari.** Its story's river is `mainRiv` 41063203 traced
    from its headwater through the reaches OpenStreetMap names Khari, citing `OSM_RIVER_NAMES`; its
    basin file `shared/river.kachchh.golden.json` is the production file of 2026-11-23 with each
    reach's districts as the decision 0153 load writes them (every reach lies inside Kachchh). The
    hand-made placeholder basin stays the ETL's golden and the renderer specs' geometry.
14. **The stream's `reaction` event is gone.** Reactions arrive as `reaction_player` blocks; the
    event, the client state and the reactions panel left together.

## Consequences

- Migration `0083_piece_districts_and_places` adds `KnowledgePiece.districtLgds` and `PlaceLookup`,
  fills the column and rekeys place pieces; its down revision is `0077_state_and_reach_districts`.
- The river load needs the role's new grant: the owner applies `infra/terraform` before the first
  river load after this change, or the load fails after its rows are in, naming the keys.
- A season row may now cite a craft's stored climate claim beside its own; a block may show a
  season chip the web of the release before does not know until the web deploys.
- The production run asks two more questions (a climate and a Ganga one), so a `questions=true`
  run costs two more answers and may take up to 112 minutes.
- Entries left open, rewritten to what remains: a curated way to write alternatives as relations,
  condition ranges tied to outcomes, and a readings kind in the review queue.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choices as taken on
2026-11-23; what the code does today is in the contracts named above. Its rules are tested by
`backend/tests/place/test_region_story.py`, `test_place_claims.py`, `test_map_layer.py`,
`test_seasons.py` and `test_supply_map.py`; `backend/tests/research/test_season_months.py` and
`test_piece_reuse.py`; `backend/tests/contracts/test_explainer_phase_b.py`,
`test_supply_district_contract.py` and `test_craft_page_contract.py`;
`backend/tests/answering/test_section_blocks.py`; `backend/tests/db/test_region_districts_db.py`,
`test_place_lookups_db.py` and `test_place_db.py`; `etl/geo/tests/test_load_rivers.py`; and
`frontend/e2e/explainer-contract-unit.spec.ts`, `learning-screens-unit.spec.ts`,
`supply-district-unit.spec.ts`, `seasons-supply-unit.spec.ts`, `river-topology-golden-unit.spec.ts`,
`explainer-phase-b-unit.spec.ts` and `production-kinds-unit.spec.ts`, and run live by the
production questions run.
