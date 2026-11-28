# Authoring a component

A component is a figure, table, map, timeline, player or card that draws a page's stored facts. A
contributor delivers it finished: the spec of its kind (its data) and the units it places (every
text a reader sees), each unit resting on shown facts. The site draws it with its kind's own view,
in the design system, and nothing a contributor sends is run as code but a `coded_figure`'s, in a
sandboxed frame (decision 0231). This guide is drawn from
the design system (Alum & Indigo, the tokens at `kalavigyan://design/tokens.json`) and the
component contracts; where it is silent, they decide.

| For | Read |
|---|---|
| The declared kinds' specs, units and checks in full | `kalavigyan://contracts/component-specs-general.md` |
| Proposals, the close-match search, drafts and bundles | `kalavigyan://contracts/open-work.md` |
| Each kind's JSON schema | `kalavigyan://components/<kind>.schema.json` |
| A figure built from a dataset | `datasets.md` |
| Which tool makes each kind, its Kutch Ajrakh example and its place on the page | `cookbook.md` |

## Find before you make

- Search the library with `list_components`, by the craft and by words for what the component
  shows. A component keyed to a concept, compound or place is shared by every craft it applies to.
- When one fits, place it by its label in the page's layout. When one nearly fits, extend it:
  `extends` its label with `SUBJECT_LINK` to key it to a new craft, concept, compound or place (it
  keeps the label and carries no spec), or with `VARIANT` for a different form of the same thing (a
  label of its own). Never a copy: a close match in the library refuses a new proposal with the
  matches and the two ways on.
- A `MISSING_COMPONENT` task names its need: `what-if`, `molecules`, `map`, `reaction-player` or
  `pictures`, and only a component of a kind that need lists completes it. An `experiment_lab`
  completes `what-if`, and a delivered `timeline_map` or `map_layer` completes `map`. Pictures are given, not
  delivered as components (the contributor skill, Pictures).

## Choosing a kind

Choose by what the reader must see:

| To show | Deliver |
|---|---|
| quantities compared across places, materials or years | `chart`, as `bars` for categories or a `line` for a series over time |
| several things side by side, by their attributes, or a few headline numbers | `fact_table`, or `stat_tiles` for a few figures |
| the craft's dated record, its places and when | `timeline_map`, as Kutch Ajrakh's history chapter holds it |
| a short ladder of dates about one thing | `timeline` |
| where a craft is practised, began, spread or moved, and when | `timeline_map` (A map of places, below) |
| places and what lies around them: neighbours, a move, a ring, a value per district, a story in steps | `map_layer`, on the site's own base map |
| a mechanism, a section, a tool or an object | a composed `diagram` (The figure kit), or `drawing` for what no kit part draws |
| one stated equation | `equation_card` |
| molecules | `structure_diagram` (flat, with their PubChem records from `lookup`) or `molecule_3d` (composed by `compose_component` from a compound the page's materials hold, or one its facts name given as `about.compound` by its CID) |
| a reaction a source states step by step | `reaction_player` |
| a process stage by stage | `stage_player`, each stage with its own kit `scene`, or `dip_player` for successive immersions |
| what each material is and does | `material_cards`, and `swatch_cards` or `swatch_pair` for its colours; `swatch_cards` may show one swatch, none, and a `why`, and a page whose stages name their colours gets its key from the site |
| sources that disagree | `source_disagreements` |
| a what-if experiment | `experiment_lab` holding one `choice_toggle` per experiment |
| what no kind or composer draws: molecules meeting and a bond breaking, a bath scene, a route or map states on the site's base, a stage scene that moves, a three.js model, a clip of the media store beside its cited steps | `coded_figure`, your own code run sandboxed over the page's cited data (`kalavigyan://contracts/component-specs-general.md`, A coded figure) |

The 25 kinds a contributor delivers, by group:

- **Figures from data** (5): `drawing`, `chart`, `fact_table`, `timeline`, `map_layer`.
- **Data and place** (4): `stat_tiles`, `map_sequence`, `source_disagreements`, `timeline_map`.
- **Plates and voices** (4): `label_card`, `swatch_cards`, `swatch_pair`, `voice`.
- **Science** (11): `reaction_player`, `dip_player`, `stage_player`, `diagram`, `molecule_3d`,
  `structure_diagram`, `equation_card`, `material_cards`, `experiment_lab`, `choice_toggle`,
  `coded_figure`.
- **Reading** (1): `reading_level`, the student version, a title unit and one cited lede for a
  younger reader. It stands in the page's reading chapter unless the layout places it.

Each has been drawn for a craft other than Kutch Ajrakh (Bidriware, Blue Pottery of Jaipur,
Bastar Dhokra, cane and bamboo) from that craft's stored facts, and none needs Kutch Ajrakh's
words: a dip player names its own phases, a material is any the design system records, and a
dip player shows an equation only where a source states one. The site builds the rest itself:

- **Built by the site for every page** (13): `ask_next`, `audio_player`, `citation_tool`,
  `concept_atlas`, `credits`, `explainer`, `film`, `generator`, `language_switch`,
  `process_replay`, `quiz`, `related_crafts`, `source_list`. They are the page's apparatus,
  computed from its data; a proposal of one is refused. Every generated craft page draws Ask next
  from its suggested questions, and every page with a translated passage the switch of its
  languages, in its reading chapter.
- **The authored page's own** (6): `picture_plate`, `specimen_plate`, `ai_illustration`, `ai_video`,
  `comic`, `model_explainer`. Pictures are given with `give_pictures` and placed by the site; a
  model runs the authored page's own script, so deliver a `drawing` or a `diagram` instead. A
  `timeline_map` without `places` is Kutch Ajrakh's own route map and is never delivered.

Each kind's spec is checked against its model (the repository's
`docs/contracts/component-specs-plates.md`, `-data.md`, `-science.md` and `-general.md`). The MCP
server publishes that model for every kind a contributor delivers as a JSON schema resource named
`kalavigyan://components/<kind>.schema.json`: read the one for your kind before you write its spec.

