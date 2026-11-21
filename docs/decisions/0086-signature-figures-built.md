# 0086. The four signature figures are built, as lede figures only, behind a setting

The four signature figures (`indigo_vat`, `mordant_bath`, `lost_wax` and `firing`) are built as lede
figures only, behind a setting, chosen by terms and built by rules. They fail closed, softly.

Date: 2026-11-18. Status: accepted. Builds plan task 3-04 on the shapes of decision 0077 item 6.

| For | Read |
|---|---|
| What it builds on | [0077 Every answer opens with a lede, its sections carry headings shaped by the question](0077-lede-headings-and-question-order.md): item 6's signature figures |
| The contracts it names | [explainer.md](../contracts/explainer.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0077 declared `indigo_vat`, `mordant_bath`, `lost_wax` and `firing` and left the lede's
`figure` null. The owner's Expert question on Kutch Ajrakh opened with a lede and no figure at all,
although its stored claims state that alum gives red and iron gives black, and that indigo turns
from green to blue in air. The production page cannot draw the figures; the redesign will.

## Decision

1. **Built as figures, never as blocks.** `research/explainer.BUILT_FIGURE_KINDS` (all four, mirrored
   in `frontend/lib/explainerContract.ts` and pinned by `e2e/backend-vocabulary-unit.spec.ts`) is
   the list the lede, its event, the document and the client's lede shape accept. The kinds stay
   out of `BUILT_BLOCK_KINDS`, so a section, a `block` event or a stored piece still refuses them,
   and the builder registry and renderer registry rules for section kinds do not apply to them.
2. **Behind a setting.** `SIGNATURE_FIGURES_ENABLED` (default `false`, `core/config.py`,
   `infra/.env.example`) makes `build_answer_pipeline` give `LedeTools.figures` a
   `SignatureFigures`; off, it is `None` and nothing on the wire changes. Turn it on with the
   redesign that draws the figures.
3. **Chosen by terms, built by rules.** After the lede's sentences are marked, `chosen_signature`
   runs over the question's term keys, then the lede's, in order. `services/signature_blocks.py`
   builds the figure with no model call from the lede's evidence (every stored claim of the craft
   the opening read, ranked for the question), each sentence one claim's own text and citations;
   the fixed rules are in `signature_rules.py` and the word lists in `signature_words.py`
   (`docs/contracts/explainer.md`, "How the server builds a figure"). The indigo vat's compounds
   come from the craft's compound rows (`craft_matter`), read only when that kind is chosen.
4. **Fail closed, softly.** A figure that misses a required value (a lift, a dye, a fibre, two
   swatches, two casting steps, a vat kind) or fails its model is not built, and any error while
   building it leaves the lede as composed; the lede itself is never lost to a figure.

## Consequences

- For the owner's question the lede marks kut, alum and gach, so with the setting on it carries
  the Ajrakh mordant bath: madder on cotton, alum to red (claim C093) and iron to black (C078). A
  question naming indigo gets the fermented vat: the lift (C086), indigo blue insoluble and indigo
  white soluble (one seed claim states both), three or four dips for the darkest blue
  (C087) and six named contents.
- The figure's sentences count as shown text in the claim ledger, so a ladder stage or prose
  sentence with the same claim text later in the answer is left out of that block.
- `shared/explainer.signature.golden.json` and `explainer.signature-lede.golden.json` are read by
  `tests/contracts/test_explainer_signature_contract.py` and `e2e/signature-figures-unit.spec.ts`.
  `LedeBlock.tsx` draws no figure it has no renderer for, and no empty frame for it.
- The word rules are English; a translated lede keeps the figure built from the English claims and
  translates its sentences with the lede.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
