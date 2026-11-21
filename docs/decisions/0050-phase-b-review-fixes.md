# 0050. Phase B review fixes

Phase B's review fixed fourteen issues: the conformer route releases its connection first, the
matter kinds reach readers, kinds that are never pieces are rebuilt on reuse, and builders run only
on a checked block. Takes, prose, stories and rainfall name only the times and places their sources
state, and the river files and load are content-addressed and scoped.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The lanes it reviewed | [0043](0043-river-lines-tracer-and-monthly-rain.md), [0044](0044-region-story-and-map-layers.md), [0045](0045-reactions-materials-molecules.md), [0046](0046-expert-panel.md), [0047](0047-seasons-and-supply.md), [0048](0048-place-renderers.md) and [0049](0049-matter-and-expert-renderers.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The review of phase B lanes 0043 to 0049 (`docs/plans/answer-experience.md`, decision 0042)
found fourteen issues: a route that held a pooled connection across S3 and PubChem, the three
matter kinds never reaching a reader, reused sections losing their map layers, builders running
on sections with nothing checked, a stale debt entry, two orders for phase B blocks, supply links
and story steps attaching model-chosen places to facts, season rows placed on months their source
rules out, expert takes naming months and places no source states, static AWS keys in the river
load, a river file served after it no longer matched its load, optional builder plan calls
spending the whole answer cap, and rainfall shown without its district. Two findings were the
same molecules route. Every issue was real; each is fixed below. Owner rules bind: every fact
cited, numbers, places and dates from claims or datasets only, guards fail closed, no connection
held across a model call or HTTP (decision 0040).

## Decision

1. **The conformer route releases its connection first.** `GET /api/molecules/{pubchemCid}/conformer`
   takes the request's one session (`get_session`, the same one `get_current_user` reads the user
   with), checks the stored compound, calls `release_connection` and only then builds the PubChem
   adapter and the conformer cache. The second session that checked the compound is gone.
   `tests/matter/test_molecule_route.py` records the session's queries and commits beside every
   bucket and PubChem call and fails if one starts while a connection is held.
2. **The matter kinds are built.** `reaction_player`, `material_card` and `molecule_3d` join
   `BUILT_BLOCK_KINDS` in `research/explainer.py` and `lib/explainerContract.ts` in one change;
   every phase B kind is now built (builders of 0045, renderers of 0049). The phase B unit spec
   now expects every fixture block to parse and stream and a later phase's kind to be refused.
3. **Kinds that are never pieces are rebuilt on reuse.** `BuilderEntry.rebuilt_on_reuse` marks
   `map_layer` and `molecule_3d` (they cite no claim, so they are never stored).
   `BlockBuilders.for_reuse()` keeps only those entries; `services/reused_sections` gets them with
   the answer id and its `PlanRequest` (`ReuseBuilds`), starts them over the placed pieces and the
   reused claims while those are sent, and marks, translates and streams what they add after the
   placed blocks and before the pictures (renumbered after them); their sources join the
   section's. A reused climate section keeps its map (decision 0042 point 3).
4. **No checked block, no builder.** `SectionBuilds.start` starts nothing for a section whose
   prose and ladder are both empty, so an empty section stays `EMPTY` with its note of what was
   searched instead of becoming a map or a month strip alone (decision 0042 point 9).
5. **One order for phase B blocks.** `PIECE_BLOCK_ORDER` (`research/piece_reuse`) stays the one
   order; `BLOCK_BUILDERS` is listed in it, so a fresh section shows its added blocks in the order
   a reused one reads them (a supply map before material cards). A test pins the registry to it.
   `SqlPieceStore.reusable` looks up region stories only for the facets a story is built for
   (`REGION_STORY_FACETS`, `GEOGRAPHY`) and only when one is asked, so other answers run no
   PostGIS crossing query or trace checks.