Five kinds also take a declared spec, which the site draws in the design system from data alone,
and which is the form for anything new: use one of the five kinds that also take a declared spec:
`drawing`, `chart`, `fact_table`, `timeline`, `map_layer`. A spec with a `head` is declared; the
same kind without one is the authored figure of a page such as Kutch Ajrakh's. A one-off visual is
a declared kind; what no kind draws is a `coded_figure`, whose code the site runs sandboxed.

## The declared kinds

Every declared spec has `head {title, caption?}`. The title states the finding of a chart and
describes a drawing, map, table or timeline; the caption is a cited sentence under it. Keys may be
written in camelCase (`valueLabel`) or snake_case (`value_label`); the stored spec keeps camelCase.

- `drawing`: `head`, `svg` (one SVG drawing) and `alt` (what it shows).
- `chart`: `head`; `form`, `bars` or `line`; `valueLabel`, what is measured with its unit;
  `series`, 1 to 3, each `{name, points}` with 1 to 60 points `{label, value, reading, cell?}` and
  the same count in every series; `emphasis`, the index of the first series' point the title names.
  Bars start at zero, so a bar chart shows no negative value; a line joins two points or more.
- `fact_table`: `head`; `columns`, 1 to 8, each `{label, numeric, column?}`; `rows`, 1 to 100, each
  `{cells, row?}` with one cell per column. Every cell of a numeric column states a number.
- `timeline`: drawn as a dated axis with a point to press for each event and one Play/Pause that
  steps through them, playing on its own in view (no slider); `head`; `events`, 2 to 40, each `{year, when, title, text}`, in the order of
  their years, from -3000 to 2100 (a negative year is BCE).
