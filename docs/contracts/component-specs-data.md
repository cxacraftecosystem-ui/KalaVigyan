# Component specs: data and place

The data group moves twelve component kinds of the approved Kutch Ajrakh page (charts, figures,
maps, timelines, lists of crafts and sources, the citation tool) from template markup to typed specs
drawn by React views. It builds on the plates group's shared parts (units, drawings, held text).
Engineers changing one of these kinds, and a contributor's agent delivering one, read it.

| For | Read |
|---|---|
| Why kinds became specs | [decision 0106](../decisions/0106-one-monograph-template-for-every-page.md), item 4 |
| The shared parts this group builds on | [component-specs-plates.md](component-specs-plates.md) |
| Delivering one of these kinds through MCP, and the five general kinds | [component-specs-general.md](component-specs-general.md) |
| How a document places a component | [monograph-renderer.md](monograph-renderer.md) |

| Side | File |
|---|---|
| Spec models | `backend/app/research/component_specs_data.py` (`SPEC_MODELS_DATA`), `component_specs_data_maps.py`, `component_specs_data_lists.py`, shared parts in `component_specs_data_parts.py` |
| Extraction | `backend/app/scripts/extract_specs_data.py`, `extract_specs_data_maps.py`, `extract_specs_data_lists.py` |
| Spec files | `backend/app/data/monographs/Kutch-Ajrakh/specs/<spec_file_name(label)>` |
| Shapes | `frontend/lib/componentSpecsData.ts` |
| Views | `frontend/components/monograph/kinds/data/`, `index.ts` exports `VIEWS` |
| Tests | `backend/tests/research/test_component_specs_data.py`, `test_spec_extraction_data.py`; `frontend/e2e/monograph-kinds-data-unit.spec.ts` |

Run `python -m app.scripts.extract_specs_data Kutch-Ajrakh` from `backend` to write the spec files,
`--check` to list those that differ from what extraction writes.

Any kind of this group, the plates group and the science group can also arrive as data from a
contributor in a `propose_page` draft or bundle, with the units it places, and is drawn by the same view
once approved (`component-specs-general.md`, which also holds the five general kinds for anything
new). A delivered spec holds no citation of its own: its text is in units resting on shown facts.

## Shared parts

| Part | What it is |
|---|---|
| `TextLine` | one line of text in its element (`p`, `h3`, `li`, `span`, `dt`, `dd`, `figcaption`, `td`, `th`) with its classes, showing a unit, held text or nothing (an empty cell or live region) |
| `FigureHead` | the figure number (unit and `data-fig` reference), the chart title and the dek, with the ids a figure is labelled by |
| `Placed` | a label set over a drawing at a left, width or top position (`12.5%`), its classes, whether it is hidden from screen readers, and its text |
| `ToggleGroup` | a segmented control the kit's script reads (`data-layers`, `data-zooms`) with its options and the one pressed at rest |
| `ComponentLabel` | another component this one holds (see Nesting) |

## Nesting

On the approved page some components sit inside others, while the layout lists every component at
the top level (`within` is empty for components):

| Container | Holds |
|---|---|
| `kutch-ajrakh/geography/suran-earthquake-ajrakhpur-cards` (map_sequence) | four map layers, the borewell diagram, two stat tiles and the iron swatch pair |
| `kutch-ajrakh/process/experts-differ` (source_disagreements) | the two range charts |
| `kutch-ajrakh/policy/gi-registration-card` (label_card) | the GI ladder (timeline) |

A container's spec names what it holds by label, in place (a card's `visual`, a sequence `component`
item, a range figure's `chart`, the card's `inset`). Extraction refuses a spec that does not name
every component its element holds. Views take an optional `renderComponent(label)` beside the
contract's props (`kinds/plates/nesting.ts`, `NestingViewProps`) and draw the held component there;
without it the place is left empty. `componentsHeldBy(spec, labels)` in `lib/componentSpecsData.ts`
lists what a spec holds, so a renderer can draw those inside their container and not again at their
layout place.

## Kinds

### chart

