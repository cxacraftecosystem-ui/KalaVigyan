# 0196. A contributor's map is drawn by the site, from places it resolves, on its own base map and layers

A contributor delivers a map as a declared `timeline_map`: it names its places by Wikidata item,
LGD district or cited coordinate and captions them with dated points, routes and undated facts;
the server resolves every place through the place finder the answers use and refuses one it
cannot; and the web draws it with the answers' timeline map on the site's base map, framed to the
places, with the relief, rivers, minerals or a district layer beneath by name, the page's place in
its terracotta hatch and the boundary note and datasets cited. A map drawn by hand is refused with
a pointer to it.

Date: 2026-11-24. Status: accepted (the lead's lane `maps` of the page-quality round; the owner,
2026-11-24, on the Sanganeri page built over MCP: "maps are shitty"). It amends
[decision 0114](0114-kinds-and-datasets.md) (the authored scripts left the contributable list;
`timeline_map` returns in its declared form, and 23 kinds are delivered) and
[decision 0177](0177-differences-named-and-the-monograph-shell-measured.md) (the served kind
fixtures, which now carry a timeline map's recorded placement). The contracts are
`docs/contracts/component-specs-general.md` (The declared timeline map) and
`docs/contracts/component-specs-data.md` (`timeline_map`); the reference is
`backend/app/data/contributor/references/datasets.md` (Maps of places).

| For | Read |
|---|---|
| One kind per job, and why the authored scripts were withheld | [decision 0114](0114-kinds-and-datasets.md) |
| The answers' timeline map and its place finder | [decision 0057](0057-zoom-story-and-timeline-map.md), [decision 0147](0147-time-market-and-figures-kept-true.md), [decision 0160](0160-place-builders-kept-true.md) |
| The kind fixtures served with each drawing's themes | [decision 0177](0177-differences-named-and-the-monograph-shell-measured.md) |
| The site's physical and district layers | [decision 0016](0016-region-profile.md), [decision 0114](0114-kinds-and-datasets.md) |
| A places map drawn on the same base, told what it is about (amends this record) | [decision 0232](0232-every-places-map-drawn-on-the-site-s-own-map-base-and-told-what-it-is-about.md) |
| A physical layer credited from the record its own file carries, and every layer's record read over MCP (amends this record) | [decision 0253](0253-a-stage-s-own-scene-a-compound-its-facts-name-and-every-map-layer-s-dataset-record.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **The contributor had no map but its own drawing.** `timeline_map` was an authored script
  (`AUTHORED_SCRIPT_KINDS`) and `not_contributable` told an agent to "deliver a drawing, a timeline
  or a map_layer instead". The agent building Sanganeri Hand Block Printing drew its own dot map and
  a plain timeline as SVG; the owner judged them far below Kutch Ajrakh, whose timeline map and
  why-here maps were authored by hand for that page.
- **The answers already draw maps from real places.** `TimelineMapBuilder` places a timeline's
  places at a register district's centroid, a curated Wikidata point or Wikidata's coordinates, and
  the web draws the block with `TimelineMap` on `IndiaMap` (land, state lines, salt flats, coast and
  the Survey of India outline with its boundary note), with routes, a year slider and keyboard pin
  controls. The site holds its own relief, rivers and mineral layers (`tools/maplayers`) and
  district layers (`geo/layers.MAP_LAYERS`).
- **`lookup` read an item's coordinates nowhere.** The dataset guide told an agent to place a
  point at its Wikidata item's coordinates "read with lookup", but the entity lookup returned the
  item's statements without its point and kept nothing a delivery could read.

## Decision

1. **`timeline_map` is delivered in its declared form.** A spec with `places`
   (`DeclaredTimelineMapSpec`) is declared; one without is Kutch Ajrakh's authored route map, kept
   for that page and refused from a contributor with `MAP_POINTER` (`withheld_form`,
   `DECLARED_ONLY_KINDS`). `timeline_map` leaves `AUTHORED_SCRIPT_KINDS` (now `model_explainer`
   alone), so 23 kinds are contributable and served as schemas; its schema is the declared form's
   (`DELIVERED_FORMS`), without the server's parts. The forms are told apart by `places`, not
   `head`, because the authored form has a `head` too (`declared_form`, `DECLARED_MARKS`, and the
   web's `declaredForm`).
2. **The spec is the answers' block in units.** Places (1 to 30) named one way each, `home` for the
   page's own; points, routes and undated facts (up to 40 each) whose text is a unit; up to three
   layers by name. The delivery holds each entry to the answers' own rules unit by unit: its years
   stated by its unit, its place named by its unit, a route's move stated from start to end, a
   cited coordinate stated and cited by its `at` unit.
3. **The server places it.** `placed_spec` resolves a district at the register's centroid and a
   Wikidata item from the site's held point, then the place finder's kept answer, then a finder the
   caller passes; a coordinate stands as cited. Each point takes the district whose shape holds it,
   a home place must lie in one, and every unresolved place is refused by name. The layers are
   checked against what the site holds, and the stored spec carries each place's `found` point, the
   boundary and layer dataset records and the boundary caption. A spec that sends any of these is
   refused.
4. **`lookup` keeps an item's point.** An entity lookup asks the Wikidata place finder for the
   found items' points through `StoredPlaces`, which keeps them in `PlaceLookup` as the answers'
   place finder does, and returns each item's `latitude` and `longitude`; a delivery naming that item
   then resolves without a network call.
5. **The web draws it with the answers' timeline map.** The timeline view model is generic over what
   an entry says (`TimelineSource`), and `TimelineMapFrame` draws both the answers' blocks (cited
   sentences) and the declared map (units, `TimelineMapDeclaredView`). `IndiaMap` takes a `frame`,
   with pins, leaders and the hover card sized and placed within it, and `placesFrame` frames the
   map to the places. `useTimelineMapLayers` draws the named layers with the craft map's own
   drawings and keys and the home districts in the place hatch. The map rests on its last year with
   every place pinned, undated places included.
6. **A map drawn by hand is refused.** A `drawing` or authored `map_layer` is a map when it paints
   the base map's land, coast, borders or salt, draws with the page kit's map frame and pins, marks
   two or more places as dots in the place colours, or draws an outline of 60 points or more with
   two dots on it; it is refused with `MAP_POINTER`. Kutch Ajrakh's own hand-drawn maps would be
   refused from a contributor; a section, a mechanism or a vat is not a map.
7. **The fixture is Bidriware.** `kind_fixtures/timeline_map.json` maps bidri from Bidar under
   Ahmed Shah Bahamani to the courts of Purnia, Murshidabad and Lucknow and the artisans' move to
   Hyderabad, from five dossier facts word for word, at the five districts' register points, over
   relief and rivers; its `placed` part is the server's placement, merged when the fixtures are
   served and parsed.

## Consequences

- An agent maps a page's places without drawing anything: the refusals name the place to look up,
  the year or move a unit does not state, or the layer the site does not hold.
- Kutch Ajrakh's page is unchanged: its authored `timeline_map` and map layers keep their specs and
  views, and only a contributor's copy of their form is refused.
- The answers' timeline map draws exactly as before; its parts take optional frames and layers.
- The placement runs inside `component_proposals_spec.checked_delivery`, after the dataset cells,
  so preview, propose and registration all see the placed spec.
- A declared `map_layer` (places by coordinate with values) keeps its job, a value per place from a
  dataset; a map of places through time is the timeline map.

## How this record is kept true

| Claim | Kept true by |
|---|---|
| The declared form, its rules, the authored form refused, the guide's keys and layers | `backend/tests/research/test_timeline_map_specs.py` |
| Places resolved and refused, layers held and credited, a looked-up point kept | `backend/tests/db/test_timeline_map_places_db.py` |
| The hand-drawn map refused and a non-map drawing allowed | `backend/tests/research/test_drawn_maps.py` |
| 23 kinds delivered, each with its fixture | `backend/tests/research/test_kind_fixtures.py`, `backend/tests/mcp/test_tool_budget.py`, `frontend/e2e/kind-fixtures-unit.spec.ts` |
| The web drawing the kind at rest, framed, hatched, at phone and desktop widths, and Kutch Ajrakh's view kept | `frontend/e2e/timeline-map-declared-unit.spec.ts` |
| The answers' timeline map unchanged | `frontend/e2e/journey-renderers-unit.spec.ts`, `sentence-once-unit.spec.ts`, `timeline-undated-unit.spec.ts` |
