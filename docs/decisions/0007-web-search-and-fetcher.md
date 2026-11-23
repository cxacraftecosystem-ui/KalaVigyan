# 0007. Web search adapters and the fetcher sandbox

Live research searches the web through SearXNG on the box, with Brave as the fallback, and reads
pages only through a separate fetcher sandbox. The sandbox reads https only, pins addresses, checks
redirects and robots.txt, caps size and time, and returns extracted text marked untrusted.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| The fetcher's process runs as a user of its own that sees no other user's processes | [decision 0173](0173-a-release-that-keeps-serving-and-its-way-back.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Live research tier T4 searches the open web and reads what it finds (PLAN section 0, 6). The
plan names SearXNG on the box as the primary search, Brave as the fallback when SearXNG returns
fewer than 3 hits or errors, and a separate fetcher process (`kv-fetcher.service`, infra
contract) that reads public pages without database or AWS credentials. The research contract
already had `FetchRequest`, `FetchedPage`, `FetchRefused` and the caps; nothing implemented
them, and nothing defined how the API process talks to the fetcher process.

## Decision

1. **Homes.** The fetcher is the package `backend/app/fetcher/` (run as `python -m
   app.fetcher`, which the systemd unit already looks for). It is a new layer that may import
   `sources`, `research` and `core` only (`tools/hygiene/layers.py`); it reuses the record rules
   in `sources/records` (dates, https URLs, whitespace) instead of copying them. The two search
   adapters and their fallback live in `backend/app/sources/web/`, the HTTP client for the
   fetcher in `sources/fetcher_client.py`, and the builder that reads the settings and the
   Brave key in `services/web_sources.py`. A test proves the fetcher process never imports the
   API settings, the database module, the services or boto3.
2. **Wire.** `POST /fetch` with a `FetchRequest` answers 200 and a `FetchedPage`, 403 and a
   `FetchRefusalBody` (`url`, `reason`, `detail`), or 502 and a `FetchFailureBody` (the
   `ExternalFailure` fields). `GET /health` answers 200. The paths, statuses and bodies are in
   `research/fetcher.py`, so the server and `FetcherClient` share one definition, and a seam
   test runs the client against the real ASGI app. The client allows the fetch's own time limit
   plus 5 seconds; an answer off the contract is an `ExternalFailure`, never a page.
3. **https only.** The contract's `HttpsUrl` and `NOT_HTTPS` stand: the task text said
   "http(s)", but plain http cannot be checked for the host it claims (no certificate), a
   redirect to http is the usual downgrade trick, and `EvidenceItem.url` is https only. Search
   hits on plain http are left out. Only port 443 is fetched; credentials in a URL are
   `BAD_URL`. International hosts are sent in punycode.
4. **Address pinning.** The fetcher resolves the host itself, refuses the whole fetch if any
   answer is not a global unicast address (Python's `is_global`, plus multicast, the cloud
   metadata addresses, and IPv4 embedded in mapped, 6to4 and NAT64 IPv6 addresses), and then
   connects to a vetted address by IP literal with the `Host` header and the TLS
   `sni_hostname` set to the original host. httpcore verifies the certificate against the SNI
   name, so the certificate is checked for the real host while DNS cannot be asked a second
   time (no rebinding window). A certificate failure is `TLS_MISMATCH`. Each hop and each
   robots.txt read gets a fresh client, because the connection pool keys on the IP origin and
   could otherwise reuse a TLS session verified for another host. IPv4 addresses are tried
   first; an unreachable address moves on to the next vetted one.
5. **Redirects** are followed by the fetcher, at most 3; each target is re-checked (https,
   port, address, robots) before it is requested. A fourth is `TOO_MANY_REDIRECTS`.
6. **robots.txt** (RFC 9309): fetched over the same guarded path for every host the fetch
   touches, cached per host for an hour (at most 1,024 hosts) in the object the server holds.
   2xx is parsed with the standard library parser for the agent `KalaVigyan`; 4xx except 429
   allows everything; 429, 5xx, an unreachable server, an oversized or non-https robots file
   disallow everything and are not cached. A private address or the time limit while reading
   robots.txt stops the fetch with that reason.
7. **Caps.** The whole fetch, robots and redirects included, runs under one
   `asyncio.timeout(timeoutSeconds)` (`TIME_LIMIT`). A declared length over `maxBytes` is
   refused unread; a streamed body is cut the moment it passes the cap (`TOO_LARGE`). The
   request asks for `identity` encoding. At most 8 fetches run at once in the process.
8. **Extraction.** HTML: trafilatura (`favor_precision`, no comments, tables kept, no links or
   images), after dropping `script`, `style`, `noscript`, `template`, embedded objects, `svg`
   and anything `hidden`, `aria-hidden="true"` or styled `display:none` /
   `visibility:hidden`; metadata from trafilatura (title, authors split on `;`, date, licence,
   canonical URL, site name) and the `<html lang>`. PDF: pypdf, a pure-Python extractor (the
   plan's Docling is heavy and the task asked for a light one): the first `PDF_MAX_PAGES`
   pages, refusing past `PDF_MAX_DECOMPRESSED_BYTES` of page content (`PDF_LIMIT`), as well as
   pypdf's own decompression limits; encrypted PDFs without an empty password and PDFs with no
   text layer are `PARSE_FAILED`. Plain text is decoded with its declared charset or UTF-8.
   Parsing runs in a worker thread. A page with no main text is `PARSE_FAILED`. The parsers
   are the one place the fetcher catches every exception, because hostile documents raise
   anything; each becomes `PARSE_FAILED` naming only the exception type.
9. **Untrusted text.** Every extracted text and metadata string passes
   `research.untrusted.clean_untrusted_text`, which drops C0/C1 controls, bidirectional
   overrides and isolates, zero-width spaces, invisible operators, the byte-order mark and the
   Unicode tag block (the usual ways to hide instructions in a page), keeps ZWJ and ZWNJ (they
   change the spelling of Indic text), and collapses blank space. `untrusted_block(ref, label,
   text)` is the one way the composer may put retrieved text into a prompt: inside an
   `untrusted_source` element naming its id and label, with any copy of that tag inside the
   text defused so the block cannot be closed early. Nothing in the fetcher evaluates or runs
   anything it fetched.
10. **Web search.** `SearxngAdapter` (`searxng`, JSON API at `SEARXNG_URL`, `safesearch=1`,
    `freshnessDays` mapped to the narrowest `time_range` that covers it, the date filter of
    decision 0005 then applied) and `BraveAdapter` (`brave`, `X-Subscription-Token`, at most 20
    results, `safesearch=strict`, freshness as an explicit date window) are `T4`
    `SourceAdapter`s. Hits are `WEB_PAGE`, trust `C`, with no quotes (snippets are not
    verbatim). The id is `<adapter>:<https URL>`, so `fetch` needs no state; a URL too long for
    an id (`EVIDENCE_ID_MAX_CHARS` 500) is left out. `fetch` goes through the fetcher and
    returns `FULL_TEXT` with the page's final URL, metadata and `sha256` (in `externalIds`,
    matching `WebFetch.sha256`); a PDF is `OTHER`.
11. **Fallback.** `WebSearch` (`web`, `T4`) asks SearXNG first. With at least `min(3, k)` hits
    it answers them. Otherwise, when a Brave key is configured, it asks Brave and appends
    Brave's hits that are new by `source_key`. A SearXNG error with no Brave key is raised; both
    failing raises Brave's failure chained to SearXNG's; a Brave failure after a few SearXNG
    hits keeps those hits and logs a warning. `fetch` goes to the adapter named by the id. No
    Brave key means no Brave adapter, without a warning (PLAN 17.1a).
12. **Shared rules moved down.** `failure_kind(status)` and `RETRYABLE_KINDS` moved from
    `sources/http` to `core/errors`, because the fetcher maps HTTP statuses the same way.
    `EVIDENCE_ID_MAX_CHARS` names the 500-character id limit once (evidence and composer ids).
    `build_document` takes `truncated` so a fetcher-side truncation is not lost.
13. **Dependencies.** trafilatura 2.3.1 and pypdf 7.1.0 (latest on 2026-11-16).

## Consequences

- Settings gain `SEARXNG_URL` and `FETCHER_URL` (defaults are the box's loopback addresses).
- The answering service and the coverage job build the web adapters with
  `services.web_sources.web_sources(session, client)` and hold the result for the process.
- The fetcher's limits and known gaps are in the debt register.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
