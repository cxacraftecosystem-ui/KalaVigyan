# 0085. The story map's layers redraw what it shows, and zoomed answer maps carry an India locator

Choosing a layer in a region story classes the districts it draws among themselves, so the map
visibly changes, and its legend says so and reads the values out. Zoomed answer maps carry an India
locator.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contracts it names | [explainer.md](../contracts/explainer.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked an Expert question on Kutch Ajrakh and reported that the answer's map offered five
layer buttons (Water plus elevation, annual precipitation, distance to a major river and river
density) and that choosing one changed nothing. The code did switch: the chosen layer was fetched
and its national class index painted every district in the story's view. But the story's view is
zoomed to a handful of neighbouring districts (Sirohi, Banaskantha, Patan, Kachchh, Morbi, Barmer
and their neighbours), and national quantile classes put nearly all of them in the same one or two
classes for every one of those layers, so each layer drew the same pale tone. The story showed no
reading per district, and its legend, below the map, named national bands that the drawn
districts barely spanned. The zoomed map also gave no sense of where in India it was.

## Decision

1. **Classes over what is drawn.** When a layer is chosen in a region story, the districts drawn in
   the story's view are classed among themselves, by the server's own rule (inclusive quantiles,
   at most five classes, breaks cut to three significant figures: `geo/layers.quantile_classes`),
   implemented once on the client in `lib/layerClasses.ts` (`viewClasses`, `layerInView`) and
   tested against values the server's function gives. The values themselves are the layer route's,
   unchanged; only the shading is relative to the map.
2. **Say so, and read the values out.** The legend under a layered story names the layer, says
   "Shades compare the N districts on this map." and gives the local bands
   (`StoryLayerReadout`); each story district is listed with its reading (`districtReading`, "No
   data" when the layer has none). A layer with no value for any drawn district says so instead of
   drawing nothing.
3. **An India locator on zoomed maps.** `components/map/IndiaLocator.tsx` draws the India outline
   and the marked districts' shapes (with a dot at each centroid, so a small district stays
   visible at inset size) from the outline and district shapes the client already bundles and
   loads; no tiles or new service. It is an `img` named "Where in India: <district>, <state>; ...".
   The region story puts it in a corner of its stage, under the step badges and clear of pointer
   events, with the story's frame outlined; the zoom story's district map shows it while the camera
   is zoomed in. Maps that already draw the whole of India (map layers, supply pins, the timeline
   map, the zoom map at rest and under reduced motion) are their own locator and get none.

## Consequences

- No payload or contract field changes; the place paragraph of `docs/contracts/explainer.md` now
  describes the layered story and the locator. `e2e/story-layer-unit.spec.ts` holds the failing
  case that proved the defect (two layers, same tones) and the locator's markup.
- The classing rule now has two implementations, one per language, held equal by hand-derived and
  server-derived expected values in the unit spec; a change to `quantile_classes` must change
  `viewClasses` in the same change.
- The production E2E's unknown-craft step and its compare outcome now find their alert by text or
  inside `main`, so Next's route announcer (an alert in a shadow root) no longer makes the locator
  match two elements, and a failed step is reported with Playwright's "Error:" line and without
  terminal colours (`checks.errorHeadline`).
- The quiz route's "nothing to quiz" answer (204, from the lead's backend change) reads as no quiz
  on the client (`learningApi.fetchExplainerQuiz` returns null), so the answer page neither logs a
  shape error nor shows a failure.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
