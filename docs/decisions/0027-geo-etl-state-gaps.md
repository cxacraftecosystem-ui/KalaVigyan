# 0027. Geo ETL: district shapes are polygons only, and a part that loses a state fails

The geo ETL keeps district shapes as polygons only, and each part states its coverage, so a part
that loses a whole state fails instead of passing quietly. `--allow-failures` tolerates scattered
districts only, and shards never outnumber the states asked for.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| What amended it | [0153 Rivers are named from Wikidata then OpenStreetMap, groundwater comes from the India data portal, a region place shows its headline values, and the geo ETL fails every gap it can see](0153-rivers-named-groundwater-loaded-and-region-values-chosen.md): coverage: reviewed districts without cells, silent districts, the probe and the CHIRPS period |
| Every decision, by group | [README.md](README.md) |

## Context

Geo ETL run 43884310432 (`cxacraftecosystem-ui/KalaVigyan`, commit `c6bf4cd`, datasets `all`,
states `all`, 12 shards, `allow_failures` and `load` on; attempt 2 green) loaded:

- CHELSA and CHIRPS for 468 of 752 districts: nothing for 15 states.
- SoilGrids for 631 of 752: nothing for Andhra Pradesh, Gujarat, Tamil Nadu and West Bengal, and
  nothing for Mumbai (482).
- WorldCover, Hansen and Copernicus DEM for 745 of 752, and GLiM for none: GLiM wrote no value
  and no geology row (the 752 `DistrictGeology` districts are all MRDS).

Every failure in the part files is `RuntimeError: Mixed-type geometries not supported.` from
exactextract: 29 in each of CHELSA shards 6, 8, 10 and 11, 130 in the same CHIRPS shards, 72 in
the same SoilGrids shards, one to three in those WorldCover, Hansen and DEM shards, and one for
GLiM covering all 752 districts.

**Cause.** `districts.assemble` returned what `make_valid` gave. The vendored rings are quantised
to 0.001 degree, and in seven districts some collapse into zero-width spikes that `make_valid`
keeps as lines beside the polygons, so the district became a `GeometryCollection`: South 24
Parganas (304) and Cooch Behar (308) in West Bengal, Kachchh (449), Morbi (673) and Gir Somnath
(675) in Gujarat, Thanjavur (586) in Tamil Nadu, Konaseema (747) in Andhra Pradesh. exactextract
refuses a collection that mixes areas and lines, and the error ends the whole `exact_extract`
call. What was lost followed each layer's call: one district for WorldCover, Hansen and the DEM
(one call per district); the state for SoilGrids (per state); the whole shard for CHELSA and
CHIRPS (one call per shard), so the other states sharing shards 6, 8, 10 and 11 with those four
went too (Meghalaya, Sikkim, Uttarakhand; Assam, Dadra and Nagar Haveli and Daman and Diu,
Lakshadweep, Tripura; Arunachal Pradesh, Haryana; Chhattisgarh, Kerala); and everything for GLiM
(one call per run). MRDS and HydroRIVERS use shapely, which accepts collections. Coastlines,
projections, bounding boxes and tile edges played no part: CHELSA and CHIRPS are single global
files, and every other shard of each layer completed with no failure.

**Why it passed.** `extract` returned 0 under `--allow-failures` whatever the failures covered,
so parts with no rows at all went green.

**Mumbai.** SoilGrids masks every cell of the district (built-up land and water): a WCS read of
its window on 2026-11-17 returned 0 finite cells of 2,720. No row and no failure were written.
This is the dataset, not a defect; no re-run fills it.

**CHIRPS in attempt 1.** Shard 12 printed nothing from 15:39:38 to 18:41:55 UTC, then failed in
`latest_year` with "no CHIRPS v3.0 annual file found for the last four years". The year was found
by opening each candidate file through GDAL `/vsicurl/` (`raster.exists`). With the workflow's
`GDAL_HTTP_MAX_RETRY=6`, `GDAL_HTTP_RETRY_DELAY=5` and `GDAL_HTTP_TIMEOUT=120` each year took
about 45 minutes against a server that did not answer, and every timeout or server error read as
"no file for this year". The other eleven CHIRPS shards had read from the same server minutes
before, and attempt 2 found 2025 at once: the server stalled, and the lookup turned the stall into
a false "missing". Had one older year answered, that shard alone would have used another period.

## Decision

1. **District shapes are polygons only.** `assemble` keeps the Polygon and MultiPolygon parts of
   the repaired shape (`districts.polygonal_part`) and drops collapsed lines and points, which have
   no area. Only the seven districts change; their areas agree to 1e-15 square degrees, and every
   shard keeps the same states. A test runs all 752 districts through one exactextract call.
2. **Each part states its coverage.** `geo_etl/coverage.coverage_of` gives every part
   `districtsWithoutValues` (selected districts with no value or geology row) and `lostStates`: a
   state none of whose selected districts has a row, or one whose selected districts are all named
   by a single failure (a step lost for the whole state). Both go into the part JSON and the
   summary's `layers`; the workflow summary shows how many districts have no values.
