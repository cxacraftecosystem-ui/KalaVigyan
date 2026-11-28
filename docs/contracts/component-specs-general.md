# Component specs: delivered components and the declared kinds

A component arrives finished: its kind's spec data and the texts it places, each resting on shown
facts. The 25 contributable kinds (`component_specs.CONTRIBUTABLE_KINDS`) can be delivered this
way; five of them (`drawing`, `chart`, `fact_table`, `timeline`, `map_layer`) also take a declared
spec that draws anything new from data, `diagram` also takes a declared spec that composes a
figure from the site's kit of designed parts (decision 0199), and `timeline_map` is delivered only
in its declared form, a map the site draws from places it resolves (decision 0196). The one kind
whose code runs is a `coded_figure` (A coded figure, below; decision 0231), and it runs only in a
sandboxed frame; nothing else a contributor sends is run as code. A
contributor's agent reads this over MCP before it delivers one, and engineers before they change a kind.

| For | Read |
|---|---|
| Why components arrive finished | the owner, 2026-11-20: contributors deliver whole components and pages through MCP (round 7) |
| The figure kit and the bar for hand-drawn art | [decision 0199](../decisions/0199-a-kit-of-figure-parts-and-hand-drawn-art-held-to-the-bar.md) |
| One kind per job | [decision 0114](../decisions/0114-kinds-and-datasets.md) |
| The proposal, the close-match search, drafts and bundles | [open-work.md](open-work.md) |
| Where a registered delivery is drawn | [page-layout.md](page-layout.md), Generated documents |
| The other groups' kinds | [component-specs-science.md](component-specs-science.md), [component-specs-data.md](component-specs-data.md), [component-specs-plates.md](component-specs-plates.md) |

```mermaid
%%{init: {"theme":"base","fontFamily":"Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif","themeVariables":{"fontSize":"15px","primaryColor":"#F2E9FE","primaryTextColor":"#1E1B2E","primaryBorderColor":"#9148D2","secondaryColor":"#FAEECD","secondaryTextColor":"#1E1B2E","secondaryBorderColor":"#CD9200","tertiaryColor":"#F3F1FA","tertiaryTextColor":"#1E1B2E","tertiaryBorderColor":"#A7A3BC","mainBkg":"#F2E9FE","nodeBorder":"#9148D2","nodeTextColor":"#1E1B2E","lineColor":"#AA69E9","textColor":"#857F9E","edgeLabelBackground":"#F9F5FF","clusterBkg":"#F9F5FF","clusterBorder":"#D6B6FB","titleColor":"#762CB1"}}}%%
flowchart LR
  D["Delivery<br/>spec and units"] --> M{"Close match?"}
  M -->|a copy| X["Refused"]
  M --> C["Eight checks"]
  C -->|a problem| X
  C --> R["Approval<br/>queue or at once"]
  R --> REG["Registered<br/>KnowledgePiece"]
  REG --> P["Drawn on<br/>generated pages"]
  classDef accent fill:#762CB1,stroke:#5F1C93,color:#FFFFFF
  class REG accent
```

## One kind per job

