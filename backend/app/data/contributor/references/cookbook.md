# The component cookbook

Every kind of component a KalaVigyan page can carry, one entry each: what it shows, when a page
needs it, why Kutch Ajrakh's page has one (what in its facts called for it), which tool makes it,
the facts it needs, how to place it and how to check it in the preview. Ajrakh is the worked
example of the thinking, never a list to copy: a page holds the figures its own craft's facts call
for. The playbook (`playbook/1`) says when to reach for an entry; the component guide
(`components/1`) holds the delivery rules every kind meets, and each kind's JSON schema is
`kalavigyan://components/<kind>.schema.json`.

| Group | Kinds |
|---|---|
| Designed and coded by you | `coded_figure` |
| A composer can make it from the page's structure | `reaction_player`, `dip_player`, `molecule_3d`, `experiment_lab`, `choice_toggle`, `stage_player`, `timeline_map` |
| Maps | `timeline_map`, `map_layer`, `map_sequence` |
| Chemistry | `reaction_player`, `molecule_3d`, `structure_diagram`, `equation_card`, `material_cards`, `diagram` |
| Process | `stage_player`, `dip_player`, `diagram` |
| Data figures | `chart`, `stat_tiles`, `fact_table`, `timeline`, `source_disagreements` |
| Plates, swatches and voices | `swatch_cards`, `swatch_pair`, `label_card`, `voice`, `drawing` |
| Pictures, given not delivered | `picture_plate`, `ai_illustration` |
| The authored page's own | `specimen_plate`, `ai_video`, `comic`, `model_explainer` |
| The site's own, on every page | `answer_block`, `why_here`, `related_crafts`, `concept_atlas`, `explainer`, `audio_player`, `quiz`, `ask_next`, `citation_tool`, `language_switch`, `reading_level`, `generator`, `film`, `process_replay`, `source_list`, `credits` |

## Reading an entry

Each entry has the same seven lines. **Shows** is what a reader sees. **When a page needs it** is
what in a page's facts calls for it. **In Kutch Ajrakh** says why Ajrakh's page has one, names each
of its components of the kind by label, its chapter's worked guide and its anchor in the authored
page: that guide's section of the label holds the spec, the place and the sentences around it.
**Made by** is the tool. **Facts** is what must be held first and how to get it. **Place** is its
chapter, role and size. **Check** is what to look at in the preview. A kind filled by hand adds
**Shape**, its spec's top-level keys, `?` marking an optional one; every string a reader sees is a
unit id (`u0001`).

## How a figure gets made

- **Designed first.** Decide what the reader must see or do, from the facts and the design
  principles (`kalavigyan-design/1`, `system/1`), before choosing a tool.
- **Coded freely.** A `coded_figure` is yours to design and write: its markup, style and script
  (three.js and d3 are served to it, pinned) over the page's cited units and values, drawn in a
  sandbox with a still (decision 0231). Match the kit (`kit-stylesheet/1`, `kit-script/1`).
- **A kind the site draws** when it says exactly what you need: the declared kinds from data, the
  others in their own form, filled by the shape below, the schema and the worked example.
- **A composer when it helps.** `compose_component` builds a craft's reactions, baths,
  molecules and what-if choices into players from the page's structure, finished and cited; with
  no kind it composes every kind the craft's facts allow in one call, and the preview's rule 29
  lists what the facts could still show. Its result is a draft to take, change or set aside for a
  design of your own.
- **Given.** Pictures go through `give_pictures`, never as a component.
- **The site's own** are drawn from the page's data on every page; a proposal of one is refused.

## Placing a component

A page's layout is a list of entries `{ref, chapter, order, role, size?, crop?, caption?}`, on top
of the layout version `get_page` returned, sent in the draft's `add.layout`. `ref` is a
component's label or a text unit's id; `order` counts from 1 within the chapter, no two alike.

- **Chapters.** A generated page has `opening` (the masthead), `glance`, `made`, `chem`, `why`,
  `history`, `market`, `whatif`, `people`, `kin` and `sources`. Ajrakh's `answer` is `opening`,
  `cloth` is `glance`, `chemistry` is `chem`, `why-kachchh` is `why` and `what-if` is `whatif`;
  a generated page also has `reading` and `media`, where the student version and the reading
  tools stand unless the layout places them (decision 0233).
- **Roles.** `HERO` is the masthead picture, once a page. `OPENER` is a chapter's opening picture,
  once a chapter. `PLATE` is a picture in the run of a chapter, `FIGURE` any other component.
  `SIDEBAR` is a note beside the prose, `PULL_QUOTE` a text unit set large, `BODY` running text.
- **Sizes.** Place every figure with intent. `COLUMN` is the reading measure (a molecule, a
  toggle, a small chart). `WIDE` is the content width (a player, a map, swatch cards, a table).
  `BLEED` is edge to edge (one strong picture or map per page). `MARGIN` sits beside the
  paragraph it follows from 1200 px and after it below (a material card, a small plate, a sidebar
  sentence). With no size, `SIDEBAR` is `MARGIN`, `OPENER` is `WIDE` and `PLATE` is `COLUMN`
  (decision 0227).
- **Order.** Name only a chapter's figures, pull quotes and sidebars, and the page sets each one
  after the paragraph that tells it; name a paragraph's unit as `BODY` only to fix your exact order.
- **Crop.** A picture's focal box `{x, y, width, height}`, each from 0 to 1 of the picture, is the
  part of the picture that is shown; it keeps people and work in frame on a phone. Check the
  preview at 1440: every margin item stands beside its paragraph.
