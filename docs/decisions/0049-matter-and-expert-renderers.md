# 0049. Matter and expert renderers

Reactions play their steps without inventing motion data, material cards show only stored values,
and 3D molecules come from 3Dmol.js behind one adapter with the CSP unchanged. The expert views of a
section form one panel, and one numbering covers the new kinds.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0042 Phase B contract: place, matter and the expert panel](0042-phase-b-contract.md) |
| The review that fixed it | [0050 Phase B review fixes](0050-phase-b-review-fixes.md) |
| What amended part of it | [0152](0152-matter-read-once-and-the-science-seed-kept-true.md): The listeners 3Dmol.js adds removed at dispose, and the renderers checked in the dark and by touch |
| Every decision, by group | [README.md](README.md) |

## Context

Phase B of `docs/plans/answer-experience.md` ("Place and matter", owner-approved, section 8
final) asks for reactions that play out, material cards, 3D molecules and an expert panel whose
disagreements show as "Experts differ" with both citations. Decision 0042 fixed the four kinds'
fields and the empty renderer registry; decision 0045 built the matter builders and the conformer
route (`GET /api/molecules/{pubchemCid}/conformer`); lane 0046 builds the expert views. This lane
draws the four kinds and edits no backend file. The boards are `Chemistry`, `Explainer` and
`Learn` of the design project. Rules that bind: every fact the reader sees is cited, numbers and
formulas come from stored rows, reduced motion shows every step, nothing widens a 390 px phone
page (finding 8a.3), and `/ask` stays light.

## Decision

1. **Registered through two modules.** `components/answer/matter/matterRenderers.tsx`
   (`reaction_player`, `material_card`, `molecule_3d`) and
   `components/answer/experts/expertRenderers.tsx` (`expert_view`) are spread into
   `BLOCK_RENDERERS`. `renderBlock`, `hasRenderer` and `ExplainerBlockView` take any typed kind
   (`explainerView.TypedBlock`), so a not-yet-built kind can be drawn by a test or a panel without
   casts.
2. **The reaction player plays steps, it never invents motion data.** The board's moving ions
   would need positions no source states, so the player shows what the block holds: a cast of
   every species of the player once (formula, or name when there is none), the open step's
   reactants and products lit by role (colour, a dot or diamond mark, a legend and the role in
   words for screen readers), and the steps as an ordered list whose open step shows its kind,
   balance and level badges, the balanced equation through the existing `ChemEquation` (spoken
   as words) or, without every formula, the species row of the Process tab, its species names
   and its citation chips. Play advances one step every `STEP_SECONDS` (4) and stops on the last;
   Replay starts again; Previous, Next and a tapped step pause. Under either reduced-motion
   switch, and for a one-step player, there is no playback: every step is open at once. The rules
   are pure (`lib/reactionPlayer.ts`: `playbackStep`, `reactionCast`, `stepRoles`,
   `stepSignal`); `SpeciesRow` moved from the Process tab's `ReactionCard` to
   `components/answer/SpeciesRow.tsx` so both draw it, and the Process tab's species helpers
   take any reaction-shaped value.
3. **Material cards show only stored values.** Name, local names (once each, from the glossary),
   role and kind (`processView.materialRoleText`, now shared with the Process tab's materials),
   the formula through `ChemEquation` with a PubChem link only when the card has a CID, a Wikidata
   link only with its id, the cited facts, and the cited handling sentences under a Handling
   badge. Version 1 has no origin field, so a material's origin shows only when a cited fact
   states it; origins with places are the supply map's.
4. **3D molecules come from 3Dmol.js behind one adapter.** `3dmol` 2.5.5 (BSD-3-Clause, published
   2026-05-22) is installed from npm and pinned exactly. `lib/moleculeViewer.ts` is the only
   module that names it, with a type-only import and one `import("3dmol")`, so the library reaches
   the browser only when a molecule nears the viewport (`useInView`, 200 px early).
   `lib/conformer.ts` fetches the backend route and checks the SDF as the PubChem adapter does
   (that CID's first line, a 3D molfile, V2000 or V3000, ending `$$$$`, ASCII, at most 256 KiB).
   Without WebGL (probed on a throwaway canvas before the import), with a 404 or with an SDF off
   the contract the block draws nothing; any other failure offers Try again. The model is
   ball-and-stick on a transparent canvas, turns once when it appears unless motion is reduced,
   and has Turn (90 degrees) and Explore. A transparent cover over the canvas keeps page scrolling
   and wheel events for the page until Explore is pressed, because 3Dmol.js cancels touch and
   wheel events on its canvas. The caption names the compound, its formula and CID and cites its
   `COMPOUND_RECORD` source with a numbered chip linking to the record.
5. **The CSP holds unchanged.** The conformer is fetched through the app's own API proxy, the
   viewer draws on a canvas, and no surface worker is started, so no source is added. 3Dmol.js
   contains one `eval`, reached only when a caller passes a callback as a string; the adapter never
   does, so a future `script-src` without `'unsafe-eval'` still holds.
6. **Expert views of a section form one panel.** `lib/expertPanel.sectionRuns` gathers a section's
   `expert_view` blocks where the first one stands, so a pair is never split by another block;
   `ExplainerSectionView` draws the group as `ExpertPanel`: the
   seat cards (label, the cited take, "Agrees with ...") two to a row from `md`, each still drawn
   through the registry, then one "Experts differ" card per pair that both seats state
   (`expertsDiffer`), the two seats' sentences side by side with their own citation chips. A
   difference only one seat states draws no card.
7. **One numbering covers the new kinds.** `blockCitations` reads the reaction steps' citations,
   `blockSentences` the card's facts and handling and the view's take and differences (the
   server's `SENTENCES` order), and `explainerSourceNumbers` numbers a molecule's record source
   too (`blockSourceIds`), so its chip and the Sources list agree.
8. **Not built yet.** `BUILT_BLOCK_KINDS` is unchanged on both sides: decision 0042 point 11 adds a
   kind on both sides in one change, and this lane edits no backend file (decision 0050 added
   the three matter kinds). The matter builders
   (0045) and this lane's renderers complete `reaction_player`, `material_card` and
   `molecule_3d`; `expert_view` waits for lane 0046's builder.

## Consequences

- Nothing a reader sees changes until the kinds join `BUILT_BLOCK_KINDS`.
- `e2e/matter-renderers-unit.spec.ts` and `e2e/expert-panel-unit.spec.ts` parse the phase B
  fixture blocks and check playback, the cast, reduced motion, the card, the conformer check
  against the backend's recorded SDF and route, the molecule's caption and failures, the numbering,
  the 3Dmol.js boundary and the CSP, the panel and its pairs, and the shrinkable columns. Shared
  spec helpers moved to `e2e/explainerRender.ts`, `e2e/moduleGraph.ts` and `e2e/phaseBFixture.ts`.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
