# 0048. Place renderers: region story, map layer, seasons and supply

The region story, map layer, seasons and supply blocks are drawn in the client from one registered
module, with map code loaded on demand. The river is drawn from the served TopoJSON in the server's
order, and motion is a progress value, never the only signal.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| What superseded part of it | [0092 The KalaVigyan design system: Alum & Indigo](0092-design-system.md): its colour, type and motion choices; its behaviour stands |
| The contract it was built to | [0042 Phase B contract: place, matter and the expert panel](0042-phase-b-contract.md) |
| The review that fixed it | [0050 Phase B review fixes](0050-phase-b-review-fixes.md) |
| The contracts it names | [region.md](../contracts/region.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase B of `docs/plans/answer-experience.md` ("Place and matter", owner-approved, section 8
final) asks for a river that flows from its source across the districts it affects, map layers,
seasons and supply. Decision 0042 fixed the four kinds' fields, the river data contract
(`docs/contracts/region.md`, Rivers) and an empty client renderer registry. This lane draws the
four kinds; their builders are lanes 0044 (region story, map layer) and 0047 (seasons, supply).
The boards are `RiverFlow`, `Explainer` and `Map` of the design project. Rules that bind: every
fact the reader sees is cited, geometry is real, the boundary caption sits under every map,
reduced motion shows the end state, nothing widens a 390 px phone page (finding 8a.3), and `/ask`
stays light.

## Decision

1. **Registered through one module, map code loaded on demand.** `components/answer/place/
   placeRenderers.tsx` holds `PLACE_RENDERERS`, spread into `BLOCK_RENDERERS`. `region_story` and
   `map_layer` are `lazyBlock` wrappers (`components/answer/lazyBlock.tsx`: `React.lazy` in a
   `Suspense` whose fallback is a map-shaped placeholder), so the outline payload, projection,
   district shapes and `IndiaMap` reach the browser only when such a block is drawn; `seasons` and
   the supply list are light and eager, and the supply pin map is lazy inside it. A chunk that
   fails to load is logged and the block is not drawn. A unit spec walks the static imports from
   the registry and fails if map code becomes eager.
2. **The river is drawn from the served TopoJSON, never from the block.** `lib/riverTopology.ts`
   reads `GET /api/rivers/{mainRiv}` (revalidated through the browser cache by its ETag), parses
   the topology with the shape kit (`type`, optional `bbox` and `transform`, `objects.reaches`, a
   `GeometryCollection` of `LineString`s with integer `id` and `properties {nextDown, ordStra}`,
   arcs of at least two positions; anything else is refused), decodes quantized and plain arcs
   (negative indexes reversed, joined arcs sharing their joint once) and requires the basin's
   outlet reach. No TopoJSON library: the contract allows only line strings, and the decoder is
   forty lines with hand-derived tests. A story whose `reachIds` are not all in the basin is
   refused as a failed load (logged, Try again), so a broken trace never draws a guess; a basin
   the route answers 404 for draws the districts and steps without a river and offers nothing.
3. **Water flows in the server's order.** The path's reaches are turned so each ends where the
   next begins (`riverGeometry.orientDownstream`; a one-reach river keeps HydroRIVERS' digitised
   direction), joined and measured in projected units. Each district the river reaches lights when
   the water first enters it: the fraction along the path where the first vertex inside its real
   polygon lies, never earlier than the district before it in `river.districtLgds` (the server's
   PostGIS order wins; simplified geometry only spaces it). A step is reached with its district; a
   step with no district or one the river does not reach is reached at the end. While the water
   flows, the latest reached step outlines its district; a tapped step (or its badge on the map)
   outlines its district and draws its stretch, the reaches with a vertex inside it.
4. **Motion is a progress value, never the only signal.** Once the figure is a third in view the
   course draws over five seconds with the board's curve (`FLOW_SECONDS`, `FLOW_EASE`), a water
   front rides it and districts fill as it passes; Replay plays it again. Under either
   reduced-motion switch, or when no river can be drawn, the full course, every reached district
   and every step are shown at once and Replay is not offered. Every step's text is always shown;
   only its number bubble and badge fill as the water reaches it.
5. **The frame follows the story.** The view is the bounds of the course and the story's district
   polygons, padded 10 %, at least 120 units (about 380 km) wide, at 4:3, so the figure holds its
   height on a phone. Neighbouring districts within 100 units of the view are drawn as context
   (the widest district spans about 130 units). River widths are fractions of the view so the
   dash animation needs no `non-scaling-stroke`; district edges keep it. Step badges and the
   Source and Outlet labels are HTML placed in percent of the view, crisp at every width.
6. **Colours.** Water is the `errand` ramp (hue 255) and districts the river reaches the
   `archive` ramp (hue 195), as on the board; other story districts and every control are purple.
   Outside India's outline is the neutral `field-100`, never sea.
7. **Layers in a story** are pills over the map: the story's listed layers that `GET /map/layers`
   serves, shading the view's districts by the layer route's classes under `ChoroplethLegend`; a
   layer the list does not serve is not offered.
8. **Map layer** reuses `IndiaMap`, `DistrictFills`, `DistrictTag`, `ChoroplethLegend` (through the
   map page's `LayerStatus`) and `MapAttribution`: the route's current values and classes, the
   highlighted districts outlined (`DistrictOutlines`, new in `DistrictLayer`) with their readings
   under the map, a hover reading on wider screens. A layer the route answers 404 for is not drawn;
   any other failure offers Try again.
9. **Seasons** is one twelve-column strip (`repeat(12, minmax(0, 1fr))`): rainfall bars with the
   wettest month read out and a roving-focus button per month, month initials, then each row's
   label, its named months filled (with the months in words for screen readers) or its season
   chip, and its cited sentence; the CHIRPS row and period beneath. No month is ever drawn for a
   season-only row.
10. **Supply** groups links by material (a shared sentence stated once), shows each origin as a
    pill with its Wikidata link, and pins only origins placed with Wikidata coordinates inside the
    map's box on `IndiaMap`, numbered the same in the list, under the default caption.
11. **Citations and translation see the new kinds.** `explainerView.blockSentences` and
    `blockCitations` take every typed kind and read the steps', rows' and links' sentences, so the
    answer's one numbering, the translated-text switch and the chips cover them once they are
    built.
12. **Not built yet on the client.** `BUILT_BLOCK_KINDS` is unchanged: decision 0042 point 11 has
    the lane that completes a kind (builder and renderer both present) add it on both sides in one
    change, and this lane edits no backend file.

Shared pieces this lane moved instead of copying: `CitedText` (from `ProseBlockView`),
`RetryLine` (from the map page's layer status, now in `RemotePanels`), `districtReading` and
`NO_DATA_LABEL` (into `lib/regionView.ts`), `Swatch` (exported from `ChoroplethLegend`),
`INDIA_BOUNDS` (its own module, `components/map/indiaBounds.ts`, so the eager supply list does not
load the outline), `numberRuns` and `listText` (`lib/format.ts`), `BOUNDARY_DATASET_CODE`
(`lib/regionContract.ts`).

## Consequences

- Nothing a reader sees changes until the four kinds are added to `BUILT_BLOCK_KINDS` with their
  builders.
- `e2e/place-renderers-unit.spec.ts` parses the phase B fixture blocks, decodes a hand-written
  quantized topology against the real Kachchh polygon, and checks reduced motion, the caption, the
  empty states, the lazy imports and the shrinkable columns.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
