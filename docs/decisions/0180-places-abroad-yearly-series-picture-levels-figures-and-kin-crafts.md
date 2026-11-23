# 0180. A place abroad sits in its own inset, a yearly series is one row, picture levels come from glossary tags, the fibre asks paper figures, and a generated page shows its kin crafts

A timeline place beyond the India frame is a pin in an inset frame of its own bounds, ask the map
folds a yearly series into one row with a sparkline, the zoom reads a picture's level from the
glossary terms it names (each tagged with the scale its definition states), the fibre level asks
the figures of open-access articles in Europe PMC after Commons and Openverse, and a generated craft
document draws its kin crafts. The craft page's film score is not built: it waits on the owner.

Date: 2026-11-23. Status: accepted (the lead's evening round brief, lane D, maps and pages). It
amends [decision 0060](0060-zoom-timeline-and-film-renderers.md), item 4 (a place beyond the frame
was a signpost), [decision 0057](0057-zoom-story-and-timeline-map.md) (picture levels read from
word lists only, no figure source) and [decision 0065](0065-climate-risk-and-ask-the-map.md), item 6
(the screen listed every year). The contracts are `docs/contracts/explainer.md` (the timeline's
renderer and the zoom builder), `docs/contracts/learning.md` (Ask the map), `docs/contracts/
page-layout.md` (Generated documents) and `docs/contracts/curation.md` (the glossary row).

| For | Read |
|---|---|
| The timeline renderer it amends | [decision 0060](0060-zoom-timeline-and-film-renderers.md) |
| The zoom builder it amends | [decision 0057](0057-zoom-story-and-timeline-map.md) |
| Ask the map | [decision 0065](0065-climate-risk-and-ask-the-map.md) |
| The answers' model-call rule it keeps | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| The design system's maps, charts and pictures | `.claude/skills/kalavigyan-design` |
| Every decision, by group | [README.md](README.md) |

## Context

Six entries of the debt register were this lane's. Each had more than one way to clear it: an inset
could be drawn over the map or under it and with or without India; a series could fold on the server
or the screen; a picture's level could come from a vision call or from stored data; a figure could
be hot-linked from Europe PMC, PubMed Central or the publisher; kin crafts could be a new kind or a
form of an existing one; and the page's film score could be built now or later.

## Decision

1. **The inset is a second frame under the map.** `components/map/projection.frameProjection(bounds,
   width, padding)` is the one projection; India's frame is `frameProjection(INDIA_BOUNDS)` and keeps
   its viewBox (1000 by 1114.2). When the timeline places a reached place outside it, an inset under
   the map (`components/map/AbroadInset`) draws India's outline and every place abroad, numbered as
   on the map, over bounds that hold India and those places with 4 degrees round
   (`abroadFrame.abroadBounds`), on the plain ground (`--sunk`) and never another country; a route
   with an end abroad is drawn in it too. Under the map, not over it, because no corner of India's
   frame is free of Indian land or islands at every width. The signpost (`journeyGeometry.edgePost`)
   is gone.
2. **The screen folds a series; the route stays as stored.** Three or more values of one dataset,
   variable, depth, statistic, aggregation and unit whose period is one year are one row
   (`lib/yearlySeries.foldedRows`): a finding naming the highest and lowest year, a sparkline in the
   variable's series token with those two years in `--chart-emph`, a break at a missing year, and
   the table behind "All N values". Two years stay two rows.
3. **Picture levels come from stored tags, never a model call.** `Term.zoomLevel` (migration 0098:
   `WORKSHOP`, `CLOTH`, `FIBRE`, `MOLECULE`) is the scale a term's own label or definition states:
   the label's last word if it is a scale word, else the one scale its meaning's words name, none
   when it names none or two; a science seed compound is `MOLECULE` because its record says so. The
   glossary seed writes it and every curated import fills a term that has none. A picture naming a
   tagged term of its craft in any of the term's names takes the term's level, beside the level
   words; a `FIBRE`-tagged term names the craft's fibre when its fibre materials name none. A vision
   check was refused (decision 0165 holds an answer's model calls).
4. **Figures come from Europe PMC's legends and PMC's CDN.** `sources/images/europe_pmc_figures`
   searches figure legends (`FIG:`) among open-access full texts, reads the first two articles under
   CC BY, CC BY-SA or CC0, and offers each figure with its legend, first author, its article's
   licence and the article's DOI page, the image from the CDN path the JATS processing instruction
   names, because Europe PMC's own figure URLs answer a challenge page to a script. A figure with its
   own permissions or a legend that cites or credits another work is left out. The zoom asks it for
   the fibre only, after Commons and Openverse find none; section pictures do not.
5. **Kin crafts are the declared form of `related_crafts`.** A generated craft document places one
   `related_crafts` component in the kin chapter from the page's relatives that have a cited lede
   sentence (`services/monograph_generated_kin`): each kin craft's name, page, states, GI and
   monograph marks, the material terms both crafts name and the lede as a held, cited unit, with the
   family line for its swatch. Its spec carries `head`, so `eitherView` draws it with
   `kinds/data/KinCraftsView` and Kutch Ajrakh's authored spec keeps `RelatedCraftsView`.
6. **The page's film score waits.** Job step 5 would make ElevenLabs music for every curated page
   each night with no reader asking, and no page plays a film since decision 0162; it waits on the
   owner's approval of that spend and on a film player for the page (debt register).

## Consequences

- The release carries migration `0098_term_zoom_levels` (parent `0095_candidate_check_differs_on`);
  the deploy's glossary seed and curated import fill the tags. A page's stamp moves once, as its
  glossary terms changed.
- A fibre picture may now be a paper figure whose page is a DOI; once research stores that paper,
  the figure's `sourceId` is it.
- The register keeps two entries rewritten: the kin crafts' capture and AI imagery, and the film
  score with AI media.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `frontend/e2e/journey-renderers-unit.spec.ts`,
`frontend/e2e/district-series-unit.spec.ts`, `frontend/e2e/kin-crafts-unit.spec.ts`,
`backend/tests/terms/test_term_scales.py`, `backend/tests/terms/test_glossary_plan.py`,
`backend/tests/journey/test_zoom_level_terms.py`, `backend/tests/journey/test_zoom_figures.py`,
`backend/tests/sources/test_europe_pmc_figures.py`, `backend/tests/layouts/test_generated_kin.py`,
`backend/tests/db/test_term_zoom_levels_db.py` and `backend/tests/db/test_kin_materials_db.py`.
