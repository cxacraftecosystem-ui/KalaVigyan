# 0057. Zoom story and timeline map builders

The `zoom_story` builder asks no model, reaches beyond the section for the district level and takes
kept pictures before searching, and the `timeline_map` builder offers dated spans by reference. A
counting numeral is never offered as a year, and undated statements stay off the timeline.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0054 Phase C contract: generated explainers, the what-if lab, zoom, timelines and film mode](0054-phase-c-contract.md) |
| The review that fixed it | [0061 Phase C review fixes](0061-phase-c-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Lane 0057 of phase C (`docs/plans/answer-experience.md` section 4, features 1 and 4; decision
0054) builds the `zoom_story` and `timeline_map` blocks through the block builder registry. Their
version-1 fields and validators were fixed by decision 0054 and the Kutch Ajrakh fixture pins
both. Owner rules bind: every fact cites a source or a dataset row; dates, places and coordinates
come from claims or datasets, never from a model, which may only choose and order; real geometry
under the boundary caption; a level without a licensed image is absent, never faked; no
connection held across a model call or HTTP (decision 0040); untrusted text only inside untrusted
blocks.

## Decision

1. **Two registry entries, waiting for their renderers.** `zoom_story` for `MATERIALS` sections
   (20 s) and `timeline_map` for `HISTORY` sections (30 s), from `services/journey_builders.py`,
   listed after the simulation entry in `PIECE_BLOCK_ORDER` order. Neither kind joins
   `BUILT_BLOCK_KINDS` here: the renderers are lane 0060's, and a kind is built only when both
   sides exist (decision 0042). Until then `from_registry` does not start them.
2. **The zoom asks no model.** Every level's caption is chosen by the server: the first stored
   fact that names the level's matter (the district's register name, the compound's name) or that
   the picture illustrates, and that no earlier level uses. A model would only pick among a handful
   of claims the server can already rank, at a cost per section. Captions are distinct so two
   levels never repeat one sentence; a level whose only caption is taken is left out.
3. **The district level reaches beyond the section.** A materials section rarely names the
   district, so the zoom also offers the craft's stored fact claims whose sentence or quotes name
   a mapped district (`knowledge_view.claims_for` ranked by the district names, at most 8), with
   their source refs returned as the builder's added sources. Without the `DR_DISTRICT_SHAPES` row
   there is no district level and these claims are not read.
4. **Pictures: kept ones first, then two searches, never a link card.** The open pictures already
   kept as `MediaRef` rows for the offered claims are read in the same short session
   (`media_ref_store.stored_pictures`, `INLINE` only); only levels still missing are searched, on
   Commons and Openverse only (SearXNG's web pictures are never shown inline). A picture's level
   is read from its own title and description words (`zoom_pictures.LEVEL_WORDS`, checked fibre,
   workshop, cloth); a fibre picture also names a micrograph word and the craft's fibre, which is
   a named fibre (`FIBRE_NAMES`: cotton, silk, wool, ...) in the name of a `FIBRE` material. Its
   relevance is the section pictures' rule (two shared content stems with a claim), and for a
   fibre a claim that names the fibre, since a micrograph shares little text with any claim. A
   chosen picture is kept through `SqlMediaStore.keep`, so the next answer finds it stored.
5. **The molecule level is the molecule block's compound.** `molecule_candidates` (decision 0045)
   offers the compounds the section names; the first whose name a claim states and whose 3D
   conformer the PubChem adapter keeps in the private bucket becomes the level, at most 3 tried.
6. **The timeline offers spans by ref.** Each dated fact of the section is offered with its
   quotes and its spans of years (`y1`, ...) on a server line outside the untrusted blocks; the
   model answers refs and place words, and the server keeps a point only where the sentence or a
   quote names the place, and a route only where one text states the move from its start to its
   end (`timeline.states_movement`). The years shown are always a span the texts state.
7. **A numeral that counts is not offered as a year.** `timeline.years_offered` drops a single
   year whose every use is followed by a plural lowercase noun ("1500 artisans"), which decision
   0054's debt entry asked the first builder to do. The validator's `years_named` is unchanged.
8. **One placing rule.** `supply_places.named_places` is the supply origins' placing (decision
   0047) generalised over named places, and the supply map now calls it; a timeline place's
   context words are the capitalised words of every text that uses it. `section_images` exposes
   `searched_images` (one service, fallback texts, a time limit), and `builder_evidence` holds
   `known_fact` and `fact_sentence`, so the new builders write none of these again.
9. **Undated statements stay off the timeline.** The plan asks that undated or unplaced claims be
   listed without a point; version 1 has no undated point and was fixed by decision 0054, so an
   unplaced place is listed without a pin (the client lists it beside the map) and an undated
   statement is not offered. Changing that needs a version 2 of the kind.

## Consequences

- Nothing a reader sees changes until lane 0060's renderers join both kinds to the built kinds.
  After that, materials sections of answers for a craft show a zoom of two to five levels and
  history sections a timeline map, each costing at most two image searches per service and one
  plan-model call from the answer's headroom respectively.
- Both builders reproduce the phase C fixture from recorded responses: the zoom from stored rows,
  the kept workshop picture and the recorded conformer; the timeline from the recorded Wikidata
  searches and coordinates, with only Fustat placed.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
