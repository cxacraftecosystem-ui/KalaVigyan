# 0019. Craft page process timeline, region panel and map choropleths

The craft page gains a cited process timeline and a region panel, and `/map` gains district
choropleths of the environment layers, every response checked at the boundary. One citation
numbering covers the page, and presentation stays in the client.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| What superseded part of it | [0092 The KalaVigyan design system: Alum & Indigo](0092-design-system.md): its colour, type and motion choices; its behaviour stands |
| The contract it was built to | [0014 Contracts for process science, region profile, voice and media](0014-science-region-voice-media-contracts.md) |
| The review that fixed it | [0022 Voice spend fails closed, a filtered style hint, region sources and one home per rule](0022-batch-3-review-fixes.md) |
| The contracts it names | [science.md](../contracts/science.md), [region.md](../contracts/region.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0014 fixed the science and region contracts and gave lane 0019 the screens that read
them: the process and region of `/crafts/[slug]`, and the environment layers on `/map`. The
process and region routes (0015, 0016) are built at the same time, so the client is built against
`docs/contracts/science.md`, `docs/contracts/region.md` and their golden files in `shared/`.
PLAN 0 binds every choice below: every fact on screen cites, nothing waits for review, open data
only, no gap admissions or how-it-works copy. PLAN 7 asks for KaTeX with mhchem and `trust:false`,
PLAN 8 for grid and period on every value, the state-only and inherited wording, no tile basemap
and the boundary caption beneath every map, PLAN 14.1 for icon-and-word evidence badges with a
scoped `evidence` ramp.

## Decision

1. **Tabs.** The craft page has Overview, Region, Process, Materials and Sources. Process reads
   `GET /crafts/{slug}/process` instead of the profile's `stages`, whose `durationText` is uncited
   (the science contract keeps durations as cited readings only). Reactions belong to their stage,
   so the Science tab is gone; the profile's `science` was always empty. The Map tab became Region:
   the places map and the environment beneath it. An old `?tab=map` or `?tab=science` opens
   Overview, as any unknown tab always has.
2. **Loading.** The profile loads first; the process and region load together once it has
   arrived. Each tab has its own loading, failure-with-retry and empty state (`useRemote`,
   `RemoteView`), so a failing region route never hides the process.
3. **Checked at the boundary.** Each response is parsed by its shape, then by the cross-field
   rules the screen depends on: a reading's claim and a cited enthalpy's claim are among the
   item's claims, every species has a name or formula, every value's dataset is listed, a layer
   has values and its own dataset (`checkedProcess`, `checkedRegion`, `checkedLayer`). A broken
   answer shows "Couldn't load…" with Try again and logs the failing path; nothing half-drawn.
4. **One citation numbering per page.** The profile's numbering comes first and the process's
   sources are appended (`craftSources`), so opening the Process tab never renumbers a chip
   already read. Numbers, sources and the open action reach every chip through
   `CitationProvider`; a chip opens the answer view's `SourceDialog`. The Sources tab lists both.
5. **The timeline.** Stages by ordinal, with the shared `staggerParent` and `riseItem`. Each stage
   shows its cited claims, materials (role, compound formula through KaTeX, a PubChem link for a
   compound id), conditions (the stated phrase, the normalised range in the contract's unit, each
   reading with its own citation, "Sources differ" when flagged) and reactions (the server's
   mhchem equation with a spoken label, the species names beneath; a species-only reaction drawn
   as its species; Balanced or Unbalanced; ΔH only beside its claim's citation). An `OUTSIDE`
   reading shows "Outside usual range" without the envelope's numbers: the envelope is a check,
   not a cited claim, and an uncited range would be a fact without a source.
6. **Evidence badges.** Icon and word for every level (PLAN 14.1). Verified and Reviewed move to a
   scoped `evidence` ramp at hue 150 on purple's eleven lightnesses, chroma
   `min(purple's, 0.94 × sRGB gamut maximum)` (the skill's rule for scoped ramps), replacing the
   literal success tones and a stock emerald so both themes hold: 800 on 100 is 7.52:1, 200 on
   950 11.69:1, 700 on white 6.44:1, 300 on the dark card 10.71:1. Sources differ, Outside usual
   range, Unbalanced and Balanced are `EvidenceSignalBadge`, which the answer view's reactions now
   use too.
7. **The region panel.** One card per place: a district place under "Kachchh district · Gujarat",
   a state of practice under "Practised across the state", an inherited district with "Values for
   Gujarat as a whole; Kachchh has no district outline." Its basis names the source, its page
   number and level. Facets follow `REGION_FACETS`; each value shows its label, its reading through
   the one unit formatter (`lib/measure.ts`) and "statistic · dataset · grid · period". A Data list
   gives each dataset's title, publisher, edition, licence, attribution, citation and distinct
   methods. A craft without places has no panel.
8. **District shapes and choropleths.** Both maps draw the existing `district-shapes.json` through
   `DistrictFills`, clipped to the DataMeet outline, which is redrawn above the fills and stays the
   only international border; there is no tile basemap. The Region tab fills the district places
   and the states of practice. `/map` gains a Layer picker (`SearchableSelect`, hidden when the
   layer list fails or is empty), the choice kept in `?layer=`; values are drawn on the
   coverage map's five-step purple ramp, spread out when a layer has fewer classes, with neutral
   "No data", a legend of ranges with units, the layer caption, the dataset credit and a summary
   for screen readers. The server's boundary caption and the district-shape source sit beneath
   the map. Hover or tap shows the district's value. The layer is fetched with
   `revalidateFromHttpCache`, so its ETag answers 304.
9. **Presentation stays in the client.** Variable labels, statistic wording and unit symbols are
   in `lib/regionView.ts` and `lib/measure.ts`; the wire carries codes, which a contract change
   would otherwise have to translate.
10. **Budgets.** The craft page split into header, tabs and panels; `IndiaMap`'s pins and scale bar
    moved to `MapMarks.tsx`; pure rules sit in `lib/` so the unit specs test them on the golden
    files with hand-worked values.

## Consequences

- The profile route still sends `stages` and `science`, which the page no longer reads.
- The map layer carries LGD codes only, so a district's value is shown without its name.
- The screens have not been seen running yet; the production build and smoke specs run on
  GitHub Actions. Each item is in `docs/TECH_DEBT.md`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
