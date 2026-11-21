# 0062. Phase D contract: learning blocks, versions, alerts, lessons, exports and the map

Phase D's contract fixes the learning blocks (quiz and compare at version 1, four kinds new),
follow-ups as new versions, alerts that detect, professors' lessons, citation formats by stated
rules, and an ask the map that reads stored stories. A quiz is a cloze of the explainer's own
sentences, and local measures convert only by an exact definition or a stated regional value.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| What amended it | [0067 Lesson packs, the explainer PDF and citation export](0067-lessons-and-exports.md): item 10, with APA written by citeproc-py while BibTeX and RIS keep the stated rules |
| The lanes built to it | [0063](0063-follow-ups-versions-and-alerts.md), [0064](0064-quiz-compare-and-shared-science.md), [0065](0065-climate-risk-and-ask-the-map.md), [0066](0066-local-measures-and-market-gi.md), [0067](0067-lessons-and-exports.md), [0068](0068-learning-block-renderers.md) and [0069](0069-learning-screens.md) |
| The contracts it names | [learning.md](../contracts/learning.md), [explainer.md](../contracts/explainer.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase D of `docs/plans/answer-experience.md` ("Learn and act", owner-approved, section 8 final)
builds the quiz, compare, the shared-science explorer, local measures, market and GI, climate and
risk, ask the map, follow-ups that build, alerts, the lesson builder, and PDF and citation
export; its proof is a professor building a lesson pack from one explainer. It runs as parallel
lanes with fixed numbers: 0063 follow-ups, versions, saved explainers and alerts; 0064 quiz,
compare and the shared-science explorer; 0065 climate and risk and ask the map; 0066 local
measures and market and GI; 0067 lesson builder, PDF and citation export; 0068 learning block
renderers; 0069 explainer, lesson, notification and map screens; 0070 review fixes. As in phases B
and C (decisions 0042 and 0054) the shapes they share are fixed first and pinned on both sides by
fixtures built only from stored seed claims, sources, districts and dataset rows. The curation
import (decision 0053) lands GI records and prices in `CraftGiRecord` and `CraftPrice`.

## Decision

1. **Quiz and compare are fixed at version 1, four kinds are new.** No payload of the 0030
   `quiz` or `compare` ever existed (the built guard refused them), so their final fields replace
   the provisional ones in `research/blocks_learning.py` (with `concept_graph`); `measure`,
   `market_gi` and `climate_risk` are new kinds in `research/blocks_insight.py`. `BLOCK_KINDS`
   gains the four and migration `0018_learning_block_kinds` widens the `KnowledgePiece` kind
   check (its downgrade deletes pieces of the four first). None joins `BUILT_BLOCK_KINDS`.
2. **A quiz is a cloze of the explainer's own sentences.** A question is a cited fact with one of
   its server-marked glossary terms blanked, and its options are terms marked in that and other
   cited sentences, so the question, the answer and every distractor come from cited claims and
   the answer shows its citation. A model may only choose sentences and drop offered
   distractors. A quiz in another language survives only where the translated sentences still
   show the option terms; a quiz is never a stored piece.
3. **Compare and the concept graph are rebuilt, not stored.** Their cells come from each craft's
   stored claims or current pieces (`pieceId`), and the crafts sharing a glossary term grow with
   curation, so a stored copy would go stale. `knowledge_pieces.UNSTORED_BLOCK_KINDS` (quiz,
   compare, concept graph, climate and risk) are refused as pieces; measure and market blocks are
   pieces in their section's slot (a comparison's other crafts' market blocks are rebuilt).
4. **Local measures convert only by an exact definition or a stated regional value.** Owner O5
   allows only conversions a source states for that region. A `REGIONAL` conversion carries its
   region and the citation whose quote states the factor itself. Units exactly defined in metric
   (inch, foot, yard, mile, square foot) convert by the definition, cited as a dataset row of NIST
   Special Publication 811 (`measures.UNIT_DEFINITIONS`); the stored claims hold no regional
   conversion yet, so the fixture's measure is the falling water table's feet. Metric values are
   the stated number times the factor in decimal arithmetic at three significant figures.
5. **Climate trends are dataset rows with their method.** A trend is the Theil-Sen slope per
   decade of a district's annual series over at least 30 years with its Mann-Kendall p-value
   (significant below 0.05), cited by the dataset row whose period is the trend's; the geo ETL
   computes them on GitHub Actions. What they mean for a craft is only cited claims.
6. **GI and prices are the registry's and the sources' own words.** Every number and year in a GI
   record or price occurs in its sentences or their quotes, proprietors and places are named by
   them, and imitation signs are claims citing GI journal text.
7. **A follow-up makes a new version; old ones are never touched.** An explainer is named by its
   first answer. A follow-up answer stores the whole merged explainer on its own answer row and a
   `VersionMark`; `version_problems` is the one rule (base sections and blocks kept and in order,
   added blocks after them and before the pictures, added sections after, the changes exact). The
   stream gains `builds_on` and `version`. Earlier documents stay whole and claims are never
   deleted, so their citations keep resolving.
8. **Alerts detect; the reader rebuilds.** The nightly re-check counts new fact-level claims per
   saved facet without any model call and writes one "answer improved" note; the reader's
   "Update" asks a follow-up for those facets under the reader's own caps. Nothing spends on a
   reader's behalf overnight. The weekly digest uses the existing SES mailer behind
   `ALERT_DIGEST_ENABLED`, off until the owner verifies a sender, and a per-reader opt-in.
9. **Lessons are the professor's.** A new capability `BUILD_LESSONS` (Professor and above; the
   client mirrors it as `canBuildLessons`) builds, lists and downloads packs; a pack is its
   builder's alone. Slides are the version's own cited sentences (at most five a slide), its open
   pictures, one slide per quiz question, a reading list ordered by reliability then citations,
   and the sources. Files are HTML with a vendored reveal.js, PPTX and PDF, all written in pure
   Python on the server: no headless browser or LibreOffice on the small EC2 box.
10. **Citations are formatted by stated rules, not a citation processor.** Stored author names
    are kept as written (inverting them would guess), so a CSL processor adds nothing but a
    dependency. The CSL item, APA 7 text, BibTeX and RIS (CRLF, as the RIS format requires) are
    fixed rule by rule in `docs/contracts/learning.md` and pinned by a hand-derived fixture; a
    processor can replace the APA writer later without a shape change.
11. **Ask the map reads stored stories, never builds on a tap.** A district answers its cited
    crafts (a state of practice alone places no craft in a district), stored region pieces with
    their reuse mark and the district's own land values (soil, climate, water, terrain), with the
    boundary caption; no model call.
12. **Fixtures.** `explainer.phase-d.golden.json` (every phase D kind for Kutch Ajrakh beside
    Bagru) and the learning goldens (versions, alerts, lesson, citations, shared science,
    district) are built from seed claims and sources, seed concepts, the LGD register, the geo
    ETL catalogue and the phase A and B goldens; the climate trend's numbers are placeholders
    until lane 0065 loads trends.

## Consequences

- The lanes build to `docs/contracts/explainer.md` (phase D blocks) and
  `docs/contracts/learning.md`; their fixtures and tests must keep the goldens reproducing.
- Nothing a reader sees changes: the kinds are not built and no route is mounted.
- `DISCIPLINES` moved to `frontend/lib/explainerBlockBase.ts` (re-exported by
  `explainerContract.ts`) so block modules can name fields without an import cycle; the region
  contract exports its place-basis and facet shapes for reuse.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
