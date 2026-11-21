# Component specs: science group

Twelve science component kinds move from the approved Kutch Ajrakh template to typed specs and
React views. A spec holds everything a view needs that is not a text unit; the view draws the same
elements, classes and text as the approved page, so the kit's `monograph.css` styles it as before.
Engineers changing a player, a drawing or the lab, and a contributor's agent delivering one, read it.

| For | Read |
|---|---|
| Why kinds became specs | [decision 0106](../decisions/0106-one-monograph-template-for-every-page.md), item 4, for the science group |
| The parts every group shares | [component-specs-plates.md](component-specs-plates.md) |
| Delivering one of these kinds through MCP | [component-specs-general.md](component-specs-general.md) |
| A family's flagship interactive, which these kinds carry | [kalavigyan-interactives](../../.claude/skills/kalavigyan-interactives/SKILL.md) |

| Side | Home |
|---|---|
| Models | `backend/app/research/component_specs_science.py` (`SPEC_MODELS_SCIENCE`: kind to model) and its parts `component_specs_science_{parts,figures,explainers,players,lab}.py` |
| Ajrakh specs | `backend/app/data/monographs/Kutch-Ajrakh/specs/<spec_file_name(label)>`, 21 files |
| Extraction | `python -m app.scripts.extract_specs_science` writes them; `--check` reports a file that differs from what the template extracts to |
| Shapes | `frontend/lib/componentSpecsScience.ts` (`SPEC_SHAPES_SCIENCE`) and its parts `componentSpecsScience{Parts,Figures,Explainers,Players,Lab}.ts` |
| Views | `frontend/components/monograph/kinds/science/` (`index.ts` exports `VIEWS: ComponentViews`) |

## Rules every science spec follows

- **Text units by id only.** A unit is named by its id (`u0123`) and drawn through
  `props.renderUnit`. Cited text is never copied into a spec. Labels the page shows uncited (control
  labels, drawing labels, molecule names, step names, the replay's source titles) are spec text.
- **Drawings are typed geometry.** `SvgNode {tag, attrs, children}` holds drawing elements only
  (`svg`, `g`, shapes, `text`, gradients, masks, patterns and the colour filters the page uses; no
  `script`, `foreignObject`, `a` or `use`). Attributes refuse `on*` handlers, `javascript:` and any
  `url()` that is not an in-drawing `#id`. `fill`, `stroke` and `stop-color` are a token
  (`var(--ink-1)`, `--dye-*`, `--dip-*`, `--mol-*`, `--chart-*`, `--map-*`, the surfaces), a mix of
  two tokens (`color-mix(in srgb, var(--a) N%, var(--b))`), an in-drawing reference, `none`,
  `currentColor`, or white or black for a mask or a highlight (`#fff`, `#000`,
  `rgba(255,255,255,a)`). Swatches outside drawings are a token or a `ColourMix`.
- **Spec text keeps its spaces.** Spec models extend `SpecModel`, which keeps leading and trailing
  spaces (`"in the paste · "`) where `ContractModel` strips them.
- **At rest, finished.** A player rests on the step the page shows at first paint (`current`), the
  dip and stage players on their last phase and stage, a toggle on its first option, the lab on its
  first experiment. Hidden steps, results and panels carry `hidden`, as on the page.
- **Behaviour comes from the kit.** Every view keeps the ids, classes and data attributes the page
  script binds to (`data-step`, `rp-rail`, `rp-play`, `mol-dial`, `data-stages`, `data-x`,
  `data-choice`, `data-v`, `data-res`, `data-tapano`, `data-pa-sw`, `data-kv-made`, `data-srcdoc`
  and the rest), so `monograph.js` drives players, toggles, dials and the replay. No view adds its
  own behaviour, and no view re-renders after the kit binds it (decision 0106, consequences).
- **Nested components are slots.** A `ComponentSlot {component: label}` marks where another
  registered component sits inside this one (the lab's three toggles, a toggle's chart, the
  materials' photograph). The view draws it through `parts/Slot.NestedComponents`, a context whose
  `render(label)` the renderer provides; without a provider a slot draws nothing. The renderer then
  draws a nested component only through its parent.
- **Held passages.** Where the template carries a cited sentence outside any text unit, the
  extraction leaves it out and reports it (`Extraction.held`); the spec field that would show it
  (a unit id) stays empty, and the view draws the passage once the unit exists. Ajrakh has 22:
  16 in the stage player (each stage's "Cloth after" sentence, stage 11's "Why" and the three
  "Sources differ" notes), two in the indigo-vat toggle's "Sources differ" note, and the PubChem
  record citation of each molecule in both structure diagrams (`rm:mol.1`, `rm:mol.6683`).

## reaction_player

`ReactionPlayerSpec {id, track, head, current, steps, scenes, key, status}`. Each step has its rail
`name`, its `text` (kicker, heading, paragraphs, an optional bond note, link and conditions, and a
"Sources differ" note of unit paragraphs) and its `chemistry`, an ordered list of species lanes
(swatch, name, formula, state, PubChem CID), equations (with the atom count and notes) and a
no-equation note. A player either draws one scene for every step (`scenes`, desk and phone) or a
reaction per step (`scene {whereIcon, where, art}`, desk, tall and phone) with a `key` line; the
second is drawn as `figure.rp.rx-player`. Ajrakh: blue (per-step reactions), red, black, white.

## dip_player

`DipPlayerSpec {id, head, phase, scene, stripLabel, phases, dipAgain, status, dipsLabel, dips,
equation?}`: the scene, the strip of phases, each named by its own key in `pose` (a lower-case
word or hyphenated words, each once; the last carries `aria-current="step"`), the label of the
repeat button, the swatches of the successive dips (colour tokens, the last `on`) and, where a source
states one, the balanced equation. The poses are the spec's words, not the model's: Ajrakh's spec
carries vat, lifted and air and its `--dip-1..4`, and Bidriware's fixture carries solution, lifted
and oiled with no equation, because the patina's compounds are unidentified. Ajrakh:
`shared/chemistry/indigo-vat-dip`.

## stage_player

`StagePlayerSpec {key, head, drawing, restName, play, source, stages, finish}`. Each stage has its
name, English name, whether the name is local (italic on the ribbon), its "after" label for the
label card and the script's `data-stages`, and its units (number, heading, texts, why, materials,
and the held "Sources differ" note and after sentence). The view draws each stage's tile, ribbon
and swatch from the page's `#tile-n` patterns, the label card at rest ("Stage 11 of 11") and the
ribbon as a toolbar. The label before each stage's after (`afterLabel`, Ajrakh's "Cloth after", a dhokra
mould's "Model after") is the spec's, and a stage may name a recorded material as its `swatch`, drawn in
place of the page's `#tile-n` pattern, so another craft's stages show their own colours.
Ajrakh: `kutch-ajrakh/process/cloth-after-each-stage`.

## diagram

`DiagramSpec`: either a whole `drawing` (the borewell depth and the Bhuj distances) or a `chain`
of links, each a kicker and ordered parts: text blocks, drawings, step links into a reaction
player (`#rp-blue`, step n, with the figure reference) and a grouped equation with its tick count.
Ajrakh: three.

## molecule_3d

`Molecule3dSpec {head, molecules, side, key}`. Each model has its CID, yaw and pitch, name, dial
label, formula, atom line, note and its at-rest projection as a drawing; the dial's value is the
yaw in whole degrees. With side paragraphs the figure is `mols mol-two`. The kit redraws the model
from the page's molecule data on drag. Ajrakh: two.

## structure_diagram

`StructureDiagramSpec {id, head, dekStyle, scale, molecules, notes, key, swatches, swatchNote}`:
flat structures with name, formula, note, atom units and PubChem record, the marked-ring key, and
(in Hindi) swatches with their labels. Ajrakh: the English and Hindi alizarin and purpurin figures.

## equation_card

`EquationCardSpec {kicker, title, mark, line, why}`: a stated step drawn as an equation line with
the hypothesis mark. Ajrakh: `kutch-ajrakh/chemistry/indoxyl-to-indigo-hypothesis`.

## model_explainer

`ModelExplainerSpec {head, badge, badgeNote, stills, controls, key, model}`: inert stills (wide and
narrow) with their units and drawings, the shared play button, slider and key, and the model-built
document `{title, height, stylesheet, document, sandbox: "allow-scripts"}` that the kit loads into
the frame from `data-srcdoc`. The stylesheet may not contain markup. Ajrakh:
`shared/chemistry/indigo-in-cotton-fibre-explainer`.

## material_cards

`MaterialCardsSpec {id, headingId, heading, intro, cards, after}`: each card's swatch (a dye token
or `crystal`), role, name, local name, botanical name, chemistry and facts as units, and the
nested photograph as a slot. Ajrakh: `kutch-ajrakh/materials/six-materials`.