- **Rhythm.** A short run of prose, the figure it sets up, the prose that reads it; the worked
  chapters show the rhythm. Never all prose first and the figures after.

## Checking in the preview

`preview_page` returns pictures of the first screen at 390 and 1440 px and of each chapter. For
every component look for: drawn whole at rest, inside its column, its title stating what it shows,
every cited unit with its citation, no text cut or scrolled, and rule 28's drawing checks passed.
Then read each chapter as a reader would: does it show what its words explain? Rule 29 lists what
the craft's own facts could still show (a reaction with no drawing, stages with no player, places
and dates with no map, quantities with no figure); it is yours to judge, never a fail.

## `coded_figure`

- **Shows**: whatever the design needs that no other kind expresses: molecules that move and bonds
  that break, a bath scene, a route map that plays, a stage scene that moves, a model of a fibre.
- **When a page needs it**: a mechanism or moment of the story is understood by watching or doing
  it, and no kind below draws it as well.
- **In Kutch Ajrakh**: none of this kind; Ajrakh's authored players and its fibre explainer
  (`model_explainer`, `ajrakh-chemistry/1`) are what such a figure reaches for, because its
  chemistry turns on changes a reader has to see happen.
- **Made by**: `edit_draft` with a coded figure (decision 0231): its HTML, CSS and script written
  by you over the page's structured data, drawn in a sandboxed frame with a still for paper and
  reduced motion. Compose first; code where no kind or composer expresses what the facts need
  (molecules meeting and a bond breaking, a dye bath, a route or map states on the site's base, a
  moving stage, a three.js model, a film the site holds). Pinned d3 7.9.2 and three 0.187.0 are
  served to the frame; code up to 64 KiB; the frame up to 1,200 px tall; films from files under
  `/monographs/` or the media store's approved clips made from the figure's facts (`films[].clip`).
- **Facts**: every fact in a cited unit, shown by `data-unit`; every number in `values` with a
  reading that states it. Labels, controls and decoration are free text.
- **Motion**: read `document.documentElement.dataset.reducedMotion` and draw the last state at
  once when it is set; give the motion a pause button.
- **Maps**: draw only through `map` and `kvMap` (the Survey of India outline, states, districts,
  rivers and relief are drawn for you); never draw geography yourself.
- **Still**: send a `still` for a canvas or WebGL figure; an svg figure's still is cut for you.
- **Place**: the chapter of what it shows, role `FIGURE`, size `WIDE`.
- **Check**: the still shows the figure whole; motion stops under reduced motion and has a pause.
  Match the kit (`kit-stylesheet/1`, `kit-script/1`) and the tokens (`system/1`).

## `reaction_player`

- **Shows**: a reaction step by step, each step with its species, its conditions and what changes,
  resting on the step the page explains.
- **When a page needs it**: a mechanism on the page's list is a reaction a source states with its
  formulas.
- **In Kutch Ajrakh**: each of its four colours is a different chemistry a source states step by
  step, so each has a player of its own (`ajrakh-chemistry/1`): `shared/chemistry/indigo-reduction-player`
  (`#rp-blue`, leaf to fibre), `kutch-ajrakh/chemistry/red-alum-madder-player` (`#rp-red`, red only
  where alum was printed), `kutch-ajrakh/chemistry/iron-tannin-black-player` (`#rp-black`, iron on
  tannin) and `kutch-ajrakh/chemistry/white-resist-player` (`#rp-white`, cloth the dye never reached).
- **Made by**: `compose_component` with kind `reaction_player` (`about {reaction}` for one)
  composes it from the page's reactions, each step's scene drawn from its own species with the
  kit's `species` part and `react` motion: the reagent that arrives (oxygen, a mordant), a bond
  that breaks only where the reaction is a hydrolysis, dehydration, dehydroxylation or a split,
  colours only from recorded materials (decision 0228). The player plays on its own in view, loops
  and has one Pause. Or design it as a `coded_figure`.
- **Facts**: a `REACTION` structure item per reaction with every formula, balanced, and its stage.
- **Place**: `chem`, role `FIGURE`, size `WIDE`, after the prose that names the change.
- **Check**: every step names its species and formulas without scrolling; the resting step is the
  one the prose explains.

## `dip_player`

- **Shows**: work going through successive baths, each dip in the depicted material of its dye,
  mordant or resist.
- **When a page needs it**: the process dips, soaks or vats the work more than once, and the change
  between dips is the point.
- **In Kutch Ajrakh**: the signature fact is cloth lifted green from the vat turning blue in the
  air, deepening with each dip, so it is the page's first figure (`ajrakh-answer/1`):
  `shared/chemistry/indigo-vat-dip` (`#fig1`).
- **Made by**: `compose_component` with kind `dip_player` (`about {stage}` for one bath) can compose
  it from the stage afters; or a `coded_figure` of the bath.
- **Facts**: the `STAGE_AFTER` of every bath stage, naming each colour, and its materials by
  substance; a colour no depicted material shows comes back in `left_out`.
- **Place**: `opening` or `made`, role `FIGURE`, size `WIDE`.
- **Check**: each dip is drawn in its material, and the rest state is the finished colour.

## `molecule_3d`

- **Shows**: a compound's molecule in three dimensions, turned and zoomed by pointer, touch and
  keyboard.
- **When a page needs it**: a mechanism turns on a molecule's shape or on atoms it gains or loses.
- **In Kutch Ajrakh**: indigo and leucoindigo differ by two hydrogens, and madder's red is two
  molecules, so both pairs are shown turnable (`ajrakh-chemistry/1`):
  `shared/chemistry/indican-indigo-leucoindigo-3d` (`[class="mols"]`) and
  `shared/chemistry/alizarin-purpurin-3d` (`[class="mols mol-two"]`).
