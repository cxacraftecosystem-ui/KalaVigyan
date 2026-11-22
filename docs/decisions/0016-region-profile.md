# 0016. Region profile and map layers from the stored district statistics

A pure `backend/app/geo/` layer builds a craft's region profile from the stored district statistics:
places from cited locations, every stored value of their districts, and state aggregates computed in
Postgres. It serves 21 map layers, none without a cited boundary row, with ETag caching and a
write-back that outlives the request.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0014 Contracts for process science, region profile, voice and media](0014-science-region-voice-media-contracts.md) |
| The review that fixed it | [0022 Voice spend fails closed, a filtered style hint, region sources and one home per rule](0022-batch-3-review-fixes.md) |
| The contracts it names | [region.md](../contracts/region.md) |
| What amended it | [0153 Rivers are named from Wikidata then OpenStreetMap, groundwater comes from the India data portal, a region place shows its headline values, and the geo ETL fails every gap it can see](0153-rivers-named-groundwater-loaded-and-region-values-chosen.md): the region's headline values and its stored state series |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0014 fixed the region contract (`docs/contracts/region.md`, `backend/app/schemas/region.py`,
three golden files) and left lane 0016 its producer: `GET /api/crafts/{slug}/region`,
`GET /api/map/layers` and `GET /api/map/layers/{layer}`, built from the tables the geo ETL loads
(`EnvDataset`, `DistrictEnvValue`, `DistrictGeology`) and the district seed (`AdminState`,
`AdminDistrict`). PLAN 8 asks for grid and period on every value, "Practised across the state" for
state-only crafts, inherited districts that say so, and no empty facet; PLAN 0 for open data and a
citation on every fact. The full geo load was running while this lane was built, with the
`load.py` that drops the per-row grid, so the code had to answer correctly with no rows, with rows
loaded before this change, and with a full load. The answer stream's debt register also asked for
the write-back to survive a learner who leaves, and for craft descriptor vectors to be filled.

## Decision

1. **A `geo` layer** (`backend/app/geo/`), pure like `science`: it may import `schemas`,
   `research` and `core`; `services` and `api` may import it. `services/region_records` and
   `services/map_layer_store` read rows into `geo/records`; `geo/places` decides the places,
   `geo/aggregation` the state aggregates, `geo/region_view` and `geo/layers` build the contract
   models. The routes hand one to the other, as the process route does (decision 0015). Constants
   the services need from the contract (`AGGREGATED_STATS`, `BOUNDARY_DATASET_CODE`) reach them
   through `geo`, since `services` may not import `schemas`.
