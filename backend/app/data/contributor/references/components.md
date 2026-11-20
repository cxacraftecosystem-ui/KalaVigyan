# Authoring a component

A component is a figure, table, map, timeline, player or card that draws a page's stored facts. A
contributor delivers it finished: the spec of its kind (its data) and the units it places (every
text a reader sees), each unit resting on shown facts. The site draws it with its kind's own view,
in the design system, and nothing a contributor sends is ever run as code. This guide is drawn from
the design system (Alum & Indigo, the tokens at `kalavigyan://design/tokens.json`) and the
component contracts; where it is silent, they decide.

## Find before you make

- Search the library with `list_components`, by the craft and by words for what the component
  shows. A component keyed to a concept, compound or place is shared by every craft it applies to.
- When one fits, place it by its label in the page's layout. When one nearly fits, extend it:
  `extends` its label with `SUBJECT_LINK` to key it to a new craft, concept, compound or place (it
  keeps the label and carries no spec), or with `VARIANT` for a different form of the same thing (a
  label of its own). Never a copy: a close match in the library refuses a new proposal with the
  matches and the two ways on.
- A `MISSING_COMPONENT` task names its need: `what-if`, `molecules`, `map`, `reaction-player` or
  `pictures`, and only a component of a kind that need lists completes it. Pictures are given, not
  delivered as components (the contributor skill, Pictures).

## Choosing a kind

Choose by what the reader must see:

| To show | Deliver |
|---|---|
| quantities compared across places, materials or years | `general_chart`, as `bars` for categories or a `line` for a series over time |
| several things side by side, by their attributes, or a few headline numbers | `general_table` |
| dated events in order | `general_timeline` |
| places, with or without a value each | `general_map_layer` |
| a mechanism, a section, a tool or an object | `general_drawing`, or `diagram` for a chain of linked steps |
| one stated equation | `equation_card` |
| molecules | `structure_diagram` (flat, with their PubChem records from `lookup_compound`) or `molecule_3d` |
| a reaction a source states step by step | `reaction_player` |
| what each material is and does | `material_cards` |
| sources that disagree | `source_disagreements` |
| a what-if experiment | `experiment_lab` holding one `choice_toggle` per experiment |

The 42 kinds of the approved page, by group:

- **Plates and media** (12): `picture_plate`, `ai_illustration`, `specimen_plate`, `label_card`,
  `swatch_cards`, `swatch_pair`, `film`, `ai_video`, `comic`, `audio_player`, `voice`, `credits`.
- **Data and place** (12): `chart`, `stat_tiles`, `fact_table`, `map_layer`, `map_sequence`,
  `timeline`, `timeline_map`, `concept_atlas`, `related_crafts`, `source_list`,
  `source_disagreements`, `citation_tool`.
- **Science** (12): `reaction_player`, `dip_player`, `stage_player`, `diagram`, `molecule_3d`,
  `structure_diagram`, `equation_card`, `model_explainer`, `material_cards`, `experiment_lab`,
  `choice_toggle`, `process_replay`.
- **Reading tools** (6): `explainer`, `quiz`, `ask_next`, `language_switch`, `reading_level`,
  `generator`.

Their specs follow the approved Kutch Ajrakh page part for part, and each is checked against its
kind's model (the repository's `docs/contracts/component-specs-plates.md`, `-data.md` and
`-science.md`). Deliver one when its form is exactly what the page needs and every part can be
filled from facts, most often as a `VARIANT` of a registered component. Deliver knowledge, not the
page's apparatus: the masthead, the citation tool, source lists, credits and the reading tools are
the page's own.

For anything the 42 do not show, use one of the five general kinds: `general_drawing`,
`general_chart`, `general_table`, `general_timeline`, `general_map_layer`. A one-off visual is a
general kind, never free-form HTML.

## The general kinds

Every general spec has `head {title, caption?}`. The title states the finding of a chart and
describes a drawing, map, table or timeline; the caption is a cited sentence under it. Keys may be
written in camelCase (`valueLabel`) or snake_case (`value_label`); the stored spec keeps camelCase.

- `general_drawing`: `head`, `svg` (one SVG drawing) and `alt` (what it shows).
- `general_chart`: `head`; `form`, `bars` or `line`; `valueLabel`, what is measured with its unit;
  `series`, 1 to 3, each `{name, points}` with 1 to 60 points `{label, value, reading}` and the
  same count in every series; `emphasis`, the index of the first series' point the title names.
  Bars start at zero, so a bar chart shows no negative value; a line joins two points or more.
- `general_table`: `head`; `columns`, 1 to 8, each `{label, numeric}`; `rows`, 1 to 100, each
  `{cells}` with one cell per column. Every cell of a numeric column states a number.
- `general_timeline`: `head`; `events`, 2 to 40, each `{year, when, title, text}`, in the order of
  their years, from -3000 to 2100 (a negative year is BCE).
- `general_map_layer`: `head`; `places`, 1 to 60, each `{longitude, latitude, name, reading,
  value?}`, inside longitude 68 to 97.5 and latitude 6.5 to 37.5; every place has a value or none
  does, a value is zero or more, and `valueLabel` names what the values measure when, and only when,
  they are given. Each place is a numbered disc whose area follows its value.

## Units and citations

- Every text the component shows is a unit, named in the spec by its id: `u0001`, `u0002` and on,
  four digits, the delivery's own. Every unit the spec names is delivered, and every delivered unit
  has a place in the spec.
- A unit is `{text, claim_ids}`: a text of 1 to 600 characters and up to 20 ids of shown facts,
  each named once. A component holds up to 400 units.