## experiment_lab

`ExperimentLabSpec {id, figure, number, pickerLabel, experiments}`: the picker and one toggle slot
per experiment. The lab provides `parts/LabContext.OpenExperiment` (its first experiment), so its
other toggles rest closed. Ajrakh: `kutch-ajrakh/chemistry/what-if-lab`.

## choice_toggle

`ChoiceToggleSpec {experiment, questionId, question, options, textParts, visualParts}`: the
question, its options (each a result of a heading, paragraphs and differs notes) and ordered panel
parts in the text and visual columns: text blocks, formula chips (a PubChem CID or a named source),
a "same either way" note, a chart slot, a stage drawing with its hidden note, a stepper and a
switch, each with the script hook it carries. A toggle drawn outside a lab is open. Ajrakh: blue,
red and wash water.

## process_replay

`ProcessReplaySpec {play, understood, angles, stages, sourcesKicker, sources, sectionsKicker,
sections, ready}`: the replay's timed stages (start and end in ms), the sources read in order with
their grade, and the sections written with what each drew. Ajrakh:
`kutch-ajrakh/overview/how-this-answer-was-made`; its heading `u1055` is the summary of the fold
around the anchor, outside it, and is not drawn by the view.

## How this document is kept true

| Claim | Kept true by |
|---|---|
| A valid and a refused spec of each kind, the drawing and colour rules, spaces kept | `backend/tests/research/test_component_specs_science.py` |
| Every Ajrakh spec validates, shows exactly the units the layout places in its component, nests the components the page nests, holds back the 22 cited passages, and equals what the template extracts to | `backend/tests/research/test_science_spec_files.py` |
| The template reader | `backend/tests/test_extract_specs_science_script.py` |
| Each of the 21 views, drawn from its spec file, gives the template element's markup (attribute order, entity spelling, style spacing and JSON formatting aside), with the held passages removed and foreign nested components as slots | `frontend/e2e/monograph-science-parity-unit.spec.ts` |
| One component of each kind checked by hand against the approved page, the client's kinds against the backend's, and the shape refusals | `frontend/e2e/monograph-science-views-unit.spec.ts` |
| The colours a drawing accepts, as the interactives skill lists them | `backend/tests/mcp/test_interactives_skill.py`, against `COLOUR_TOKEN_PATTERN` |

Re-read it when a science kind gains a field, a held passage becomes a unit, or the colour rule changes.