2. **Migration `0005_region_profile`** adds `DistrictEnvValue.resolution`, `EnvDataset.url`,
   `DistrictGeology.lithologyName` and `.method` (geo contract rows 3 and 5), and an index on
   `(datasetId, variable, depthOrPeriod, stat)` for the layer queries. `load.py` now loads
   `resolution`. Rows loaded before the migration are backfilled once: WorldCover and Copernicus
   DEM rows take their grid from the method text the ETL wrote with the same string
   (`read at <grid>;`, `area_spherical_km2 at <grid>;`), and GLiM rock codes take the names of the
   GLiM legend (Hartmann and Moosdorf 2012, the ETL's `GLIM_CLASSES`). Without the backfill a
   WorldCover share read at 40 m would be shown at its native 10 m until the multi-hour ETL ran
   again. Dataset links (`url`) are not backfilled: they arrive with the next load, and a missing
   link hides nothing that is cited.
3. **Places.** A cited `DISTRICT` location, or a `POINT` placed in the district whose polygon
   covers it (lowest LGD when polygons overlap; its own `districtLgd` when no polygon covers it),
   is one district place; two locations in one district are one place cited by the stronger level.
   A location whose source is missing or `RESTRICTED` is not shown and is logged. A cited `STATE`
   location is a state place too, and competes with the master list for its state by level (the
   master list is `REVIEWED`; a cited location wins a tie). `All India` in the master list is not a
   state; any other unmatched state name is logged.
4. **Values.** A district place shows every stored value of its district. GLiM writes each class
   share twice, as `DistrictEnvValue` `lithology_<code>` and as a `DistrictGeology` row; the geology
   row carries the name, so it is the one read (variable `lithology`, the name as `valueText`, the
   share, `SHARE`, `fraction`) and the `lithology_*` twins are not. Geology rows without an area
   share (the MRDS occurrence list) are not values; the MRDS counts come from the value table.
   Values within a facet are ordered by dataset, variable, depth from the surface down, period,
   `ENV_STATS` order and value text, so the golden craft file lists clay before pH.
5. **State aggregates** are computed in Postgres per request from a materialised CTE of district
   areas (`ST_Area` of the geography, on the sphere) and finished in `geo/aggregation`: count,
   area-weighted sum, area, sum, minimum and maximum per series, so one query answers a state of
   any size. Two series are sparse: GLiM class shares and MRDS per-commodity counts exist only
   where the class or commodity occurs, so for them every district of the state that holds any
   value of the dataset counts, with zero where the row is absent (`ABSENT_MEANS_ZERO`); averaging
   over only the districts that have sandstone would overstate the state's sandstone. A state
   aggregate lists every grid its districts were read at and their distinct methods. Values are
   rounded to the 6 decimals the table stores.
6. **Layers.** A registry of 21 layers in facet order (`geo/layers.MAP_LAYERS`), each one dataset,
   variable, stored depth or period and stat; the facet comes from `DATASET_FACETS`, the unit from
   the stored rows (exactly one, or the layer fails loudly), and a CHIRPS layer's period from its
   dataset row, since CHIRPS is built for a run's years. Classes are Hyndman and Fan type 7
   quantiles (`statistics.quantiles(..., method="inclusive")`, the rule of R and d3), at most
   `min(5, distinct values)` classes, inner breaks kept to 3 significant figures and dropped when
   they fall on the range's ends. The hand-written classes of the golden layer file followed no
   rule a server could reproduce, so the file now carries the computed ones (6.4, 7.08, 7.64, 7.88,
   8.04, 8.3) and the client specs' expected fills and legend changed with it. `version` is the
   SHA-256 of the canonical JSON (sorted keys, no spaces) of everything else in the body, so any
   change to the values, classes, grid, dataset row or caption moves the ETag; the contract's
   "dataset sha256 and rows" missed edits to the dataset row, and most dataset rows have no
   sha256.
7. **No boundary row, no layers.** Without the `DR_DISTRICT_SHAPES` dataset row a map cannot cite
   its boundary, so `/map/layers` answers 404 and so does every layer; the client already hides the
   picker when the list fails. Before any geo load a craft's places still answer, with no facets.
8. **HTTP caching** (`core/http_cache`): `quoted_etag` and `etag_matches` moved from
   `services/craft_catalogue` now that a second route uses them, with `revalidated`, which sets the
   ETag and `private, no-cache` or answers 304, for both the catalogue and the layer.
9. **The write-back outlives the request** (`core/shielded.ShieldedWork`, one per process on
   `app.state`): `SqlAnswerStore.keep` runs as a task the request awaits through `asyncio.shield`,
   so a learner who leaves no longer rolls back research already paid for. The task is held until
   it ends, a failure after the caller left is logged, and shutdown waits up to 8 s
   (`DRAIN_SECONDS`, inside the unit's 25 s stop timeout after uvicorn's 15 s drain) and logs what
   is still running. Shielding the planner and composer too was rejected: a learner who leaves
   should stop new spending, not continue it.
10. **Craft descriptor vectors** are filled by `app.scripts.embed_craft_descriptors` after the seeds
    and the craft sync on every release (a failure is a warning, like the sync) and first in the
    daily Coverage enrichment run, which fills what a failed release left.

## Consequences

- The three region routes answer from stored rows; the golden craft, list and layer files are
  reproduced byte for byte from hand-built rows by DB tests on GitHub Actions and from records by
  DB-free tests.
- A district place carries every stored value (about 300 with the full load) and a state place
  every aggregable series; aggregates are recomputed per request. Both are in the debt register.
- The sparse-series rule and the twin rule depend on how the GLiM and MRDS layers write rows;
  a change there must change `ABSENT_MEANS_ZERO` or `LITHOLOGY_TWIN_PREFIX` with it.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