- `map_layer`: `head`; `places`, 1 to 60, each `{longitude, latitude, name, reading, value?,
  cell?}`, inside longitude 68 to 97.5 and latitude 6.5 to 37.5; every place has a value or none
  does, a value is zero or more, and `valueLabel` names what the values measure when, and only when,
  they are given. Each place is a numbered disc whose area follows its value. What the map is
  about, all optional: `frame?`, `emphasis?`, `routes?`, `rings?`, `districts?` and `sequence?`
  (shapes in the cookbook's `map_layer` and the general contract). The site draws the base
  beneath it: relief, rivers, the Survey of India outline with state and district lines, the home
  district hatched, a scale bar and the India locator (decision 0232), and in a town's frame the
  small rivers and streams of OpenStreetMap. `emphasis` may name a small river as OpenStreetMap
  names it or by the name the site's river register gives it where the two agree by name and
  district (the Suran, as Kutch Ajrakh's dossier names the Dhamadka stream), and a dam by
  OpenStreetMap's name for it or for its reservoir; one the site does not hold is refused by name
  (decision 0239). A `coded_figure`'s `map` names them the same way and reads them from
  `kvMap.rivers` and `kvMap.dams`.

A `chart`, `fact_table` or `map_layer` drawn from a stored dataset names it as `dataset {code}` and
each value's place in its table as `cell {row, column}` (a table's rows by `row`, its columns by
`column`): the dataset guide's Contributed datasets says how a table is stored. The gates read
every such value from its row, so its unit needs no fact of its own; the site writes the dataset's
credit under the figure.

## A map of places

Never draw geography. A map of the page's places is a `map_layer` (places, routes, rings,
district values, a sequence) or, for places through time, a `timeline_map`; you declare it and the
site draws it on its base map and the Survey of India outline, framed to your places. A map story
beyond them is a `coded_figure` drawing through `map` and `kvMap`. A `drawing` or a `map_layer` of your own SVG that is a map (the base map's colours,
an outline with dots, places marked as dots in the place colours) is refused with this pointer.

- `timeline_map`: `head`; `places`, 1 to 30, each `{name, home?}` and one of `wikidata` (an item
  `lookup` found), `district` (its LGD code) or `longitude`, `latitude` and `at` (the unit citing
  the fact that states that coordinate); `points` `{place, yearFrom, yearTo, text}`, `routes`
  `{start, end, yearFrom, yearTo, text}` and `undated` `{place?, text}`, up to 40 each, one at
  least; `layers`, up to 3 of `relief`, `rivers`, `minerals` and the site's district layers, one
  area layer at most. `name` is a label; `home: true` hatches the page's own district.
- Every listed place is named by an entry. A point's or route's `text` states its years, a point's
  or undated fact's `text` names its place, and a route's `text` states the move from its start to
  its end, each as its facts say it.
- The server resolves each place and refuses, by name, one it cannot; it writes the points, the
  boundary record and each layer's dataset record into the stored spec. Send none of them.

## Depicted materials

A swatch's `dye` or `ground`, a `--dye-*` token in a drawing and a dip's colours name depicted
materials: colours the design system generates from material records, each naming the craft's
material, the facts that state its colour and the swatch it draws. `kalavigyan://design/tokens.json`
lists every one under `specimen`, with its craft, material and facts. Kutch Ajrakh's dyes were the
first records; Bidriware's alloy, silver and black, Jaipur's quartz white, cobalt and copper
turquoise and Bastar dhokra's soils followed. A material no record holds is refused; ask for its
record (its colour and the fact that states it) before you draw it.

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
  "kind": "chart",
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
the bundle; every number of a unit in its facts or its dataset rows; and the declared kinds' values
stated by their units.

## Withdrawing, replacing and borrowing

- **Who may.** A registered component is retired at once only by the account that proposed it or
  an Admin. A steward of its owning craft asks: its withdrawal waits for an Admin to confirm on the
  Review page (give a reason of 12 to 500 characters), and its replacement waits for review. Anyone
  else is refused. A withdrawal names a component of the bundle's own page.
- **Withdrawing.** A withdrawal takes your registered component off every page that places it:
  `{label, reason}` in a draft's or bundle's `withdrawals` (up to 10 a call and 100 a draft), or Withdraw on Your
  components on the site. It stays in the record, hidden, and keeps its label, so whatever comes next
  takes a label of its own.
- **Replacing.** Propose the better one with `replaces` naming the old label. It is never refused as
  a copy of the one it replaces, it is never a `SUBJECT_LINK`, and once it is registered the old one
  is retired and every page layout that named the old label names the new one in the same place.
