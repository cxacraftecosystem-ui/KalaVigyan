# 0177. A difference is named from what the judge already answers, the kind preview is served its themes, and what holds Kutch Ajrakh's authored shell is measured

An answer sentence names what its sources differ on from its claim, the duplicate judge's own
subject and property name a difference it finds and are stored with its outcome, every host draws a
flagged sentence's readings after it, and `/design/kinds` reads its fixtures from the API with each
drawing's four themes.

Date: 2026-11-23. Status: accepted (the lead's debt brief of 2026-11-23 evening, monograph shell
lane). It amends [decision 0156](0156-expert-panel-and-field-voices-kept-true.md), item 10 (where a
difference's subject comes from), and [decision 0114](0114-kinds-and-datasets.md) (where the kind
fixtures live). The contracts are `docs/contracts/knowledge-writes.md` and
`docs/contracts/component-specs-general.md`.

| For | Read |
|---|---|
| Sources differ after its paragraph, and `differsOn` on the claim | [decision 0156](0156-expert-panel-and-field-voices-kept-true.md) |
| The flag that lasts while a live pair holds it | [decision 0171](0171-imports-keep-approvals-and-differences-settle.md) |
| No added model call or input token while answers are measured | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| One kind per job, and its fixture on another craft | [decision 0114](0114-kinds-and-datasets.md) |
| A drawing in the design's vocabulary, served in four themes | [decision 0131](0131-drawings-in-the-design.md) |
| The gates, the judge and the flag | [knowledge-writes.md](../contracts/knowledge-writes.md) |
| The general kinds and the kind fixtures | [component-specs-general.md](../contracts/component-specs-general.md) |
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

## Consequences

- The register entry "Leftovers of the design-conformance lane" is cleared.
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
`frontend/e2e/matter-cited-values-unit.spec.ts` and `frontend/e2e/kind-fixtures-unit.spec.ts`.
