# 0068. Learning block renderers

The quiz, compare, concept graph, measure, market and GI and climate blocks are drawn from two
registered modules: a quiz hides its answers until the reader picks, and compare is one table that
stacks on a phone. A measure shows the source's words first, a climate trend is drawn as a slope
from zero, and one numbering covers the new kinds.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0062 Phase D contract: learning blocks, versions, alerts, lessons, exports and the map](0062-phase-d-contract.md) |
| The review that fixed it | [0070 Phase D review fixes](0070-phase-d-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase D of `docs/plans/answer-experience.md` ("Learn and act", owner-approved, section 8 final)
asks for a quiz, compare, the shared-science explorer, local measures, market and GI, and climate
and risk. Decision 0062 fixed the six kinds' fields and validators; lanes 0064 to 0066 build their
builders. This lane draws the six kinds through the client renderer registry and edits no backend
file. The boards are `Learn`, `Explainer`, `Map` and `Craft` of the design project. Rules that
bind: every fact the reader sees is cited to a source or a dataset row, numbers come from the
block (never computed into new facts on the client), nothing widens a 390 px phone page, every
animation has a static end state under either reduced-motion switch, and no how-it-works copy
reaches a screen.

## Decision

1. **Registered through two modules.** `components/answer/learning/learningRenderers.tsx`
   (`quiz`, `compare`, `concept_graph`) and `components/answer/insight/insightRenderers.tsx`
   (`measure`, `market_gi`, `climate_risk`) are spread into `BLOCK_RENDERERS`. None needs a heavy
   library, so all six are eager. `BUILT_BLOCK_KINDS` is unchanged on both sides: decision 0042
   point 11 adds a kind on both sides in one change, together with its builder. The phase D
   contract spec now asserts that each kind has a renderer while the parser and the stream still
   refuse it.
2. **A quiz hides its answers until the reader picks.** Each question shows its prompt with the
   blank drawn as a line ("blank" for screen readers) and its options as buttons in alphabetical
   order (`lib/quizView.optionOrder`, code-point order of the case-folded text, the same on server
   and client render), so the key is never given away by its place. A question takes only its
   first pick: the key is marked right (green, a tick and "right answer" in words), a wrong pick
   wrong (red, a cross and "your answer"), the rest dimmed, and the keyed sentence appears with
   its citation under "Right." or "Not quite. It is …". Distractors' sentences are never shown.
   The score reads "1 of 2 right · 1 to go" and, when every question is answered, "Start again"
   clears the picks. Picks live in the page only. The reveal rises in unless motion is reduced.
3. **Compare is one table that stacks on a phone.** One `role="table"` structure: on a phone each
   row is a card with its title and each craft's cell under the craft's name; side by side from
   `sm` for two crafts, `md` for three and `lg` for four (`lib/compareView.compareLayout`, literal
   classes), the craft names become linked column headers. A row is titled by its term (with its
   facet above) or by its facet. An empty cell is a dash, "Not stated" for screen readers.
4. **The concept graph is a picture over a list.** Pills choose a shared term (`Alum · 4`). The
   figure (`role="img"`, labelled "Alum is shared by …") draws the term at the hub and up to seven
   sharing crafts on a ring with a "+N" for the rest (`lib/conceptGraph.graphLayout`), the asked
   craft outlined; its craft chips are mouse shortcuts out of the tab order. The list under it is
   the accessible route: each craft linked to its page with its cited sentence, six at first and
   "Show all N". The figure is 4:3 on a phone (square when crowded) and 5:2 from `sm`; its spokes
   and chips appear in a short stagger unless motion is reduced. `ConceptGraphView` takes
   `focus`, `nodes` and an optional first term, so the explorer screen can reuse it.
5. **A measure shows the source's words first.** "10-15 feet → 3.05–4.57 m": the stated text as
   written, the server's metric value, then the conversion ("1 foot = 0.3048 m · Exact
   definition", or "1 seer = 0.933 kg · As stated for Kachchh, Gujarat" with the chip of the
   claim that states the factor), the cited sentence, and each definitions dataset row once under
   the block. Factors are printed in full (`Intl` up to ten decimals), never rounded.
6. **Market and GI shows the registry's facts and the sources' words.** The craft's name links to
   its page beside a status badge (GI registered, GI applied for, GI application withdrawn, each
   with an icon); application, certificate, filing and registration dates (partial dates as
   stated: a year, a month or a day), the journal issue and authorised users as tiles, the
   proprietors, the GI sentences, "Signs of imitation" apart with their citations, and prices as
   stated with "Per metre · Bhuj · 2019". A block with nothing to show draws nothing.
7. **Climate trends are drawn as what the block holds: a slope from zero.** The block carries each
   trend's mean, Theil–Sen slope per decade and Mann–Kendall p-value, not the annual series, so a
   line over the years would draw values no dataset row states. Each variable gets one diverging
   chart (rainfall in the water ramp, temperature in the warm ramp; "Drier 0 Wetter", "Cooler 0
   Warmer"), a row per district with a bar from zero scaled to a rounded domain shared by the
   chart (`lib/climateView.niceCeiling`), solid when significant and dashed and pale when not, and
   in words the slope, "Significant" or "Not significant" with the p-value, and the mean, period
   and resolution. Groundwater values appear only where a dataset gives them. The meaning
   sentences sit under "For the craft", and every dataset row is credited once with the trend
   method. Bars grow from zero when scrolled into view unless motion is reduced.
   `TREND_SIGNIFICANCE` mirrors the backend's and a spec pins it.
8. **One numbering covers the new kinds.** `explainerView.blockSentences` reads each kind in the
   server's `SENTENCES` order (every quiz option's sentence, filled compare cells, each concept
   craft, measure rows, GI then imitation then price sentences, meaning), and `blockCitations`
   adds a measure's conversion citations after its sentences, as the backend's
   `MeasureBlock.citations` does, so the client's source numbers equal the fixture's `sources`
   order.
9. **Shared helpers stay where they were.** `lib/measure` gained `m²`, `L` and `°C per decade`;
   cited sentences go through `CitedText`, dataset rows through `DatasetCredit`, rows through
   `StripLine`, and motion through `guideMotion` and `useAppReducedMotion`.

## Consequences

- Nothing a reader sees changes until the kinds join `BUILT_BLOCK_KINDS` with their builders.
- `e2e/learning-renderers-unit.spec.ts` and `e2e/insight-renderers-unit.spec.ts` parse the phase D
  fixture blocks (`e2e/phaseDFixture.ts`) and check option order, hidden and revealed answers, the
  score, compare's columns and empty cells, the graph's hub, ring, overflow and list, conversions,
  GI facts and dates, imitation, prices, trends and groundwater, empty blocks, reduced motion, the
  numbering against the fixture's sources and the shrinkable columns. Rendered at 390, 834 and
  1280 px in both themes, no page scrolled sideways.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
