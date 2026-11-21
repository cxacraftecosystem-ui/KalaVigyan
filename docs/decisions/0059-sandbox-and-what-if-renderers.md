# 0059. Sandbox and what-if renderers

Generated explainers render in a sandboxed frame whose document puts the policy first, sized by a
height message the page bounds, and the site policy names the one frame source the app needs. A
hidden explainer is hidden for readers and collapsed for Professors, and the what-if lab chooses one
option at a time.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0054 Phase C contract: generated explainers, the what-if lab, zoom, timelines and film mode](0054-phase-c-contract.md) |
| The review that fixed it | [0061 Phase C review fixes](0061-phase-c-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase C of `docs/plans/answer-experience.md` ("Play", owner-approved, section 8 final) asks for
sandboxed generated explainers and a what-if lab. Decision 0054 fixed the `simulation` and
`what_if` fields, the static check, the frame and the hide route; lanes 0055 and 0056 build the
builders and the route. This lane draws the two kinds through the renderer registry and edits no
backend file. The boards are `Simulation`, `Explainer` and `Learn` of the design project. Rules
that bind: every value the reader sees is cited, the frame cannot read the page, the account or
the network, nothing widens a 390 px phone page, reduced motion has a static end state, and no
how-it-works copy reaches a screen.

## Decision

1. **Registered through one module.** `components/answer/play/playRenderers.tsx` (`simulation`,
   `what_if`) is spread into `BLOCK_RENDERERS`. `BUILT_BLOCK_KINDS` is unchanged on both sides:
   decision 0042 point 11 adds a kind on both sides in one change, and the builders (0055, 0056)
   are not in this lane, so the review (0061) joins the two kinds. The phase C spec no longer
   asserts that no phase C kind has a renderer; the parser and the stream still refuse them.
2. **The frame document puts the policy first.** `lib/sandboxFrame.sandboxDocument` writes
   `<!doctype html><html lang="en"><head>`, then the policy meta (`SANDBOX_CSP`), then `charset`,
   `viewport`, the `kv-data` element (`JSON.stringify` of `{key: value}` in values order, keys
   checked once each and numbers finite) and the sizing script, then `<body>{HTML}</body>`.
   Decision 0054 point 6 already asked for the policy as the first head element; the contract's
   template listed `charset` first and now follows the decision, because a policy meta governs only
   what is parsed after it, and a `srcdoc` document is always UTF-8.
3. **Sized to its content by a message the page bounds.** The frame cannot be measured from
   outside (no same origin), and generated code may not call `postMessage` or name `parent`
   (the static check's `API` rule). So the client adds one fixed script of its own,
   `FRAME_SIZER`: a `ResizeObserver` on the document element that posts
   `{kvFrameHeight: <px>}` to the parent. `SandboxFrame` listens from a layout effect, takes a
   message only when its `source` is that frame's own window and its data is exactly that one
   finite number (`ownFrameHeight`), and clamps it to 120 to 1,200 px (360 px until the first
   message). Anything else is ignored: the most a frame can do is choose its own height within
   the bounds, and the frame can still not read or script the page.
4. **The site policy names the one frame source the app needs.** `next.config.ts` adds
   `frame-src https://accounts.google.com/gsi/` (`FRAME_SOURCES`), not decision 0054's
   `frame-src 'none'`: Google's sign-in button is an iframe from that path (and the same path is
   already in `connect-src`), so `'none'` would break Google sign-in on the sign-in, sign-up and
   confirm-it's-you screens. A frame that navigates itself to any other URL loads nothing.
   `e2e/sandbox-frame-unit.spec.ts` proves it in Chromium under the site's real header: the
   fixture's explainer draws and runs on its data, a probe frame cannot read the page, its
   storage or the network, and a probe that navigates to another site sends no request; without
   `frame-src` the same run sends that request.
5. **What the reader sees of a generated explainer.** "Generated explainer · model · date"
   (`lib/simulationView.generatedCaption`), the title, the frame (`title` the block's title, no
   `allow` or other granting attribute), "Built from": each value's label, its value with unit
   (exact, never rounded), and either the quoted words that state it with their citation chips or
   its dataset row's credit (`DatasetCredit`). A value that rests on neither, or on both, or a
   repeated key, means the block is not drawn (`valueBases`), failing closed. View code shows the
   fragment as text in a `pre` (React escapes it; it is never parsed as markup); Close code hides
   it.
6. **Hidden for readers, collapsed for Professors.** `canHideGenerated` (Professor and above,
   mirroring `HIDE_GENERATED`) offers Hide explainer once the answer is done
   (`AnswerIdProvider` in `ExplainerView` gives the answer id only then).
   `setSimulationHidden` sends `PUT /api/answers/{answerId}/simulations/{blockId}/hidden` with
   `{hidden}` and refuses an answer about another answer, block or state. A hidden simulation is
   not drawn for anyone else; for Professors it is a dashed card with Show again (no frame, no
   code). A failed call says "Couldn't save. Try again." and changes nothing.
7. **The what-if lab chooses one option at a time.** "What if" over the changed input, the
   options as pressed-state buttons with their count of cited outcomes (one column on a phone,
   two from `sm`, three from `lg`), the first chosen, and the chosen option's outcomes as cited
   sentences in a polite live region. An option with no outcome reads "Unknown" on its button and
   in the panel, with no sentence and no citation. Changing the option swaps the panel with the
   shared `swapVariants`; under either reduced-motion switch the swap is instant and the content
   identical (`data-motion` says which).
8. **One numbering covers both kinds.** `blockCitations` reads a simulation's values' citations
   (the server's `citations()` order) and `blockSentences` a what-if's outcome sentences (its
   `SENTENCES`), so their chips and the Sources list agree; a simulation has no sentences, so
   Listen, translation and term marking skip it as the contract says.

## Consequences

- Nothing a reader sees changes until the two kinds join `BUILT_BLOCK_KINDS` (0061).
- `e2e/generated-explainer-unit.spec.ts`, `e2e/what-if-unit.spec.ts` and
  `e2e/sandbox-frame-unit.spec.ts` parse the phase C fixture and check the frame document, the
  exact sandbox and policy, the bounded height, View code as text only, the caption and values,
  hiding and the route, the options and Unknown, reduced motion, the numbering and the shrinkable
  columns; `e2e/playFixture.ts` loads the fixture.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
