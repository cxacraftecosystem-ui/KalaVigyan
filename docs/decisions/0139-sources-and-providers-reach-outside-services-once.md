# 0139. Sources and providers reach outside services once, at the pace and spend every process shares

Every rate limit, scholarly pace and allowance is counted once in Postgres for every API process,
worker and script; each outside service is reached through its own adapter, key checks included;
the model catalogue, the AI spend settings and the key store sit below the services that use them;
and research reads more of what it finds: national ports and prose statements of open licences,
Zenodo, Europe PMC full text, every Wikipedia edition, coarse Wikidata dates and Commons dates,
quotes in other languages through a checked English rendering, and web pages ranked by a reviewed
list of the sites that publish them.

Date: 2026-11-22. Status: accepted (the lead's round 7 debt brief, sources and providers lane,
after the live Khurja test of answer 504968ea-49cc-469c-88f9-205a2ea90e8a). It amends
[decision 0001](0001-adopt-practice-skills.md), item 5, and
[decision 0127](0127-coherent-answers.md), item 4, and builds on decisions
[0005](0005-scholarly-source-adapters.md), [0006](0006-reference-source-adapters.md),
[0007](0007-web-search-and-fetcher.md), [0011](0011-claim-write-back-and-coverage-enrichment.md)
and [0013](0013-review-fixes-quotes-licences-scope.md). The contracts are
`docs/contracts/research.md` (Scholarly adapters, Pacing, Reference adapters, Web search and the
fetcher) and `docs/contracts/explainer.md` (the `paced` event).

