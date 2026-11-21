# Component specs: plates and media

Decision 0106, item 4. The plates group moves twelve component kinds of the approved Kutch Ajrakh
page from template markup to typed specs drawn by React views.

| Side | File |
|---|---|
| Spec models | `backend/app/research/component_specs_plates.py` (`SPEC_MODELS_PLATES`), `component_specs_plates_media.py`, shared parts in `component_specs_plates_parts.py` |
| Extraction | `backend/app/scripts/extract_specs_plates.py` and `extract_specs_plates_media.py`, on the shared `extract_specs_markup.py` (case-keeping markup tree, anchors), `extract_specs_parts.py` (units, pictures, drawings, held text) and `extract_specs_files.py` (the group run, `--check`) |
| Spec files | `backend/app/data/monographs/Kutch-Ajrakh/specs/<spec_file_name(label)>`, one per component |
| Shapes | `frontend/lib/componentSpecsPlates.ts` |
| Views | `frontend/components/monograph/kinds/plates/`, `index.ts` exports `VIEWS` |
| Tests | `backend/tests/research/test_component_specs_plates.py`, `test_spec_extraction_plates.py`; `frontend/e2e/monograph-kinds-plates-unit.spec.ts` with `e2e/monographKinds.ts` |

Run `python -m app.scripts.extract_specs_plates Kutch-Ajrakh` from `backend` to write the spec
files and `--check` to list those that differ from what extraction writes. The extraction is strict:
a component whose markup the kind's spec cannot hold fails with the label and what is missing.

## Shared parts

- **UnitRef** (`u0001`): a text unit of the content. A spec names every unit its component holds and
  no other; the view draws each through `renderUnit` inside the element the template wraps it in.
- **Picture**: a monograph picture (`/monographs/<folder>/img/…`), its size, alt text, and the
  loading, fetch priority and decoding the page asks for.
- **ArtFrame**: a drawing kept once on the page as a symbol (`#ai-vat`), shown through `<use>` with
  its view box and size.
- **DrawingElement**: vector geometry as a tree of SVG elements (svg, g, path, rect, circle, text,
  gradients, patterns, masks, clip paths, a blur filter). Attributes keep their SVG names; `href`
  points only within the page (`#id`); no handler and no script value is accepted. Colours are the
  page's tokens and dye specimen variables (`var(--dye-kut)`), never typed values.
- **HeldText**: text the template holds outside any unit, in the units' mark grammar (sentence,
  span, italic with its role, bold, sub, sup, highlight, link, figure reference, citation). A held
  citation carries `shown`, its sources' numbers and titles as the page shows them, because a view
  has no source table. Held text is a bridge: such sentences should become units (see Open).
- **DepictedMaterial**: a depicted material the design generator records, drawn as its specimen
  variable `--dye-<name>`. The names are generated from the material records
  (`tools/design/materials.json`, each naming a craft's dossier material and the facts that state
  its colour) into `backend/app/research/depicted_materials.py` and `frontend/lib/depictedMaterials.ts`;
  Kutch Ajrakh's dyes were the first records, and any craft's material with a record can be drawn.

## Kinds

### picture_plate

