# 0098. How the craft page chapters were built: the readings taken where the contract was open

While the craft page chapters were built, the readings taken where decision 0095's contract was open
were recorded in eighteen items, among them the answer builders' pure halves reused, one ledger for
the page, a lazily written archive and a minimal novelty rule for readers' pieces. What was not
built yet is recorded with them.

Date: 2026-11-18. Status: accepted. Implements decision 0095 (craft page schema version 3) for the
page builders, the snapshot store and the routes; records what is not built yet.

| For | Read |
|---|---|
| What superseded part of it | [0100 The Kutch Ajrakh craft page is the hand-built monograph, served as built](0100-ajrakh-monograph-served-as-built.md): its renderer, for Kutch Ajrakh only, until 2026-11-20 |
| What amended it | [decision 0162](0162-unused-craft-page-chapters-retired.md): the pieces not built yet, the reader's pieces (item 8), the archive (items 6 and 13) and job steps 2 and 3 retired rather than built |
| What it builds on | [0095 The craft page becomes a monograph in chapters, public to read, built without a question](0095-craft-page-chapters.md): the page builders, the snapshot store and the routes |
| The contracts it names | [craft-page.md](../contracts/craft-page.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0095 and `docs/contracts/craft-page.md` describe the chapters, the rules that replace a
question and the cache. While building them some rules needed a reading, and some pieces could not
be built from the rows a page may read.

## Decision

1. **The answer builders' pure halves are reused, with a rule for the model's choice.** The page
   calls `region_story.region_story_block` with a `StoryChoice` built from the dossier's places by
   role, `climate_risk.climate_risk_block` with the meaning claims in dossier order,
   `timeline_story.timeline_entries` and `timeline_block` with a `TimelineChoice` built from the
   dated facts, `market_builder.market_block`, `material_cards.material_card` with a `CardChoice`
   of the material's own facts, `science/ladder.process_ladder`, `science/reaction_player` and
   `signature_blocks.signature_block`. No page builder calls a model, a search or the network.
2. **One ledger for the page.** `services/chapter_ledger.PageLedger` wraps the answer's
   `ClaimLedger`: blocks go through `admit` once per chapter; page parts drop a sentence whose text
   the page has shown, and a sources-differ reading the page has shown becomes `shownIn`. A
   sentence never counts as shown by itself. Open questions keep their hypotheses and drop facts
   already shown. A plate whose record entry is dropped is kept as a plate of its own.
3. **Seasons read the craft's practice only.** A seasons row comes from a stage's SEASON timing, or
   from a fact naming a month or a season in PROCESS, CLIMATE, MATERIALS, BOTANY, ECOLOGY or
   GEOGRAPHY. A GI filing date names a month but isn't a season of the work.
4. **A stored explainer joins only when the page lists its claims.** The same rule as decision
   0096's "which show". (The first explainer fixture cited science-seed claims the preview does not
   hold and was not placed; item 18 replaces it.)
5. **Pictures without a placement keep their version 2 places.** For a schema 1 dossier, or a
   picture with no placement, the hero becomes the masthead, a stage picture goes to its ladder
   stage, and the rest are At a glance plates. A stage picture whose stage is not on the ladder is
   a plate in How it is made.
6. **The archive is written lazily.** When a rebuild finds the stored snapshot under another
   curation version, it copies that snapshot to `CraftPageArchive` first. The import does not need
   to call the page.
7. **The `OPEN` variant reads `research/retrieval.chunk_acls_for(None)`.** That is the anonymous
   reader's set, the same as a signed-in Student's (decision 0097).
8. **A reader's pieces join by a minimal novelty rule.** `services/craft_page_answer_assets.py`
   reads the craft's answer pieces (not stale, superseded or hidden) and adds one to its kind's or
   facet's chapter only when every claim it cites is listed and it adds something the chapter
   lacks: a kind not there yet, or a claim not shown. A kind the page rebuilds from rows keeps the
   page's own. Each item is marked `READERS` with the month it was asked; the question text is never
   shown until the screen of decision 0096 is built.
9. **Migration 0031** creates `CraftPageSnapshot` and `CraftPageArchive` (one row per craft and
   variant, one per craft, curation version and variant) and adds `Compound.conformerKeptAt`.
10. **The preview's stored rows come from a fixture file.** `shared/craft.page.inputs.json` holds
   the geo rows, conformers and explainers that the golden adds. Its yearly climate values are
   synthetic (debt register).

