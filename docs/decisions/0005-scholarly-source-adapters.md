# 0005. Scholarly source adapters

Live research reads OpenAlex, Crossref, Semantic Scholar, CORE, Europe PMC, arXiv and DOAJ, with
Elsevier and Springer Nature dormant without keys, through one `SourceAdapter` each in a new
`backend/app/sources/` package, and keeps Unpaywall as a locator only. Each adapter returns the text
its own record carries, grades trust from one table, paces itself below the service's limit and
never follows a redirect or logs a key.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| The contracts it names | [research.md](../contracts/research.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Live research (PLAN section 0, tier T3) needs one `SourceAdapter` per scholarly service
(`docs/contracts/research.md`): OpenAlex, Crossref, Semantic Scholar, CORE, Unpaywall, Europe
PMC, arXiv and DOAJ, plus Elsevier and Springer Nature adapters that stay dormant without keys
(PLAN 17.1a). Each has its own rate limit, key scheme and record shape. Live calls were made on
2026-11-16 to record fixtures and to confirm the shapes; several facts differed from the plan.

## Decision

1. **Home.** A new package `backend/app/sources/` (layer row: `sources`, `research`, `core`,
   `models`; `services` may import it). It holds what every HTTP source adapter shares
   (`http.py`: pacing, Retry-After, a short response cache, failure kinds; `records.py`:
   DOI, date, URL, markup and work-kind rules; `adapter.py`: the search and fetch skeleton) and
   one module per service under `sources/scholarly/`. Later Wikipedia, Wikidata, PubChem,
   SearXNG and Brave adapters reuse the same three modules. The plan's `websearch/` and
   `evidence/` names were not used: these are adapters for any source, not web search only,
   and `evidence` is reserved for the level rules.
2. **Unpaywall is a locator, not a `SourceAdapter`.** Its title search answered 410 Gone on
   2026-11-16 ("retired on 2026-09-18; use OpenAlex"), and its DOI record carries no abstract.
   It is kept for what only it gives: whether a DOI is open and where the legal copy is
   (PLAN 17.1a: publisher full text is fetched only for DOIs Unpaywall reports as closed). The
   contract gains `OpenAccessLocation` and `OpenAccessLocator` (`research/evidence.py`), with
   `OPEN_ACCESS_STATUSES` `GOLD`, `DIAMOND`, `HYBRID`, `BRONZE`, `GREEN`, `CLOSED`. Only https
   copy URLs are kept, so an open work may carry no URL.
3. **What fetch returns.** API adapters return the text their own JSON or XML carries:
   `ABSTRACT` for OpenAlex (rebuilt from the inverted index), Crossref (JATS reduced to text),
   Semantic Scholar, Europe PMC, arXiv, DOAJ, Elsevier and Springer Nature, and `FULL_TEXT` for
   CORE when its record has `fullText`, capped at `FETCH_TEXT_MAX_CHARS`. A record with no text
   is `ExternalFailure(kind="not_found")` naming what is missing, so the caller tries the next
   source. Open-access full text from a URL goes through the fetcher sandbox, not an adapter.
4. **Ids.** `openalex:W…`, `crossref:<DOI>`, `semantic_scholar:<paperId>`, `core:<id>`,
   `europe_pmc:<SRC>:<id>`, `arxiv:<id with version>`, `doaj:<32 hex>`,
   `elsevier:<Scopus id>`, `springer_nature:<DOI>`.
5. **Trust.** One table, `records.WORK_KINDS`: a journal article, book or chapter from a
   scholarly index is `A`; a preprint (arXiv, posted content), a repository copy (CORE, whose
   records do not say whether they were peer reviewed), a dataset, thesis or report is `B`;
   anything else is `C`. Each adapter maps its own type names onto these kinds.
6. **Search filters.** Crossref searches with `has-abstract:true`, because without an abstract
   nothing can be quoted. arXiv, DOAJ and Scopus get the query's words only (their query
   syntaxes treat `:`, `/` and brackets as operators); a query with no words is no hits.
   `freshnessDays` is applied after the call to every adapter alike: an item counts when the
   latest day its partial date can mean is on or after the cutoff; an undated item is left out.
7. **Bad records.** A record without an id or title, or one the contract model refuses, is left
   out of the results and logged at warning with the adapter, its position and the reason
   (never the raw record). One bad row does not fail a search.
8. **Rates.** Each adapter has its own `SourceHttp` with a minimum interval below the
   service's published limit: OpenAlex 0.1 s (its allowance is a daily budget: $1 a day with a
   free key, $0.10 a day shared per IP without one, about $0.001 a call, per the response's
   `meta.notice` on 2026-11-16), Crossref 0.2 s (polite
   pool, `x-rate-limit-limit: 10` per second seen), Semantic Scholar 1.0 s (1 request/s with a
   key), CORE 2.0 s (about 5 per 10 s, PLAN 6), Europe PMC 0.2 s (no published limit),
   arXiv 3.0 s (API terms: one request every three seconds), DOAJ 0.5 s (2 per second),
   Elsevier 0.2 s, Springer Nature 0.6 s, Unpaywall 0.1 s. A 429 or 503 with Retry-After of at
   most 10 s is waited out once; a longer one fails as `rate_limit` (retryable, with
   `retry_after`) and further calls fail without being sent until it passes; without the
   header the service is paused for `DEFAULT_BLOCK_SECONDS` (60).
9. **Cache.** Successful responses are kept for 600 s, at most 512 per service, keyed by URL,
   public parameters and headers. Keys are passed separately (`secret_params`,
   `secret_headers`) and never enter the key. The cache lives in the `SourceHttp` the caller
   holds, not in module state.
10. **Keys and contact.** `RESEARCH_CONTACT_EMAIL` (default `cxa.craftecosystem@gmail.com`,
    validated as an email at start-up) replaces `CROSSREF_MAILTO`: one address for OpenAlex
    `mailto`, Crossref `mailto`, Unpaywall `email` and the User-Agent. Keys come from the
    managed secrets (`services/scholarly_keys.py`). Without `CORE_API_KEY` CORE is left out and
    named in `ScholarlySources.unconfigured`; without their keys Elsevier and Springer Nature
    are left out silently (PLAN 17.1a). OpenAlex and Semantic Scholar run without keys at a
    shared, lower allowance.
11. **No redirects, no keys in logs.** The client does not follow redirects (custom key headers
    would follow a redirect to another host); a 3xx is a failure. `core/logging` now redacts
    `api_key`, `apiKey`, `insttoken` and `access_token` query values, because httpx logs
    request URLs at INFO and OpenAlex and Springer Nature take their keys in the query.
12. **Retry-After parsing** moved from `providers/retry_after.py` to `core/retry_after.py`, so
    the providers and the sources share one parser.

## Consequences

- The answering service and the coverage job can build every scholarly adapter with
  `sources.scholarly.registry.scholarly_sources(await scholarly_keys(session), client)` and
  hold the result for the process, so pacing and the cache are per process (debt register).
- Fixtures are recorded responses from 2026-11-16, trimmed to the fields the adapters read;
  CORE full text is cut to 3,000 characters. Two are not plain recordings (debt register).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