One kind per job (decision 0114): the general_* names are retired. `chart`, `fact_table`,
`timeline` and `map_layer` each take two forms of spec: a spec with a `head` is declared and drawn
by the general view, a spec without one is the authored figure of a page (Kutch Ajrakh's) and drawn
by the kind's own view (`component_specs_either.EITHER_FORMS`, `form_model`;
`frontend/components/monograph/eitherView.tsx`). `drawing` has only the declared form, and the page
tool `related_crafts` takes both too: its declared form is the kin crafts the site builds for a
generated craft document (`research/kin_crafts.KinCraftsSpec`, decision 0180). `diagram` takes
both as well: a spec with a `head` is composed from the kit (The figure kit, below) and drawn by the
kit's view, one without is a drawing or a chain of steps (`DiagramSpec`, Kutch Ajrakh's three). The page
tools (`PAGE_TOOL_KINDS`), the authored art (`AUTHORED_ART_KINDS`) and the authored script
(`AUTHORED_SCRIPT_KINDS`: `model_explainer`) are refused with a reason
(`component_specs.not_contributable`). `timeline_map` (`DECLARED_ONLY_KINDS`) takes two forms told
apart by `places` rather than `head` (`component_specs_either.declared_form`, `DECLARED_MARKS`): a
spec with `places` is declared and contributable; one without is Kutch Ajrakh's authored route map,
kept for that page and refused from a contributor with a pointer to the declared form
(`component_specs.withheld_form`, `MAP_POINTER`). Each contributable kind has a fixture for a craft other
than Kutch Ajrakh in `backend/app/data/kind_fixtures/` (`data/kind_fixture_files.kind_fixtures`, in
the preview's order), checked by the gates in `backend/tests/research/test_kind_fixtures.py`, drawn
by its view in `frontend/e2e/kind-fixtures-unit.spec.ts` and placed together on `/design/kinds`,
which reads them from `GET /api/design/kind-fixtures` with each drawing's four themes added by
`services/drawing_themes.themed_spec`, as a delivered drawing is served (decision 0177), so the
preview draws its drawing in every theme at first paint.

Last reviewed: 2026-11-26.

| Side | File |
|---|---|
| General kinds | `backend/app/models/component_kinds.GENERAL_KINDS` (the one home of the names), spec models `backend/app/research/component_specs_general.py` (`SPEC_MODELS_GENERAL`, registered in `component_specs.SPEC_GROUPS`) |
| The SVG intake | `backend/app/research/component_specs_general_svg.py` |
| Delivery (units, checks, renaming) | `backend/app/research/component_specs_general_delivery.py` |
| Checks against stored facts | `backend/app/services/component_proposals_spec.py` |
| Registration on approval | `backend/app/services/component_proposals_register.py` |
| Drawing a registered delivery | `backend/app/services/component_proposals_drawn.py`, called by `monograph_generated_assembly._drawn` and `monograph_generated.generated_parts` |
| Shapes | `frontend/lib/componentSpecsGeneral.ts` |
| Views | `frontend/components/monograph/kinds/general/` (`index.ts` exports `VIEWS`, registered in `componentViews.ts`) |
| The places map | parts `backend/app/research/component_specs_map_parts.py` (`MapParts`, the base of `GeneralMapLayerSpec`), their delivery rules `component_specs_map_delivery.py` (`map_layer_problems`), the held shapes and rivers `app/data/map_layers.py` (`held_shapes`, `held_river_names`) checked at placement by `services/map_layer_places.py` (`held_map_problems`, run by `services/timeline_maps.placed_spec`); shape `frontend/lib/componentSpecsMapLayer.ts` (`mapPartShapes`, `shownMarks`, `valueClasses`) and `lib/mapStillShape.ts`, frame and scale `components/map/mapLayerFrame.ts`, drawing `components/map/PlacesMap.tsx` and `PlacesMapMarks.tsx`, view `components/monograph/kinds/general/MapLayerView.tsx` with `MapSequence.tsx` and `useMapSequence.ts`; the still `lib/server/mapStills.ts` (`placesMaps`, `stillOfPlaces`) and `components/map/mapStillCut.ts` |
| The declared timeline map | spec `backend/app/research/component_specs_timeline_map.py`, its delivery rules `component_specs_timeline_map_delivery.py`, its places `backend/app/services/timeline_map_places.py` and placement `services/timeline_maps.py` (`placed_spec`); the hand-drawn map test `backend/app/research/drawn_maps.py`; shape `frontend/lib/componentSpecsTimelineMap.ts`, view `frontend/components/monograph/kinds/general/TimelineMapDeclaredView.tsx` on the answers' `components/answer/journey/TimelineMap.tsx` (`TimelineMapFrame`) with `components/map/TimelineMapLayers.tsx` and `placesFrame.ts` |
| The figure kit | the vocabulary `backend/app/research/art_kit.py` (`KIT_PARTS`, `kit_vocabulary`, `choice_named`, both sides' golden `shared/art-kit.golden.json`), the composed diagram `component_specs_kit.py` (`DeclaredDiagramSpec`, `kit_label_problems`), the kit scene `component_specs_kit_scene.py` (`KitScene`, `KIT_SCENE_KINDS`, `kit_scene_label_problems`), the bar for hand-drawn art `drawn_art.py` (`drawn_art_problems`, `scene_problems`); the web's `frontend/lib/artKit.ts`, `componentSpecsKit.ts`, `componentSpecsKitScene.ts`, `artKitMotion.ts`, `artKitSheet.ts`, the parts `frontend/components/artkit/` (`KitScene.tsx` for a player's scenes) and the view `components/monograph/kinds/kit/KitDiagramView.tsx`; the kit sheet `/design/kit` (`app/design/kit`) |
| Tests | `backend/tests/research/test_component_specs_general.py`, `test_component_specs_general_delivery.py`, `test_timeline_map_specs.py`, `test_drawn_maps.py`, `test_map_layer_parts.py`, `test_art_kit.py`, `test_component_specs_kit.py`, `test_kit_scenes.py`, `test_drawn_art.py`, `backend/tests/db/test_delivered_components_db.py`, `test_timeline_map_places_db.py`; `frontend/e2e/monograph-kinds-general-unit.spec.ts`, `places-map-unit.spec.ts`, `timeline-map-declared-unit.spec.ts`, `art-kit-unit.spec.ts` |

## A delivered component

A component in a draft or bundle of `propose_page` (MCP) and `ComponentProposalDraft` carry,
beside the proposal's label, title, description, kind, field, subjects and considered labels
(`open-work.md`):

| Part | What it holds |
|---|---|
| `spec` | the kind's spec as a JSON object, checked by `component_specs.checked_spec` and stored as the model writes it back (camelCase, defaults filled, a drawing's SVG cleaned); the MCP server serves each kind's JSON schema as `kalavigyan://components/<kind>.schema.json` (`api/mcp_component_schemas.py`), so the tools' own input schemas take a spec as an object |
| `units` | `{u0001: {text, claimIds}}`, at most 400, each text 1 to 600 characters with at most 20 fact ids. Unit ids are the delivery's own (`u` and four digits); every unit the spec names is delivered and every delivered unit has a place in the spec |

On MCP a spec is required except for a `SUBJECT_LINK`, which carries none. The site's own form
(`POST /api/contributions/proposals/components`) may still send a proposal without one: it is
approved for a builder as before.

**The checks**, each refusal one sentence naming every problem (`problems_sentence`, the first six
and a count of the rest):

1. the spec validates against its kind's model;
2. the spec's unit refs and the delivered units are the same set;
3. no citation is held in the spec's own text (a `cite` mark): a fact is cited through a unit;
4. at least one unit cites a fact, so the registered piece rests on facts and their sources;
5. every cited fact is stored and shown (`knowledge_view.claims_by_id`: not hidden, open, with a
   readable source), or a fact of the same page bundle (`page_proposals`);
6. every number a unit states is in its facts' texts or quotes (`quotes.unsupported_figures`); a
   unit citing nothing is a label of at most 80 characters and states no number;
7. the general kinds' values: a chart point's value is a number its `reading` unit states, a
   timeline event's year (without its sign) is stated by its `when` unit, a map place's value by its
   `reading` unit, a coded figure's value by its `reading` unit, and a numeric table column's cells
   state a number; a timeline map's years,
   places, moves and coordinates are stated by their units (The declared timeline map, below); a
   composed diagram's every part label and section layer label cites a fact, and so does every part
   label of a kit scene in a player, a toggle's stage box or a label card's seal (The figure kit,
   below);
8. the spec speaks the design's vocabulary (`drawing_spec_rules.spec_design_problems`): every
   drawing node of a science kind (`SvgNode`), every swatch, dip and colour token and a drawing's
   SVG name colours only by design role, name no font, keep text at 12 px or more and blend no two
   roles in a gradient (The design's vocabulary, below); a swatch or dip names a depicted material;
   a spec sends no `themes`, which the server draws; and every free drawing of a `drawing`, a
   `diagram`, a player, a toggle or a label card meets the bar for hand-drawn art, and every other
   kind's free drawing paints no depicted material (The hand-drawn figure, below).

The close-match search of `open-work.md` runs first: a copy of a registered component is refused
before its spec is read.

## Registration (no builder step)

The proposal row keeps the delivery (`ComponentProposal.spec`, `units`, `claimIds`, migration
`0049_delivered_components`). Approval registers it (`register_component`): an Admin's approval in
the review queue (`review_queue_components.approve_component`, "Approved and registered in the
library"), or at once for a Professor's, Admin's or Master Admin's own proposal ("Registered at once
in the library"). Registering writes one `KnowledgePiece`: the proposal's label, title,
description, kind, field (`facet`) and further fields, its owning craft, `payload {delivered: {spec,
units}, proposalId}`, `claimIds` the units' facts, `sourceIds` their sources, `topicKey`
`component:<label>`, depth `EXPERT`, language `en`, and one `KnowledgePieceSubject` per subject. A
`SUBJECT_LINK` adds its subjects to the registered piece it names. Approval is refused (409) while a
fact the component rests on is not shown, or when its facts cite no readable source.

## Drawing

Every generated document (`page-layout.md`, Generated documents) draws a registered delivery as it
draws a component with a spec file: `subject_components` reads `payload.delivered` into the
`RegisteredComponent` (`stored_delivery`; a payload off its contract is logged and left out), the
facts it rests on join the page's shown facts (`with_delivered_claims`), and `_drawn` renames its
units to page-unique ids `u5001` to `u8900` in unit order (`unit_ids.DELIVERED_UNITS`), rewrites the spec's
refs (`renamed_spec`), and places the units within the component (`within` its label) as cited
units, so each carries its citation cluster, quotes and claims like any sentence of the page. A
delivery whose facts are no longer shown is left out of the page. The web app draws the spec with
the kind's view (`componentViews.ts`); the general kinds sit in the default frame
(`monographScopes.componentPlace`: `bx-mb`, `wrap`).

## The general kinds

Each spec has `head {title, caption?}`: the title states the finding (a chart) or what is shown (a
drawing, map, timeline, table), the caption is a cited sentence under it. Every text is a unit.

| Kind | Spec | View |
|---|---|---|
| `drawing` | `head`, `svg` (one SVG in the design's roles, cleaned at intake), `alt` (what it shows) | the drawing in the reader's theme: generated documents serve `themes {light, dark, hcLight, hcDark}` (`services/drawing_themes.themed_spec`), each the SVG with every role's value from the tokens and its text in the UI face, and the view shows the variant the page's theme asks for as an image (`img` of a `data:image/svg+xml` URI at its viewBox's size), following `data-theme`, `data-high-contrast` and the system preference as the tokens do; `alt` as its description |
| `chart` | `head`, `form` (`bars` or `line`), `valueLabel` (what is measured, with its unit), `series` 1 to 3 `{name, points [{label, value, reading, cell?}]}`, `dataset?` (1 to 60, the same count in each), `emphasis` (the first series' point the title names) | one small multiple per series: bars as rows (label, bar at its share of the largest from zero, the cited reading), a line on a plot with three ticks and its first and last label, every value behind "All N values"; `--chart-series`, the emphasised mark `--chart-emph` |
| `fact_table` | `head`, `columns` 1 to 8 `{label, numeric, column?}`, `rows` 1 to 100 `{cells, row?}` (one per column), `dataset?` | a table with the first cell of a row as its header, numeric columns at the end in tabular figures |
| `timeline` | `head`, `events` 2 to 40 `{year, when, title, text}` in year order (-3000 to 2100) | a dated axis with a point to press for each event at its year (points kept apart and inside the axis, `lib/timelinePlay.spreadPositions`), its first and last year (BCE for negative years) and one Play/Pause that steps through the events in order, then one row per event: the date as written, the title, the cited sentence; it plays on its own once in view and rests on the last event (decision 0228) |
| `map_layer` | `head`, `places` 1 to 60 `{longitude 68 to 97.5, latitude 6.5 to 37.5, name, reading, value?, cell?}`, `dataset?`, `valueLabel` (only and always when places have values), and what the map is about: `frame?`, `emphasis?`, `routes?`, `rings?`, `districts?`, `sequence?` (The places map, below) | the site's map base for its frame (The places map, below), a numbered disc per place sized by the square root of its value with its name beside it, the routes, rings and district values it asks for, a sequence that plays, and the numbered list of places with their cited readings |

General figures carry their kind as the kicker ("Chart", "Table") rather than a figure number:
numbering them through the page with the answer blocks' figures is open. A page draft (decision
0110, `open-work.md`, Drafts) holds delivered components and general figures as `{proposal, cites}`
like a bundle, and its checklist report numbers every figure of the assembled page in reading order
with its kind, field and whether it cites through its units (rule 9); a declared `chart` passes rule 17
because the view draws its bars from zero.

A declared `chart`, `fact_table` or `map_layer` may rest on a contributed dataset (`dataset {code}`,
each value's `cell {row, column}`, a table's `row` and `column`): `services/dataset_cells.checked_cells`
reads each cell from the stored `DatasetTable`, refuses a cell the table does not hold or a value
that is not the number it states, lets a unit state the figures of its cells without a fact, and
replaces the spec's `dataset` with the stored record's credit and address. A dataset proposed with
a `layer` (a map layer of the site's own, the datasets reference's Map layers over MCP) stores no
table, so no component cites its cells. A component citing a dataset needs no fact of its own; an `experiment_lab` rests on its toggles' facts
(`CONTAINER_KINDS`).

### The SVG intake (`cleaned_svg`)

A drawing is at most 200,000 characters, declares no document type, entity or processing
instruction (so no entity expands), parses as XML, and is one `svg` element in the SVG namespace
with a viewBox of four numbers and a positive size. Cleaning keeps only SVG elements of the drawing
set (`KEPT_DRAWING_TAGS`: shapes, groups, text, gradients, patterns, masks, clips, markers, symbols,
`use`) and removes, with everything inside them, scripts, `foreignObject`, `image`, `style`, links
and every element of another namespace; it removes every event handler (`on…`), every attribute of
another namespace, every `href` that is not a local `#` reference, every value with an outside
`url(…)`, `image-set(`, `cross-fade(`, `image(`, `src(`, a backslash escape, `javascript:`,
`expression(` or `@import` (`research/drawing_attributes.loads_nothing`, decision 0216), and the
root's fixed `width` and `height`. The
stored spec holds the cleaned markup, and the web app only ever draws it as an image, which runs no
script and loads nothing.

### The design's vocabulary (`drawing_roles`, `drawing_rules`)

An image cannot read the page's tokens, so a drawing names its colours by role and the server
paints each theme (owner, 2026-11-21). After cleaning, a drawing is refused with a reason that
names the element and the allowed roles when it:

- names a colour other than `var(--role)` or a `color-mix` of two roles, where a role is one of
  `ink-1` to `ink-3`, `rule`, `rule-strong`, `ground`, `raised`, `sunk`, the `chart-*` and
  `series-*` tokens, a ramp step (`rain-1` to `rain-6` and the other ramps), the `map-*` tokens,
  a depicted `dye-*` or `dip-*` material, `terracotta` (place) or `madder` (a hazard), in a paint
  attribute or a style declaration; `none`, `transparent`, `currentColor`, a local `url(#id)` and,
  inside a mask or clip, white and black are kept; indigo, which means a control, is refused;
- names a font (`font-family`, `font`), or sizes text other than in drawing units;
- sets text that would draw under 12 px when the drawing is 320 px wide (its font size, with its
  groups' scales, under 12 times the viewBox width divided by 320; unsized text counts as 16);
- blends two roles in a gradient (a gradient fades one role, steps through one ramp or passes
  between depicted materials), fills text with a gradient, blurs or casts a shadow; or
- draws words as outlines (a labelled group of paths carrying type settings, glyph symbols).

Contributed SVG pictures (`image_intake_svg.clean_svg`, `give_pictures`) meet the same rule;
they are stored in roles and served by `?theme=light|dark|hcLight|hcDark`, and a plate marks
them `themed`, so the page shows the variant its reader's theme asks for. Inline science
drawings (`SvgNode`) and colour tokens are drawn with the page's tokens, so the delivery check
holds them to the roles (and the molecule kit's `mol-*` and `atom-*`) without variants. The
preview's report fails a delivered figure off the vocabulary, a drawing without its four
variants, a figure or picture without its alt text and a reaction step's species drawn with no
colour, with the lane swatch that disagrees (checklist rule 27, `page_report_species`, decision 0252).
Agents that draw
KalaVigyan's knowledge themselves read `kalavigyan://design/tokens.css` and
`kalavigyan://design/drawing.md`.

## The places map (decision 0232)

A declared `map_layer` is a map of a page's places drawn on the site's own map base, never a drawing
of geography by the contributor: the contributor says what the map is about and the base does the
rest, from the data the site holds. A spec of the old shape (`head`, `places`, `valueLabel`,
`dataset?`) is stored and drawn exactly as before, on the new base, without being delivered again.

**The base**, for the map's frame: the relief bands of `relief.json` with their hillshade once the
file lands, the rivers and lakes of `rivers.json` (Natural Earth, named from the file's own labels),
the Survey of India outline (always drawn, with and without a still), neighbouring land, state lines
and, in a frame of at most 35 per cent of India's width (`DISTRICT_LINES_SHARE`), district lines and
the small waters of OpenStreetMap (`waters.json` and its two-degree tiles, decision 0239: named
rivers and streams, unnamed rivers as plain lines), water and the Rann's salt flats in the design's map tokens, the page's home
districts in the place hatch (every `place:lgd:<code>` subject of the component), place names with
halos, a scale bar of a round number of kilometres at the frame's middle latitude, the India
locator with the frame marked, and a key (the elevation and river keys, the home hatch, the salt
flats where the frame holds them, the district values' classes). The frame is cut to the places at
least 3.5 per cent of India's width across (`MAP_LAYER_ZOOM`), and the home hatch is drawn every 9
px on the screen whatever the zoom (`components/map/PlaceHatch.tsx`). Every text and pin of the map
(place names and numbers, ring and value labels, the scale's figure, river, range and peak labels,
dams) is drawn in a layer of screen pixels over the map at the caption token, placed by its share of
the frame, so it is the caption size before and after hydration and with no script; a label whose
point lies outside the frame is not drawn (`components/map/MapLabelLayer.tsx`, decision 0239). The
source line gives the boundary note and each layer's dataset credit.

**What the map is about**, beside its places; every index counts from 0 into the spec's own lists:

| Part | What it holds |
|---|---|
| `frame` | one of `{places: [i, ...]}` (framed to those places and their rings), `{district: <LGD code>}` or `{state: <LGD code>}` (framed to the shape the site holds); without one, the map is framed to all its places and rings |
| `emphasis` | `{layers?, rivers?, dams?}`: `layers` names any of `relief`, `rivers`, `water` to draw stronger (the hillshade, the river lines, the lakes' edge); `rivers` names up to 6 rivers whose labels are always shown, each as Natural Earth names it (`rivers.json` labels), as OpenStreetMap names it (`waters`), or by a name of the site's river register that agrees with an OpenStreetMap river by name and district (a river place of a curated dossier, a river names dataset, or a river alias the register records only with a source whose quote names the rivers as one: the Suran by Kutch Ajrakh's "Dhamadka River (Suran)", the Dravyavati by the alias `RIVER_ALIASES:dravyavati`, decision 0244), drawn stronger and named in the frame; `dams` names up to 6 dams by OpenStreetMap's name for the dam or for the one reservoir it holds back, each marked where its record puts it and named |
| `routes` | `routes`, 1 to 20 `{start, end, text}`: an arrow for a move from one place to another; `text` is a unit that states the move from the start's name to the end's name and cites a fact |
| `rings` | `rings`, 1 to 6 `{place, radiusKm, text}`: a ring of a stated radius (above 0 and up to 500 km) around a place, labelled with its kilometres; `text` states that number and cites a fact |
| `districts` | `{valueLabel, values}`: 2 to 60 districts `{district, value, reading}`, each district by its LGD code and filled by the class of its value (up to five classes of near-equal counts, the density ramp), with the value printed at its centre; `reading` states the value and cites a fact |
| `sequence` | `sequence`, 2 to 12 steps `{text, places, routes, rings, districts}`: states that play in order; each step shows the places, routes and rings it names (and the district values when `districts` is true) on top of the steps before it, and `text` is its cited sentence |

```json
{
  "head": {"title": "u0001", "caption": "u0002"},
  "places": [
    {"longitude": 75.79, "latitude": 26.82, "name": "u0003", "reading": "u0004", "value": null},
    {"longitude": 75.55, "latitude": 26.82, "name": "u0005", "reading": "u0006", "value": null}
  ],
  "valueLabel": null,
  "frame": {"district": 102},
  "emphasis": {"layers": ["rivers"]},
  "routes": [{"start": 0, "end": 1, "text": "u0007"}],
  "rings": [{"place": 0, "radiusKm": 20, "text": "u0008"}],
  "districts": {"valueLabel": "u0009", "values": [{"district": 102, "value": 650, "reading": "u0010"}, {"district": 110, "value": 410, "reading": "u0011"}]},
  "sequence": [
    {"text": "u0012", "places": [0], "routes": [], "rings": [0], "districts": false},
    {"text": "u0013", "places": [], "routes": [0], "rings": [], "districts": true}
  ]
}
```

Here `u0007` says "Printers moved from Sanganer to Bagru", `u0008` "within 20 km of Sanganer" and
`u0010` "Jaipur district receives 650 mm of rain a year", each citing its fact.

**The checks.** The model (`MapParts`, `parts_problem`) refuses a frame chosen two ways or none, a
route from a place to itself, an index past the places, routes or rings, a step that shows nothing
or shows district values a map does not give, an emphasis that names nothing or names a layer
twice, a radius of 0 or past 500 km and a district given twice. Check 7 adds, unit by unit
(`component_specs_map_delivery.map_layer_problems`): a route's unit states the move
(`timeline.states_movement`), a ring's unit states its radius and a district's reading its value
(`quotes.states_value`), and every route, ring, district value and step cites a fact. At placement
(`services/map_layer_places.held_map_problems`, run by `placed_spec` after the cells), a framed or
valued district, a framed state and an emphasised river or dam the site does not hold are refused by
name (`held_water_problems`, from `app/data/layers/waters-names.json` and the `rivers.json` labels).

**The still** (decision 0220, extended). The web server's pass (`lib/server/mapStills.withMapStills`)
gives every declared `map_layer` of a page a still cut to the frame the view draws
(`components/map/mapLayerFrame.mapLayerFrame`, or for a named frame the shape's own box, sent as
`still.named` so the view frames to it): the relief bands, rivers and lakes, the home districts, and
beyond the timeline map's still the neighbouring land (`neighbours`), the district lines (`lines`),
the state lines (`states`, decision 0246, drawn from the still at first paint, so the view loads no
border file for them), each valued district's shape and centre (`valued`), the layers' dataset
credits (`credits`) and the
boundary note read from `/map/layers` (`boundary`), and in a zoomed frame its small waters
(`waters`: their lines, each emphasised river with the point its label sits at, each named dam's
point) with OpenStreetMap's credit. The view draws it at first paint in the map tokens; the
hillshade and the river and range labels arrive with their files. A map drawn without the pass
loads the waters tiles of its frame itself. Sanganeri's map's still is under 40 KB. On paper
(`services/page_export_maps.places_map_figure`, decision 0244) the PDF and Word export draw a
declared map on the same base, cut by the API from the files it holds (`app/geo/map_base`,
`services/export_map_base`): the Survey of India outline and state lines the web map draws (mirrored
into `app/data/layers` by `tools/maplayers_mirror.py`), the relief bands, Natural Earth's rivers and
lakes, district lines in a zoomed frame and the home districts outlined, with the numbered places,
the routes, each part's sentence, the layers' credits and the boundary note, at 1800 pixels across
in Word (300 dots an inch over its 150 mm). In a frame of at most 35 per cent of India's width the
paper map also draws OpenStreetMap's small waters, from the tiles the API holds beside the web's
(`app/data/layers/waters`, mirrored by `tools/maplayers_mirror.py` and the map layers build;
`app/geo/map_waters`), with each river `emphasis.rivers` names drawn strong over a halo and named
at the middle of its longest run, each dam `emphasis.dams` names marked and named, and
OpenStreetMap's credit (decision 0246).

**Every sentence on the page.** Beside the map, the numbered places with their readings, each
route's and ring's sentence under its label ("Move", "Within 20 km") and the district readings by
rank under the value label; under the map, every step's sentence with its number to press, the
shown step marked by the 2 px ink rule and `aria-current="step"`, as are the places it shows.

**Motion.** A sequence rests on its last step, with every mark shown. Where neither reduced-motion
switch is on, it plays from its first step when it comes into view, a step every four seconds, and
loops back to its first after its last, pausing out of view; one Play/Pause (`aria-pressed`) reads
Pause while it plays, its status names the step (`aria-live="off"` while it plays), and pressing a
step's number shows it at once and playing goes on from it (decision 0242: `useMapSequence` is the
shared `usePlayInView`). Under either switch nothing moves and Play steps forward one state at a
time.

## The declared timeline map (decision 0196)

A map of a page's places is drawn by the site, never by the contributor: a spec names its places
and the dated points, routes and undated facts that caption them, the server resolves every place
through the place finder the answers use, and the web draws it with the answers' timeline map on
the site's own base map. A contributed `drawing` or authored `map_layer` that is a map by hand is
refused with the same pointer (The hand-drawn map, below).

| Part | What it holds |
|---|---|
| `head` | `{title, caption?}`, as every declared kind |
| `places` | 1 to 30, each `{name, home?}` and one of `wikidata` (a Wikidata item, Q and digits), `district` (an LGD district code) or a cited coordinate (`longitude`, `latitude` and `at`, the unit that states both numbers and cites the fact that holds them); `name` is a label unit; `home: true` marks the page's own place, hatched in terracotta |
| `points` | up to 40 `{place, yearFrom, yearTo, text}`: a place at a span of years |
| `routes` | up to 40 `{start, end, yearFrom, yearTo, text}`: a move between two places |
| `undated` | up to 40 `{place?, text}`: a fact of a place with no year, pinned at every year |
| `layers` | up to 3 names the site holds, drawn beneath the places: `relief`, `rivers`, `minerals` (`tools/maplayers`, mirrored in `backend/app/data/layers`) or a district layer of `geo/layers.MAP_LAYERS` with stored values; at most one area layer (relief or a district layer) |

The model (`DeclaredTimelineMapSpec`) refuses a place named two ways or none, a coordinate without
its `at`, a map with no point, route or undated fact, an index past the places, a place no entry
names, a place listed twice, a route from a place to itself, a span whose `yearFrom` is after its
`yearTo`, a layer named twice and two area layers. Check 7 adds the answers' own rules, unit by
unit (`component_specs_timeline_map_delivery.timeline_map_problems`): a point's and a route's years
are stated by its `text` unit (`timeline.years_named`), a point's and an undated fact's unit names
its place (`blocks.named_in_texts`), a route's unit states the move from its start to its end
(`timeline.states_movement`), and a cited coordinate's `at` unit states both numbers and cites a
fact. A spec that sends the server's parts (`found`, `datasets`, `boundaryCaption`) is refused.

**Placement** (`services/timeline_maps.placed_spec`, run by `checked_delivery` after the cells): a
`district` is the register's point (`AdminDistrict.centroid`); a `wikidata` item is the site's held
point (`WikidataPoint`), then the place finder's kept answer (`PlaceLookup`, `item:<Q>`, which
`lookup` with kind entity now keeps for every item it finds, `services/entity_points.py`), then a
place finder the caller passes; a cited coordinate stands as given. Each point takes the district
whose shape holds it (`ST_Contains`), and a `home` place outside every district is refused. Each
unresolved place is refused by name: "look it up with lookup (kind entity, qid Q…) and deliver it
again". The layers are checked against what the site holds (`map_credits`: the layer files and
`map_layer_store.listed_layers`), and the spec is stored with `places[].found {latitude, longitude,
wikidataId?, districtLgd?}`, `datasets` (the boundary record `DR_DISTRICT_SHAPES` first, then each
layer's records in the order the layers are named) and `boundaryCaption` (`datasets.BOUNDARY_CAPTION`).
A physical layer's records are the ones its own file carries (`services/layer_records.physical_records`:
each code once, with the day its first download was read and its SHA-256, the registry's record as the
map layers build wrote it), whether or not the database holds a row, and a file that names none is
refused (`timeline_maps.NO_LAYER_RECORD`); a district layer's is its stored `EnvDataset` row
(`NO_RECORD` when none is held). Every layer and its record is listed in the guide page `map-layers`
(`services/layer_guide`, `get_page` with `guide` `map-layers/1`), a layer without one marked as
refused (decision 0253).

**Drawing** (`TimelineMapDeclaredView`): `withDeclared` tells the forms apart by kind
(`lib/componentSpecsTimelineMap.declaredForm`), so Kutch Ajrakh's authored route map keeps its own
view. The declared view turns the spec into the answers' timeline source
(`timelineMapSource`, each entry's sentence a unit) and draws it with `TimelineMapFrame`, the
answers' timeline map, which draws the track a plain `timeline` draws (`TimelineTrack`: one
Play/Pause and a point to press for each year, the places lighting in step, no slider; decisions 0228
and 0238), the entries through time with `aria-current="step"`, the
undated facts, pins on `IndiaMap` with keyboard pin controls, routes in terracotta and places beyond
India in the abroad inset. The map is framed to the places (`components/map/placesFrame.ts`), the
layers come from `components/map/TimelineMapLayers.tsx` (the physical layers' own drawings and keys,
a district layer's fills and legend) with the home districts in the place hatch, a scale bar and
the India locator with the frame marked (decision 0232), and the source line gives the boundary
note and every layer's dataset credit at first paint. Every text and pin of a timeline map (the
numbered pins, the scale's figure, the river, range and peak labels) is drawn in the places map's
layer of screen pixels at the caption token (`MapLabelLayer`, `ScreenPins` through `IndiaMap`'s
`screenLayer`, decision 0244), so it is the caption size before and after hydration and with no
script, and a layer label whose point lies outside the frame is not drawn; the map's own `svg`
holds only geometry.

**The still** (decision 0220). When the site's web server reads a page
(`lib/server/mapStills.withMapStills`, run by `lib/monographRenderServer.documentRead`, the preview
and `/design/kinds`), it cuts each declared map's still to the frame the view draws
(`components/map/timelineMapStill.timelineMapFrame`) with `components/map/mapStillCut.ts`, from the
layer files bundled with the server (`lib/server/mapLayerFiles.ts`, the same files the browser
fetches): the land below the first elevation break and each relief band, the rivers by rank and
the lakes, clipped to the frame with a two-step margin, simplified within one step of a grid of 500
steps across the frame, rings under four square steps dropped, and written as relative paths in
grid steps; the home districts in tenths of a map unit, unscaled, so their hatch matches the
layer's; the minerals key's classes with their counts; and a district layer's legend (title, class
labels, caption, summary and dataset), read from `/map/layers/{id}` on the server. It sends them in
the spec as `still {box, grid, relief, rivers, lakes, home, minerals, district}`, keeps each
frame's geometry in memory (200 frames), and removes any `still` a stored timeline map spec
brings; the model refuses one from a contributor as an unknown field, and the web reads a still
only in that shape (paths of `M`, `L`, `l`, `z`, digits, spaces, points and minus signs). The
view draws the still at first paint in the map tokens (`components/map/MapStillLayers.tsx`:
`--elevation-1` to `--elevation-7` under the district rule, `--map-river` and `--map-water`, the
place hatch), beneath the pins, and each layer's own drawing takes its part's place in the same
spot when its file lands; a still whose box is not the view's frame is not drawn. The Bidriware
map's still is 28.2 KB, against 451.6 KB of path data for its layers drawn whole. The key is
whole at first paint: the relief key from the design's elevation classes
(`lib/mapPalettes.ELEVATION_BREAKS`, which the relief file is cut at), the rivers key, and the
minerals key and a district layer's legend from the still, drawn exactly as they draw once their
data lands, so nothing below moves; without a still (a district layer the server could not read)
they hold a legend-shaped skeleton. Once the page is loaded and idle the near view asks for the
named layers' files with `link rel="prefetch"` (`componentSpecsTimelineMap.timelineMapFiles`), so
they are cached before the view nears (decision 0216). The mineral symbols and a district layer's
fills are drawn from their files once the view loads. It rests on its last year with every place
pinned; motion is only the entries' colour change, which both reduced-motion switches turn off.

**The hand-drawn map** (`research/drawn_maps.drawn_map_problems`, in check 8 for `drawing` and
`map_layer`): a drawing is a map, and refused with `component_specs.MAP_POINTER`, when it paints the
base map's land, coast, borders or salt flats (`BASE_MAP_ROLES`), draws with the page kit's map
frame and pins (`KIT_MAP_CLASSES`, `data-pin`), marks two or more places as dots in the place
colours (`PLACE_ROLES`: terracotta, the map marker and place roles), or draws an outline of 60 or
more points (`OUTLINE_VERTICES_MIN`) with two or more dots on it. A section, a mechanism, a vat or
a drawing with one place dot is not a map.

## The figure kit (decision 0199)

A figure is composed, not drawn. A declared `diagram` names parts of the site's kit in one of four
layouts; the web draws every part in the design system (depicted materials textured, edged in ink
and named in a key, line work in the ink tokens, labels at the type scale), at every width, phone
first. The kit's vocabulary has one home, `research/art_kit.py`, which `shared/art-kit.golden.json`
copies for the web (`frontend/lib/artKit.ts`), and both sides' tests hold the three equal.

| Part | What it takes | What it draws | Serves |
|---|---|---|---|
| `cloth` | `form` (`swatch`, `length`, `folded`), `material`, `printed?` `{motif, material}` | a swatch with its fringe, a length with its turned end, a folded cloth seen edge on; the print tiled in its material | textiles, more crafts |
| `block` | `motif`, `paste?` | a carved block with its handle in wood grain, and its print beneath in the paste (line work when no paste is stated) | textiles, wood |
| `bath` | `vessel` (`vat`, `pot`, `trough`, `pit`), `liquor?`, `piece?` | the vessel in cutaway (a vat or pit sunk in earth strata), its liquor rippled, a piece hanging into it | textiles, metal, leather, fibre, paper |
| `paste` | `form` (`spread`, `printed`, `outline`), `material`, `on?`, `dried?` | a paste spread over a slab, printed in dabs or drawn in outlines on its ground; the dried colour at rest | textiles, metal, paper, more crafts |
| `heat` | `source` (`sun`, `fire`, `furnace`, `lamp`) | line work: the sun's disc and rays, flames over logs, a domed furnace with its pipe, a lamp | textiles, metal, clay, wood, fibre, paper, more crafts |
| `water` | `form` (`running`, `still`, `sprinkled`) | running water with its direction, a still basin's rings, falling drops | textiles, metal, leather, fibre, paper |
| `tool` | `tool` (`block`, `brush`, `chisel`, `mallet`, `knife`, `stick`), `held` (default true), `load?` | the tool in a hand, a brush or a stick loaded with its material | textiles, metal, stone, wood, fibre, paper, more crafts |
| `section` | `layers` 2 to 6, each `{material, label}` top to bottom, a material or `earth` | a layered section, earth in the hatch grammar's strata, each layer named in the key | textiles, metal, clay, leather, more crafts |
| `piece` | `shape` (`lump`, `vessel`, `slab`, `billet`, `sheet`, `figure`, `culm`), `material?`, `inlay?` `{motif, material}` | a shaped piece in its material (line work and its family's texture when none is stated), an inlay tiled in its material | metal, clay, stone, wood, fibre, paper, more crafts |
| `species` | `role` (`reactant`, `reagent`, `product`), `material?` or `mark?` (`clear`, `gas`, `ion`, the lane's marks, one or neither), `breaks` (default false, a reactant's only) | a species of one reaction as a bead in its material with the speckle texture and an ink edge; a colourless one by its mark: `clear` a raised bead with a solid ink-2 edge and a glint, `gas` three small rings, `ion` a bead with an ink-1 edge round a smaller ring; one with neither a dashed outline marked `data-kit-uncoloured`, which the preview's rule 27 names and its drawing checks fail (decision 0252); a crack across it where a bond breaks, a small arrow into a reagent that arrives; a scene of species stands the reactants and reagents before an arrow and the products after it (decision 0228) | every family |

Motifs are `star`, `lattice`, `dots` and `lines`. A material is a depicted `--dye-*` or `--dip-*`
token the design system records (`drawing_roles.MATERIAL_ROLES`); a material no record holds is
refused and asked for first. Every part has a `label`, a unit that cites the facts that state it,
as does every layer of a section (check 7, `kit_label_problems`); a part takes no coordinate,
size or colour of its own.

| Spec part | What it holds |
|---|---|
| `head` | `{title, caption?}`, as every declared kind |
| `layout` | `steps` (2 to 6 numbered panels), `before_after` (2), `section` (1 panel holding one `section` part), `sequence` (2 to 6 joined by arrows) |
| `alt` | a unit saying what the figure shows, drawn under it |
| `panels` | each `{label, text?, via?, motion?, parts}`: `label` the step's name, `text` a cited sentence under it, `via` the change on the arrow into a later panel of a sequence or a before and after, `motion` the change the panel explains, `parts` 1 to 3 |

**Motion** is part of the kit and runs only when the reader presses Play: `dip` (a bath's piece
going in, the dip motion), `take` (a cloth's colour taking from the bottom, the dip motion) and
`dry` (a paste's wet colour withdrawing to its dried one, the oxidise motion), each on the one
part it explains (`MOTION_NEEDS`), and `react` (decision 0228; a product species and a species it
is made from): over the vat's 2,600 ms the reactants come in, a reagent comes down into place,
the arrow, a breaking bond's crack and then the product appear, every species' layer at once
(`artkit.css`, `kv-rx-*`), each at rest in its end state. The figure rests complete: every end state is the default
style, the server and first client render move nothing; once in view the figure plays on its
own, marking each panel in turn (`aria-current="step"`, the ink rule) and then a rest beat, and
loops, with one Play/Pause and its status `aria-live="off"` while it plays (decision 0238); under
either reduced-motion switch nothing plays and each press shows the next panel at once and
announces it (`artKitMotion.kitBeat`, `kitPanel`, `usePlayInView`). **Layout** (`components/artkit/artkit.css`): one column on a phone (steps two),
two or three from 640 px, four from 1024 px; a sequence's arrows point down on a phone and along
the line from 640 px, mirrored right to left; a section sets its drawing beside its key from
640 px. **The kit sheet** (`/design/kit`) draws every part in every form and every depicted
material and the four layouts, at the sheet's widths, in the theme its switches choose.

**Kit scenes** (decision 0200). A player's step, phase and stage drawing, a toggle's stage box and a
label card's seal take a kit scene beside the free drawing: `{parts, motion?}`, one to three parts
of the same vocabulary, or up to eight when every part is a species of one reaction
(`SPECIES_PER_SCENE_MAX`, as a diagram panel), each labelled by a cited unit (`component_specs_kit_scene.KitScene`, told
from a drawing by `parts`). The five kinds are `KIT_SCENE_KINDS`: `reaction_player` (a step's
`scene.art`, its where icon then optional), `dip_player` (`scene` and each phase's `drawing`),
`stage_player` (`drawing`), `choice_toggle` (a `stage` part's `drawing`) and `label_card`
(`seal`). Only a scene the reader shows again may name a motion (a reaction step, a dip phase, a dip
player's scene); a stage player's drawing, a stage box and a seal rest as drawn and name none. The
web draws it inside the slot's frame with the key beside it (`components/artkit/KitScene.tsx`), and
the page kit plays the shown scene's moving part (`kitMove`) and never under either reduced-motion
switch. The kit plays every reaction, dip and stage player on its own once it is in view, and a
3D molecule turns slowly; each has one Pause, and a step pressed plays on from there (decision
0228, `docs/contracts/component-specs-science.md`).

**The hand-drawn figure** (`research/drawn_art.drawn_art_problems`, in check 8): every free drawing
a `drawing` or `diagram` delivery carries (a `drawing`'s SVG, a `diagram`'s drawing and chain
drawings) and every free scene of the five kinds that take a kit scene (`drawn_art.scene_problems`:
a player's scenes, phase and stage drawings, a toggle's stage box, a card's seal; icons excepted)
is refused, naming the kit part to use, when it

- sets text off the type scale: drawn at 320 px wide, a text is 12, 13, 14 or 16 px, within a
  quarter of a pixel (`UI_SIZES_PX`; under 12 px the vocabulary's floor refuses it);
- draws fewer than six shapes (`SHAPES_MIN`, outside its definitions) or has no line work in ink
  (no stroke whose paint resolves to `--ink-1` to `--ink-3` or a mix of one);
- paints a depicted material by hand, textured or not, in a fill or a stroke (the kit's `cloth`,
  `bath`, `paste`, `section`, `piece` or `species` part draws it, or the one its own words name); a figure
  points to a composed diagram (`KIT_POINTER`), a scene to a kit scene in its own slot
  (`SCENE_POINTER`);
- in a `drawing` or `diagram`, says it shows what a kit part draws (its title, description and
  labels and, for a `drawing`, its title and alt units, naming a part's subject:
  `art_kit.parts_named_by`), pointing to a composed diagram.

A paint is judged as the reader sees it (`research/drawn_paints`, decision 0215): a fill, stroke or
`color` is inherited from the nearest group that sets it (`inherit` keeps the parent's);
`currentColor` takes the nearest `color`, and the page's `--ink-1` when the drawing sets none; a
local `url(#id)` and its fallback paint every stop of the gradient, every shape of the pattern and
whatever a gradient or pattern it `href`s paints; and a `use` paints what the shape or group it
places paints. A paint that names a variable is followed through the drawing's own declarations
(decision 0218): a custom property a group or shape declares in its `style`, a design role's name
included, is resolved where it is declared and inherited as CSS inherits it, a fallback is read
too, and a property that refers to itself stands for nothing, so its paint is the parent's; a
variable the drawing does not declare and the design does not define for a drawing (the page's
`--dip-c` or `--hand`) is refused, since the page may hold a depicted material in it.

A free scene in line work, painting no depicted material, is kept: a molecule's structure or an
emblem drawn in ink. Every other kind's free drawing (an authored `chart`'s, a `map_layer`'s and
the like: `drawn_art.data_drawing_problems`) draws data, and is refused, pointing to a composed
diagram, when it paints a depicted material by the same reading; its words are not read, since a
data figure's subjects (water, cotton, the sun, layers) are the kit's words too. The molecule
drawings of `structure_diagram` and `molecule_3d` (`MOLECULE_KINDS`) and a swatch's motif
(`SWATCH_KINDS`: a swatch shows its depicted material by design, its print in it) are not held to
the bar.

Kutch Ajrakh's authored figures and players are its page's own and never pass through the delivery
check, so the bar does not re-check them.

## A coded figure (decision 0231)

A `coded_figure` is your own HTML, CSS and script, as large as a chapter section, beside the values
and cited units it shows; the site runs it in a sandboxed frame. Compose first: a reaction, a dip, a
molecule or a what-if is `compose_component`'s, and what a declared kind or the kit draws is that
kind's. Write code for what no kind or composer expresses and Kutch Ajrakh shows: a reaction's
molecules meeting and a bond breaking, a dye bath scene, a route or a sequence of map states on the
site's base, a stage scene that moves, a three.js model, a film the site holds played beside its
cited steps.

- **The spec**: `head {title, caption?}`; `alt`, a unit saying what it shows; `code`, an HTML
  fragment of at most 64 KiB with `style` and plain `script` elements; `values`, up to 120
  `{key, value, reading}`, every number it plots, animates or states, each stated by its `reading`
  unit; `texts`, up to 120 `{key, unit}`, the units whose words it shows; `libraries`, any of `d3`
  (7.9.2, global `d3`) and `three` (0.187.0, global `THREE`); `map {layers, districts}`; `films`, up
  to 4 `{key, src}` with `src` a film the site serves under `/monographs/`, or `{key, clip}` with `clip`
  the id of an approved AI video of the media store made from a fact the figure cites; and `still`, an SVG of
  the figure at rest, sent only when the code draws no single `svg` (a canvas or WebGL scene).
- **Data in**: `JSON.parse(document.getElementById("kv-data").textContent)` gives `{key: value}`.
- **Words in**: an element with `data-unit="<key>"` shows that unit's words, `data-unit-label` gives
  them as its `aria-label`, and setting either to another key shows that unit's words. Labels,
  controls and decoration may be your own words; a fact is a unit, and every unit the figure shows
  is listed under it with its citations.
- **Films**: `<video data-film="<key>">`; the frame sets the address. A clip reaches the frame as a
  signed address of that one file that lasts five minutes, and nothing else on its host; its credit
  ("AI video, made with <model> on <day>") is written by the server and drawn under the figure, and
  the page's export draws a still of the clip with that credit.
- **Maps**: declare `map`, with `layers` any of `states`, `districts`, `rivers` and `relief` and
  `districts` the LGD codes to outline, and draw in an `svg data-map` whose `viewBox` is
  `kvMap.viewBox` or `kvMap.box(west, south, east, north, margin)`. The site draws its base and the
  Survey of India outline into it first, and again if the code removes them; place your marks with
  `kvMap.project(longitude, latitude)`, which returns `{x, y}`, and `kvMap.places`, each named
  district's `{lgd, x, y}`. Never draw India yourself.
- **The look**: the frame holds the page's tokens in the reader's theme (`var(--ink-1)`, `var(--indigo)`
  for what can be pressed, `var(--map-*)`, `var(--elevation-*)` and the rest) and styles buttons,
  `aria-pressed`, focus and `role="status"`; reach for them. Nothing is refused for its look.
- **At rest**: the figure's markup is its finished state. Read
  `document.documentElement.dataset.reducedMotion`; when it is `"true"` no timer, animation frame,
  animation or film runs, so draw the last state at once and let each press step one state. With
  motion allowed it may play on its own; give it a button with `aria-pressed` that pauses it. A
  three.js scene renders its rest once directly, not only from its animation loop.

Delivery refuses it only for: a number it shows that is not one of its values (a counting number up
to 12 is free), a sentence of its own past 80 characters, or a key `texts` or `films` do not hold;
anything that reaches past the frame (network, storage, cookies, other windows, navigation, loaded
scripts, addresses, the frame's ids, a library or film off the list, a clip the page does not hold); a timed script that never
reads the flag, no still, or a map without its base; and code past 64 KiB. Each refusal names the
fault.

## How this document is kept true

| Claim | Kept true by |
|---|---|
| The general kinds' specs, bounds and the SVG intake | `backend/tests/research/test_component_specs_general.py` |
| A delivery's units and its eight checks | `backend/tests/research/test_component_specs_general_delivery.py` |
| The design's vocabulary for drawings, pictures and science specs | `backend/tests/research/test_drawing_vocabulary.py` |
| The four themes, the tokens as CSS and the drawing guide | `backend/tests/mcp/test_design_kit.py` |
| The report's design rule | `backend/tests/research/test_page_report_design.py` |
| Registration and drawing on generated pages | `backend/tests/db/test_delivered_components_db.py` |
| Each kind's fixture for a craft other than Kutch Ajrakh | `backend/tests/research/test_kind_fixtures.py` and `frontend/e2e/kind-fixtures-unit.spec.ts` |
| The views | `frontend/e2e/monograph-kinds-general-unit.spec.ts` |
| The declared timeline map's spec, its delivery rules and its authored form refused | `backend/tests/research/test_timeline_map_specs.py` |
| Its places resolved and refused, its layers held and credited, a looked-up item's point kept | `backend/tests/db/test_timeline_map_places_db.py` |
| The hand-drawn map refused, both ways | `backend/tests/research/test_drawn_maps.py` |
| The kit's vocabulary, its families and the golden both sides read | `backend/tests/research/test_art_kit.py` and `frontend/e2e/art-kit-unit.spec.ts` |
| A species part's roles, its bond, a scene of up to eight species and the react motion, the page's still of it, a colourless species' mark and one with no colour named and failed | `backend/tests/research/test_kit_species.py`, `backend/tests/exports/test_export_species.py`, `frontend/e2e/players-play-unit.spec.ts`, `frontend/e2e/kit-species-unit.spec.ts`, `backend/tests/research/test_page_report_species.py` |
| A timeline's points and Play, no slider, and its play state, on a page and in an answer | `frontend/e2e/monograph-kinds-general-unit.spec.ts`, `frontend/e2e/timeline-map-declared-unit.spec.ts`, `frontend/e2e/journey-renderers-unit.spec.ts`, `frontend/e2e/answer-players-unit.spec.ts` |
| The composed diagram's spec, its layouts, motions, materials and cited labels | `backend/tests/research/test_component_specs_kit.py` |
| The hand-drawn figure refused and allowed, rule by rule, with Kutch Ajrakh's authored figures left alone | `backend/tests/research/test_drawn_art.py` |
| Each of the five kinds takes a kit scene beside its free drawing, its labels cited, a hand-painted scene refused naming the part, and the composer's scenes built from the kit | `backend/tests/research/test_kit_scenes.py`, `backend/tests/compose/test_compose_kit.py`, `frontend/e2e/kit-players-unit.spec.ts` |
| Every part in every material, each layout at phone and desktop, light and dark, motion off under both switches, and the kit sheet | `frontend/e2e/art-kit-unit.spec.ts` |
| The places map's parts, their checks both ways and the old shape stored unchanged | `backend/tests/research/test_map_layer_parts.py` |
| The places map drawn on the base, the outline always present, its still with its state lines drawn at first paint, a route, ring and sequence from the spec alone, and the map at 390 and 1440 px | `frontend/e2e/places-map-unit.spec.ts` |
| The declared timeline map drawn from its fixture, framed, hatched and at phone and desktop widths | `frontend/e2e/timeline-map-declared-unit.spec.ts` |
| Every text and pin of a timeline map at the caption size at 390, 1440 and 1920 px with JavaScript off and on, and no layer label outside its frame | `frontend/e2e/timeline-map-labels-unit.spec.ts` |
| A river named through the register's cited alias drawn and labelled, and an alias without a source refused | `backend/tests/geo/test_river_aliases.py`, `tools/tests/test_maplayers_waters_names.py`, `tools/tests/test_maplayers_waters_files.py`, `frontend/e2e/map-waters-unit.spec.ts` |
| A places map and a coded map on paper on the site's base, with their credits and boundary note, at print resolution, and in a town's frame the small waters with the river and dam a map names (none in a wide frame, none named that the tiles lack) | `backend/tests/exports/test_map_exports.py`, `backend/tests/geo/test_map_base.py`, `backend/tests/geo/test_map_waters_base.py`, `tools/tests/test_maplayers_mirror.py` |
| A coded figure refused and accepted, rule by rule, its frame, words, map base and still | `backend/tests/research/test_coded_figures.py`, `frontend/e2e/coded-figure-unit.spec.ts` |
| The same limits, as the component guide states them to contributors | `backend/tests/mcp/test_reference_limits.py` reads them from the constants, not from this page |
| The copy a contributor's agent reads | `backend/tests/mcp/test_skill_references.py` holds `backend/app/data/contributor/contracts/component-specs-general.md` byte for byte equal to this file |

Re-read it when a kind becomes contributable or retires, a bound changes, or the SVG intake keeps or
removes another element; copy it to `backend/app/data/contributor/contracts/` in the same change.