6. **A supply link is about its material.** `supply_links._link` keeps a stored material's link
   only when the statement is one of that material's own use claims or names one of its surfaces
   (its name, the term's label, aliases or local names); otherwise a model could pin a material to
   a place its sentence connects to something else.
7. **A month or season its clause rules out times nothing.** `calendar.year_months` and
   `only_season` (what places a season row) drop a month, range or season when its clause holds,
   within its five words before, a negating or excluding word (`EXCLUDING_WORDS`: not and its
   contractions, no, never, nor, neither, without, avoid, stop and their forms, and the point words
   such as except, outside, unlike, after, until). A range is judged by its first month. The bare
   abbreviations Jan, Mar and Dec followed by a capitalised word are names, not months. The
   validator still checks only that a shown month or season is named. Failing closed drops the
   fixture's second monsoon row ("so they do not expand in the rainy season"); the phase B fixture
   now holds one.
8. **Takes and prose name only the times and places their sources state.** `services/stated_names.
   unstated_names(text, supports)` lists the months, seasons and register places (every state and
   district of the LGD register, `DistrictRegister.place_names`, matched as written, whole words;
   names made only of compass words such as North or South West are left out) a sentence names and
   no cited claim text or quote states. `section_blocks.prose_problems` refuses them, so an expert
   take that adds "in March" drops its view, and `section_sentences` drops such a sentence alone
   before a section's prose is built, so one sentence does not cost the section its prose. Rivers
   are not checked: no dataset names rivers yet (decision 0044 point 5).
9. **A story step is placed only in a district its sentence names.** `region_story._steps` keeps a
   step's district only when its sentence or quotes name the district (`blocks.named_in`), else
   the step shows as "Step n" with no map focus; `RegionStoryBlock` refuses a stored story that
   places a step otherwise. Decision 0044 point 3 now says so. The fixture's four Kachchh steps
   name Dhamadka, not Kachchh, so they are unplaced.
10. **The river load assumes a scoped role.** The Geo ETL's `load-rivers` job no longer exports the
    app's long-lived AWS keys. It asks for `id-token: write` and assumes `kalavigyan-river-load`
    through GitHub OIDC (`aws-actions/configure-aws-credentials`, pinned like the other
    workflows), whose policy allows only `s3:PutObject` and `s3:GetObject` on
    `media/rivers/*` and `s3:ListBucket` limited to that prefix (without it S3 answers a missing
    key with 403 and the upload check fails). The role is in `infra/terraform/iam.tf` with the
    output `river_load_role_arn`, and `seed_secrets.py` sets the repository variable
    `AWS_RIVER_LOAD_ROLE_ARN`; the owner applies both.
11. **River files are content-addressed and fail closed.** A topology's key carries its SHA-256:
    `media/rivers/<edition>/<mainRiv>/<sha256>/<file>` (`naming.river_topology_key` and the ETL's
    `topology_key`, both pinned by the naming golden rows, which now carry the digest). A load
    writes new files beside the old ones, so a row and its object never drift. A file whose hash
    differs from `RiverBasin.topologySha256` is not served (404, the client hides the river).
12. **Builder plan calls spend only from the headroom too.** `build_answer_pipeline` takes
    `builder_plan_model` beside `builder_compose_model`; the answer route and the nightly rebuild
    build it on the answer's `AnswerHeadroom`, so the region story, supply map and material card
    calls stop once the answer keeps half its cap and never refuse a later section's compose.
    Master Admins are uncapped as before.
13. **Rainfall names its district.** `MonthlyRain` carries `district` (a `DistrictRef` from the
    district register) in place of `districtLgd`; a craft district with no register row gives no
    rainfall. The client credits "Rainfall · Kachchh, Gujarat · monthly normal · 2016-2025". No
    version-1 seasons payload exists (phase B is not deployed), so version 1 changes in place as in
    decision 0047 point 3.
14. **The production E2E asks about Kachchh's water.** A third known-answer question ("How does the
    water of Kachchh shape Kutch Ajrakh?", Detailed, English) passes only when a `region_story`
    arrives with a traced river and every step cited. While the river lines are not loaded
    (dispatch input `rivers_loaded` false) a missing story is written to the report's notes and
    does not fail; with `rivers_loaded` true it fails.

## Consequences

- Readers see reaction players, material cards and 3D molecules after the next deploy; reused
  climate and chemistry sections keep their maps and molecules.
- Before the first river load the owner applies the Terraform role and sets
  `AWS_RIVER_LOAD_ROLE_ARN` (`docs/RUNBOOK.md`, Geo ETL). The load has never run, so no file sits
  under the old keys.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