`form` picks the part: `drawing` (the chart is its SVG: the range charts and the two bar charts of
the What if chapter), `dots` (a row of dots, the first `marked` of `total` filled, with its spoken
label), `rows` (HTML bars: label, value, the shown figure, the emphasised bar; the view draws each
bar at its share of the largest to two places, with a 2px floor for the smaller ones), `figure` (a
figure head, the drawing and the source line) and `series` (the rainfall figure: the plot with its
data series written into `data-series` as the kit's script reads it, the drawing, the placed axis
and annotation labels, the events, the table of every value with its CSV download, the source).

### stat_tiles

Tiles of a headline figure (with an optional small unit word) over a caption unit, and the row's
extra classes (`three`).

### fact_table

"At a glance": the chapter numeral, chapter number and title units, and term and value rows.

### map_layer

`drawing` (a small map that is its SVG drawing) or `explorer` (the district climate map: figure
head, the toggle groups, the map drawing with its label, the inset drawing and caption, the hidden
key, the caption, the side panel's lines and the rank caption and button). The kit's script fills
the legend, tooltip, live region and rank table, binding `data-comp`, the toggles' data attributes
and `data-rank-*`; the view keeps them.

### map_sequence

A figure of cards in two lists with a source line between. A card is its own (the held visual, when,
title, its lines, and an optional "Sources differ" note as held text) or is another component drawn
whole (the iron swatch pair).

### timeline

A dated ladder of a `variant` (`gi`): figure number, title, the scale (marks, spans, ticks at their
left positions, with its spoken label) and the steps.

### timeline_map

The dated record on a map: figure head; the events (view, routes, pins, when, title) written into
`data-events` for the kit's script; the play label and status; the supply switch; the map's views
and drawing; the legend; the caption; one card and one list item per event; the supply note; and
the axis (breaks, ticks, spans, one mark per event). At rest the `rest` event is pressed and its card
shown; the view writes the marks' names ("1868, Alizarin made in a laboratory") and the list's pick
buttons ("Show … on the map") from the events.

### concept_atlas

Shared science: per concept its title, text and co-occurrence units and the crafts naming it, first
shown and the rest behind "Show all N" (place, family and how many cited sentences name it).

### related_crafts

Kin crafts: per craft its plate tile, the swatch line, family line, name, place and source count,
Monograph and GI tags, what it shares, and its sentence unit.

### source_list

`status` (the live region that announces the source list's filter) or `listing` (the kin crafts'
sources: per source its key and number, title, publisher line, grade with its words, how many
sentences it supports, the monograph it comes from, its link and the link's hidden name).

### source_disagreements

"Experts differ": the intro and per disagreement its summary, at least two readings (who and the
unit) and an optional range figure holding a chart component.

### citation_tool

Cite this page: the title and tabs, and per panel its tab and panel ids, label, the citation styles
with the text each one copies (`data-apa`, `data-bibtex`, `data-link`, `data-text`), the text and
link units and the copy button. The kit's script switches tabs and styles and copies.

## Open

- **Held citations.** Twelve cited sentences of these components live in the template, not in units:
  one in the climate map's side panel, four in the map sequence (two cards and the two readings of its
  "Sources differ" note), four in the timeline map (two events, each in its card and its list item)
  and three in the concept atlas's rows. Their specs carry them as held text.
- **The kin source count.** The listing's summary says "Show the 24 sources" over 25 entries; the
  spec keeps the page's words.
- **Charts as drawings.** Charts and maps keep their drawn geometry; a spec that holds only data and
  lets the view lay it out is the step after parity.

## How this document is kept true

| Claim | Kept true by |
|---|---|
| Each kind's spec model and its bounds | `backend/tests/research/test_component_specs_data.py` |
| The spec files are what extraction writes from the approved page | `backend/tests/research/test_spec_extraction_data.py`, and `python -m app.scripts.extract_specs_data Kutch-Ajrakh --check` |
| Each view draws the approved page's elements, classes and text | `frontend/e2e/monograph-kinds-data-unit.spec.ts`, and the Monograph parity run |

Re-read it when a kind of this group gains a field, a held citation moves into a unit, or a chart
becomes a data-only spec.
