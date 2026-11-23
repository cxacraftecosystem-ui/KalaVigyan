# 0169. A write-back asks the cheap judge first, a reviewer decides readings, map layers and a category's structure, and a PDF is described by its first page

An answer's research write-back asks the contribution worker's judge ladder, cheapest model first;
a district is named by any of its listed names; a contributed PDF takes its authors, issue date,
journal and title from its first page when its file says only what made it; a reading outside its
stage's usual range, a proposed map layer and a category page's structure each wait in the review
queue; and a material's alternatives are curated, not read from English words.

Date: 2026-11-23. Status: accepted (the lead's debt-clearing brief, MCP follow-ups lane, on the
answer lane's hand-back of the judge cost, decision 0165, and the lead's correction of source
7365bdde, 2026-11-23). It amends [decision 0149](0149-a-fact-readers-can-see.md), item 9's ladder,
which now also serves the write-back, and item 8, which a PDF's first page extends;
[decision 0108](0108-structure-proposals-become-curated-facts.md), its craft-only subject and its
kinds; [decision 0114](0114-kinds-and-datasets.md), the dataset record, which a map layer now
carries over MCP; [decision 0015](0015-science-engine.md), what an `OUTSIDE` reading leads to; and
[decision 0056](0056-what-if-lab.md), how two materials become alternatives. The contracts are
`docs/contracts/knowledge-writes.md` (Cost at the centre; The research write-back; Structure
proposals; gate 2), `docs/contracts/review-queue.md`, `docs/contracts/science.md` (What is shown),
`docs/contracts/curation.md` (Materials, tools and reactions), `docs/contracts/explainer.md`
(what-if inputs), `docs/contracts/research.md` (The writer and the coverage job) and the datasets
reference (Map layers over MCP).

