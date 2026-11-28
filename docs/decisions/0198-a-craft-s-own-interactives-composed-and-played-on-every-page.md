# 0198. A craft's own interactives are composed by the server from its facts and played on every page as on Kutch Ajrakh's

An agent no longer writes a reaction player's, dip player's, molecule's or what-if lab's spec by
hand or borrows Kutch Ajrakh's: `compose_component` builds it finished from the craft's own curated
page and facts, every unit citing only those, or names what to propose first; a delivered molecule
carries PubChem's 3D model, and the monograph kit plays every dip player and lab, not only
Ajrakh's.

Date: 2026-11-24. Status: accepted (the lead's page-quality round, lane `interactives`, after the
owner judged the Sanganeri Hand Block Printing page: "the reactions are not interactive, there are
no 3d models that I can play around with"). It amends
[decision 0106](0106-one-monograph-template-for-every-page.md) (the kit that drives every page's
players) and uses the room of [decision 0191](0191-room-for-the-page-quality-tools.md) (one tool
more in the pages group). The contracts are `docs/contracts/component-specs-science.md`
(molecule_3d, dip_player, experiment_lab and Composed from a craft's own facts),
`docs/contracts/open-work.md` (MCP) and `docs/contracts/knowledge-api.md` (the tools).

| For | Read |
|---|---|
| One template, its kit and the science specs | [decision 0106](0106-one-monograph-template-for-every-page.md) |
| The tool list's room for the page-quality tools | [decision 0191](0191-room-for-the-page-quality-tools.md) |
| How structure becomes a curated fact of its page | [decision 0108](0108-structure-proposals-become-curated-facts.md) |
| A conformer kept once per CID, a miss asked again after 90 days | [decision 0152](0152-matter-read-once-and-the-science-seed-kept-true.md) |
| The composed players' scenes built from the figure kit | [decision 0200](0200-players-and-cards-drawn-from-the-kit.md) |
| A dip's colours from the substances its stages name, and molecules of twenty elements (amends items 2 and 3) | [decision 0202](0202-a-dip-s-colours-from-its-facts-the-crafts-dyes-and-pigments-and-twenty-atoms.md) |
| A composed reaction player draws each step's species from the kit, and every player plays in view (amends this record) | [decision 0228](0228-players-molecules-and-timelines-that-play-and-a-reaction-s-species-drawn-from-the-kit.md) |
| A molecule composed from a compound the page's facts name, given by its PubChem CID (amends this record) | [decision 0253](0253-a-stage-s-own-scene-a-compound-its-facts-name-and-every-map-layer-s-dataset-record.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **A borrowed player fails its page.** The agent that built Sanganeri linked Kutch Ajrakh's
  alizarin model and indigo dip player; their units cite Ajrakh's facts, so the page's checks
  refuse them, and the lifecycle lane now refuses such a borrowing before it is proposed. The way
  forward it names, a component of that kind on the craft's own facts, had no tool: an agent wrote
  each spec by hand, unit by unit, with its drawings.
- **The server held what a composer needs.** A curated page (`CuratedCraft.page`) holds each
  stage with its colour after and its time, each material with its compound and alternatives and
  each reaction with its stage, as `propose_structure` writes them (decision 0108); `CuratedClaim`
  names the facts the craft owns; `ProcessStage`, `StageMaterial` and `Reaction` give the stage
  names, the materials each stage uses and the balance the server checked; `tokens.json` records a
  depicted colour for each craft's material; and `ConformerCache` keeps PubChem's 3D conformer of a
  compound once in the bucket, as the answers' zoom builder reads it.
- **A generated page drew three of the four kinds as stills.** The kit's molecule viewer reads its
  model from the page's `mol-data`, which only Kutch Ajrakh's content held, so a delivered molecule
  never turned. The kit's dip player animates Ajrakh's own cloth (`.cl-move`), so Bidriware's dip
  player and every other one did nothing when pressed. The kit's lab binding sat inside the loops
  of the region explorer and the time map, so a lab ran only on a page that drew both, and on such
  a page Ajrakh's three toggle handlers threw on any other lab. The reaction player alone was
  driven by its rail and Play on any page.
- **A molecule key was refused.** Delivery holds every `swatch` to a depicted material, so the
  `--atom-*` swatches of a molecule's key, which Ajrakh's figure shows, were refused in a
  delivered one.

## Decision

1. **`compose_component {craft, kind, about?}`** joins the pages group (`api/mcp_compose_tools.py`,
   registered in `api/mcp_tools.py`; the contribute scope, read-only and open-world, an account of
   Researcher or above). `about` names at most one stage, reaction or material key, or a compound's
   CID. It reads the craft through `services/compose_reads.craft_held`: its curated page, the facts
   it owns that readers see as facts and that fit a unit (600 characters), the stage names and
   uses, the balanced reactions' coefficients, the materials' compounds, their recorded colours and
   the colours recorded with each fact (`data/specimen_records.craft_specimens`,
   `stated_specimens`). A craft without a curated page composes nothing.
2. **Each kind from its own structure** (`services/compose_reaction`, `compose_dip`,
   `compose_molecule`, `compose_lab`, with `compose_parts` and `compose_scene`):
   - `reaction_player`: two to twelve reactions stated by the craft's facts, in the order of their
     stages; each step named by its stage, its kicker the reaction's kind, its heading its species,
     its paragraphs its facts, the stage's time as its condition; species in their material's
     depicted colour and PubChem record or drawn as an outline (`clear`); an equation with its
     coefficients only where the server balanced the reaction, otherwise a note that names it as
     the sources do; one scene of swatches, a group a step, resting on the last.
   - `dip_player`: two bath stages or more (scouring, mordanting, dyeing, resist, washing), each
     with its colour after and the depicted colour the team recorded with the fact that states it
     (Ajrakh's indigo stage is `--dye-indigo`, recorded with its fact C087, never the vat's green
     `--dye-leuco` of the same material); the strip of those stages, the colour of each in `dips`,
     resting on the last.
   - `molecule_3d`: up to two compounds of its materials whose facts it owns, one material a
     compound, from PubChem's 3D conformer read through `ConformerCache`; only carbon, hydrogen,
     nitrogen and oxygen, the atoms the design colours; its facts beside the model.
   - `experiment_lab`: a `choice_toggle` for each of two or three materials with a stated
     alternative, each option a material cited by its own facts and its formula with its record,
     then the lab that holds them.
   A label cites no fact; a name holding a number or a formula, or longer than a label, cites the
   facts that state it. Nothing a composer writes cites a fact the craft does not own.
3. **Too little composes nothing.** The reply's `missing` names each fact or structure item to
   propose (`propose_structure REACTION`, `STAGE_AFTER`, `ALTERNATIVE`, a specimen colour or an
   atom colour to ask the team for); `leftOut` names what a composed component went without. The
   reply gives each component as `edit_draft`'s add takes it, in snake_case, so placing it raises no
   notice; nothing is stored until `propose_page`.
4. **A delivered molecule carries its model.** `MoleculeModel.geometry {atoms, bonds, radius}`
   (`research/component_specs_science_geometry`) is optional and, when given, its drawing holds one
   `g.mol-g` with every atom and bond once. `science/molecule_conformer` reads the V2000 SDF:
   PubChem's recorded conformer of alizarin gives exactly Kutch Ajrakh's `mol-data` for CID 6293.
   `science/molecule_drawing` projects it at rest as the kit does: Ajrakh's alizarin at its yaw
   and pitch is the approved drawing, each letter raised to the 12 px floor. A generated page that
   places a delivered molecule carries its `mol-data` (`document_components_data.kit_data`,
   formerly `borrowed_data`, which a borrowed figure still uses).
5. **The kit plays every dip player and lab, and molecules zoom.** In `monograph.js` (the source,
   the served kit and the static page, one text): a dip player without Ajrakh's cloth plays its
   own phases, over the vat's 2,600 ms, its status naming each, a phase a press under either
   reduced-motion switch; every lab is bound whatever else the page draws, a lab that is not
   Ajrakh's by each toggle's options; the molecule viewer zooms from 0.6 to 2.5 times on plus and
   minus, a two-finger pinch and a trackpad's pinch, and refuses a drawing without its group.
   Ajrakh's markup is unchanged and its players behave as before.
6. **A molecule key's atom swatches are accepted** at delivery (`drawing_spec_rules`, the key's
   `swatch` alone); any other swatch is still a depicted material.

## Consequences

- An agent building a page calls `compose_component` for each kind, places what it returns with
  `edit_draft`, previews and reads the preview's pictures before `propose_page`; a craft that holds
  too little is told exactly what to propose. The contributor skill and the craft-pages and
  interactives skills gain the text the lane's report gives, merged by the lead; until it lands,
  `test_the_skill_teaches_every_tool_the_server_offers` names `compose_component` as untaught.
- A composed component is checked at proposal like any delivery; the close-match search may name
  a registered component of the same title, and the way on is a `VARIANT` that keeps the craft's
  own facts.
- Most crafts have no recorded depicted colour, so their dip players wait for the team's specimen
  tokens, and a compound with an atom other than C, H, N or O waits for its atom colour; both are
  named in `missing`.
- The geometry a contributor sends by hand is checked for its shape and its drawing, not against
  PubChem's record; a composed model is PubChem's.
- The kit now binds labs on pages that draw no region explorer or time map; on Ajrakh's page the
  binding order is the same.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/compose/`,
`backend/tests/mcp/test_compose_tool.py`, `backend/tests/science/test_molecule_model.py`,
`backend/tests/research/test_molecule_geometry_spec.py`,
`backend/tests/layouts/test_generated_molecules.py`, `backend/tests/mcp/test_tool_budget.py` and
`frontend/e2e/composed-interactives-unit.spec.ts`.