| For | Read |
|---|---|
| The layer table it changes | [decision 0001](0001-adopt-practice-skills.md), item 5 |
| The pacing it shares across processes | [decision 0127](0127-coherent-answers.md), item 4 |
| The adapters it extends | [0005](0005-scholarly-source-adapters.md), [0006](0006-reference-source-adapters.md), [0007](0007-web-search-and-fetcher.md) |
| The coverage job and the licence rule | [0011](0011-claim-write-back-and-coverage-enrichment.md), [0013](0013-review-fixes-quotes-licences-scope.md) |
| The `AiTask` re-export goes, and every router settles a cut-off call alike | [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) |
| The composer reads a failing quote in an Indian script through its rendering, and the planner reads a closed DOI from its publisher | [decision 0167](0167-answer-leftovers-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The debt register held eleven entries about how research reaches outside services and models. In
answer 504968ea Crossref, Semantic Scholar and CORE answered with rate limits, so the expert seats
read fewer papers than they searched for: CORE was paced at 24 requests a minute against a
documented 10, and Crossref ran in the public pool. Every limiter of `core/rate_limit.py` and the
scholarly pace lived in one process's memory, though the API's two slots overlap during a release
and the contribution worker and the coverage job research too. `providers/` imported `services/`
for the model catalogue, the spend settings and the keys; `services/managed_secrets.py` probed
eleven providers over HTTP itself. The licence allow-list closed national ports and prose; a
quote in Hindi could not carry an English sentence; the coverage job neither counted a family's
shared facts nor capped a single call.

## Decision

1. **The provider layer sits below services.** The catalogue moves to `providers/catalogue`
   (types in `catalogue_types`, provider specs in `catalogue_specs`, so no file is over budget);
   the AI spend keys and defaults to `providers/spend_settings` (`load_spend_settings` reads only
   those `AppSetting` rows); the key store and the list of managed keys to `core/managed_keys` and
   `core/key_catalogue`; `AnswerModels` and `ScreenTools`, pure records of research protocols, to
   `research/`. `LAYER_IMPORTS` loses `providers -> services` and gains `services -> providers`.
   Passing settings and keys in from every caller was the alternative; it would have changed
   twenty-one call sites across five layers for a value only the provider layer reads.
   `services/ai_providers.py` re-exports `AiTask` for one round, for the voice lane's files.
2. **One adapter per service, key checks included.** `core/key_checks` holds the verdict and
   the one GET (`checked_get`, the statuses read as before); each adapter keeps its `check_key`
   beside its calls (Anthropic, Gemini, OpenAI and DeepSeek by base URL, ElevenLabs, Brave,
   OpenAlex, Semantic Scholar, CORE, Springer Nature, Elsevier), and `services/managed_secrets`
   only maps a key to its check or to its `KeyFormat`. The unused Gemini reply helpers are
   deleted.
3. **Rate limits are counted once, in Postgres.** Every limiter of `core/rate_limit.py` keeps
   its name, key, limit and window and is counted by `core/allowances.take_sliding`: the
   sliding-window counter (the current window's use plus the previous window's times the share
   still inside), read and taken in one statement on `AllowanceBucket`, whose `hourStart` now
   holds any window's start. Postgres over Redis: the table and its counting pool exist, and no
   new service or dependency is needed; the cost is one statement per counted read. Holders are
   an HMAC of the subject, never an address or an e-mail. A count that cannot be read refuses
   with a 60 s wait (a guard fails closed); a refund that cannot be written is logged. Every
   route awaits its attempt and refuses through `core/throttle_refusal.refuse_when_throttled`,
   the one 429 of [decision 0140](0140-voice-and-listen-kept-true.md), item 11.
4. **One scholarly pace for every process.** `core/paces` reserves each service's next slot and
   holds its `Retry-After` in `SourcePace`, and its requests in flight as expiring leases in
   `SourceLease`, both atomically on the database clock (migration 0065); `ScholarlyPacing`
   keeps a memory store for tests. Limits follow each service's documentation read on
   2026-11-22: Crossref in the polite pool with `mailto` (lists 3 a second, lookups 10, three at
   once; this replaces 0127's "no e-mail"), Semantic Scholar 1 a second with or without a key,
   CORE 10 a minute (the lowest registered tier, since a key's tier is unknown), OpenAlex 10 a
   second without a key and 30 with one, all at 80 %. Seats wait in the one queue up to
   `QUEUE_WAIT_MAX`; only a service's own 429 or 403 counts toward the two refusals that end it
   for an answer.
5. **The wait is in the answer's trail.** `sources/scholarly/pacing.answer_pace()` keeps, per
   answer and service, the seconds and requests that waited, the refusals and the requests not
   sent; `services/answer_trail.TrailLog` sends it as the stream's `paced` event after a `trail`
   `FOUND` or `READ` whenever it changed. A client that does not draw it ignores it.
6. **Open licences by family, not by spelling.** `open_licence` reads a national port
   (`CC BY 2.5 IN`, `Creative Commons Attribution 2.5 India`) and a prose statement naming an
   open licence as open; any restriction word (NC, ND, all rights reserved), a public domain
   limited to a place, or a URL that is not an open licence's keeps it closed.
7. **The coverage job.** A craft's coverage counts its sub-category's shared concepts' claims at
   half weight beside its own; each of the job's model calls is capped by the day's remaining
   budget, read just before the call (`RequestBudget`).
8. **Quotes in other languages.** `research/quote_renderings.english_renderings` renders foreign
   quotes into English through the TRANSLATE route and keeps a rendering only when
   `translation_problems`, read from the quote's own language, finds nothing;
   `sentence_violations(..., renderings=)` measures the overlap, the unrelated-source and the
   stance checks on it while the citation keeps the verbatim quote. The composer's side, asking
   for the renderings, is open in the register for the answer-composition lane.
9. **Reference sources.** Commons files are `SourceKind` `MEDIA` (PDF and DjVu stay `OTHER`;
   `MEDIA` is appended after `OTHER`, as every enum value added later is, is grouped with `WEB` in the trail and read by the history
   seats); every Wikipedia edition of Wikimedia's sitematrix is accepted, with ISO aliases;
   Wikidata decades, centuries and millennia are written as Wikibase counts them; Commons
   original dates are read from their common forms. PubChem keeps three hazard sources: the
   ECHA terms in `docs/DATA_SOURCES.md` are the limit, by choice.
10. **Scholarly full text.** Zenodo is an adapter (trust B, one lane at 30 a minute) and the
    open-copy locator for its DOIs; Europe PMC reads its open full text; Elsevier and Springer
    Nature full text is read for a DOI Unpaywall calls closed, by DOI prefix, stored for
    researchers only under its text-mining licence, silent without a key. Wiley is deferred
    (it serves PDF only).
11. **The web and the fetcher.** Parsing runs in two spawned worker processes of the fetcher's
    own, killed when the fetch's time limit fires and replaced (`ProcessPoolExecutor` cannot kill
    one stuck task without breaking the pool). robots.txt is read by RFC 9309's longest match; a
    rule not starting with `/` or `*` is read with one, which fails closed. The PDF cap counts
    what text extraction decodes, not images it never decodes. A page's trust is the longest
    domain of a reviewed list in `research/` (`sources` may not import `data`) by its final URL:
    zones give `B`, named records, standards bodies and journals `A`, any other page `C`. Plain
    http on the default port is read as https, never fetched over http; a URL too long to be its
    id is still refused, since `fetch` keeps no state. Every fetch writes its `WebFetch` row from
    the services layer through the fetcher client's recorder; bytes already stored add a row with
    an empty `sha256`; the nightly upkeep, the candidate sources and the picture client record
    theirs too. A body starting `%PDF-` declared as an octet stream is read as a PDF, nothing else
    is sniffed. One client serves each host and address within one fetch, never across fetches.

## Consequences

- One statement more per counted read: an anonymous public read or asset read, a sign-in, an
  ask. Under load each process may open up to eight counting connections to the pooler, and the
  web server's own reads queue on one row.
- A scholarly request makes about four statements (its slot, its lease, the release); response
  caches stay per process, since every request they let through is paced.
- Government, academic and museum pages rank above other web pages in research and in
  contributor-proposed sources, as the reviewed list says.
- CORE answers fewer requests of a large answer: at 10 a minute more of its queue is refused as
  unsent, which the trail now shows.
- The scholarly sources need migration 0065 before a pace or a lease can be stored; until it runs,
  a reservation refuses and the request is not sent.
- Publisher full text and quote renderings are built but not asked for until the planner and the
  composer call them (the register names both seams).
- The re-export at `services/ai_providers.py` goes in the next round.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/test_key_checks.py`,
`backend/tests/test_rate_limits.py`, `backend/tests/test_allowances.py`,
`backend/tests/db/test_sliding_limits_db.py`, `backend/tests/sources/test_shared_pacing.py`,
`backend/tests/db/test_source_paces_db.py`, `backend/tests/answering/test_answer_trail.py`,
`backend/tests/write_back/test_licences.py`, `backend/tests/write_back/test_coverage_enrichment.py`,
`backend/tests/db/test_coverage_backoff_db.py`, `backend/tests/research/test_quote_renderings.py`,
`backend/tests/planner/test_wiring.py` and `tools/tests/test_layers.py`, with the adapters' own
tests under `backend/tests/sources` and `backend/tests/fetcher`.
