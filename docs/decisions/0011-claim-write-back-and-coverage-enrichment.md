# 0011. Claim write-back and the coverage enrichment job

What live research finds for one learner is written back as cited claims, its documents stored first
and each citation keeping its provenance, through one writer whose derived ids make concurrent
writes safe. A daily coverage enrichment job widens coverage across every craft within the monthly
ceiling.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| Every decision, by group | [README.md](README.md) |

## Context

PLAN section 0: the knowledge base grows. What live research finds for one learner is written
back as cited claims so the next answer is faster, and a background job keeps widening
coverage across every craft within the monthly ceiling. No review gates. The contract
(`research/write_back.py`, decision 0002) fixed the `ClaimWriteBack` shape, the labels and
levels and the dedupe key, but there was no writer, nothing that turned a composed answer into
write-backs, no place for the question and retrieval time of each citation, and no job.

## Decision

1. **What is written** (`services/write_back_plan.write_back_plan(pack, answer, *, found_by,
   answer_id)`, pure). Each composed sentence that cites a read live document becomes one
   `ClaimWriteBack`. Sentences that cite stored claims only are skipped (they are stored).
   - A sentence in a section with at least one span found verbatim in its cited document's text
     is `QUOTED` (stored `PROVISIONAL`), relation `DIRECT`. An open question, or a sentence whose
     spans are not in the document, is `INFERRED` (stored `HYPOTHESIS`), relation `CONTEXTUAL`.
   - The passing span becomes the citation's quote and joins the evidence item's quotes (it was
     matched against the document, so the item still satisfies the contract). A cited document
     with no passing span is a citation without a quote (`NA`).
   - The subject is the plan facet of the first cited evidence (concept type and target); the
     predicate is the constant `states`, so the same sentence found once as an inference and
     later quoted has one dedupe key.
   - A sentence that breaks the contract (for example a figure not in a passing quote) is
     skipped with the validation message, never written in a weaker form.
   - Two sentences with the same dedupe key merge their citations; a quoted one wins the label.
2. **Evidence is stored before claims** (`services/live_source_store.keep_document`). A read
   document's source is found by id (`uuid5` of its source key), then DOI (case-insensitive),
   then URL (as given or canonical); otherwise inserted with `origin=LIVE_RESEARCH`, storage
   from the content (`FULL_TEXT`, or `EXCERPT` for an abstract or excerpt), the text's SHA-256
   and the retrieval time. Its text is chunked with `retrieval/indexing.replace_source_chunks`
   and every pending vector filled with `embed_pending` after the claims commit, so stored
   retrieval (T2) sees it on the next question.
   - An imported source that already has chunks keeps them: curated text is not replaced by a
     web read. A live source's full-text chunks are not replaced by a later abstract.
   - Chunk ACL is `PUBLIC` unless the document is full text with no licence (`RESEARCHER`), so a
     student's stored search never reads an unlicensed full copy.
3. **The writer** (`services/claim_writer.SqlClaimWriter`, the `ClaimWriter` of the contract).
   - Ids are derived, so dedupe is enforced by primary keys and concurrent writers race safely:
     claim `uuid5("claim-write-back:" + dedupeKey)`, citation `uuid5` of claim, source key and
     the quote's `quote_key`, new concept `uuid5` of craft, type and folded name. Inserts are
     `ON CONFLICT DO NOTHING`; a second write answers `created=false` and adds only new
     citations.
   - The concept is the given `conceptId` (it must belong to the craft or its sub-category and
     have the type), else for `PROCESS_STAGE` the concept of the craft's `ProcessStage` with that
     name, else the craft's concept of that type and name (case and spacing folded), else the
     sub-category's, else a new craft concept (`originRef=live_research`). This is how a claim is
     linked to its craft and, where known, its stage.
   - A quoted write of a claim stored as `HYPOTHESIS` raises it to `PROVISIONAL` (a quote passed;
     not a review), unless it was rejected or retracted. Nothing lowers a level; nothing goes
     above `PROVISIONAL`.
   - Each creation and each raise appends a `ReviewEvent` (`SYSTEM`, `live_research`) noting how
     it was found and the answer id.
4. **Provenance per citation.** Migration `0003_claim_source_provenance` adds `ClaimSource.foundBy`
   (`ANSWER` or `BACKGROUND`), `answerId` (the question's `Answer`, `SET NULL` when an answer is
   deleted) and `retrievedAt`; `checkedAt` is the retrieval time when a quote was checked.
   Provenance is per citation because one claim gathers citations from many questions. The
   schema test now folds later `add_column`/`drop_column` calls into the tables it compares.
5. **`services/research_write_back.store_live_research`** runs the three steps (documents,
   claims, embeddings) for the answering service and the job, and reports created, matched and
   skipped sentences.
6. **The coverage job** (`services/coverage_selection`, `services/coverage_enrichment`, thin
   entry point `scripts/enrich_coverage.py`, `.github/workflows/coverage-enrichment.yml` daily at
   22:17 UTC, 03:47 IST, after the craft sync).
   - Crafts: every `ACTIVE`, non-catch-all `Craft` row (master list and both portals), without
     an `EnrichmentJob` in the last 7 days, ordered by visible claims on the craft's own
     concepts, then slug; only crafts with an open standard question.
   - Standard questions, one per facet: materials, stages, mechanisms, tools, environment,
     history. A question is open while its facet has fewer than `FACET_COVERED_MIN_CLAIMS` (2)
     claims. Each runs the planner in `HYBRID` (live research only for uncovered facets), then
     the composer when documents were read, then the write-back as `BACKGROUND`.
   - Budget: `ENRICHMENT_DAILY_BUDGET_USD` $2.50 a day (about $75 a month, the plan's $80
     enrichment line) inside the router's monthly ceiling. Every model call of a job runs under
     the request id `enrichment-<job id>` (`core/logging.request_id_scope`), so the router's
     `UsageEvent` rows are summed by `providers/router.tagged_spend`. A question starts only
     while at least `ENRICHMENT_QUESTION_RESERVE_USD` ($0.25) of the day is left, so a run
     overshoots by at most one question.
   - Each craft gets an `EnrichmentJob` row (facets, budget, spend, status, error). A failing
     craft is recorded `FAILED` and the next craft runs; a spent ceiling, no route or a missing
     setup stops the run; an unexpected error closes the job and is raised. The script prints
     one JSON report and exits 1 when any craft failed, so the workflow turns red.
   - The scripts layer may now import `planner`, `composer` and `research` to wire the job.

## Consequences

- An answer that ran live research grows the stored knowledge at once; the next question on
  the same facet is answered from T1 and T2.
- Write-backs are labels, not gates: they show at once, and a professor can still correct,
  retract or verify them.
- `EnrichmentProposal` is not used: there is nothing to approve.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