3. **`--allow-failures` tolerates scattered districts only.** A part with a lost state exits 1
   with or without the flag, after writing its files; without the flag any failure still exits 1.
   In practice the flag now covers only the per-district layers (WorldCover, Hansen, DEM) missing
   some districts of a state. A failed SoilGrids, CHELSA, CHIRPS, MRDS, GLiM or HydroRIVERS step
   covers a whole state or more, so it fails the part.
4. **The CHIRPS year is found over HTTP.** A HEAD per candidate year, newest first, each with 4
   attempts (connect 10 s, read 60 s, waits of 5, 10 and 15 s). Only 404 or 410 means "no file for
   that year". Any other persisting error falls back to the listing of `annual/global/tifs/`,
   parsed for `chirps-v3.0.<year>.tif`; when both fail the part stops and names both causes. The
   worst case is about ten minutes, not three hours.
5. **One retry helper.** `layers.with_retries` (4 attempts, waits of 5, 10, 15 s) is the one home
   for retrying; the SoilGrids WCS read uses it with the schedule it had.
6. **Shards never outnumber the states asked for.** The plan job caps `shards` at the number of
   states in `states`. An empty shard exits 2 by design and would stop the combine and load.

## Consequences

- The fix must be on `main` before the re-run; the old code fails the same four shards again.
- Re-run for run 43884310432's gaps, one dispatch at a time (the `geo-etl` concurrency group keeps
  one pending run and cancels an older pending one), each with `load` on:
  1. datasets `chelsa,chirps`, states `5,6,11,12,16,17,18,19,22,24,28,31,32,33,38`, shards 12.
  2. datasets `soilgrids,worldcover,hansen,copdem`, states `19,24,28,33`, shards 4: the four
     SoilGrids states and the seven districts the other three layers lost.
  3. datasets `glim`, states `all`.
- The upsert rewrites only the keys in the new files; values already loaded keep their keys.
- A run with `allow_failures` can now go red where it went green. The failing part names its
  states; when the cause was transient, re-running the failed jobs is the remedy.
- Mumbai keeps no SoilGrids values and is listed under `districtsWithoutValues` in every SoilGrids
  part that selects it (`docs/DATA_SOURCES.md`).
- Left as debt (`docs/TECH_DEBT.md`, "Geo ETL state gaps"): tile reads still treat an unreachable
  tile as an absent one, and each shard resolves the CHIRPS year on its own.

## Addendum, 2026-11-17: districts measured without valid cells

**Context.** Actions run 43949571146 (`cxacraftecosystem-ui/KalaVigyan`, datasets `glim`) failed
with "glim: states [31] lost every district or a whole step". Lakshadweep (state 31, one district,
553) lies on no land cell of the GLiM 0.5 degree grid: exactextract measured it and found no
valid cell, so it got no row and no failure. Mumbai (482) is the same case for SoilGrids and
passed only because Maharashtra's other districts had rows. Point 2's rule could not tell such a
district from one lost silently.

**Decision.**

1. Every raster layer lists the districts it measured without a valid cell in
   `Result.districts_without_cells`. `layers.Measured` reads each step's zonal table (per district
   for WorldCover, Hansen and the DEM; per state for SoilGrids; per shard for CHELSA and CHIRPS;
   per run for GLiM) and lists a district when the table returned it and its `pixels` (exactextract
   `count`, which skips nodata) was 0 or NaN in every step: nodata everywhere under the polygon,
   or the polygon outside the grid. A polygon smaller than a valid cell still gets a value, since
   exactextract weights by coverage fraction. A district missing from the table, or in a step that
   raised, is never listed: it stays silent or failed.
2. Such a district gets no rows. WorldCover and Hansen wrote 0.0 shares, areas and losses for it;
   they now write nothing, as the other layers already did.
3. `coverage_of` counts it as accounted for. It stays in `districtsWithoutValues` and is also in
   `districtsWithoutCells`, which gives the reason. A state is lost when none of its selected
   districts has a row or is listed without cells, or when one failure names all of them. A failure
   still outweighs the no-cells list, and a state with no row, no listing and no failure is still
   lost. This is the state-level reading: a state with no rows passes when at least one of its
   districts is listed without cells, even if another is silent.
4. `districtsWithoutCells` goes into the part JSON and the summary's `layers`. The workflow summary
   shows its count beside districts without values.

**Consequences.** Re-run 3 (datasets `glim`) needs this on `main`. It is expected, from the
synthetic tests and run 43949571146's message, to list 553 under both keys instead of failing on
state 31; that is not yet observed on the real grid. Left as debt under "Geo ETL state gaps": an
unreachable tile or a grid read as nodata everywhere now reads as "no valid cells", and a silent
district does not fail the part when another district of its state is accounted for.

## How this record is kept true

Its Addendum of 2026-11-17 records what followed the decision that day. Beyond that it is not edited
except to mark it superseded: a later choice is a new record that names this one, and the table
above links the two both ways. It records the choice as taken on 2026-11-17; what the code does
today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the [contracts](../contracts/README.md).
