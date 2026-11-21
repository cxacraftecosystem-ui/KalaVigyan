# 0002. One contract package for research and answering

Research and answering meet at one contract package, `backend/app/research/`, which fixes the shared
errors, vocabulary, wire names, mode limits, figure and quote rules, fetcher outcomes and stream
events before any lane is built. Live findings are written back as cited claims instead of being
kept for one answer only.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The lanes built to it | [0004](0004-craft-resolver.md), [0005](0005-scholarly-source-adapters.md), [0006](0006-reference-source-adapters.md), [0007](0007-web-search-and-fetcher.md), [0008](0008-stored-knowledge-retrieval.md), [0009](0009-planner-and-tiered-research.md), [0010](0010-composer.md), [0011](0011-claim-write-back-and-coverage-enrichment.md) and [0012](0012-answer-stream-end-to-end.md) |
| The contracts it names | [research.md](../contracts/research.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The next lanes (craft resolver, planner, source adapters, fetcher, composer, claim writer,
answering service, frontend) will be built in parallel. They meet at a handful of interfaces
and must agree on them before any of them is written (engineering practices: agree the
interface, build the shared piece first). The plan names the interfaces (PLAN 3.1, 5.2, 6) but
leaves several choices open, and section 0 changed some of them: live research is written back
as claims, there are no review gates, and research is not limited to the named sources.

## Decision

1. **Home.** The contracts live in a new package `backend/app/research/`, a foundation layer
   that may import only `core` and `models` (`LAYER_IMPORTS`). `services` and `api` may import
   it; later packages (`retrieval/`, `websearch/`, `evidence/`) will get a row that allows it.
   Putting the models in `schemas/` was rejected: that layer is for HTTP bodies, cannot import
   `models` (where the vocabulary lives), and the protocols and rules are not bodies. One
   package also lets the composer-to-stream seam be tested in one place.
2. **Errors.** A shared hierarchy in `core/errors.py` (`AppError`, `InvalidInput`, `Refused`,
   `NotConfigured`, `ExternalFailure`), because the backend practices ask for one and none
   existed. `ProviderError` becomes a subclass of `ExternalFailure` with the same constructor,
   and `RouterError` of `AppError`, so existing `except` clauses keep working while new code can
   catch by category. The failure kinds and the router's stop set move to `core/errors.py`
   (one home); the router's unused `NEXT_ROUTE_KINDS` copy is deleted.
3. **Vocabulary.** Literal types are built from the tuples in `models/enums.py`, so a new enum
   value reaches the contracts without a second edit. `LEVEL_ORDER` moves from
   `services/knowledge_view.py` to `research/vocabulary.py`, with `weakest_level` as the one
   rule for combining levels. The evidence labels reuse the stream's existing words `QUOTED` and
   `INFERRED` (model-inferred) rather than adding a third spelling.
4. **Wire names.** Contract models use snake_case in Python and camelCase in JSON
   (`ContractModel`), matching the stream and the database columns. They are frozen and refuse
   unknown fields.
5. **Mode limits.** PLAN 6 gives DEEP 8 queries and 20 fetches and no numbers for HYBRID.
   HYBRID gets 4 queries and 10 fetches, run only for facets the stored tiers left empty.
   VERIFIED runs T0 and T1 only and never searches. The limits are constants in
   `MODE_POLICIES`; the owner may change them there.
6. **Live research is written back.** Under section 0, live findings become `Claim` rows
   (`origin=LIVE_RESEARCH`, `status=APPROVED`, level `PROVISIONAL` when a quote passed, else
   `HYPOTHESIS`), not only answer-scoped `LiveCandidate` rows; PLAN 6's "only an enrichment job
   writes claims" is superseded. A write-back must cite at least one source and every figure in
   it must be in a passing quote. Duplicates are found by an exact key (craft, concept type and
   name, predicate, folded text); a repeat adds citations to the existing claim instead of a
   new row. Near-duplicate merging by embedding is left to the writer lane.
7. **Composer output.** Sentences cite stored claim ids and, for live items not yet written
   back, evidence ids, with quoted spans. The post-checks are pure functions
   (`sentence_violations`) returning every violation, so the caller can retry once and then
   drop the sentence (PLAN 3.1) instead of failing the whole answer; the stream model refuses
   an uncited sentence outright. Reactions are not composer output: they come from stored,
   mechanically balanced `Reaction` rows.
8. **Figures.** A figure is a chemical-formula-like token containing a digit (matched whole) or
   a number outside such a token (thousands commas removed). Digits inside a formula do not
   support a standalone number, so `H2O` in a quote does not license "2 hours".
9. **Quote matching.** PLAN 3.1 asks for NFKC, whitespace and hyphenation normalisation. Also
   folded: typographic dashes and quotation marks (PDF text and model output disagree on them
   constantly) and hyphens between letters (a PDF's `dye-` line break against a model's
   `dye-stuff`). Case is kept.
10. **Fetcher outcomes.** What a sandbox rule stops is a `FetchRefused` with a stable reason
    code (stored in `WebFetch.blockedReason`); what the remote side does is an
    `ExternalFailure`. The 10-second limit is a rule (`TIME_LIMIT`). Cleaned text is capped at
    200,000 characters (PLAN 6 says "length capped" without a number).
11. **Stream.** The event set stays what the client consumes, plus one new `status` event for
    progress during research, which the current client ignores. The heartbeat is an SSE
    comment every 60 seconds, which the client already skips; 60 s is under CloudFront's 120 s
    origin read timeout and nginx's 300 s. The existing stored-answer route now builds every
    frame through `event_frame`, so the contract is enforced at run time, and a shared golden
    stream (`shared/answer-stream.golden.sse`) is checked by both the backend and the frontend
    tests. Frontend checks now also run when that file changes.

## Consequences

- Lanes build against `backend/app/research/` and `docs/contracts/research.md`; a change to a
  type changes the page and the tests in the same change.
- A badly formed stored row (for example a source title that is empty) now fails the answer
  loudly instead of sending a malformed event; the seed data was checked and passes.
- Number words, units and formula-free quantities are not yet checked (debt register).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
