# 0153. Rivers are named from Wikidata then OpenStreetMap, groundwater comes from the India data portal, a region place shows its headline values, and the geo ETL fails every gap it can see

The geo, region and rivers lane of the debt round (2026-11-22): river names from two open datasets
kept apart by licence, the districts each reach crosses computed once in the ETL, basin files
compressed, district groundwater loaded from the India data portal with the owner's key, a curated
headline set of values per facet with state aggregates kept in the database, real ETL output in the
region and craft page goldens, and the geo ETL's remaining state gaps closed.

Date: 2026-11-23. Status: accepted (the owner's decisions of 2026-11-22 for the lane: river names
from Wikidata and OpenStreetMap, groundwater from the India data portal with the owner's key, and the
lead's choice of a curated headline set per facet). It amends
[decision 0016](0016-region-profile.md) (the region's values and state aggregates),
[decision 0027](0027-geo-etl-state-gaps.md) (coverage and the CHIRPS period),
[decision 0043](0043-river-lines-tracer-and-monthly-rain.md) (the districts a trace reaches and the
basin files), [decision 0044](0044-region-story-and-map-layers.md) (a river's name),
[decision 0048](0048-place-renderers.md) (a district's stretch),
[decision 0050](0050-phase-b-review-fixes.md) (river names in prose) and
[decision 0065](0065-climate-risk-and-ask-the-map.md) (groundwater). The contracts are
`docs/contracts/geo.md`, `docs/contracts/region.md` and `docs/contracts/explainer.md`; the datasets
are in `docs/DATA_SOURCES.md`.

| For | Read |
|---|---|
| The region profile it amends | [decision 0016](0016-region-profile.md) |
| The geo ETL's coverage rules it amends | [decision 0027](0027-geo-etl-state-gaps.md) |
| The river lines and the tracer it amends | [decision 0043](0043-river-lines-tracer-and-monthly-rain.md) |
| The region story it amends | [decision 0044](0044-region-story-and-map-layers.md) |
| The place renderers it amends | [decision 0048](0048-place-renderers.md) |
| The stated-names check it amends | [decision 0050](0050-phase-b-review-fixes.md) |
| The climate block it amends | [decision 0065](0065-climate-risk-and-ask-the-map.md) |
| The datasets, their licences and the matching rules | [DATA_SOURCES.md](../DATA_SOURCES.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Twenty entries of `docs/TECH_DEBT.md` were open in the lane on 2026-11-22. Four of them waited on
an owner decision or a measurement: HydroRIVERS names no river, so the region story drew every
river unnamed and prose naming a river could not be checked; no key-free district groundwater
dataset exists; a district place sent every stored value (about 300); and the cost of tracing a
river and the size of the largest basin files had never been measured. The owner decided river
names come from Wikidata (CC0) first and OpenStreetMap (ODbL) to fill gaps, kept apart, and that
groundwater comes from the India data portal with the owner's key; the lead chose a curated
headline set per facet. The production Geo ETL runs' artifacts (runs 43884310432 to 44302045906,
2026-11-16 to 2026-11-18) hold the real district values and the river job's basin sizes.

## Decision

1. **River names come from Wikidata first, then OpenStreetMap, matched by stated rules.** The geo
   ETL's `river-names` step (`geo_etl/wikidata_rivers.py`, `river_names.py`, `osm_rivers.py`,
   `river_names_osm.py`, `river_names_files.py`) matches each Wikidata river with a qualified mouth
   coordinate to the HydroRIVERS reach ending within 10 km of it (30 km for a basin outlet, where a
   delta or an estuary puts the stated mouth off the drawn line), follows its course to a headwater
   within 30 km of its stated source (or, without one, checks its stated basin area within half of
   the reach's upstream area, or takes the one basin outlet near its mouth), carries a tributary
   that ends short of the river its mouth names down to where it joins it (within 10 km of the
   mouth) and refuses one that does not join it; a reach two rivers claim takes the shorter river's
   name. The run of 2026-11-23 (run 45088759547) matched 147 of the 513 Wikidata rivers with a
   qualified mouth in the river lines' box (14,250 reaches) and named 4,303 more rivers from
   OpenStreetMap (36,626 reaches) of the 128,756 reaches drawn. Prose is checked for every name
   of several words and for a Wikidata river's one-word name; an OpenStreetMap name's one-word form
   is too often a person's or a god's name to be checked alone. A reach no Wikidata river names takes the one OpenStreetMap
   `waterway=river` name that at least 80% of points every 500 m along it lie within 1 km of. The
   two are written to separate files and dataset rows (`WIKIDATA_RIVER_NAMES`, CC0;
   `OSM_RIVER_NAMES`, ODbL, credited "© OpenStreetMap contributors"), never merged.
2. **The names are vendored, not loaded into a table.** The two files are copied unchanged from the
   rivers job's artifact into `backend/app/data/rivers/` and read once per process
   (`app/data/river_names.py`). The checks of prose, headings and expert takes are synchronous and
   run inside every composed sentence, so the names must be in the process without a query; a
   vendored edition is also reviewed in its change, as the Natural Earth and SCOWL word lists are.
   A table loaded by `load_rivers.py` was the alternative: it would keep the names beside the
   reaches but need a query in every sentence check, or a process cache with its own invalidation.
3. **A named river is named from its dataset, not only from a step.** A region story's river takes
   the name of the reach it is traced through and cites the name's dataset row; the contract
   (`blocks_place._river_name_problems`) accepts a name a step states or one a river names dataset
   row the block cites states. The trace climbs the named river's own reaches before the largest
   branch (`river_trace.traced_reach_ids(..., named=...)`), so the drawn source is the named river's.
   The offer puts first the rivers crossing the craft's districts whose names its statements name
   (`place_offers.stated_crossings`), so the story a step tells (the Suran at Dhamadka) can draw
   that river rather than only the three largest.
4. **The districts each reach crosses are computed once, in the ETL.** `geo_etl/river_districts.py`
   intersects every kept reach with the same district shapes the backend seeds, on the full
   HydroRIVERS line, and keeps the fraction of the reach's length at which it first enters each
   district. The basin file carries them per reach (`properties.districts`), so the client draws a
   district's stretch and entry from them, and `load_rivers.py` writes them to `RiverReachDistrict`,
   so `trace_river` and `rivers_crossing` read a table instead of intersecting polygons on every
   trace. This replaces measuring the trace on production first: the cost the entry asked to time
   is no longer paid. Rivers count as loaded only when the reach districts are.
5. **Basin files are compressed, not split.** The production rivers job (run 44154095333,
   2026-11-17) wrote 410 basins; the largest, the Ganga-Brahmaputra (`mainRiv` 41067217, 42,650
   reaches), is 5,412,393 bytes, the next 2,145,168, and gzip at level 9 makes them 736,058 and
   308,964 bytes; with each reach's districts (run 45088759547) the largest is 6,347,825 bytes,
   813,603 compressed. `GET /api/rivers/{mainRiv}` answers gzip to a reader that accepts it, compressed
   once per file and kept with it in the topology cache, under its own ETag (`<sha256>-gzip`) and
   `Vary: Authorization, Accept-Encoding`. A per-path topology would change the contract and the
   client's one fetch per basin for a gain gzip already gives.
6. **A craft page draws the places abroad and the rivers its dossier names.** A dossier place
   abroad with a stored Wikidata point is pinned outside India's outline on the document's ground
   figure (`research/why_here.GroundPin`, credited to its Wikidata item, CC0) when it lies within
   500 km of a located place (`ABROAD_REACH_KM`), so a far place (Persia, Glasgow) stays listed
   only; a RIVER place matched by `river_names.place_river` is drawn from its basin file
   (`GroundRiver`), citing the HydroRIVERS row and its name's row, and not drawn when either row is
   missing. A place is drawn only when a claim a reader can see names it. Kutch Ajrakh's page draws
   no ground figure and is unchanged (decision 0100's parity holds).
7. **A remote file is absent only when its server says so.** `geo_etl/remote.py` is the one home
   for the geo ETL's HTTP: the user agent, the retries, the probe and the deadline. A remote raster
   is probed with HEAD before it is opened; only 404 or 410 means the tile does not exist, any other
   answer that persists after the retries raises `Unreachable`, and every read finishes within
   600 s (`FILE_DEADLINE_S`, the ten-minute worst case decision 0027 accepted for the CHIRPS year
   lookup) instead of riding GDAL's per-request retries for hours. An unreachable file fails its
   district in WorldCover, Hansen and the DEM and ends the shard's reads in CHELSA and CHIRPS.
   Listing each dataset's tiles once was the alternative: it needs a tile index per layer, and the
   probe already tells an ocean tile (404) from a server that did not answer.
8. **A district without cells must be one a person reviewed.** `coverage.EXPECTED_WITHOUT_CELLS`
   lists, per dataset with its evidence, the districts known to have no valid cell (Lakshadweep 553
   in GLiM, Mumbai 482 in SoilGrids); any other district measured without cells is listed under
   `unexpectedWithoutCells` and fails the part, so a grid read as nodata everywhere can no longer
   pass. An independent land mask was the alternative, but district polygons are land already: only
   a look at a dataset's own grid separates a real gap from a bad read.
9. **A silent district fails its part.** A selected district with no row, no failure and no
   listing without cells is listed under `silentDistricts` and fails the part even with
   `--allow-failures`, as the stricter rule decision 0027's addendum left open.
10. **The CHIRPS period is resolved once per run.** The plan job runs `python -m geo_etl
   chirps-last-year` and passes the year to every CHIRPS shard (`--chirps-last-year`); `combine`
   refuses parts of one dataset whose dataset rows differ and names the fields.
11. **A region place shows its headline values; the rest is the map's.** `geo/headline.HEADLINE_SERIES`
   is, per facet, every layer of the map-layer registry, the two climate trends (slope and p-value)
   and the rock types: about 30 values of a district instead of about 300. No web screen reads the
   region route since the tabbed page was retired, so no "More" view was added; every value stays
   on the map's district view and its layers.
12. **State series are stored by each load.** `StateEnvValue` (migration
   `0077_state_and_reach_districts`) holds each state's grouped series; one statement in
   backend Python (`services/state_values.state_values_insert`) is compiled to
   `shared/region.state-values.sql`, which `etl/geo/load.py` runs after every load and
   `seed_districts` runs after every seed, so the grouping keeps one home and a request reads rows
   instead of grouping a state's districts. A materialised view was the alternative; it would move
   the rule into a migration that every change must replace.
13. **The two rules about the ETL's rows live in one file both sides read.** The GLiM twin prefix
   and the series where an absent district means zero are in `geo/region_rules.json`; an ETL
   contract test runs the GLiM and MRDS row builders on a fixture and checks them, and migration
   0005's copy of the GLiM legend, against it.
14. **The goldens hold real ETL output.** The region goldens are regenerated from a small extract of
   the production runs' `geo-district-env` artifacts (Kachchh and the districts the layer golden
   draws, the redistributable datasets only, at the database's six decimals); the craft page
   golden's yearly series already were the real rows of district 449 (run 44204618054), which a
   test now proves.
15. **The registry never overwrites what a run sets.** `sync_dataset_registry` runs on every deploy
   and copied the registry's "set per run" into the CHIRPS and GHCN CAMS rows' `period`, which their
   load had set to the run's years, so the trends, the seasons' rainfall and the headline normals
   matched no stored row. `dataset_registry.synced_columns` leaves out every field whose registry
   value starts with "set per run" (`SET_PER_RUN`).
16. **Groundwater comes from the one district table the portal holds.** The India data portal
   holds no all-India district table of the Dynamic Ground Water Resources assessment as an API
   resource (searched 2026-11-23); the one table of whole districts is the Rajya Sabha answer for
   Rajasthan as on 31 March 2023, so the `groundwater` layer reads it with the owner's key
   (`DATA_GOV_IN_API_KEY`) and Rajasthan's 33 districts get groundwater. The figures keep the table's
   units (ham, and % for the stage, stored as `SHARE` like the other ratios); no category is derived
   from the stage; rows match LGD names after folding case, spacing and punctuation, with five
   spellings written out (Chittaurgarh, Dhaulpur, Jalor and Jhunjhunun as the Census of India 2011
   spells them, and Sri Ganganagar for Ganganagar), and every unmatched or doubly matched row is a
   failure; a layer whose dataset covers named states only says so (`Result.states`) and coverage
   judges it there. The climate block shows four figures (recharge, extractable resource,
   extraction, stage) and is built on groundwater alone when a district has no trend.

## Consequences

- Migration `0077_state_and_reach_districts` adds `StateEnvValue` and `RiverReachDistrict`
  and restores the CHIRPS and GHCN CAMS periods the registry sync had overwritten, from their
  stored trend rows. Until the next river load `RiverReachDistrict` is empty, so `rivers_loaded` is
  false and no new region story is built, and a stored story lights its districts at the source
  with no stretch; the lead's Geo ETL run (`riverlines,groundwater`, load on) fills it.
- The river names are an edition in the repository: a refresh is a Geo ETL run and a reviewed copy
  of its two files. The OpenStreetMap names stay under the ODbL in their own file and row; the
  open-data release holds no river names.
- A Wikidata river with no qualified mouth coordinate, or whose mouth lies far off the HydroRIVERS
  line (the Ganges' is 98 km out in the delta), is named only if OpenStreetMap names its reaches.
- A part fails on a district a person has not reviewed as without cells: the first full raster
  run of a dataset may stop on one, which is then checked and listed with its evidence.
- Groundwater shows only for Rajasthan, and only once loaded from a network the portal answers:
  GitHub's runners could not connect to it on 2026-11-23 (run 45088759547); the rest of the
  country waits on the portal (`docs/TECH_DEBT.md`, Groundwater values only for Rajasthan, and not
  yet loaded).
- The region route sends about a tenth of what it did; every value is still stored and on the map.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choices as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `etl/geo/tests/test_river_names.py`, `test_osm_rivers.py`, `test_rivers.py`, `test_load_rivers.py`, `test_coverage.py`, `test_remote.py`, `test_raster.py`, `test_cli.py`, `test_layers.py`, `test_region_rules.py`, `test_groundwater.py` and `test_load.py`; `backend/tests/geo/test_river_names.py`, `test_river_trace.py`, `test_river_routes.py`, `test_headline.py`, `test_state_values.py`, `test_groundwater.py` and `test_ground_marks.py`; `backend/tests/db/test_rivers_db.py`, `test_state_values_db.py`, `test_run_period_repair_db.py` and `test_groundwater_db.py`; `backend/tests/place/test_region_story.py` and `test_climate_groundwater.py`; `backend/tests/research/test_place_matter_blocks.py` and `test_dataset_registry.py`; `backend/tests/contracts/test_river_contract.py` and `test_watched_files.py`; and `frontend/e2e/place-renderers-unit.spec.ts`, `river-topology-unit.spec.ts`, `ground-marks-unit.spec.ts` and `release/place-tones-unit.spec.ts`.