- A unit that cites facts says no more than they do (the quote rules, `quotes.md`), and every
  number it states is in its facts' statements or quotes.
- A unit that cites no fact is a label of at most 80 characters that states no number: an axis
  name, a column head, a place name.
- At least one unit cites a fact, and the spec's own text holds no citation. The page draws every
  cited unit with its citation cluster, quotes and sources, as it draws any sentence.
- The values a view draws are stated by units: a chart point's value by its `reading` unit, a
  timeline event's year (without its sign) by its `when` unit, a map place's value by its `reading`
  unit.
- In a page bundle a unit may rest on the bundle's own new facts: the component's `cites` names
  them per unit as `fact:0`, `fact:1` and on (their places in the bundle's facts), beside the stored
  facts in its `claim_ids`. A component resting on a fact that waits for review waits with it.

The shape, with the texts left to the facts:

```json
{
  "kind": "general_chart",
  "spec": {
    "head": {"title": "u0001", "caption": "u0002"},
    "form": "bars",
    "valueLabel": "u0003",
    "series": [{"name": "u0004", "points": [
      {"label": "u0005", "value": 12, "reading": "u0006"},
      {"label": "u0007", "value": 9, "reading": "u0008"}
    ]}],
    "emphasis": 0
  },
  "units": {
    "u0001": {"text": "<the finding, as the facts state it>", "claim_ids": ["<fact id>"]},
    "u0002": {"text": "<a sentence the facts state>", "claim_ids": ["<fact id>"]},
    "u0003": {"text": "<what is measured, unit>"},
    "u0004": {"text": "<the series>"},
    "u0005": {"text": "<the first label>"},
    "u0006": {"text": "<a reading stating 12 and its unit>", "claim_ids": ["<fact id>"]},
    "u0007": {"text": "<the second label>"},
    "u0008": {"text": "<a reading stating 9 and its unit>", "claim_ids": ["<fact id>"]}
  }
}
```

## Proposing it

- **Label**: `<craft-or-shared>/<field>/<name>`, lower-case words joined by hyphens, three parts or
  more (`shared/chemistry/indigo-vat-dip`, `kutch-ajrakh/process/cloth-after-each-stage`).
- **Title**, and a **description** of two or three sentences written for a model, 40 to 600
  characters: what it shows and when a page should place it.
- **Kind**, **field** and further fields; **subjects**, 1 to 20: a `CRAFT` by its slug, a
  `CONCEPT`, a `COMPOUND`, or a `PLACE` as `lgd:<district code>` or `basin:<river basin id>`.
- **The labels you considered** in the library, and `extends` with `extension` for an extension.
- **The task**: a `MISSING_COMPONENT` task you claimed whose need lists the kind, as `task_key`;
  otherwise no task. Then the `spec` and `units`.

How a component is sent, seen first and registered is the contributor skill's (Components and
Pages). The checks it meets, each refusal naming every problem in one sentence: the close-match
search of the library; the spec against its kind's model; the spec's units against the delivered
units; no citation in the spec's own text; at least one cited unit; every cited fact shown or in
the bundle; every number of a unit in its facts; and the general kinds' values stated by their
units.

## The design rules for a contributed figure

- **Give data, not styling.** A general kind's view sets every colour, size and position itself:
  bars and lines in the chart series colour with the one mark the title names emphasised, places as
  numbered paper discs on India's outline in the map colours, tables in tabular figures. A spec
  carries no colour, font or size.
- **Tokens, never typed colours**, in the drawings of the 42 kinds: a fill, stroke or stop colour
  is a token (`var(--ink-1)`, a specimen `--dye-*`, a `--chart-*` or `--map-*` token, a surface), a
  mix of two tokens, an in-drawing reference, `none` or `currentColor`; plain white or black only
  for a mask or a highlight.
- **A general drawing** is shown as an image on the cloth-white specimen mat in every theme, so it
  cannot read the page's tokens: draw its lines and text in the light theme's ink values from the
  tokens resource, and a depicted material in its specimen `--dye-*` value, named in the caption or
  `alt`.
- **Identity colours never on data.** Indigo means a reader can press it; madder is emphasis, a
  disagreement between sources or a real hazard; terracotta is place; turmeric only highlights. No
  bar, line, area, class or series takes any of them. Area fills (classes on a map, relief) take a
  ramp; bars and lines take a series colour, because ramps flip in dark.
- **The hatch grammar**: five patterns, one meaning each, and the caption or key explains every
  hatch a figure shows. Stipple is salt flat; 45-degree terracotta lines are the place the page is
  about; 135-degree madder lines are the span where sources differ; a 45 and 135 cross-hatch is no
  reading in the dataset; horizontal dashed strata are earth in a section drawing.
- **Caption first, credit after.** A figure made from someone else's drawing or data names its
  maker and licence under it; a stand-in says what it shows.
- **Words in units, not in the drawing.** Text inside an SVG shrinks with it, so names, values and
  keys belong in units (the caption, `alt`, a table). A drawing that must carry a key letter sizes it
  to stay 12 px or more at its narrowest: a font size of at least 12 times the viewBox width divided
  by 320.
- **Complete at rest.** The figure reads whole at first paint, with nothing to hover, play or step
  through, and every value is also in its table ("All N values") or the map's numbered list.
- **No executable code.** Never a script, an event handler, a `foreignObject`, an embedded image, a
  `style` element, a link, an outside reference or free-form HTML. A drawing is at most 200,000
  characters of SVG with no document type or entity, one `svg` element with a viewBox of four
  numbers and a positive size; it is cleaned of everything else before it is stored, and the site
  draws it only as an image, which runs nothing and loads nothing.
