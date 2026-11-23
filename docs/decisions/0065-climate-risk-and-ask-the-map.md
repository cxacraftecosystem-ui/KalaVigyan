# 0065. Climate and risk, and ask the map

Climate trends use one CHIRPS period from 1981 and GHCN CAMS temperatures, with the Theil-Sen and
Mann-Kendall method stated once and no groundwater values. Ask the map reads the stored story of the
district tapped.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0062 Phase D contract: learning blocks, versions, alerts, lessons, exports and the map](0062-phase-d-contract.md) |
| The review that fixed it | [0070 Phase D review fixes](0070-phase-d-review-fixes.md) |
| What amended it | [0153 Rivers are named from Wikidata then OpenStreetMap, groundwater comes from the India data portal, a region place shows its headline values, and the geo ETL fails every gap it can see](0153-rivers-named-groundwater-loaded-and-region-values-chosen.md): groundwater from the India data portal |
| What amended it | [decision 0180](0180-places-abroad-yearly-series-picture-levels-figures-and-kin-crafts.md): the screen folds a yearly series into one row with a sparkline |
| Every decision, by group | [README.md](README.md) |

## Context

Phase D lane 0065 (plan section 4, features 12 and 14; section 3, rainfall trends) builds the
`climate_risk` block and ask the map to the shapes decision 0062 fixed: a trend is the Theil-Sen
slope per decade of a district's annual series over at least 30 years with its Mann-Kendall
p-value, cited by the dataset row whose period is the trend's; what it means for a craft is only
cited claims; a tapped district answers its cited crafts, stored region pieces and its own land
values with no model call. The geo ETL already reads CHIRPS v3.0 annual and monthly files per
district, but over the last ten years by default, and no open temperature series per year was
loaded. The phase D fixture cites `CHIRPS_3_0` over `1981-2025`.

## Decision

1. **One CHIRPS period, from 1981.** The CHIRPS layer runs from `--climate-first-year` (default
   1981, the first year of the record) to the last complete year, so the one `CHIRPS_3_0` dataset
   row's period is the period of the yearly series, the annual and twelve monthly normals and the
   trend. The alternative, a second dataset code for the long series, would have given one
   dataset two rows and changed the fixed fixture; a 45-year monthly normal is a sound baseline
   for the seasons block, which reads the row's period. The cost is four times the monthly reads;
   the runbook dispatch uses 24 shards. `chirps.run` is split into steps (the long-function count
   falls by one).
2. **Temperature from GHCN CAMS.** NOAA CPC's GHCN CAMS monthly 2 m land air temperature (0.5
   degree, 1948 to the present, one netCDF file on `downloads.psl.noaa.gov`) is public domain:
   PSL's data help page states that data on federal government servers are in the public domain
   unless annotated otherwise (checked 2026-11-18); it needs no key or account. CRU TS (CEDA
   account, ends 2024), ERA5 (key), Berkeley Earth (non-commercial), CHELSA monthly (licence
   unconfirmed, ends 2019) and IMD (terms unstated) were not used. The `ghcncams` layer downloads
   the file once a month into the run's cache, reads it through GDAL's netCDF driver (band months
   from their time tags, which must be consecutive; Kelvin outside 150 to 400 K is no data), takes
   each cell's annual mean of twelve months (a missing month leaves the cell out of that year),
   and writes `GHCN_CAMS_T2M` rows like CHIRPS's: the yearly district mean, the normal and the
   trend over the same period. It is one job whatever the shards.
3. **The trend method, stated once.** `etl/geo/geo_etl/trend.py`: the Theil-Sen slope (median of
   the slopes between every pair of years) times ten, and the two-sided Mann-Kendall p-value from
   the normal approximation with the tie-corrected variance and a continuity correction; written
   only for a complete series of at least 30 years, as `TREND_PER_DECADE` and `TREND_P_VALUE`
   (unit `p-value`) over the run period, with the method in each row. Migration
   `0021_climate_trend_stats` adds the two stats to `EnvStat` (its downgrade deletes their rows and
   restores the type); the client mirrors them with labels. A contract test pins the ETL's
   constants, stats and variable names to the backend's.
4. **The builder.** `ClimateRiskBuilder` joins `CLIMATE` sections after `seasons`, rebuilt on
   reuse because the kind is never a piece. It reads the trends of the craft's first four mapped
   districts (`geo/climate.climate_trends`: the three rows over the dataset row's period in the
   contract's units, else no trend) and offers the section's fact-level cited claims that name
   water, rain, heat, groundwater or dryness to one plan-model call within the answer's headroom,
   which picks at most six by ref. A ref not offered adds nothing; a failed call shows the trends
   without meaning; no trend, no block. Policy and NGO notes stay `in_practice`'s.
5. **No groundwater values.** No open, key-free district groundwater dataset exists in a
   machine-readable form (CGWB publishes state PDFs; the India data portal's copies need a key),
   so none is loaded and groundwater reaches a block only as cited claims.
6. **Ask the map.** `GET /api/map/districts/{districtLgd}` reads the register row, the boundary
   dataset row, the crafts with a district or point location placed there as the region route
   places it (one shared `region_records.located_places`), the newest reusable cross-craft region
   story of the district or a basin crossing it (`region_pieces.district_story_pieces`), the place
   prose pieces of the listed crafts whose topic names the district, and the district's values,
   on one session with no model call. The assembly is pure (`geo/district_view`) and reproduces
   the fixture from the region golden's rows.

## Consequences

- After the deploy that carries migration 0021, the owner dispatches the Geo ETL with
  `chirps,ghcncams`, all states, 24 shards, load and prune (`docs/RUNBOOK.md`, Geo ETL); until
  then the builder finds no trend and adds nothing, and the seasons rainfall keeps its ten-year
  period. The workflow gains the `ghcncams` dataset and a `prune` input.
- The fixture's Kachchh trend stays a placeholder until that load (`docs/TECH_DEBT.md`).
- `climate_risk` joins `BUILT_BLOCK_KINDS` on both sides, its renderer being decision 0068's, so
  a Climate section shows the block once trends are loaded. Ask the map is mounted now; its
  screen is lane 0069's.
- The region panel lists each year of both series under Climate (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