- **Made by**: `compose_component` with kind `molecule_3d` (`about {compound}` by its CID) composes
  it from PubChem's 3D record, for a compound a material holds or one the page's own facts name by
  PubChem's name or a synonym; a refusal names what is missing (no record under that CID, no fact
  naming it).
- **Facts**: the material's compound with its CID, or a fact of the page naming the compound
  (`lookup` kind compound gives the CID and PubChem's name).
- **Place**: `chem`, role `FIGURE`, size `COLUMN`, beside the reaction it explains.
- **Check**: the molecule rests drawn, its name and formula in words beside it.

## `experiment_lab`

- **Shows**: what-if experiments a reader runs: change one thing and see what the sources say
  follows.
- **When a page needs it**: the facts compare alternatives a maker chooses between.
- **In Kutch Ajrakh**: its sources compare a natural vat with a chemical one, madder with synthetic
  alizarin and clean wash water with iron-laden, so the reader gets to choose
  (`ajrakh-what-if/1`): `kutch-ajrakh/chemistry/what-if-lab` (`#lab`).
- **Made by**: `compose_component` with kind `experiment_lab` can compose it with one
  `choice_toggle` per experiment from the page's alternatives; or a `coded_figure`.
- **Facts**: `ALTERNATIVE` structure items and the facts that compare each pair.
- **Place**: `whatif`, role `FIGURE`, size `WIDE`; its toggles inside it.
- **Check**: each choice shows its outcome at rest and cites the fact that states it.

## `choice_toggle`

- **Shows**: one experiment of a lab: a question, its options and what each leads to.
- **When a page needs it**: inside an `experiment_lab`, one per experiment.
- **In Kutch Ajrakh**: one for each choice its sources compare (`ajrakh-what-if/1`):
  `kutch-ajrakh/chemistry/what-if-indigo-vat` (`[data-exp="blue"]`),
  `kutch-ajrakh/chemistry/what-if-red-dye` (`[data-exp="red"]`) and
  `kutch-ajrakh/chemistry/what-if-wash-water` (`[data-exp="water"]`).
- **Made by**: `compose_component` with kind `experiment_lab` makes them with their lab.
- **Facts**: as its lab.
- **Place**: inside its lab, named in the lab's `experiments`; the lab places them.
- **Check**: the toggle's default option matches the page's prose.

## `stage_player`

- **Shows**: the work after every stage of its making, stage by stage, with each stage's name,
  what it does and why.
- **When a page needs it**: the process has stages whose results look different, and seeing the
  work change is how a reader follows it.
- **In Kutch Ajrakh**: its eleven stages each leave the cloth visibly changed, so one cloth is drawn
  after each (`ajrakh-made/1`): `kutch-ajrakh/process/cloth-after-each-stage`
  (`[aria-labelledby="fig2-t"]`).
- **Made by**: the spec filled by hand in `edit_draft`, each stage with its own `scene` from the kit
  (a carved block, a cloth in a bath, washing water), its motion played when the stage is shown, and
  the `drawing` the finished work the player rests on; a stage without a scene keeps the nearest
  earlier stage's; or a `coded_figure` of the stages.
- **Shape**: `{key, head {figure, number, title, titleId?, dek?}, drawing, restName, play, source,
  stages [{name, english, local, after, number, heading, texts, why?, differs?, afterSentence?,
  materials?, swatch?, scene?}], finish {heading, paragraphs}, afterLabel}`; the last stage takes no
  `scene`.
- **Facts**: every stage with its `STAGE_AFTER` (colours) and `STAGE_WHY`, its local name.
- **Place**: `made`, role `FIGURE`, size `WIDE`, after the chapter's opening prose.
- **Check**: every stage is reachable, and the rest state is the finished work.

## `timeline_map`

- **Shows**: the craft's places on India's map with what happened at each and when, routes between
  them, and the site's relief, river or mineral layers.
- **When a page needs it**: the craft's history happens in places: where it began, moved, traded.
- **In Kutch Ajrakh**: its dated record runs from Mohenjo-daro and Fustat to a 2024 registration
  across many places, so dates and places are read together (`ajrakh-history/1`):
  `kutch-ajrakh/history/dated-record-timeline-map` (`[aria-labelledby="fig1-t"]`).
- **Made by**: `compose_component` with kind `timeline_map` once composed timeline maps land; the
  spec declared by hand in `edit_draft`; or a `coded_figure` for a route that plays.
- **Shape**: `{head {title, caption?}, places [{name, wikidata? | district? | longitude?,
  latitude?, at?, home?}], points? [{place, yearFrom, yearTo, text}], routes? [{start, end,
  yearFrom, yearTo, text}], undated? [{place?, text}], layers?}`; places by index.
- **Facts**: each place by Wikidata item (`lookup` kind entity), LGD district or a stated
  coordinate; each point's unit states its years and names its place. Each layer's dataset record
  is read with `get_page` and `guide` `map-layers/1`; the server credits it under the map.
- **Place**: `history` for a dated record, `why` for the craft's places; role `FIGURE`, `WIDE`.
- **Check**: every place is drawn and named, and the map frames them.

## `map_layer`

- **Shows**: the craft's places on the site's own map base, framed to them: relief with hillshade,
  rivers and lakes, the Survey of India outline with state and district lines, neighbouring land,
  sea and salt flats, the home district hatched, each place a numbered disc named beside it, a
  scale bar and the India locator; and, when asked, an arrow for a move, a ring of a stated radius,
  a value per district, and a sequence that plays with Play, Pause and a step to press
  (decision 0232).
- **When a page needs it**: where the craft is made and what lies around it is part of the story:
  a town and its neighbours, a move after a flood or earthquake, a distance, rainfall across
  districts, a spread told step by step.
- **In Kutch Ajrakh**: `shared/climate/kachchh-district-climate-map` (`ajrakh-why-kachchh/1`,
  `[aria-labelledby="fig3-t"]`) is what a `districts` part draws;
  `kutch-ajrakh/geology/dhamadka-epicentre-circle-map` is a 20 km `ring` round Dhamadka;
  `kutch-ajrakh/history/dhamadka-to-ajrakhpur-move-map` is a `route`; the two Suran maps
  (`kutch-ajrakh/geography/suran-flowing-north-map` and
  `kutch-ajrakh/geography/suran-dry-below-tapar-dam-map`) are a frame on the villages with
  `rivers` emphasised (the Suran itself is too small for the site's data, so its sentence carries
  it).
- **Made by**: `edit_draft`, a declared spec by hand (values from a dataset: `propose_dataset`
  first). Places with years or moves through time: a `timeline_map`. Never draw geography.
- **Shape**: `{head {title, caption?}, places [{longitude, latitude, name, reading, value?,
  cell?}], valueLabel?, dataset? {code}, frame? {places [i] | district | state}, emphasis?
  {layers? [relief|rivers|water], rivers? [name]}, routes? [{start, end, text}], rings? [{place,
  radiusKm, text}], districts? {valueLabel, values [{district, value, reading}]}, sequence?
  [{text, places [i], routes [i], rings [i], districts}]}`; indices count from 0 in the spec's own
  lists; up to 20 routes, 6 rings (up to 500 km each), 2 to 60 districts, 2 to 12 steps.
- **Facts**: a route's unit states the move ("moved from Dhamadka to Ajrakhpur"), a ring's states
  its kilometres, a district reading states its value, and each cites a fact; every step cites a
  fact. Name districts and states by LGD code (`lookup`), rivers by the site's own river names.
- **Place**: `why`, role `FIGURE`, size `WIDE`.
- **Check**: the map frames the places, not all of India; every disc is named and numbered in the
  list; each arrow, ring and value sits where its sentence puts it; a sequence rests on its last
  step.

## `map_sequence`

- **Shows**: a run of dated cards, each a moment in the place's story, with a map or figure where
  it has one.
- **When a page needs it**: the place itself changed over time, and each change shaped the craft.
- **In Kutch Ajrakh**: a river dammed, an earthquake and a village founded 40 km away changed where
  and how ajrakh is printed, so the four moments are read in order (`ajrakh-why-kachchh/1`):
  `kutch-ajrakh/geography/suran-earthquake-ajrakhpur-cards` (`[aria-labelledby="fig4-t"]`).
- **Made by**: `edit_draft`, filled by hand; or a `coded_figure`.
- **Shape**: `{head {number?, title, titleId?, dek?, dekId?}, first [{card? {visual?, when, title,
  lines, differs?}, component?}], source {tag?, classes?, unit?, text?}, more?}`.
- **Facts**: each card's date and change, each a cited fact.
- **Place**: `why`, role `FIGURE`, size `WIDE`.
- **Check**: the cards read in order of their dates.

## `structure_diagram`

- **Shows**: molecules drawn flat, atom by atom, with their names, formulas and PubChem records.
- **When a page needs it**: a mechanism turns on a bond or ring a flat drawing shows best.
- **In Kutch Ajrakh**: red is alizarin closing a ring on aluminium, which a flat drawing shows
  better than words (`ajrakh-chemistry/1`): `shared/chemistry/alizarin-aluminium-ring-structures`
  (`#fig3-en`); the same in Hindi for its readers (`ajrakh-reading/1`):
  `shared/chemistry/alizarin-purpurin-structures-hindi` (`#fig3-hi`).
- **Made by**: `edit_draft`, filled by hand from `lookup` kind compound records.
- **Shape**: `{id, head {figure, number, title, titleId?, dek?}, dekStyle?, scale, molecules
  [{drawing, name, formula, note, atomsTerm, atoms, recordTerm, cid, recordCite?}], notes?, key,
  swatches?, swatchNote?}`.
- **Facts**: each compound's CID and the fact naming its role.
- **Place**: `chem`, role `FIGURE`, size `COLUMN`, after the reaction it explains.
- **Check**: atoms are labelled in words, and the key names every colour.

## `equation_card`

- **Shows**: one stated equation, reactants to products, with why it matters.
- **When a page needs it**: a source states an equation, or words that the page must mark as a
  hypothesis.
- **In Kutch Ajrakh**: one source's wording of indigo forming does not balance, so the page shows
  it as a hypothesis beside the balanced form (`ajrakh-chemistry/1`):
  `kutch-ajrakh/chemistry/indoxyl-to-indigo-hypothesis` (`[class="kv-hyp wrap"]`).
- **Made by**: `edit_draft`, filled by hand.
- **Shape**: `{kicker, title, mark, line {reactants [{formula, name?}], products [{formula,
  name?}]}, why}`.
- **Facts**: the equation balanced for atoms and charge, and the fact stating it.
- **Place**: `chem`, role `FIGURE`, size `COLUMN` or `MARGIN`.
- **Check**: the formula reads whole with its subscripts.

## `material_cards`

- **Shows**: what each material is and does, a card each with its swatch, role, local and
  botanical names and its chemistry.
- **When a page needs it**: the process rests on materials a reader needs to tell apart.
- **In Kutch Ajrakh**: six dyes, mordants and resists make its four colours, each with a printer's
  name, a plant or a compound (`ajrakh-chemistry/1`): `kutch-ajrakh/materials/six-materials`
  (`#materials`).
- **Made by**: `edit_draft`, filled by hand.
- **Shape**: `{id, headingId, heading, intro, cards [{swatch, role, name, local, botanical?,
  chemistry, facts}], after?}`.
- **Facts**: each material with its `BOTANICAL_NAME` and native name, and what it does.
- **Place**: `chem`, role `FIGURE`, size `WIDE`.
- **Check**: every card cites its facts; a swatch is a depicted material.

## `diagram`

- **Shows**: a mechanism, a section, a tool or an object composed from the figure kit: cloth, a
  block, a bath, a paste, heat, water, a section or a shaped piece, panel by panel.
- **When a page needs it**: a chain of steps, a layered section or a measured depth reads best as
  a drawing of its parts.
- **In Kutch Ajrakh**: the blue's cycle from leaf to cloth, the falling water table and the
  distances between its villages are each easier seen than told (`ajrakh-chemistry/1`):
  `shared/chemistry/indigo-leaf-to-cloth-chain` (`[aria-labelledby="ch-h"]`); and
  (`ajrakh-why-kachchh/1`) `kutch-ajrakh/geology/ajrakhpur-borewell-depth`
  (`[class="well-svg kv-well"]`) and `kutch-ajrakh/geography/bhuj-ajrakhpur-dhamadka-distances`
  (`[aria-labelledby="dst-t"]`).
- **Made by**: `edit_draft`, declared with kit parts (`components/1`, The figure kit); or a
  `coded_figure` when the parts must move.
- **Shape**: `{head {title, caption?}, layout, alt, panels [{label, text?, via?, motion?, parts}]}`,
  `layout` one of `steps`, `before_after`, `section` and `sequence`.
- **Facts**: each panel's label a cited unit.
- **Place**: the chapter of what it shows, role `FIGURE`, size `COLUMN` or `WIDE`.
- **Check**: every part draws in its material and every label is legible at 390 px.

## `chart`

- **Shows**: quantities compared, as bars across categories or a line over time.
- **When a page needs it**: a source or dataset gives numbers of one measure that differ in a way
  that matters.
- **In Kutch Ajrakh**: where sources give a span (days of fermenting, hours in the red bath), a
  climate series, a workshop's output or a count of makers, the numbers are drawn to scale:
  `ajrakh-chemistry/1`, `kutch-ajrakh/process/kut-fermenting-days-range` and
  `kutch-ajrakh/process/red-bath-hours-range`; `ajrakh-why-kachchh/1`,
  `shared/climate/kachchh-annual-rainfall-chart` and `shared/climate/kachchh-annual-temperature-chart`;
  `ajrakh-market/1`, `kutch-ajrakh/economics/dhamadka-yardage-2014`; `ajrakh-what-if/1`,
  `kutch-ajrakh/process/vat-setting-days` and `kutch-ajrakh/process/red-bath-hours`;
  `ajrakh-people/1`, `kutch-ajrakh/society/khavda-khatris-2011-dots`.
- **Made by**: `edit_draft`, a declared spec; a table of values through `propose_dataset` first.
- **Shape**: `{head {title, caption?}, form, valueLabel, series [{name, points [{label, value,
  reading, cell?}]}], emphasis, dataset?}`, worked in `components/1`.
- **Facts**: every value stated by its `reading` unit's fact or a dataset row.
- **Place**: the chapter of its field, role `FIGURE`, size `COLUMN`.
- **Check**: drawn to scale from zero, its title stating the finding.

## `stat_tiles`

- **Shows**: a few headline numbers, a tile each with its caption.
- **When a page needs it**: a source gives two or three striking quantities about one subject.
- **In Kutch Ajrakh**: an effluent plant's year and cost, and a survey's stages, centres and
  masters, are numbers worth seeing at a glance beside their prose (`ajrakh-why-kachchh/1`):
  `kutch-ajrakh/ecology/effluent-treatment-stats` (`[class="ws-stats"]`) and
  `kutch-ajrakh/geography/lower-sindh-ajrak-survey-stats` (`[class="ws-stats three"]`).
- **Made by**: `edit_draft`, filled by hand.
- **Shape**: `{classes?, tiles [{figure, small?, caption}]}`.
- **Facts**: each number in a fact's statement or quote.
- **Place**: beside the prose that cites them, role `SIDEBAR` or `FIGURE`, size `MARGIN`.
- **Check**: each number is exactly its fact's.

## `fact_table`

- **Shows**: several things side by side by their attributes, or the craft at a glance.
- **When a page needs it**: a reader wants the craft's essentials in one place, or a comparison of
  three or more things.
- **In Kutch Ajrakh**: centres, makers, colours, dyes, stages and time per piece are what a reader
  asks first, so they open the cloth chapter (`ajrakh-cloth/1`): `kutch-ajrakh/overview/at-a-glance`
  (`#glance`).
- **Made by**: `edit_draft`, a declared spec, or a dataset's table.
- **Shape**: `{head {title, caption?}, columns [{label, numeric, column?}], rows [{cells, row?}],
  dataset?}`.
- **Facts**: every cell a cited unit or a dataset cell.
- **Place**: `glance`, role `FIGURE`, size `COLUMN`.
- **Check**: numbers in tabular figures, no empty cell.

## `timeline`

- **Shows**: a short ladder of dated steps about one thing.
- **When a page needs it**: a few dates in one sequence, such as a registration's path.
- **In Kutch Ajrakh**: its GI took 447 days from application to certificate in three dated steps
  (`ajrakh-market/1`): `kutch-ajrakh/policy/gi-application-to-certificate` (`[class="gi-ladder"]`).
  Its longer dated record, across places, is a `timeline_map`.
- **Made by**: `edit_draft`, a declared spec.
- **Shape**: `{head {title, caption?}, events [{year, when, title, text}]}`, in year order.
- **Facts**: each event's year stated by its `when` unit's fact.
- **Place**: `market` or `history`, role `FIGURE`, size `COLUMN`.
- **Check**: events read in order; no year is inferred.

## `source_disagreements`

- **Shows**: where sources differ, each disagreement with its readings side by side.
- **When a page needs it**: the page holds `CONFLICT` items or facts that differ on a number.
- **In Kutch Ajrakh**: six points of its process are read differently by two sources, and the page
  shows both rather than choosing (`ajrakh-chemistry/1`): `kutch-ajrakh/process/experts-differ`
  (`#differ`).
- **Made by**: `edit_draft`, filled by hand from the conflicts the page holds.
- **Shape**: `{id, titleId, title, intro, items [{summary, readings, figure?}]}`.
- **Facts**: `CONFLICT` structure items naming the facts that disagree.
- **Place**: the chapter of the subject, role `FIGURE`, size `COLUMN`.
- **Check**: each reading cites its own source.

## `swatch_cards`

- **Shows**: the craft's colours, each from what it was to what it becomes, with its agent.
- **When a page needs it**: a dyed, printed or painted craft whose colours each have a cause. A
  page whose stages name their colours gets its colour key drawn by the site; deliver cards only
  for colours no stage names.
- **In Kutch Ajrakh**: one cloth holds four colours made by four chemistries, the idea the whole
  page builds on (`ajrakh-cloth/1`): `kutch-ajrakh/chemistry/four-colours-four-chemistries`
  (`[aria-labelledby="four-h"]`).
- **Made by**: `edit_draft`, filled by hand.
- **Shape**: `{chapterNo, title, titleId, intro, weave, colours [{before? {dye, caption}, join?,
  after? {dye, caption}, name, agent, text, why?}]}`.
- **Facts**: each colour's fact naming its dye or mordant by substance.
- **Place**: `glance`, role `FIGURE`, size `WIDE`.
- **Check**: every swatch is a depicted material, named in words too.

## `swatch_pair`

- **Shows**: two swatches compared, such as one effect on purpose and the same by accident.
- **When a page needs it**: a source contrasts two outcomes of one material.
- **In Kutch Ajrakh**: the iron that prints its black on purpose also spots the cloth from bad wash
  water (`ajrakh-why-kachchh/1`): `kutch-ajrakh/chemistry/iron-on-purpose-and-by-accident`
  (`#b-ws-iron`).
- **Made by**: `edit_draft`, filled by hand.
- **Shape**: `{id, wide, pairClass, description, weave, swatches [{ground, motif, label}], when,
  title, texts, go?}`.
- **Facts**: the fact stating each outcome.
- **Place**: the chapter of the cause, role `FIGURE`, size `COLUMN`.
- **Check**: the two read as a pair at 390 px.

## `label_card`

- **Shows**: a specimen label: the GI record or another registered fact, with its seal.
- **When a page needs it**: the craft holds a GI record or a registration a reader looks for.
- **In Kutch Ajrakh**: its GI application, proprietor and four-colour rule are the record a buyer
  checks (`ajrakh-market/1`): `kutch-ajrakh/policy/gi-registration-card` (`[class="label-card gi"]`).
- **Made by**: `edit_draft`, filled by hand.
- **Shape**: `{variant, kicker, seal, sentence, inset?, facts [{term, value}]}`.
- **Facts**: the `GI_RECORD` structure item: number, date, proprietor.
- **Place**: `market`, role `FIGURE`, size `COLUMN` or `MARGIN`; never repeat the masthead's date.
- **Check**: every term and value cites the GI record.

## `voice`

- **Shows**: a practitioner's own words, as testimony beside the prose or as the page's coda.
- **When a page needs it**: a source quotes a maker on something the page explains.
- **In Kutch Ajrakh**: a printer's words on iron in the water say in one line what the chemistry
  chapter took pages to show, and they close the story (`ajrakh-people/1`):
  `kutch-ajrakh/society/sufian-khatri-iron-water-voice` (`[aria-labelledby="d7-vk"]`); and
  (`ajrakh-kin/1`) `kutch-ajrakh/society/coda-printer-on-water` (`[aria-label="Coda"]`).
- **Made by**: `edit_draft`, filled by hand.
- **Shape**: `{setting, testimony? {kicker, kickerId, evidence, quote, credit, meta, echo?},
  coda? {label, viewBox, tile, weave, kicker, quote, caption, note}}`.
- **Facts**: the quote verbatim from its source, with who said it as the source states.
- **Place**: `people` for testimony, the end of `kin` for the coda; role `FIGURE`, size `COLUMN`.
- **Check**: the quote is the source's words, credited.

## `drawing`

- **Shows**: one still SVG figure.
- **When a page needs it**: rarely; a composed `diagram` or a `coded_figure` first.
- **In Kutch Ajrakh**: none of this kind.
- **Made by**: `edit_draft`, a declared spec (`components/1`, the design rules for a figure).
- **Shape**: `{head {title, caption?}, svg, alt}`.
- **Facts**: its caption a cited unit.
- **Place**: the chapter of what it shows, role `FIGURE`, size `COLUMN`.
- **Check**: rule 27 passed in all four themes; no map, no hand-painted material.

## `picture_plate`

- **Shows**: a photograph or drawing of the craft with its caption and credit.
- **When a page needs it**: every page: the masthead first, then a chapter opener and plates of the
  work, its materials, its place and its makers.
- **In Kutch Ajrakh**: the whole cloth opens the page, and each chapter shows what its words name:
  `ajrakh-answer/1`, `kutch-ajrakh/design/cloth-field-and-borders-photo`
  (`[class="plate kv-open-photo"]`, the masthead); `ajrakh-cloth/1`,
  `kutch-ajrakh/design/indigo-ground-print-photo`; `ajrakh-made/1`,
  `shared/process/printing-block-carving-photo` (a margin plate); `ajrakh-chemistry/1`,
  `shared/materials/madder-roots-and-dyed-silk-photo` and
  `kutch-ajrakh/materials/natural-dye-materials-photo`; `ajrakh-why-kachchh/1`,
  `shared/geography/great-rann-of-kachchh-photo` (the opener) and
  `shared/geography/banni-grasslands-photo`; `ajrakh-history/1`,
  `shared/history/mohenjo-daro-priest-king-trefoil`; `ajrakh-people/1`,
  `kutch-ajrakh/design/printer-hand-at-border-photo`.
- **Made by**: `give_pictures`: an open-licence picture by its `page_url`, the person's own with
  their declaration; then its `plate` label in the layout.
- **Facts**: the facts it illustrates, its caption written from them.
- **Place**: `HERO` in `opening` for the masthead, `OPENER` with size `BLEED` for a chapter's
  first, `PLATE` with size `MARGIN` or `COLUMN` in the run; a `crop` for each.
- **Check**: each picture once, its credit under it, people and work in frame on a phone.

## `ai_illustration`

- **Shows**: an AI-made illustration of a step or place, always labelled an illustration.
- **When a page needs it**: no photograph shows a moment the story needs.
- **In Kutch Ajrakh**: its media gallery shows moments no photograph caught, each labelled AI
  (`ajrakh-media/1`): `kutch-ajrakh/chemistry/ai-cloth-lifted-from-vat`,
  `kutch-ajrakh/history/ai-caravan-on-salt-flat`, `kutch-ajrakh/design/ai-double-sided-ajrakh-drying`,
  `kutch-ajrakh/geography/ai-dry-riverbed-and-well`, `kutch-ajrakh/economics/ai-stacked-printed-yardage`,
  `kutch-ajrakh/design/ai-block-divided-into-sixteen` and `kutch-ajrakh/process/ai-cloth-steeping-in-saaj`.
- **Made by**: `give_pictures` with origin `AI_GENERATED`, its tool, model and prompt declared by
  the person; the authored page's are its own.
- **Facts**: the facts it shows; never a real person, place or object.
- **Place**: `PLATE` in the chapter it illustrates, size `COLUMN`.
- **Check**: it is captioned as an illustration naming its tool.

## `specimen_plate`

- **Shows**: the authored page's specimen of the cloth, with its label card.
- **When a page needs it**: the authored page's own.
- **In Kutch Ajrakh**: the stars on an indigo ground are the cloth's identity, shown full width
  (`ajrakh-cloth/1`): `kutch-ajrakh/design/indigo-ground-specimen` (`[class="hero"]`).
- **Made by**: the authored page; a contribution gives a picture or designs a `coded_figure`.
- **Facts**: none to propose.
- **Place**: not placed by a contribution.
- **Check**: nothing to check.

## `ai_video`

- **Shows**: a short AI-made film of one moment of the process.
- **When a page needs it**: the authored page's own.
- **In Kutch Ajrakh**: the green-to-blue moment of its first figure, in motion (`ajrakh-media/1`):
  `kutch-ajrakh/chemistry/ai-video-blue-in-the-air` (`#vid`).
- **Made by**: the authored page; no tool delivers a video.
- **Facts**: none to propose.
- **Place**: not placed by a contribution.
- **Check**: nothing to check.

## `comic`

- **Shows**: the signature moment told as panels, an alternative telling.
- **When a page needs it**: the authored page's own.
- **In Kutch Ajrakh**: the indigo dip retold for a younger reader in six panels
  (`ajrakh-reading/1`): `kutch-ajrakh/chemistry/indigo-dip-story-panels` (`[data-role="comic"]`).
- **Made by**: the team for the authored page, every panel generated with Gemini or ChatGPT image
  generation and no other image tool (owner, 2026-11-28); a `coded_figure` may tell a moment in
  steps instead.
- **Facts**: none to propose.
- **Place**: not placed by a contribution.
- **Check**: nothing to check.

## `model_explainer`

- **Shows**: a scripted model of a mechanism at the scale of fibres and molecules.
- **When a page needs it**: the authored page's own; a contribution reaches it with a coded figure.
- **In Kutch Ajrakh**: what happens inside one cotton fibre in the vat and the air cannot be
  photographed, so a model counts it (`ajrakh-chemistry/1`):
  `shared/chemistry/indigo-in-cotton-fibre-explainer` (`[aria-labelledby="mf-t"]`).
- **Made by**: the authored page; for your craft, a `coded_figure`.
- **Facts**: as the coded figure's.
- **Place**: as the coded figure's.
- **Check**: as the coded figure's.

## `answer_block`

- **Shows**: a stored answer block on a generated page: a process ladder, the reactions, a card of
  a field, drawn from the page's facts.
- **When a page needs it**: the site places it where a chapter's facts support one.
- **In Kutch Ajrakh**: none of this kind; its authored chapters hold their own figures.
- **Made by**: the site.
- **Facts**: the page's own facts and structure; more of them make richer blocks.
- **Place**: the site's.
- **Check**: it reads whole; a figure of your own may take its place in the layout.

## `why_here`

- **Shows**: why the craft is where it is: its region's water, soil, climate and trade.
- **When a page needs it**: every craft page with places; the site builds it.
- **In Kutch Ajrakh**: the ground under its villages explains its water and its colours
  (`ajrakh-why-kachchh/1`): `kutch-ajrakh/geography/why-here` (`[class="kv-page kv-why-here"]`).
- **Made by**: the site, from the page's places and environment facts.
- **Facts**: place, water, soil and climate facts of the page.
- **Place**: the site's, in `why`.
- **Check**: every factor names its place.

## `related_crafts`

- **Shows**: the craft's kin crafts, each joined through a sentence that uses a term in one sense.
- **When a page needs it**: the site builds it for every page.
- **In Kutch Ajrakh**: `ajrakh-kin/1`, `kutch-ajrakh/overview/related-crafts` (`[class="kv-related"]`).
- **Made by**: the site.
- **Facts**: shared concepts and family facts.
- **Place**: the site's, in `kin`.
- **Check**: no card without a sentence.

## `concept_atlas`

- **Shows**: the science the craft shares with others, concept by concept.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-kin/1`, `kutch-ajrakh/overview/shared-science-atlas` (`[class="kv-shared"]`).
- **Made by**: the site.
- **Facts**: the page's shared concepts.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `explainer`

- **Shows**: how to read the page's citations.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-reading/1`, `kutch-ajrakh/overview/how-to-read-citations` (`[aria-labelledby="hc-h"]`).
- **Made by**: the site.
- **Facts**: none.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `audio_player`

- **Shows**: the page read aloud.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-reading/1`, `kutch-ajrakh/overview/listen` (`[class="end-block kv-listen-block"]`).
- **Made by**: the site.
- **Facts**: none.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `quiz`

- **Shows**: questions a reader checks themselves with.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-reading/1`, `kutch-ajrakh/overview/check-yourself-quiz` (`#quiz-block`).
- **Made by**: the site.
- **Facts**: none.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `ask_next`

- **Shows**: the questions a reader might ask next.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-reading/1`, `kutch-ajrakh/overview/ask-next` (`[class="asknext"]`).
- **Made by**: the site.
- **Facts**: none.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `citation_tool`

- **Shows**: Cite this monograph.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-reading/1`, `kutch-ajrakh/overview/cite-this-page` (`#kv-cite`).
- **Made by**: the site.
- **Facts**: none.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `language_switch`

- **Shows**: the page in another language.
- **When a page needs it**: the site builds it; translations are `TRANSLATE` tasks.
- **In Kutch Ajrakh**: `ajrakh-reading/1`, `kutch-ajrakh/overview/answer-in-hindi-and-urdu` (`#lang-demo`).
- **Made by**: the site, from translated passages.
- **Facts**: the passages, as a `translation` part.
- **Place**: the site's.
- **Check**: the language reads whole in the preview.

## `reading_level`

- **Shows**: the student version of the page.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-reading/1`, `kutch-ajrakh/chemistry/student-version` (`[class="kv-alt-teen"]`).
- **Made by**: the site.
- **Facts**: none.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `generator`

- **Shows**: the film of the craft being made, generated on request.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-media/1`, `kutch-ajrakh/overview/watch-it-being-made` (`[data-aid="gen"]`).
- **Made by**: the site.
- **Facts**: the page's stages.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `film`

- **Shows**: the page told as a film with its score.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-media/1`, `kutch-ajrakh/overview/answer-as-a-film` (`#film-block`).
- **Made by**: the site.
- **Facts**: none.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `process_replay`

- **Shows**: how the page was made, step by step.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-sources/1`, `kutch-ajrakh/overview/how-this-answer-was-made` (`[class="kv-made-fold"]`).
- **Made by**: the site.
- **Facts**: none.
- **Place**: the site's.
- **Check**: nothing to deliver.

## `source_list`

- **Shows**: the page's sources, numbered, and the kin crafts' apart.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-sources/1`, `kutch-ajrakh/overview/source-list` (`#kv-src-status`)
  and `kutch-ajrakh/overview/kin-craft-sources` (`#kv-src-kin`).
- **Made by**: the site, from the sources your facts cite.
- **Facts**: every fact's sources.
- **Place**: the site's.
- **Check**: borrowed sources are counted apart.

## `credits`

- **Shows**: the picture and data credits.
- **When a page needs it**: the site builds it.
- **In Kutch Ajrakh**: `ajrakh-sources/1`, `kutch-ajrakh/overview/picture-and-data-credits`
  (`[class="wrap credits kv-credits"]`).
- **Made by**: the site, from what the server read of each picture and dataset.
- **Facts**: none.
- **Place**: the site's.
- **Check**: every picture and dataset is credited.

## How this reference is kept true

| Rule | Kept true by |
|---|---|
| An entry for every kind the registry knows, each with its seven lines, so a new kind without one fails | `test_playbook_cookbook.py` in `backend/tests/mcp`, against `models/component_kinds`, `research/component_specs` and `services/compose_components` |
| Every Kutch Ajrakh component named in its kind's entry with its chapter's worked guide | that test again, against Ajrakh's document |
| Every kind the server composes names `compose_component` as a way to make it | that test again, against `COMPOSED_KINDS` |
| Every guide address it names served | that test again |
