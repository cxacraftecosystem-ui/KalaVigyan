# 0177. A difference is named from what the judge already answers, the kind preview is served its themes, and what holds Kutch Ajrakh's authored shell is measured

An answer sentence names what its sources differ on from its claim, the duplicate judge's own
subject and property name a difference it finds and are stored with its outcome, every host draws a
flagged sentence's readings after it, `/design/kinds` reads its fixtures from the API with each
drawing's four themes, Kutch Ajrakh's authored shell is measured and its register entries say what
is left, and the layout preloads only the Latin faces the first screens at 360 draw.

Date: 2026-11-23. Status: accepted (the lead's debt brief of 2026-11-23 evening, monograph shell
lane). It amends [decision 0156](0156-expert-panel-and-field-voices-kept-true.md), item 10 (where a
difference's subject comes from), and [decision 0114](0114-kinds-and-datasets.md) (where the kind
fixtures live), and measures what [decision 0164](0164-every-cited-sentence-a-unit-and-chapter-names-in-the-content.md)
left of the authored shell. The contracts are `docs/contracts/knowledge-writes.md` and
`docs/contracts/component-specs-general.md`.

| For | Read |
|---|---|
| Sources differ after its paragraph, and `differsOn` on the claim | [decision 0156](0156-expert-panel-and-field-voices-kept-true.md) |
| The flag that lasts while a live pair holds it | [decision 0171](0171-imports-keep-approvals-and-differences-settle.md) |
| No added model call or input token while answers are measured | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| One kind per job, and its fixture on another craft | [decision 0114](0114-kinds-and-datasets.md) |
| A drawing in the design's vocabulary, served in four themes | [decision 0131](0131-drawings-in-the-design.md) |
| What decision 0164 left of the authored shell, measured here | [decision 0164](0164-every-cited-sentence-a-unit-and-chapter-names-in-the-content.md) |
| The approved page, served as built | [decision 0100](0100-ajrakh-monograph-served-as-built.md) |
| The gates, the judge and the flag | [knowledge-writes.md](../contracts/knowledge-writes.md) |
| The general kinds and the kind fixtures | [component-specs-general.md](../contracts/component-specs-general.md) |
| The shared template drawing the parts the shell held for every generated page (amends item 5) | [decision 0183](0183-the-shared-template-draws-the-approved-page.md) |
| A difference named only when every differing pair names it (amends item 2) | [decision 0188](0188-an-unscored-answer-any-craft-filing-chapters-apart-and-one-named-difference.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **An answer never named a difference.** `knowledge_view.ClaimView` carried no `differs_on`, so
  `section_blocks.explainer_sentence` read the subject through a named seam that nothing filled and
  every flagged answer sentence summarised as plain "Sources differ"; the craft page's three flagged
  sentences carried no `differsOn` either.
- **A flag the duplicate judge set stored no subject.** `candidate_writes.mark_sources_differ`
  took an `about` that no caller passed, and the review's settling, which raises the flag of a
  waiting fact when it is approved (every live-research write-back on production waits), had no
  subject to give. The judge already answers, for every pair, the `subject` and `property` both
  facts speak of; a DIFFERS verdict requires both.
- **One host drew a flagged sentence without its readings.** The what-if lab's outcomes drew each
  sentence's tag but not `SentencesDiffer`. The reaction step's "What happens and why" already did,
  through `CitedText`.
- **The kind preview drew its drawing late.** `/design/kinds` bundled its fixtures in the web, and
  a delivered spec may not carry `themes`, so its drawing showed a sunk placeholder until the
  browser resolved its roles.
- **The brief asked to retire Kutch Ajrakh's authored shell.** Every remaining component native,
  the React page drawing the masthead and its counts, the table of contents, the margin notes, the
  sources chapter and each chapter's wrappers, then plate crops as focal boxes and the shell's CSS
  isolation removed, all proven by Monograph parity on the branch's preview with the approved page
  unchanged and its classes kept (decision 0100). Measured against the code on 2026-11-23, four
  things stand in the way. A Vercel preview reads the production API's stored document, so no
  change to the document (its `native.json`, its content, its specs) can be seen on a preview
  before its release loads it. Stored versions are never changed, so every edition stored with a
  shell keeps it and `/crafts/<slug>/v<N>` serves it. The shell's own markup outside units and
  components is 1,633 elements and 365 runs of hand-written text in 13 chapters, 320 of them in the
  sources chapter's 44 hand-made entries, whose groups no anchor of the split's form selects once
  (the list's wrapper repeats in the kin crafts' list), which is why `source-list` is only its
  status line. The ground figure's native drawing waits on the map in `components/map`, the place
  builders' area, drawing its neighbours and pins at first paint.
- **The first screen's faces were preloaded by choice.** The layout preloaded six font files
  (359,276 bytes) on every page so that no first screen swaps its type, chosen by hand in round 7;
  nothing checked which faces a first screen draws.

## Decision

1. **`ClaimView.differs_on`** is filled by `cited_view` from `Claim.differsOn` while the claim is
   flagged; `section_blocks` reads `sources_differ` and `differs_on` from the view and the two seam
   names are gone. The craft page golden is regenerated with the documented command: its three
   flagged sentences gain their dossier's `differsOn`, and the paragraph ids, which hash their
   sentences, change with them. Kutch Ajrakh's page draws its stored monograph document, not these
   sentences, so its parity is unchanged.
2. **The judge's own answers name a difference.** `candidate_verdicts.differs_about` makes "The
   indigo vat, number of dips" from a DIFFERS pair's `subject` and `property`, the words its reason
   already opens with; `FactComparison.about` and the duplicate `GateOutcome.about` carry the first
   named pair's, and `CandidateCheck.differsOn` (migration `0095_candidate_check_differs_on`) stores
   it. `mark_sources_differ` reads it from the stored outcome, so its `about` argument is gone, and
   the settling names a raised flag from the outcome of a live pair that holds it, never over a
   subject already stored. A `differsOn` field in the judge's schema, with a prompt line asking for
   it, was the alternative; it adds input tokens to every write-back's judge call inside an answer,
   which decision 0165 forbids while answers are measured.
3. **Every host draws the readings after its sentence.** The what-if lab draws each outcome with
   `SentenceWithReadings`; the reaction step's why keeps `CitedText`; both are tested.
4. **The kind fixtures are the backend's data.** The 24 fixtures move to
   `backend/app/data/kind_fixtures/` (`data/kind_fixture_files`, in the preview's order) and
   `GET /api/design/kind-fixtures` (public) serves them with `drawing_themes.themed_spec` applied, as
   a delivered drawing is served; the page reads them on each request through the data cache. A
   generated file of the themed variants beside the web's fixtures was the alternative; it would be a
   second copy of what the server works out.
5. **The authored shell is measured, not ported.** The register's four shell entries ("Fragments
   are a bridge", "A plate's crop is a class or a focal box", "Kutch Ajrakh's React page draws the
   authored shell", "The authored shell keeps the app's CSS out by name") are rewritten to what the
   measurement leaves and what each waits on. Carrying the template's main markup in the document as
   a tree of elements, drawn by React instead of as a string, was the alternative: it would retire
   the string and every `dangerouslySetInnerHTML` of the shell, but it carries the same 1,633
   hand-made elements and 365 text runs under another name, computes no count, gives the sources'
   groups no spec, keeps every stored edition's shell and still needs the CSS isolation, and the
   preview could not show it before its release. Drawing the six page tools natively inside the
   shell was the other; their views carry React behaviour for generated pages, so in the shell they
   would nest a second kit scope and be driven twice by the kit's script, as decision 0164 found.
6. **The layout preloads the faces the first screens draw, found from their computed styles.** The
   smoke (`e2e/first-screen-fonts.smoke.spec.ts`) opens Kutch Ajrakh, the landing and the sign-in
   page at 360 by 800, reads the computed family, style and weight of every text the first screen
   shows, matches each character to the page's own `@font-face` rule as the browser does (family,
   style, nearest weight, range, the last rule winning) and checks that each face drawn is
   preloaded and that no face is preloaded that none of them draws. Plex Sans italic is drawn by
   none, so it loads when a page draws it (23,096 bytes off every page's first round); the other
   five files are drawn on Kutch Ajrakh's first screen, Newsreader italic by its standfirst. A
   preload per route was the alternative for the italic; it would not help Kutch Ajrakh, whose
   first screen draws it.
7. **The kit stylesheet is not split by chapter.** Its rules are grouped by kit scope, every chapter
   mixes scopes, and a later rule decides over an earlier one, so a split by chapter would reorder
   the cascade the approved page is built from and parity could not stay exact. What the release
   gains is measured by the lead's Lighthouse at 360, which CI does not run; the register's speed
   entry waits on it.

## Consequences

- The register entry "Leftovers of the design-conformance lane" is cleared; the four shell entries
  are rewritten to what is left (item 5).
- Kutch Ajrakh's page draws as before; only Plex Sans italic waits until a page draws it. Its
  reader data names the GI journal's author whole, as the seed does since decision 0178
  (`content.json`, the rebuilt approved page's data block and the golden document), which the
  production document takes at the release's `load_monograph`. The native smoke hides sticky and
  fixed bars in its component captures, so a bar's place no longer fails it.
- The speed entry is rewritten to the Lighthouse measurement it waits on.
- After the deploy, the migration adds the column; outcomes stored before it name no subject, so a
  flag they raise keeps the plain summary until its pair is judged again.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/answering/test_grounded_blocks.py`, `backend/tests/knowledge_writes/test_structural_verdicts.py`,
`backend/tests/knowledge_writes/test_candidate_gates.py`, `backend/tests/db/test_sources_differ_db.py`,
`backend/tests/research/test_kind_fixtures.py`, `frontend/e2e/what-if-unit.spec.ts`,
`frontend/e2e/matter-cited-values-unit.spec.ts`, `frontend/e2e/kind-fixtures-unit.spec.ts`,
`frontend/e2e/first-screen-fonts-unit.spec.ts` and `frontend/e2e/first-screen-fonts.smoke.spec.ts`.
