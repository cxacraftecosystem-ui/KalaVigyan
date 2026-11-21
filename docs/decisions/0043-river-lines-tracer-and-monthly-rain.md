# 0043. River lines, the tracer and monthly rainfall

HydroRIVERS lines for India are stored with their licence and credit, a tracer follows `NEXT_DOWN`
and computes the districts each trace reaches in PostGIS, and CHIRPS monthly rainfall normals are
kept per district. A route serves the traces, and a workflow loads the data.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0042 Phase B contract: place, matter and the expert panel](0042-phase-b-contract.md) |
| The review that fixed it | [0050 Phase B review fixes](0050-phase-b-review-fixes.md) |
| The contracts it names | [region.md](../contracts/region.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Plan section 3 (`docs/plans/answer-experience.md`) needs HydroRIVERS lines for India, a path
tracer over `NEXT_DOWN` with the districts crossed computed in PostGIS, and CHIRPS monthly
normals per district. Decision 0042 fixed the shapes other lanes build to (`research/rivers.py`,
`docs/contracts/region.md` Rivers and Monthly rainfall). The geo ETL already downloads
HydroRIVERS v1.0 (Asia) for district aggregates and CHIRPS v3.0 for rainfall. Nothing heavy runs
on the laptop: the ETL runs on GitHub Actions and is the only writer of the river tables and
files.

**Licence, checked 2026-11-17.** The HydroRIVERS Technical Documentation v1.0 (October 2019,
section 4.1) puts HydroRIVERS under "the same License Agreement as the HydroSHEDS database":
free for non-commercial and commercial use. That agreement is Appendix A of the HydroSHEDS
Technical Documentation v1.4 (April 2022,
https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf): the data
may be distributed only incorporated into derived products, never as a stand-alone product
(2.1.2), and Exhibit B's copyright statement must go with the product's documentation or
metadata. The licence page the catalogue named before (`/terms-of-use`) covers the website's own
materials, not the data. HydroRIVERS asks to be cited as Lehner and Grill (2013).

## Decision

1. **Licence and credit.** The `HYDRORIVERS_1_0` dataset row names the v1 License Agreement and
   links Appendix A; its attribution is Exhibit B's statement with "KalaVigyan" as the product,
   so it travels with every citation of the dataset row. River geometry is only drawn inside the
   app for signed-in readers; it is never offered as a download or export.
2. **Which reaches.** Every HydroRIVERS v1.0 Asia reach with `UPLAND_SKM >= 100` km²
   (`LINE_UPLAND_MIN_SKM`) in a basin (`MAIN_RIV`) at least one of whose kept reaches crosses a
   district polygon, so a river crossing India is kept whole, from Tibet or Nepal to its mouth.
   Upstream area only grows downstream, so the filter keeps every `NEXT_DOWN` inside the table;
   a river's source as drawn is its first reach of that size. The ETL refuses the whole run on
   any network problem (a reach listed twice, flowing into itself, into a reach not kept or into
   another basin, an outlet rule broken, a cycle, a measure out of range, a line that is not one
   line) and writes nothing.
3. **Stored.** `RiverBasin` (`mainRiv`, the dataset row, reach count, topology SHA-256) and
   `RiverReach` (the contract's fields, a `LINESTRING` in EPSG:4326, GiST-indexed), migration
   `0016_river_reaches`, with check constraints mirroring the contract and RLS on. A load uploads
   the topologies first, then replaces both tables in one transaction, upserting the dataset row.
4. **Topology files.** One TopoJSON per basin: each reach is simplified on its own with the
   topology-preserving Douglas-Peucker at 0.005 degree (about 550 m), which keeps both ends, so
   every junction stays a shared position; positions are quantized to 100,000 steps over the
   basin's box and delta-encoded, one arc per reach. Keys are
   `media/rivers/<edition>/<mainRiv>/KalaVigyan_Dataset_HydroRIVERS-1-0_River-Topology_Basin-<mainRiv>.json`
   (`services/naming.river_topology_key`; the ETL mirrors it and both run the `riverTopologies`
   rows of `shared/naming-golden.json`). Decision 0050 adds the file's SHA-256 as a folder before
   the file name, so a stored row and its object never drift. Each object carries its SHA-256 as metadata, so a re-run
   uploads only what changed. The app's media key (`media/*`) writes them; no new grant.
5. **The tracer** (`geo/river_trace.py`, pure): from a reach, downstream over `NEXT_DOWN` to the
   outlet, and upstream at each junction to the reach with the largest `UPLAND_SKM` (ties: the
   lowest `HYRIV_ID`) until a headwater. At most 10,000 reaches on a path and 250,000 in a basin;
   a cycle, a `NEXT_DOWN` that is not stored or a reach of another basin is refused
   (`RiverNetworkError`), and every trace passes `rivers.trace_problems`, which now takes any
   reach topology (`ReachTopology`). Traced from the outlet it is the basin's main stem.
6. **Districts reached are computed per trace**, not once per basin at load as 0042 said: PostGIS
   intersects the path's reaches with `AdminDistrict.geom`, dumps each intersection into parts and
   takes `ST_LineLocatePoint` of each part's start; districts are ordered by path position, then
   entry fraction, then LGD, and kept at their first entry. This follows the stored district
   shapes as they are and needs no second table to keep in step.
7. **Offered rivers.** `services/river_store.rivers_crossing(district_lgds)` answers, per basin,
   the reach with the largest upstream area inside those districts, largest first, at most five;
   it is the start reach a region story traces from (lane 0044).
8. **The route.** `GET /api/rivers/{mainRiv}` (signed in) reads the basin row, releases its
   connection before the bucket is read (decision 0040), answers 304 to a matching
   `If-None-Match` without touching the bucket, and serves the file from a 48 MB per-process cache
   keyed by its hash, else from the bucket. A file whose hash differs from the load's is not served
   (decision 0050). 404 for an unknown basin, a missing file or a changed one; 503 when the bucket
   is not configured or does not answer; 422 for an id no reach can have.
9. **Monthly rainfall needs no new extraction.** The CHIRPS layer already writes twelve
   `monthly_precipitation` rows per district (`<period>-<MM>`, `NORMAL`, `mm/month`, the 0.05
   degree grid), only when every year of the period has every month. `services/monthly_rain`
   reads the twelve months of the CHIRPS dataset row's period for a district and answers
   `MonthlyRain` with the dataset row; a missing month, a negative value or another unit gives no
   rainfall. A contract test pins the ETL's row call to the reader's constants.
10. **Workflow.** `riverlines` joins the Geo ETL's datasets (`all` includes it); one job builds the
    lines and files whatever the states and shards, and with `load` a second job uploads and
    replaces the tables using `DATABASE_URL`, the app's AWS key and `MEDIA_BUCKET` (decision 0050
    replaced the key with a scoped OIDC role). Every dispatch
    now lints and tests `etl/geo` first. `boto3` joins the ETL's dependencies (the backend's floor).

## Consequences

- After the backend deploy that carries migration 0016, dispatch Geo ETL with `riverlines` and
  `load` (`docs/RUNBOOK.md`, Geo ETL). Until then the river route answers 404 and the tracer finds
  nothing, so no river is offered.
- The phase B fixture's reach ids stay placeholders until that run gives the traced Kachchh
  river's ids (`docs/TECH_DEBT.md`).
- The largest basins (Ganga-Brahmaputra, Indus) are files of a few MB; see the debt register.
- `shared/river.topology.golden.json` is the fixture's placeholder river written by the ETL's
  encoder; the ETL tests reproduce it byte for byte and a client unit spec parses it with
  `riverBasinOf`, so the writer and the reader of the file are tested against each other.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