11. **The stamp reads what the page reads, and only that** (review of 2026-11-19). Each term is
   scoped to the craft: its concepts, claims, citations and their sources by the craft claim scope
   (`retrieval/statements.scope_claims`); its family's claims and citations
   (`CuratedCategoryClaim`); the relatives' crafts, curations and claims (same sub-category);
   materials and compounds of its stages and concepts, with kept conformers; pictures and media
   refs linked to its or its family's claims; locations, GI, prices, workforce; geo values of its
   mapped districts, the dataset rows and the Wikidata points of its dossier places; its pieces
   and AI assets; its field recordings, segments and images, the set of portal streams fresh as
   `field_scope.fresh_portals` reads them (`lastContactAt` per stream); the artisan-images setting;
   and its testimony (count, latest change, approval and withdrawal) and conversations. The site
   address joins the release in the stamp, because Cite this writes it.
12. **A process keeps the last pages it served.** `services/craft_page_cache.PageCache` on
   `app.state.craft_pages` keeps 48 pages as served bytes with their stamp and ETag; a hit costs the
   stamp read. Builds are single-flight: a per-process lock per craft and variant, then a
   transaction advisory lock, and the stored snapshot is read again before building. The route
   sends the stored bytes with the stored ETag. `?version=N` compares `N` with
   `CuratedCraft.version` before anything is built.
13. **Archived versions carry no field voice or testimony.** `craft_page_archive.without_field_voices`
   drops `artisan_voice` and `field_photos` items, `voices` and `fieldPhotos`, zeroes the totals and
   drops a source only they cite, when a version is archived and again when it is read, so a
   withdrawal or a hold never reaches a frozen version.
14. **The job runs steps 1 and 6.** `app.scripts.build_craft_chapters [--craft]` keeps the 3D
   conformer of every CID of the crafts' compounds (`Compound.conformerKeptAt`), stores the P625
   point of every dossier place with a Wikidata id in `WikidataPoint` (one row per item, migration
   0031), then rebuilds both snapshots of every curated craft and every craft with a snapshot,
   logging a body that changed under its stamp. It runs nightly from Coverage enrichment.
15. **Rules read narrowly.** `start_research` asks whether the craft has a claim of its own (the
   family's don't count). A dossier's `whyClaimId` is the stage's only why, left out when the stage
   already shows it; the rule's fallback runs only for a stage the dossier gives no why. The
   fallback `after` keeps the stated change from its last verb when the whole is longer than 120
   characters, never a cut. A curated stage with no fact of its own takes the claims the dossier
   lists for it, its why claim excepted, so every curated stage reaches the ladder. A claim's
   season row is labelled by its stage, material or tool, else the season it names first, else
   its months; claims are read in dossier order (`CuratedPage.claimOrder`, filled by the import,
   empty for an older index). A dated record is labelled with the span as its text states it
   (`research/timeline.years_stated`). Timeline names add a district's other names
   (`data/district_other_names.json`: Kutch for Kachchh). The version 2 `HERO`, a relative's hero
   and the catalogue hero are the picture placed `MASTHEAD` when it is inline. The family source
   group keeps the family label's case.
16. **No river is chosen.** HydroRIVERS basins carry no name, so the region story's river rule
   (an offered basin whose name a step states) never matches; the page draws no river until basin
   names are stored (debt register).
17. **Cite this is absolute and resolvable.** Text and BibTeX (`howpublished = {\url{...}}`) carry
   `PUBLIC_WEB_URL` and the lower-case path; `url` stays the path. `knowledge_view.resolve_craft`
   falls back to one case-insensitive slug match, and the web app reads `/crafts/<slug>/v<N>` with
   `?version=N`.
18. **The golden's stored explainer is the craft's own.** `shared/explainer.craft-mechanism.golden.json`
   is what `SimulationBuilder` makes from a recorded draft over Kutch Ajrakh's C078 and its reaction
   R02 (`tests/simulations/craft_mechanism.py` holds the build, and a test holds the file to it); the
   inputs store it as the `kut` explainer, so the golden places it. The register golden is built
   with the Textiles family, as production builds it.

## Consequences

- `what_if`, `concept_graph`, `zoom_story`, `supply_map` and `measure` are not on the page yet,
  and one reaction player holds every step (debt register, "Craft page chapters not built yet").
- Live pages show molecules only after the job's first run keeps conformers, and Kutch Ajrakh's
  timeline has no pins until its places carry Wikidata ids (debt register).
- The rest of decision 0096 (cross-craft pieces, the question screen, AI media and their routes,
  film scores) and job steps 2 to 5 are not built (debt register).
- `READ_ALL_EVIDENCE` is removed from `core/roles.py`, and `research/craft_page.without_evidence`
  is gone.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