| For | Read |
|---|---|
| The judge ladder and floors the write-back now shares | [decision 0149](0149-a-fact-readers-can-see.md), item 9 |
| The answer cost that handed the judges back | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| Structure proposals as they began | [decision 0108](0108-structure-proposals-become-curated-facts.md) |
| The dataset record a map layer carries | [decision 0114](0114-kinds-and-datasets.md) |
| The stage envelopes a reading is checked against | [decision 0015](0015-science-engine.md) |
| The what-if inputs that read alternatives | [decision 0056](0056-what-if-lab.md) |
| The review page's rule for a kind it does not know | [decision 0167](0167-answer-leftovers-kept-true.md) |
| The queue's kinds and decisions as they stand | [review-queue.md](../contracts/review-queue.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Seven follow-ups were left to this lane. The write-back of an answer asked its novelty and duplicate
judges on the evaluation route, which starts with Opus: $0.119 of the $1.05 that q001 cost
(decision 0165). Source 7365bdde, a Journal of Environmental Biology paper on Sanganer dyes, was
stored with the title "aa.MDI", the author "sys", the year 2009 (the file's creation) and the kind
OTHER, while its first page names its authors, its journal and January 2007; the lead corrected the
row by hand. A craft placed in Kachchh was not named by a source writing Kutch unless its own name
said Kutch. Three debt entries asked for review queue kinds and paths that did not exist: readings
outside their envelope, a category page's structure and a dataset for a new map layer; and the
what-if read alternatives only from English words standing between two names.

## Decision

1. **The write-back's judges are a ladder.** `research/judge_ladder.JudgeLadder(first, escalate)`
   is the one type; `providers/judge_routes.thrifty_judges` (moved from services so the answer
   routes in providers can build it) gives each provider's least priced verified model first and
   the configured route after. The answer, the coverage enrichment and the contribution worker take
   it; the write-back's later gates also take the worker's thrift (no judge for a near twin or a far
   fact). The cheap judge is "unsure" exactly when its reply is unusable (not JSON, off its schema, a
   pair or candidate left unanswered), the rule decision 0149's evaluation already measures; no
   confidence score was invented. Claude Haiku 5.5 is priced at 1/40 of Opus 5.5 for the same
   tokens, so the $0.119 becomes about $0.003 plus $0.119 times the share that escalates: about
   $0.116 saved per answer with no escalation, $0.104 at one in ten, before thrift.
2. **A district is named by any of its names.** The filing widens a craft's placed keys with the
   LGD name and the listed other names of the same district (`data/district_other_names.json`),
   both ways.
3. **A PDF is described by its first page when its file says only what made it.** An author that
   is a producer's word (sys, user, admin, a software name, a login name) is never an author; the
   first fifteen lines give a journal line (a periodical word, a month and a year), the title after
   it and an authors line of capitalised names or initials; a page with a journal line is a `PAPER`
   with its `containerTitle` and dated by its issue, since a PDF's own date is its file's creation.
   A DOI on the page is not looked up and not set: a DOI changes a source's stored key
   (`live_source_id`), so the same paper would be stored twice. Stored rows are never rewritten;
   `retitle_sources` lists the stored sources whose authors are producer words for the lead.
4. **A reading outside its range waits for a reviewer.** The queue's `READINGS` kind lists the
   readings whose converted bounds leave their stage type's envelope, computed with the one check
   the process view shows (`science/reading_checks`) when the queue is read, so a changed envelope
   changes what waits without a backfill. Approve keeps the reading as its source states it; reject
   marks a misreading (`ConditionReading.reviewStatus`) and every view leaves it out, while the row
   stays so a re-run seed does not bring it back. A stored status was the alternative; it would go
   stale with the envelopes.
5. **A map layer's dataset is proposed over MCP.** `propose_dataset` takes an optional layer plan;
   its upload is a GeoJSON file checked by the rules of the datasets reference (WGS 84, inside
   India's frame, coordinates to 0.001 degree, the layer class's tolerance as the most it may be
   simplified, a value or no reading on every feature, no interpolation) and held as a
   `MapLayerProposal` in the queue's `LAYERS` kind for an Admin. Approval draws nothing: an engineer
   ships the layer through `tools/maplayers`, as the site's own layers enter.
6. **A category page takes structure.** `StructureProposal` names a category or a craft (exactly
   one, migration 0092). A category page keeps no stages, materials, native names or GI record, so
   it takes an unstaged reaction, a term, an open question and a conflict; its facts are curated
   facts of the category's dossier.
7. **Alternatives are curated.** A dossier's material lists its `alternatives` with the claim that
   states each, and `propose_structure` takes an `ALTERNATIVE`; both become a `CONTRASTS_WITH` edge
   carrying the claim, which the what-if reads beside stated contrasts. The word-based reading stays
   for what no curator has recorded.
8. **The new kinds join the review page's unknown-kind rule.** The production build leaves out a
   kind or structure item it does not know ([decision 0167](0167-answer-leftovers-kept-true.md),
   `shape.knownOnly`), so `READINGS`, `LAYERS` and `ALTERNATIVE` reach a web app released before
   them as absent, never as a broken page.

## Consequences

- An answer's judges cost about a fortieth of what they did; a rise in escalations shows in the
  nightly judge evaluation and the cost ledger.
- New PDF sources from journals are stored as papers with their journals and issue years; the rows
  stored before stay until the lead corrects them from the listing.
- `tools/list` holds 61,316 of its 61,440 bytes after the new kinds; the next schema change needs a
  saving first.
- No reading is outside its range in today's seed, and no layer is proposed yet, so both kinds are
  empty until research or a contributor adds one; the cards wait for a signed-in capture
  (`docs/TECH_DEBT.md`, Review cards not yet seen in a browser).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in the contracts named above. Its rules are tested by
`backend/tests/write_back/test_write_back_judges.py`, `test_novelty_failure.py`,
`test_district_other_names.py`, `backend/tests/research/test_front_page.py`,
`backend/tests/sources/test_pdf_front_page.py`, `backend/tests/db/test_producer_authors_db.py`,
`backend/tests/science/test_reading_checks.py`, `backend/tests/db/test_reading_review_db.py`,
`backend/tests/research/test_map_layer_proposals.py`, `backend/tests/db/test_map_layer_proposals_db.py`,
`backend/tests/structure/test_alternatives_and_categories.py`,
`backend/tests/curation/test_material_alternatives.py`,
`backend/tests/db/test_structure_categories_db.py` and `frontend/e2e/review-readings-unit.spec.ts`,
`review-layers-unit.spec.ts`, `review-structure-unit.spec.ts` and `review-queue-unit.spec.ts`.