- **Borrowing.** On your page a component another craft owns, or a shared one, is borrowed. Linking it
  (`SUBJECT_LINK`) or naming its label in the page's layout is refused when its units cite facts the
  page does not hold, and the refusal names them: build the page's own component of that kind on the
  page's own facts. One resting on facts the page holds (its own, its family's science, its shared
  concepts; on a category's page also its crafts' facts), or a shared figure keyed to the craft's own
  district, is placed as before, and the preview draws it.
- **An Admin's removal.** An Admin may stage a component's removal from every page or from one page;
  nothing changes until a person confirms it on the Review page.
- **A page held for you.** When this account's proposals reach readers at once, `propose_page` with a
  draft or a bundle of several parts proposes nothing and returns a `confirm_url`. The person signed
  in to this account opens it within 3 days and presses Confirm once, or Discard. A component, a
  layout or a fact sent alone goes by the account's tier as before.

## The figure kit

Cloth, vats, pastes, heat, water, tools, layered sections, shaped pieces and the species of a
reaction are composed from the site's kit, never drawn: a `diagram` with a `head`, a `layout` (`steps`, `before_after`, `section` or `sequence`), an `alt`
unit and `panels`, each panel naming one to three parts with a cited `label` (up to eight when
every part is a species of one reaction). The parts are `cloth`, `block`, `bath`, `paste`, `heat`,
`water`, `tool`, `section`, `piece` and `species` (its `role` a `reactant`, `reagent` or
`product`, and `breaks` marking the reactant in which a stated bond is broken); each takes a depicted material, a named form or a
layer list, never a coordinate, size or colour. A panel's `motion` (`dip`, `take`, `dry`, `react`)
plays on Play in a diagram and rests complete; in a reaction, dip or stage player the kit plays it
on its own once the player is in view, with one Pause, and never under reduced motion. A stage player's
stage may carry its own `scene`, shown in the stage box whenever that stage is, with its motion; a stage
without one keeps the scene of the nearest stage before it that has one, and the last stage rests on the
player's `drawing`, so it carries none. What each part takes, draws
and serves is in `kalavigyan://contracts/component-specs-general.md` (The figure kit), and
`/design/kit` shows every part in every material.

## The design rules for a contributed figure

A `coded_figure` is held to none of these, only to its facts, its frame, its rest and its budget
(`kalavigyan://contracts/component-specs-general.md`, A coded figure); it reaches for the same tokens.

- **At the bar.** Text at 12, 13, 14 or 16 px at 320 px wide; six shapes or more; line work in
  ink (a stroke whose colour is `--ink-1` to `--ink-3`, `currentColor` counting as the `color` it
  takes); a depicted material only through the kit: a composed diagram, or a kit scene in a
  player's, toggle's or label card's slot. A material reached through `currentColor`, a gradient,
  a pattern or a `use` is painted by hand as surely as a direct fill, and a chart's, a map layer's
  or any other data drawing paints none.
- **Give data, not styling.** A declared kind's view sets every colour, size and position itself:
  bars and lines in the chart series colour with the one mark the title names emphasised, places as
  numbered paper discs on India's outline in the map colours, tables in tabular figures. A spec
  carries no colour, font or size.
- **Colours by role, never typed.** Every colour in a drawing, a declared `svg` or a science drawing
  node alike, in an attribute or a style, is `var(--role)` or a `color-mix(in srgb, ...)` of two
  roles. The roles: `--ink-1` to `--ink-3`, `--rule`, `--rule-strong`, `--ground`, `--raised` and
  `--sunk` for lines, words and grounds; `--chart-*`, `--series-*`, a ramp step (`--rain-1` to
  `--rain-6`, `--heat-*`, `--density-*`, `--ph-*`, `--elevation-*`, `--earth-*`, `--cover-*`,
  `--mineral-*`) and `--map-*` for data and maps; a depicted `--dye-*` or `--dip-*` material;
  `--terracotta` only for place and `--madder` only for a hazard; in a science drawing also the
  molecule kit's `--mol-*` and `--atom-*`. `none`, `transparent`, `currentColor` and an in-drawing
  `url(#id)` are kept, and plain white or black only inside a mask or clip. A hex, rgb, hsl or
  named colour, indigo (it means a control) and any other token are refused with the element named.
