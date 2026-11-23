# 0009. Planner and tiered research

A new `app/planner/` layer plans each question in one model call and runs tiered research that stops
at the first tier where every facet is covered at the mode's threshold. Both live tiers run in
parallel, and their deduplicated, ranked readings become the evidence pack the composer cites.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| Reference lists followed through OpenAlex in the reserve the cited DOIs leave | [decision 0181](0181-names-kept-out-of-pictures-reference-lists-and-the-wood-handbook.md) |
| Every decision, by group | [README.md](README.md) |

## Context

PLAN section 3.1 steps 3 and 4 and section 6 describe a planner (a cheap model with a strict
JSON schema whose enums come from the database: intent, facets, needsRegion, language) and
tiered retrieval that stops at the first tier where every facet has a claim at the mode's
minimum level. Section 0 overrides the rest: knowledge grows through live research, accuracy
over speed, research is not limited to the named sources and follows references. The contract
(`research/planning.py`, decision 0002) had the plan and its mode limits but no coverage rule,
no evidence pack, no model protocol, and nothing that runs the adapters, the fetcher and the
open-access locator together.

## Decision

1. **A new layer, `app/planner/`** (`planner -> sources, research, core, models`), below
   `services`. It depends on protocols only (`StructuredModel`, `KnowledgeRetriever`,
   `SourceAdapter`, `Fetcher`, `OpenAccessLocator`), plus two `sources` helpers it must not
   copy (`build_document`, `doi_of`) and the fetcher's service name. The concrete pieces are
   joined outside it: `providers/structured.router_structured_model(AiTask.PLAN, principal)`
   (the AI router, so the Settings hub routing and the monthly ceiling apply) and
   `services/live_sources.live_sources(session, client)` (every scholarly, reference and web
   adapter, one `FetcherClient`, the Unpaywall locator and Crossref as the DOI source).
   `services/web_sources.web_sources` is removed: it built a second fetcher client and had no
   caller; `web_search_config` stays.
2. **One model call per question.** The `PLAN` task returns intent, needsRegion, facets
   (concept types from `models/enums.py`) and per-facet queries (tier `T3` or `T4`) in one JSON
   object. The question is sent inside `untrusted_block`; the reply is validated, retried once
   (`PLAN_DRAFT_RETRIES`) and otherwise raised as `ExternalFailure` (service `model`). There is
   no rule-based fallback plan: a plan the model did not make would be a silent fallback. The
   router's own degrade flag comes back with the reply (`StructuredReply.degraded`), so past
   80% of the ceiling a `DEEP` question is planned as `HYBRID` (`DEGRADED_MODES`) by the same
   computation the router used; at 100% the router refuses and the caller shows verified-only.
3. **Coverage is a named threshold.** A facet is covered when at least
   `FACET_COVERED_MIN_CLAIMS` (2) stored claims match its target lexically (a full-text rank, so
   the claim shares a word with the target) at a level the mode shows without the open-questions
   block (`COVERING_LEVELS`: the mode's claim levels minus `HYPOTHESIS`). Two, not the plan's
   one: one claim rarely answers a facet well, and accuracy is preferred over speed. The vector
   rank alone does not count, because inside one craft's facet every row gets a vector rank.
   `HYBRID` researches only uncovered facets; `DEEP` researches all; `VERIFIED` never does.
4. **Search egress.** Every open facet gets at least one query; when the model gave none, the
   query is the craft name and the facet target (the plan's own construction). A query that
   does not name the craft gets the craft name in front. Queries carrying personal data
   (`personal_data_in`) or a caller's withheld term (`PlanRequest.withheldTerms`, for the
   asker's own names) are left out, duplicates are dropped, and the mode's query limit applies.
5. **Both live tiers run in parallel.** PLAN section 6 says "T3 then T4"; running T4 only after
   T3 leaves a facet empty doubles latency and narrows research, which section 0 rejects. Every
   query runs on every source of its tier at once (`SEARCH_CONCURRENCY` 12, each search capped at
   `SEARCH_TIMEOUT_SECONDS` 30) with per-mode, per-tier result counts (`LIVE_BUDGETS`: `HYBRID`
   5 scholarly and 8 web results per source, `DEEP` 10 and 15). A failing source is recorded in
   the pack and the rest go on; when every search fails, `ExternalFailure` (service
   `live_research`) is raised; a tier with no source is `NotConfigured`.
6. **Dedupe and rank.** Hits merge by `source_key` (DOI, else canonical URL) and by id; the
   kept item is the most trusted, with quotes, best ranked. Evidence ranks by trust tier, then
   by how many source-and-query pairs found it, then best rank, then id, so results reproduce.
7. **Reading.** The best item of each facet is read first, then the rest by rank, through the
   source that found it (web pages through the fetcher sandbox), up to the plan's `maxFetches`;
   a failed read is replaced by the next item, at most `READ_ATTEMPT_FACTOR` (2) attempts per
   document. In `DEEP` a scholarly item with a DOI is first looked up with the open-access
   locator and its open copy read as full text through the fetcher.
8. **Following references.** `DEEP` follows DOIs cited in the documents it read (at most
   `REFERENCES_PER_DOCUMENT` 5 new ones per document) through Crossref, with the open copy when
   there is one. `DEEP_REFERENCE_RESERVE` (6) of the 20 fetches are kept for them, so every
   read, primary or followed, stays inside the plan's limit. DOIs are the one reference form
   that can be resolved to a citable record without guessing; links inside pages are not
   followed (the fetcher returns text, not links).
9. **The evidence pack** (`research/evidence_pack.py`) is the output: plan, the degraded flag,
   stored hits for the question, coverage per facet, ranked deduplicated evidence, the
   documents read, and every failure with its stage. Its validator ties it together (coverage
   in facet order, unique evidence, documents only of packed evidence and within
   `maxFetches`, followed references naming packed parents).

## What follows

- The answering service builds `ResearchPlanner(model=router_structured_model(AiTask.PLAN,
  principal), retriever=StoredKnowledgeSearch(session, embed=router_embedder(principal)),
  sources=...)` with `live_sources` held for the process, and turns the pack into composer
  candidates after a reader step extracts verbatim quotes (`WEB_READ`).
- Coverage runs one stored search per facet; each embeds its target (a cheap call, but up to
  eight per question). `LiveCandidate`, `WebFetch` and `AnswerTrace` rows are not written yet
  (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
