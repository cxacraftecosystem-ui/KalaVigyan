# 0047. Seasons and supply

The `seasons` and `supply_map` blocks are chosen by the server with no model: a season becomes
months only through a cited mapping, and rainfall is the first craft district with twelve normals.
Supply links are words the model chooses and the server checks, with coordinates only from Wikidata.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0042 Phase B contract: place, matter and the expert panel](0042-phase-b-contract.md) |
| The review that fixed it | [0050 Phase B review fixes](0050-phase-b-review-fixes.md) |
| Season months from a craft's stored calendar claims, regional months and new seasons, register pins and kept place lookups | [decision 0160](0160-place-builders-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Lane 0047 of phase B (`docs/plans/answer-experience.md`, decision 0042) builds the `seasons` and
`supply_map` blocks through the block builder registry. Their fields and validators were fixed by
decision 0042, the CHIRPS monthly normals by decision 0043 and their renderers by decision 0048.
Owner rules bind: every fact the reader sees cites a source or a dataset row; months, districts,
coordinates and numbers come from claims or datasets, never from a model, which may only choose
and order; a named Indian season is mapped to months only where a source states the mapping; no
connection held across a model call or HTTP (decision 0040); untrusted text only inside untrusted
blocks.

## Decision

1. **Two registry entries.** `seasons` for `CLIMATE` sections (8 s, no model) and `supply_map` for
   `MATERIALS` sections (30 s, one plan-model call and Wikidata), from
   `services/season_supply_builders.py`. Both kinds join `BUILT_BLOCK_KINDS` on both sides in this
   change; their renderers (decision 0048) were already registered.
2. **Season rows are chosen by the server, no model.** One short session reads the craft's Process
   rows, its rainfall and the subjects of the section's claims. Rows, in this order
   (`services/season_rows`): each stage of the craft in process order whose stored fact claims
   name a month or a season (the first such claim; its months and season), else whose claim the
   section cites (listed without a month); then the section's own fact claims that are no stage's
   and name a month or a season, labelled by their concept's name. A claim is read from its own
   text: months of the year only (`calendar.year_months`: a month next to a day or a year is a
   date, never a season), one season only (`only_season`; a text naming two gives none); a month or
   season its clause rules out (not, never, except, until, ...) times nothing (decision 0050). At most
   12 rows, timed rows kept first; no timed row is no block.
3. **A stage may be listed without a month.** `SeasonRow` now admits a row with no months and no
   season when it is a stored stage (`stageId` set): the owner asked that a stage with no dated
   claim be listed, not placed. Any other row still needs months or a season its sentence or quotes
   name. No version-1 seasons payload existed (the kind was never built), and the client already
   draws such a row as its label and sentence with no month cells.
4. **A season becomes months only through a cited mapping.** `calendar.season_months(quote)` reads
   a source's own words for a season joined to one month range: the season word, then at most 8
   words, then the range (`monsoon months bringing in 650mm of rain from June to September`), or
   the range, then at most 3 words, then the season word (`the June–September monsoon`), with no
   sentence break, no clause word (`and`, `but`, `when`, ...), no other month or season between;
   each range serves one season, read forwards first. A row that names a season and no month takes
   the months of the one mapping all offered quotes agree on (`season_mappings`; two different
   spans for a season map nothing), and its sentence carries the mapping's citation after its own,
   at the weaker of the two levels, so the validator finds every month in a cited quote. A mapping
   stated only in a claim's paraphrase, never in a quote, maps nothing.
5. **Rainfall is the first craft district with twelve normals.** The craft's mapped districts
   (`place_offers.mapped_districts`) in order, each read with `monthly_rain.district_rainfall`;
   the first complete one is the block's `rainfall` with its CHIRPS dataset row (period and
   resolution). No complete district leaves `rainfall` null and `datasets` empty; the rows stay.
6. **Supply links: the model chooses words, the server checks them.** `supply_links.supply_offer`
   offers the craft's materials a section sentence names (at most 8, by first mention) and the
   section's fact claims (at most 12) followed by those materials' own stored claims (at most 16
   statements). One plan-model call (`composer/supply_map`, every material and statement inside
   an untrusted block) answers `{statement, material | none, materialWords, origin}`. A link is
   kept when its statement and material refs were offered, its origin is stated by the sentence or
   its quotes and an unstored material's words are too (the `SupplyLink` validator), the material
   is not its own origin, and the pair is new; at most 12. A stored material is shown by its
   glossary term's label (the contract's first choice), else its stored name, with its material id
   and term key.
7. **Coordinates only from Wikidata, through its adapter.** `WikidataAdapter.place_candidates`
   asks `wbsearchentities` (English, items, 10 hits) and keeps hits whose matched label or alias
   is the origin; `place_points` asks one SPARQL query for P625 of the chosen items and reads only
   Earth points in range, preferred rank over normal, never deprecated, and nothing when one rank
   holds two different points (`sources/reference/wikidata_places`). An origin is placed when one
   item matches it, or when exactly one of several has a description naming a capitalised word of
   the link's sentence or quotes (Shikarpur "in Sindh" is the Sindh city, not the Gujarat
   village). Anything else, a failed lookup included, lists the origin without a place: the client
   pins only placed origins. The district register is not used to place an origin: version 1 of the
   link has no field to cite a district row, and placing needs the Wikidata id the client links to.
8. **Shared pieces moved, not copied.** `services/builder_evidence` holds `section_facts` (the
   fact-level stored claims a section's blocks cite, in order of first citation; the region story's
   statements now read it) and `sources_beyond` (the source refs a built block adds; the matter
   builders now use it). `LiveSourcesStore.reference(sessions, kind)` finds a live adapter by type
   (`live_pubchem` uses it). `wikidata_statements.binding_value` reads a SPARQL cell for both the
   statements and the coordinates.

## Consequences

- Readers see seasons in climate sections and supply maps in materials sections after the deploy;
  rainfall bars wherever the CHIRPS normals are complete (decision 0043's debt entry).
- Tests: the fixture's seasons and supply blocks rebuilt from their claims, a stage without a dated
  claim listed with no month, a season mapped only through a cited quote and never through a
  paraphrase or disagreeing quotes, dates left out of months, missing monthly data dropping the
  rainfall, recorded Wikidata searches and coordinates, an origin without coordinates listed but
  not drawn, a failed lookup listing every origin, links the sentence does not state dropped, the
  registry seam for both kinds; on GitHub Actions the seasons loader against the seeded claims and
  stored CHIRPS rows and the supply links against the seeded Indigo material
  (`tests/db/test_seasons_supply_db.py`).
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
