# 0228. Players, molecules and timelines play on their own once in view, a reaction's species are drawn from the kit, and nothing in a player scrolls

A reaction player, a dip player, a stage player, a 3D molecule and a dated record start playing
when they come into view, loop, and stop at one visible Pause; a step, stage or point pressed is
shown at once and playing goes on from it. Under either reduced-motion switch nothing moves and
every step rests on its end state. The composer draws each reaction step from its own species as
kit parts that move: the reactants before, a reagent arriving, a bond breaking, the product after.
A lane's names, formulas and states wrap inside the lane, and no part of a player shows a scroll
bar.

Date: 2026-11-26. Status: accepted (the lead's UX round of 2026-11-26, lane `players`, after the
owner judged the Sanganeri Hand Block Printing page: "the chemical compounds and the reactions
should be animated at all times"; of the dated record, "that slider should not be there. It should
play ... if they click on a certain location on the timeline, they might be able to jump to that
location. But it should be a play pause button"; and, through the lead, "a molecule model turns
slowly on its own once in view"). It amends
[decision 0092](0092-design-system.md) (motion only when the reader asks: the owner's instruction
overrides it for these five figures),
[decision 0198](0198-a-craft-s-own-interactives-composed-and-played-on-every-page.md) (a composed
reaction player's scene),
[decision 0199](0199-a-kit-of-figure-parts-and-hand-drawn-art-held-to-the-bar.md) (the kit gains a
tenth part and a fourth motion),
[decision 0200](0200-players-and-cards-drawn-from-the-kit.md) (a composed reaction step drew its
stage) and
[decision 0220](0220-a-declared-timeline-map-complete-at-rest-from-a-still-the-server-cuts-to-its-frame.md)
(the declared timeline map's slider). The contracts are `docs/contracts/component-specs-general.md`
(The figure kit, Kit scenes, `timeline`) and `docs/contracts/component-specs-science.md` (the
players, `molecule_3d`, Composed from a craft's own facts).

Amended by [decision 0252](0252-field-photographs-and-reaction-scenes-drawn-in-a-preview-and-on-the-page.md): a species is drawn in its material or by the mark of a colourless substance, and one with neither is named by rule 27 and refused by the drawing checks.

| For | Read |
|---|---|
| The design system's motion rules and the two reduced-motion switches | [decision 0092](0092-design-system.md) and the kalavigyan-design skill, section 6 |
| The composer and the kit playing every page's players | [decision 0198](0198-a-craft-s-own-interactives-composed-and-played-on-every-page.md) |
| The kit's parts and motions | [decision 0199](0199-a-kit-of-figure-parts-and-hand-drawn-art-held-to-the-bar.md) |
| The players drawn from the kit | [decision 0200](0200-players-and-cards-drawn-from-the-kit.md) |
| The declared timeline map at rest | [decision 0220](0220-a-declared-timeline-map-complete-at-rest-from-a-still-the-server-cuts-to-its-frame.md) |
| An answer's figures play like a page's, on the site and over MCP, and its timeline map has no slider (amends this record) | [decision 0238](0238-an-answer-s-figures-play-like-a-page-s-on-the-site-and-over-mcp.md) |
| A stage carries its own scene, and a stage without one keeps the nearest earlier stage's (amends this record) | [decision 0253](0253-a-stage-s-own-scene-a-compound-its-facts-name-and-every-map-layer-s-dataset-record.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **Nothing moved unless pressed.** The kit played a reaction player only from its Play, once
  through, stopping on the last step; a dip player only on Dip again; Kutch Ajrakh's stage player
  only on Play, and a stage player that was not Ajrakh's not at all (its Play did nothing). The
  molecule turned only on Turn. The design system and the interactives skill said Play is the
  reader's choice, never autoplay, never a loop.
- **A composed reaction scene was rectangles.** `compose_scene.reaction_scene` drew one line-work
  swatch per species, a group a step, painting no material, and a step drew a kit scene only of
  its stage when the kit drew every stage, which Sanganeri's did not. No part of the kit drew a
  species, an arriving reagent or a breaking bond, so an agent over MCP reported "compounds at
  every stage, bond breaking and where the oxygen comes in" as not possible.
- **A lane overflowed.** A lane's formula was set `white-space: nowrap`, its species card and change
  label had fixed widths, so a long name, formula or state ran past the lane at 320 px; the stage
  ribbon scrolled sideways with a visible scroll bar on a phone.
- **The dated record had a slider.** The declared timeline map stepped by a range input, and the
  plain `timeline` drew its events as marks on an axis nobody could press.

## Decision

1. **The players play in view** (the kit, `monograph.js`: its source part, the served script and
   Kutch Ajrakh's static page, one text). `KV.seen` watches the middle three fifths of the
   viewport. A reaction player in view plays from its first step, a step every 3.6 s (3.8 s for a
   drawn scene), back to the first after the last; a dip player plays its dips in turn, every phase
   of each, 1.2 s between dips; a stage player plays its stages, 1.6 s after each stage's motion,
   Ajrakh's living cloth and any other stage player alike (`stageDriver`; one that is not Ajrakh's
   shows each stage's label card, ribbon and list, swaps in a stage's own kit scene where it holds
   one and lays the stage's swatch in a band that dips in, `genericStages`). Out of view a player
   pauses and goes on from where it was when it comes back.
2. **One control.** The player's own button is Pause while it plays and Play when it does not
   (`aria-pressed`); a dip player's Dip again is that button while motion is allowed. Pause holds
   the player on the state it shows; Play goes on from it. A step, stage or point pressed is shown
   at once with its motion, and a playing player plays on from it; a paused one stays paused.
   While it plays the status is `aria-live="off"`, so a screen reader is not read every step; on a
   press it is `polite` again.
3. **Reduced motion is unchanged.** Under either switch nothing plays or moves: the player rests on
   its `current` step with every end state drawn, Play (or Dip again, or Turn) shows the next state
   at once and announces it, and nothing loops. A switch turned on while a player plays stops it
   (`KV.onMotion`).
4. **A player holds its height.** The kit reserves each player's text, lane and scene box at the
   height of its tallest step (`KV.steady`, every box of a player measured in one pass once the
   player is within 300 px below the viewport, so a page's load does no more work), the
   status line three lines, and a dip key and a stage label card the height they have reached
   (`KV.ratchet`), so a player that plays on its own moves nothing around it.
5. **A molecule turns slowly** (15 degrees a second) once in view, holds still under the pointer,
   while anything in it has focus, while it is dragged and when its Turn button, which reads Pause
   while it turns, is pressed; under either switch it rests at its angle and Turn turns it a
   quarter at once, as before.
6. **The kit draws a reaction's species.** `research/art_kit.py` gains a tenth part, `species`
   (`role`: reactant, reagent or product; `material?`, a depicted token; `breaks`, only a
   reactant's; a cited `label`), serving every family, and a fourth motion, `react`, which needs a
   product and a species it is made from. A kit scene or diagram panel holds one to three parts, or
   up to eight when every part is a species (`SPECIES_PER_SCENE_MAX`). The web draws a species as a
   bead in its material with the speckle texture and an ink edge, an outline dashed in ink when no
   colour is recorded, a crack across a breaking bead and a small arrow into an arriving one; a
   scene of species stands its reactants and reagents before an arrow and its products after it
   (`SpeciesScene.tsx`, `export_still_kit_species.py` for the page's stills). The `react` motion
   (`artkit.css`, on the vat's 2,600 ms) brings the reactants in, the reagent down into place, the
   arrow, the crack and then the product, on every species layer at once, and the step's lane plays
   the same order; the end state of every layer is its rest.
7. **The composer draws each step's species.** `compose_scene.species_scene` composes a reaction
   step's scene from its own reactants and products: a species takes its material's recorded
   colour and nothing else; oxygen (`O2`, or a name saying oxygen) arrives where it is one of
   several reactants, otherwise a mordant (its material's role, or a name saying alum, aluminium,
   iron, ferrous, ferric or mordant) arrives where it is not the only kind; a bond breaks in a
   reactant only in a hydrolysis, a dehydration or a dehydroxylation (the first reactant that is
   not water) or where one reactant gives two products or more. Every label cites the reaction's
   facts. A player draws every step this way when each reaction has at most eight species and
   otherwise keeps its one line-work scene (`reaction_scene`). A scene a contributor wrote keeps
   drawing as before.
8. **Nothing in a player scrolls.** A lane's name, formula, state and change label wrap anywhere
   inside it, its cards and arrow never take more than the lane's width, an equation's term in a
   reaction or dip player wraps before it runs past its box, and the stage ribbon scrolls without a
   scroll bar, the stage shown kept in view.
9. **Timelines play.** The plain `timeline` and the declared timeline map draw no slider: a
   Play/Pause button steps through the events in order (the map's places light in step), playing
   on its own in view and resting on the last event under either switch; each event's point on the
   axis is a button that jumps there (`TimelineTrack`, points kept apart and in the axis by
   `spreadPositions`); the points are in tab order and Space on a point toggles play
   (`useTimelinePlay`, the reducer `lib/timelinePlay.played`). An answer's timeline map keeps its
   slider (`TimelineMapFrame` takes a `control`).

## Consequences

- Kutch Ajrakh's four reaction players, its dip player, its living cloth and its molecule now play
  on its page too; its markup is unchanged, its players taller by their tallest step.
- The release controls spec reads each player playing on its own, a pressed step, Pause and a held
  state on a page whose kit plays in view (`KV.seen`), and the earlier kit's press-driven players by
  their earlier checks (`e2e/release/earlierPlayers.ts`), since its post-deploy run reads
  production before this change is deployed; that file goes once production serves this kit.
- The parity runs (the native smoke and `monograph-parity`) compare pages at rest, so they draw
  them with motion reduced.
- A page whose players play in view still rests finished at first paint and in the preview, which
  draws with motion reduced; page checklist rule 10 says a player plays on its own and any other
  replay is opt-in.
- The interactives skill's "Play is the reader's choice, never autoplay, never a loop" is replaced
  by these rules in its three copies.
- Ajrakh's timeline map in its shell already had Play and pressable moments; an answer's timeline
  map keeps its slider until the answers' lane takes the same control.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-26; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`frontend/e2e/players-play-unit.spec.ts`, `frontend/e2e/kit-players-unit.spec.ts`,
`frontend/e2e/composed-interactives-unit.spec.ts`, `frontend/e2e/art-kit-unit.spec.ts`,
`frontend/e2e/monograph-kinds-general-unit.spec.ts`, `backend/tests/research/test_art_kit.py`,
`backend/tests/research/test_kit_species.py`, `backend/tests/research/test_kit_style_rules.py`,
`backend/tests/compose/test_compose_scene.py`, `backend/tests/compose/test_compose_reaction.py`
and `backend/tests/exports/test_export_species.py`.
