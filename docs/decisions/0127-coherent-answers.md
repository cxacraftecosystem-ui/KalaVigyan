# 0127. An answer says each fact once, never admits a gap, keeps the stages it is asked and paces its sources

An answer no longer tells a fact twice in nearly the same words, never shows a sentence admitting
that something is unknown (such a sentence becomes an open question with its citation), always shows
on its process ladder the stages a process question names, and asks the scholarly services no
faster than their published limits, stopping for the rest of the answer once a service has refused
it twice.

Date: 2026-11-22. Status: accepted (lead's round 7 brief, coherence lane, from the live answer
evaluation of 2026-11-21, run 44919641295). The contracts are `docs/contracts/explainer.md` (One
claim, one rendering; No gap on the page; the reused and the composed ladder) and
`docs/contracts/research.md` (Scholarly adapters, Pacing).

| For | Read |
|---|---|
| The ledger rule it widens | [0080-claim-ledger.md](0080-claim-ledger.md), and [explainer.md](../contracts/explainer.md), One claim, one rendering |
| The evaluation that found the faults | [answer-eval.md](../contracts/answer-eval.md) |
| The scholarly adapters it paces | [0005-scholarly-source-adapters.md](0005-scholarly-source-adapters.md) and [research.md](../contracts/research.md), Scholarly adapters |
| Every decision, by group | [README.md](README.md) |

## Context

The judge of the live evaluation scored ten answers and named four faults the audit lanes had not:

- **A section said twice.** Blue pottery's geography "repeats its six sentences twice nearly
  verbatim"; two Ajrakh answers held "near-duplicate sentences across economics and history". Every
  story builder (region story, zoom, seasons, measure, supply map, timeline) retells the section's
  prose facts with the claims' own text, and the composer writes those facts in nearly the claims'
  words. The ledger dropped a story item only when its text matched word for word, and a prose
  sentence only when its text matched or its claims were all shown, so a near copy, or one fact
  written back under two fields as two claims, passed.
- **Gaps in the prose.** Three Bidriware answers said "the compounds have not been identified" and
  "the craft's origins are unknown" in their sections. The evaluation already held the pattern of a
  gap admission, but nothing on the answer path read it; reused pieces carried such sentences into
  every later answer.
- **A process question lost its stages.** "What are the stages of making a Bidri vessel, from casting
  the alloy to setting the silver?" got a ladder without moulding and casting. The ladder showed only
  the stages the composer chose, and a reused process section only the stages its stored blocks
  cited, so the stages the question named could be left out.
- **Throttled sources.** Semantic Scholar and Crossref answered `rate_limit` dozens of times in one
  run. Each adapter paced only its own client, which the live sources rebuild every ten minutes;
  Crossref's public pool allows one search a second and one request at a time, while the adapter
  sent five a second with no limit on overlap; and a refused source was asked again on every search
  and fetch of the answer.

## Decision

1. **A restatement is held back.** `services/restatements.restates` compares a sentence with each one
   already shown: at least four content stems, no new number, the same negation, and either the same
   claim group (its claims, or its citations' source and quote, within the shown sentence's) with half
   the stems shared, or other evidence with the same numbers and 0.8 of the stems shared. Restating
   blocks drop it as before; story blocks now drop it too, but a story that would not stand without
   its restating items keeps the first of them, so a map or a stepper is never lost to the prose it
   draws; a ladder stage drops it only while it keeps another sentence. The lede keeps its
   word-for-word rule.
2. **A gap becomes an open question.** The pattern moves to `research/gap_admissions.py`, gains "is
   unknown or unclear" and "has not been identified or established", and is the one the evaluation's
   `noGaps` measure and the answer stream both read. `ExplainerStream.blocks` takes every sentence
   that admits a gap out of its block before the ledger, and sends it as an `open_question` with its
   citations, translated with the section; a block left empty is not sent, and its gaps are still
   asked.
3. **A process question's stages are on its ladder.** `research/sections.named_stage_ids` adds to the
   composer's choice every stored stage a process question names (a content stem of the stage's name,
   process words and the craft's name aside), and every stage between two named in a "from ... to"
   question. The composed ladder and a reused section's ladder both carry them, built from the stored
   rows.
4. **Sources are paced per process and per answer.** `sources/scholarly/pacing.PacedHttp` gives every
   scholarly adapter one process-wide token bucket per service and request kind, at 80 % of the
   published limit, with Crossref and Semantic Scholar one request at a time. A `Retry-After` holds
   the service for every client; identical lookups share one cache across rebuilds; within an answer a
   failed lookup is not repeated, and a service that refused twice is not asked again. Crossref is
   asked with the site's address in its `User-Agent` and no e-mail.

## Consequences

- A figure whose every item repeats the prose nearly word for word is drawn with one item, so one
  restatement can remain; the place and journey builders could offer their stories the facts the
  prose did not say, which would remove it (open for the builders' owner).
- The Bidriware answers lose their gap sentences from the sections and gain them as open
  questions, streamed with the answer like every other open question; the stored explainer's
  sections no longer hold them, so the evaluation's `noGaps` reads the same answer the reader saw.
- Crossref now runs in the public pool (one search a second) rather than the polite pool, which asks
  for an e-mail; the shared bucket keeps the answer under it instead of collecting 429s.
- The process-wide pacing state lives behind `shared_pacing()`, a cached factory like
  `get_settings()`; tests pass their own `ScholarlyPacing`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/ledger/test_restated_facts.py`,
`backend/tests/ledger/test_gap_routing.py`, `backend/tests/research/test_gap_admissions.py`,
`backend/tests/research/test_named_stages.py`, `backend/tests/answering/test_reused_stages.py` and
`backend/tests/sources/test_scholarly_pacing.py`.