A photograph framed as a plate. `setting` picks one of five frames, each with its own part:
`figure` (a `figure.plate` with extra `classes`, a `crop` class on `.ph`, caption lines, one marked
`look`, and the credit), `row` (the figure beside a note in `.plate-row`), `pull` (the figure beside
a pull quote whose attribution is held text), `opener` (a chapter opener: the photograph under the
chapter number, kicker, title with its id, dek and credit) and `masthead` (the first screen: the
figure staged with the specimen label, its seal drawing, the held GI line, the place, the sources
counted by grade and the curated day; the view writes "Monograph drawn from N sources", the
reliability strip's spoken summary and "Curated 17 Nov 2026" from them). Every setting but the
opener has a `figure`.

### ai_illustration

A drawing kept on the page as a symbol, shown soft and sharp (`ai-soft`, `ai-pic`), with the AI tag,
the caption "<subject>. Drawn from sentence(s) N of this section; not a photograph.", the made day
and the download (`data-dl-ill`, `data-name`). The kit's script drives the drawing meter and the
download; the view keeps its classes and data attributes.

### specimen_plate

The hero specimen: the photograph, the oxidation and scrim layers, and the on-photo label (kicker,
name with its id, cited sentence, the "Dip it again" replay with its status, credit). The vat
moment is the kit's script: the view keeps `.vat-again`, the status id and `data-phase`.

### label_card

A specimen label card of a `variant` (`gi`): kicker, seal drawing beside its sentence, an optional
`inset` (the label of a component the card holds between the seal and the facts: the GI ladder, a
`timeline`) and the facts as term and value units. The view draws the inset through
`renderComponent` (see Nesting in `component-specs-data.md`).

### swatch_cards

The "four colours, four chemistries" section: chapter number, title with its id, intro, the weave
pattern id, and per colour a before and after swatch (dye and caption unit) joined by "→" or "or",
its name, agent and text.

### swatch_pair

A wide card comparing two swatches drawn on one dye ground with a motif drawing each, under the
weave; the pair's class and spoken description; when, title and text units; and an optional link to
a stage of Fig. 2 (`data-goto-stage`, label as held text) that the kit's script follows.

### film

The answer as a film: title and meta units, scenes (art frame, title, field, still arriving), the
scene label and subtitle units, playback (length, step, resting position), the AI tags, the note and
the two downloads. The kit's script plays it: the view keeps every id (`film-block`, `film`,
`film-play`, `film-range`, `film-time`, `film-ticks`, `film-strip`, `film-note`, `film-dl`,
`film-vtt`) and the play and pause icon markup in `data-play` and `data-pause`. At rest the first
scene shows and the clock reads its resting position.

### ai_video

An eight-second AI video: the whole vat drawing (`DrawingElement`, with its masks and clips), the
phase unit, playback, the held caption with its figure link, the made day and the download. The
kit's script plays it through the ids `vid`, `vid-svg`, `vid-phase`, `vid-play`, `vid-range` and
`vid-time`; at rest it shows the end of the dip.

### comic

Story panels: each panel has its layout class, held caption (a cited sentence), drawing and tag;
the view numbers them and writes the hidden "Panel N of M." for screen readers.

### audio_player

The listen block: title and description units, the action, the minutes it takes and the id of the
player it opens (`data-listen-open`, `aria-controls`), which the kit's script binds.

### voice

A person's words. `testimony`: kicker with its id, the evidence label, quote, credit and meta units,
and an optional echo (a second quote with held attribution). `coda`: the closing card over the cloth
(tile and weave pattern ids, view box), with kicker, quote, caption and note units.

### credits

Picture and data credits: groups of a title unit, an optional list class and lines, each a unit or
held text (a credit the template holds with its link).

## Open

- **Held citations.** Nine cited sentences of these components live in the template, not in units
  (the masthead's GI line, the Banni pull quote's attribution, the second voice's attribution, the
  six comic captions). Their specs carry them as held text with the numbers the page shows, which
  is right only on the Ajrakh page. Moving them into `content.json` as units lets the specs name
  them like any other unit.
- **The GI card's anchor.** `content.json` anchors `kutch-ajrakh/policy/gi-registration-card` at
  `[aria-labelledby="gi-h"]`, which no element of the template has since the card was unframed;
  extraction reads it at `[class="label-card gi"]` (`ANCHOR_CORRECTIONS`). The content's anchor
  should be corrected.
- **Components inside components.** The GI card holds the ladder and the map sequence holds the
  iron swatch pair; the layout lists them at the top level. The views draw what they hold through an
  optional `renderComponent` beside the view contract's props; the renderer has to pass it and skip
  held components at their layout place, or the contract and layout have to record nesting.