- **A declared drawing follows the reader's theme.** It stays an image, so it cannot read the page's
  tokens; the server draws it once per theme (light, dark and both high contrasts), putting each
  role's value from the tokens in its place and setting its text in the UI face, and the page shows
  the variant its reader's theme asks for. A contributed SVG picture is served the same way. Send
  `svg` alone; a spec that sends `themes` is refused.
- **Type in the design's faces.** A drawing names no font (`font-family`, `font`) and sizes text in
  drawing units; words are `<text>`, never outlines or glyph symbols.
- **Flat ink on paper.** No gradient blends two roles (one may fade a single role, step through
  one ramp or pass between depicted materials), no text sits in a gradient, and nothing blurs or
  casts a shadow.
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
  by 320, with any scale on its groups counted. Text without a size counts as 16 units.
- **Seen in your own chat too.** When your client draws a chart, a diagram or a page of KalaVigyan's
  knowledge itself, it uses `kalavigyan://design/tokens.css` (every role in the four themes, with
  the type sizes) and the guide `kalavigyan://design/drawing.md`, so what the reader sees before you
  deliver matches what the site draws.
- **Complete at rest.** The figure reads whole at first paint, with nothing to hover, play or step
  through, and every value is also in its table ("All N values") or the map's numbered list.
- **No executable code.** Never a script, an event handler, a `foreignObject`, an embedded image, a
  `style` element, a link, an outside reference or free-form HTML. A drawing is at most 200,000
  characters of SVG with no document type or entity, one `svg` element with a viewBox of four
  numbers and a positive size; it is cleaned of everything else before it is stored, and the site
  draws it only as an image, which runs nothing and loads nothing.
- **Inline drawings load nothing.** A drawing node (a label card's seal, a swatch's motif, a
  player's scene, a map or chart drawing) sets in its `style` only paint, stroke, opacity,
  transform, text, display, blend and custom properties, each with a token, a number or a
  keyword, never `position`, `inset`, `z-index`, `cursor` or a background. No value names an
  outside address (`url()` other than `url(#id)`, `image-set()`, `cross-fade()`, `image()`,
  `src()`) or a backslash escape, in capitals or not, and `href` is `#id`; the delivery refuses
  any other with the attribute named.
- **Inline drawings stay in their box.** A drawing's `class` names only the classes the kit's own
  drawings carry (`ink1`, `lab`, `scene` and the like), or none, never one of the site's (`fixed`,
  `inset-0`, `animate-spin`). An `svg` is drawn within its box: its `width` and `height` at most its
  viewBox's (or 100%), any transform only shrinks it (`scale` of 1 or less), with no
  `transform-origin` or `transform-box`, and nothing is shown past its edge (`overflow` is
  `hidden`). A paint that names a variable is read through the drawing's own declarations, and a
  variable the drawing never declares is refused unless it is one of the design's roles, since the
  page may hold a depicted material in it.

## How this reference is kept true

| Rule | Kept true by |
|---|---|
| The kinds in each group and their counts, against the server's own lists | `test_reference_limits.py` in `backend/tests/mcp`, reading `models/component_kinds` and `research/component_specs` |
| Every delivery limit it states | that test again, reading each bound from the spec and delivery modules |
| Withdrawing, replacing, borrowing and the held page, with their limits | that test again, against `research/page_proposals` and `research/page_holds`; `backend/tests/db/test_component_lifecycle_db.py` and `test_borrowed_and_held_pages_db.py` |
| The colours a drawing may use | `test_interactives_skill.py` in `backend/tests/mcp`, against the drawings' colour pattern |
| The design's roles, fonts, the text floor and gradients, at intake and in the preview's report | `test_drawing_vocabulary.py` and `test_page_report_design.py` in `backend/tests/research` |
| The four themes a drawing is served in, the tokens as CSS and the drawing guide | `test_design_kit.py` in `backend/tests/mcp` |
| This text, as every prompt and the site serve it | `test_skill_references.py` in `backend/tests/mcp` |

Read it again whenever a kind is added or retired, a bound changes, or the design system changes a colour's role.
