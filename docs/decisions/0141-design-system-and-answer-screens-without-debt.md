# 0141. The design system holds no migration alias, and the answer screens number their figures, read every caption from the server and keep only what is stored

The Tailwind config is the token generator's output with no alias left, the design guard counts
the shadcn colour names, the answer essay numbers its figures after the signature figure, every
map prints the Survey of India caption the server serves, a finished answer says whether it has a
quiz, a lesson's sections reorder with the one Up and Down control, and a failed map chunk offers
Try again.

Date: 2026-11-22. Status: accepted (the lead's debt brief of 2026-11-22, design and answer UI
lane). It closes the migration of [decision 0092](0092-design-system.md), point 6 (the retired
ramps aliased in `frontend/tailwind.migration.ts`), and amends [decision 0131](0131-drawings-in-the-design.md)
(the themed picture's ETag) and [decision 0069](0069-learning-screens.md) (Check yourself, the
lesson builder). The contracts are `docs/contracts/region.md` (Map layers),
`docs/contracts/explainer.md` (the stream's `done`) and `docs/contracts/backend.md`.

| For | Read |
|---|---|
| The design system whose migration it closes | [decision 0092](0092-design-system.md), and the skill `kalavigyan-design`, sections 11 and 13 |
| The themed drawings and pictures | [decision 0131](0131-drawings-in-the-design.md) |
| The learning screens | [decision 0069](0069-learning-screens.md) |
| The boundary caption's one home on the server | [decision 0042](0042-phase-b-contract.md) |
| What amended it | [0156 The expert panel takes a failing view again, differs across linked concepts and reuses only the seats it seats, and field voices reach the craft page, their pictures and every run](0156-expert-panel-and-field-voices-kept-true.md): the Sources differ readings after their paragraph, naming what the sources differ on |
| Every decision, by group | [README.md](README.md) |

## Context

Seventeen entries of `docs/TECH_DEBT.md` were the web app's design-system and answer-screen debt.
Only one component (`craft/RegionPlaceCard`, of which only two parts were still drawn) and the
sandbox frame still used an alias class; the shadcn colour names in the config had no user; the
retired guide motions had three. The answer essay drew "Fig. 1" on its signature figure and no
number on the figures after it. Maps of states and places printed a client copy of the Survey of
India line while district maps printed the server's. A finished explainer always asked for its
quiz; a follow-up's section that found nothing showed until a reload; a lesson kept the
explainer's order. Each choice below had a real alternative.

## Decision

1. **The config is generated, alias-free, in both places.** `tools/design/tailwind.py` writes the
   config without the `legacy…` objects, `bold`, `display`, `shadow-sm`, `ease-spring`, the `-100`
   and `-600` status steps and the shadcn names, and `tools/design_tokens.py` writes it to
   `frontend/tailwind.config.ts` as well as to the skill's reference, so `--check` holds the app to
   it. `frontend/tailwind.migration.ts` is deleted. `white` stays (#FFF in every theme) for the
   sandboxed HTML canvas. The two drawn parts of `RegionPlaceCard` moved to `map/PlaceFacts` on
   the token classes, and the card itself, unused, is gone.
2. **The guard counts the shadcn names as aliases.** Physical keys in inline `style` objects stay
   with review (the skill, section 11): every one in the app is a run-time coordinate from a chart
   axis or `getBoundingClientRect`, which is physical by nature, so counting them would only fill
   the baseline.
3. **The evidence badge is an `EvidenceTag` with a label.** `citationCluster.levelMark` and
   `signalMark` give a level's or a signal's state and words; `components/answer/EvidenceBadge` is
   deleted. `SourceDialog` stays only while the voice call screen wires it (the voice lane's file).
4. **Figures are numbered by a CSS counter scoped to the essay.** `article.kv-essay` resets
   `kv-figure` (to 1 when the lede has a signature figure, which is Fig. 1), and each
   `AnswerFigure` inside the sections (`NumberedFigures`) increments it and prints "Fig. N" before
   its kicker. Numbering in script would need every renderer to declare its figures in advance (a
   climate block draws one figure per series and per group) and would renumber as lazy map chunks
   arrive; the counter follows the document as drawn. `editorialText.numberFigures` had no caller
   and is deleted.
5. **Leucoindigo is seeded with its PubChem CID** (23035, C16H12N2O2, the record the Kutch Ajrakh
   monograph checked on 18 November 2026). The seed writes a CID through `COALESCE`, so a CID the
   lookup linked is never cleared by a later seed, and `link_compounds` now fills the record (its
   source, InChIKey, weight) of any compound whose CID is known but has no source, when PubChem
   holds the same composition.
6. **`done` carries `quizAvailable`.** The stream route wraps its emit
   (`services/answer_quiz.with_quiz_offer`) and asks the same service the quiz route uses; the flag
   is left out when it cannot be read, and the client then asks as before. It is not stored on the
   explainer: hidden marks and withdrawn field voices change what a quiz may ask, so a stored flag
   would go stale; a reopened explainer still asks once.
7. **A follow-up's empty added section leaves when its version arrives.** The client marks a
   section the follow-up added and drops it at `version` when it has no block, which is exactly what
   the stored version keeps; reloading the version would cost a request for the same result.
8. **One Up and Down control.** `lib/listOrder` (`moveItem`, `usableAfterMove`, `movedText`,
   `inListedOrder`), `ui/MoveButtons` and `hooks/useMoveFocus` serve the AI routing page and the
   lesson builder; focus follows the moved row to the button still usable.
9. **The server serves both captions.** `GET /map/layers` adds `outlineCaption` (the Survey of
   India line alone, `research/datasets.INDIA_OUTLINE_CAPTION`) beside `boundary.caption` (with
   "District boundaries are indicative."); maps of states or places print the outline, district
   maps the boundary caption, and the landing and the supply pins read the list. The web app holds
   no copy: while the list loads, a map prints its credits without a caption rather than one of its
   own making.
10. **Crowded concept rings are separated by measurement.** After paint the figure measures each
    label and pushes overlapping ones apart vertically, the hub fixed and every label inside the
    frame (`conceptGraph.separatedLabels`). The researchers' whole view is the monograph's Shared
    science chapter (the concept atlas the board draws), so no force layout is added.
11. **A failed chunk is retried, not hidden.** Each lazy block sits in its own `BlockBoundary`;
    Try again re-creates the lazy component through `retryableLazy`, and a stale instance's retry
    reuses the fresh one.
12. **Small calls.** Tilt rotates a quarter about x and Zoom in and Zoom out scale by 1.25, through
    the viewer adapter, unbounded as the pointer is. `brotli` joins the backend's development
    group, where the tools run. A themed SVG's ETag is the hash of the file, the theme and the token
    set (`drawing_themes.picture_version`). Captures add high contrast, light and dark, at 360, as
    the acceptance asks. The retired guide motions are gone: anchors scroll through
    `motion/scrollToAnchor`, a film scene settles with `motion-enter`, and the dictation bars are
    the named CSS motion `motion-sound`.

## Consequences

- An old alias or retired class compiles to nothing; the guard still blocks every one, and the
  baseline holds only the sandbox frame's `bg-white` and the two theme-colour hex values of
  `lib/preferences.ts`.
- `frontend/tailwind.config.ts` is generated: change `tools/design/tailwind.py` and regenerate.
- Figure numbers are drawn by CSS, so they are read by screen readers that read generated content
  and are not part of copied text.
- The leucoindigo record reaches production with the next deploy's seed and the next coverage
  enrichment run (`link_compounds`); the vat figure's equation and atom count draw from then.
- `MapLayerList` has a new required field; the golden `region.layers.golden.json` carries it.
- What is left of the design-conformance leftovers (Sources differ drawn after the paragraph, the
  kind fixture's variants) and the voice screen's source dialog stay in the debt register with what
  they wait on.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `frontend/e2e/design-guard-unit.spec.ts`,
`design-tokens-unit.spec.ts`, `answer-essay-view-unit.spec.ts`, `map-attribution-unit.spec.ts`,
`place-renderers-unit.spec.ts`, `learning-screens-unit.spec.ts`, `lesson-map-screens-unit.spec.ts`,
`learning-renderers-unit.spec.ts`, `lazy-block-unit.spec.ts`, `matter-renderers-unit.spec.ts` and
`capture/capture-parts-unit.spec.ts`, `tools/tests/test_design_tokens.py`,
`tools/tests/test_wordmark.py`, `backend/tests/learning/test_answer_quiz.py`,
`backend/tests/science/test_science_seed.py`, `backend/tests/db/test_compound_lookup_db.py` and
`backend/tests/public/test_contributed_picture_route.py`.
