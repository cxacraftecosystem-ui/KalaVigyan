# Technical debt register

What is knowingly below standard, why it was left, and what clears it. Add an entry in the same
change that takes the shortcut; delete it in the change that clears it. Engineers and reviewers read
it before changing an area.

| For | Read |
|---|---|
| Why an area is built the way it is | [decisions/README.md](decisions/README.md) |
| Where the work stands | [PROGRESS.md](PROGRESS.md) |
| The hygiene baseline of files and functions over budget | `tools/hygiene_baseline.json` |

```mermaid
%%{init: {"theme":"base","fontFamily":"Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif","themeVariables":{"fontSize":"15px","primaryColor":"#F2E9FE","primaryTextColor":"#1E1B2E","primaryBorderColor":"#9148D2","secondaryColor":"#FAEECD","secondaryTextColor":"#1E1B2E","secondaryBorderColor":"#CD9200","tertiaryColor":"#F3F1FA","tertiaryTextColor":"#1E1B2E","tertiaryBorderColor":"#A7A3BC","mainBkg":"#F2E9FE","nodeBorder":"#9148D2","nodeTextColor":"#1E1B2E","lineColor":"#AA69E9","textColor":"#857F9E","edgeLabelBackground":"#F9F5FF","clusterBkg":"#F9F5FF","clusterBorder":"#D6B6FB","titleColor":"#762CB1"}}}%%
flowchart LR
  S([A shortcut taken]) --> E[An entry<br/>what, why, what clears it]
  E --> C[The work that clears it]
  C --> D([The entry deleted<br/>in the same change])
  classDef accent fill:#762CB1,stroke:#5F1C93,color:#FFFFFF
  class E accent
```

Last reviewed: 2026-11-18.

## Infrastructure

### CloudFront to origin is plain HTTP

- **What:** CloudFront reaches nginx on the EC2 box over HTTP on port 80 (`docs/RUNBOOK.md`,
  `infra/terraform/cloudfront.tf`). The origin is protected by the CloudFront-only security
  group and the `X-Origin-Verify` header, but the hop between CloudFront and the box is not
  encrypted. The designer and documentation portals use the same pattern.
- **Why left:** TLS ends at CloudFront; there is no custom domain or origin certificate yet, and
  the pattern matches the portals so they can be changed together.
- **Clears it:** an origin certificate (custom domain with certbot, already installed and
  unused on the box) and `https-only` origin protocol, done for all three portals in one change.

### Turnstile keys pending

- **What:** `TURNSTILE_SECRET_KEY` (GitHub secret) and `TURNSTILE_SITE_KEY` (GitHub variable) are
  not yet issued for `kalavigyan.vercel.app`. With `APP_ENV=production` and either missing,
  email sign-up answers 503 and the sign-up page offers Google only
  (`docs/contracts/infra.md`, `backend/app/services/turnstile.py`).
- **Why left:** the Cloudflare widget has to be created by the owner.
- **Clears it:** create the widget, set both values; Deploy backend copies them to Parameter
  Store.

### The frontend can go live before the backend it needs

- **What:** Vercel deploys every push to `main` straight to production through its git
  integration, while Deploy backend waits for Backend checks. On 2026-11-18 release d51c504 failed
  its database tests, so the backend stayed on 31890bf while Vercel served the new craft page,
  whose `GET /api/crafts/{slug}/page` the old backend answers 404. The fix was promoting the
  31890bf build by hand (`vercel promote`). Promoting an older build does not stop the next push
  from taking the domain on the Hobby plan, so it was promoted again after the fix push, and the
  new build was promoted once the backend was healthy.
- **Why left:** found during that release; the frontend-checks and deploy workflows were not
  changed mid-release.
- **Clears it:** turn off Vercel's production deploys from git (`git.deploymentEnabled`) and have
  Deploy backend call a Vercel deploy hook after its CloudFront smoke step, with a frontend-only
  path that fires the same hook after Frontend checks when no backend file changed.

### Slow craft page builds hold database connections

- **What:** four concurrent readers exhausted the API's pool of 5 on 2026-11-19 (production E2E:
  `QueuePool limit of size 5 overflow 0 reached`, 500s from `/api/crafts/*/page`,
  `/shared-science`, `/region`, `/api/answers/config` and `/api/preferences/me`). The pooler now
  holds 30 and the API 12 (RUNBOOK, Connection budget), but a page build still holds its
  connection for seconds, so a classroom opening craft pages at once can queue behind them.
- **Why left:** the cure is to build pages ahead of the reader, which is decision 0101, item 11.
- **Clears it:** the nightly static pages of decision 0101, item 11. Re-run the production E2E
  with four workers after each step.

## Backend structure

### Python code over budget

- **What:** recorded in `tools/hygiene_baseline.json` on 2026-11-16: 12 files over 400 lines, 54
  functions over 40 lines, 9 functions with more than 5 positional parameters. The largest files:
  `backend/migrations/versions/0001_initial_schema.py` (2853), `etl/crafts/wikidata_link.py`
  (1121), `backend/app/api/routes/auth.py` (784), `backend/app/services/two_factor.py` (703),
  `etl/crafts/seed_claims.py` (642), `backend/app/providers/router.py` (566),
  `etl/crafts/aliases.py` (543),
  `backend/tests/db/test_db_flows.py` (464), `backend/app/services/knowledge_view.py` (502),
  `backend/app/services/managed_secrets.py` (496), `backend/app/services/ai_providers.py` (454),
  `backend/app/data/craft_master_loader.py` (433).
- **Why left:** most were ported from the designer portal with the same shapes so the portals
  stay mergeable; splitting them is a separate restructuring change.
- **Clears it:** split along responsibilities when a file is next changed; run
  `tools/hygiene_check.py --update-baseline` after each clean-up. The initial migration stays
  one file (migrations are not rewritten).

### Answer stream: gaps left on 2026-11-16 (decision 0012)

- **What:** (1) Cleared by decision 0016: the write-back runs as shielded work and finishes
  when the learner leaves; only a write-back still running 8 s into a shutdown is lost (logged).
  (2) `AnswerSentence`, `AnswerCitation`, `AnswerTrace` and `LiveCandidate` rows are not
  written; the `Answer` row has the plan, tiers and cited claim ids but no `costUsd`,
  `latencyMs` or `payload`. `VERIFIED` answers write no `Answer` row (`answerId` null).
  (3) The planner's stored search reads `PUBLIC` chunks only; the `RESEARCHER` ACL of
  researchers is not passed through. (4) `Citation.context` is always null (the passage around
  a quote is not stored with the citation). (5) The resolver holds its session while it embeds
  the question for the semantic step. (6) A researched answer is shown only after write-back,
  so the learner waits for the whole pipeline before the first sentence.
- **Why left:** the trace and answer-sentence tables, cost settlement per answer and chunk
  citations each widen the contract; this change wires the flow first.
- **Clears it:** write the answer rows and trace from the events already produced, with spend from the
  request id's `UsageEvent` rows; pass `RESEARCHER` to the stored search when the asker may
  read it; store the quote's surrounding passage on `ClaimSource`; embed before opening the
  resolver's session; send stored-claim sentences before write-back once the client can
  replace a sentence's citations.

### Figure post-check covers digits and formulas only

- **What:** `research/quotes.unsupported_figures` checks numbers written in digits and
  formula-like tokens with a digit. Number words ("three"), units (a sentence may say °F where
  the quote says °C), unit conversions and element-only formulas (`NaCl`) are not compared.
  PLAN 3.1 asks for numbers, units and formulas.
- **Why left:** the contract needed a deterministic rule before the composer lanes start; unit
  handling belongs with the pint normalisation of PLAN 3.1 step 5.
- **Clears it:** parse quantities with pint on both sides and compare values and dimensions;
  match number words; treat element-symbol sequences as formulas.

### Model catalogue sits in services, used by providers

- **What:** `providers/budget.py` and `providers/router.py` import `services/ai_providers.py`,
  `services/app_settings.py` and `services/managed_secrets.py`, so the adapter layer sits above
  services (decision 0001). `providers/budget.py` also imports `app_settings` inside a function.
- **Clears it:** move the catalogue into `providers/` (kept in the designer portal's shape) and
  pass settings and keys in from the caller.

### Provider calls outside the adapters

- **What:** `services/managed_secrets.py` probes provider endpoints over HTTP itself to test a
  key, and `services/ai_providers.py` still holds `ModelDeclined` and `gemini_reply_text`, which
  nothing calls. One adapter per external service is the rule.
- **Clears it:** give each adapter a key-test call used by `test_secret`, and delete the unused
  Gemini helpers.

### Rate limits are per process

- **What:** `core/rate_limit.py` keeps its windows in module-level memory, so each API colour
  and worker counts separately and a restart resets them. The same holds for the scholarly
  adapters' pacing, Retry-After pauses and response cache (`sources/http.SourceHttp`): each
  process that builds `scholarly_sources` paces itself, so two workers can together exceed a
  service's interval.
- **Clears it:** a shared store (Redis is on the box) behind the same functions.

### An answer piece whose answer was deleted reads as curated for supersession

- **What:** decision 0090 item 2 keeps "a piece no answer made" from being superseded, and
  `services/piece_store._supersede` tells such a piece by `createdFromAnswerId` being null. That
  column is set null when an answer is deleted, so a reader's piece outlives its answer as if it
  were curated. The craft page tells them apart by the curated claims a piece cites (decision 0096
  item 2), but supersession and reuse order (`piece_reuse.answered_first`) still read the id alone.
- **Why left:** the craft page's merge is one module that edits no other file (decision 0096).
- **Clears it:** one shared rule for "curated piece" (every cited claim curated and no answer id)
  used by `_supersede`, `answered_first` and the page merge, with a test that deletes an answer.

### Craft descriptor embeddings are not filled

- **What:** `app/scripts/embed_craft_descriptors.py` now runs after the seeds and the craft sync
  on every release and first in the daily Coverage enrichment run (decision 0016), but it fills
  only missing vectors, so a craft whose aliases change later (portal sync, enrichment) keeps
  its old vector.
- **Why left:** detecting a changed descriptor needs a stored hash per craft, a schema change.
- **Clears it:** store a hash of `descriptor_text` per craft and embed again when it differs.

### Craft matching has no evaluation set

- **What:** PLAN 5.2's gate (300 match cases, top-1 at least 95%, in CI on seeded fixtures) does
  not exist. The resolver's weights, `FUZZY_MIN_SIMILARITY` 0.85, `SEMANTIC_MIN_SIMILARITY` 0.6
  and the hand list `GENERIC_TOKENS` were set from about 30 questions tried by hand against the
  master list (decision 0004). The model choice among the top 5 (PLAN 5.2 step 6) is now the
  understanding step's `PLAN` call (decision 0031), unmeasured as well.
- **Why left:** the cases have to be written from real questions in several scripts; owner
  direction is 1-2 known-answer checks at a time, not a large suite on every change.
- **Clears it:** collect the cases as answers are corrected, run them in Backend checks, and tune
  the constants and the understanding prompt against them.

### Scholarly adapters: gaps left on 2026-11-16 (decision 0005)

- **What:**
  - The answering service and the coverage job call `scholarly_sources` through
    `live_sources`; the API rebuilds them every 600 s (`LiveSourcesStore`), which resets each
    adapter's pacing and cache.
  - Two fixtures are not plain recordings. Semantic Scholar's search answered 429 to every
    unauthenticated try, so `tests/sources/fixtures/semantic_scholar_search.json` wraps two
    recorded paper records in the search envelope; and no `SPRINGER_NATURE_API_KEY` exists, so
    `springer_nature_search.synthetic.json` is hand-written from the documented shape (only its
    401 is recorded).
  - The configured `ELSEVIER_API_KEY` may search Scopus but not read abstracts (the abstract
    record has no `dc:description`, and `view=META_ABS` answers 401), so `elsevier` fetch is
    `not_found` for every record until an institutional token is set.
  - Publisher full text (Elsevier article, Springer Nature JATS, Wiley TDM) for DOIs Unpaywall
    reports closed (PLAN 17.1a) is not built; nor are the Zenodo adapter (PLAN 17.1) and
    Europe PMC full text.
  - OpenAlex without a key shares $0.10 a day per IP; the box will exhaust it quickly.
- **Why left:** keys, an institution token and the callers do not exist yet.
- **Clears it:** the owner sets `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` and
  `SPRINGER_NATURE_API_KEY` (and an Elsevier institution token); record the missing fixtures
  then; add the publisher full-text adapters behind the Unpaywall `CLOSED` check.

### Reference adapters: gaps left on 2026-11-16 (decision 0006)

- **What:**
  - The per-process pacing above applies to `reference_sources` too.
  - Wikidata time values coarser than a year (decade, century) are left out of the item text,
    and the Commons `published` date is empty unless the original date is ISO.
  - PubChem hazards keep at most three reporting sources; the ECHA terms allow non-commercial
    reuse only, which suits the IIT research use but would need review for any commercial use.
  - Commons media use `SourceKind` `OTHER`: the enum has no image or media kind.
  - `WIKIPEDIA_LANGUAGES` is English and Indian languages only; a learner writing in another
    language gets `InvalidInput` from the Wikipedia adapter.
- **Why left:** no caller yet needs other wikis; a media source kind needs a migration of the
  `SourceKind` enum.
- **Clears it:** add a `MEDIA` source kind with its migration when the media lane stores Commons
  files; widen the language list when the planner asks for it.

### Web search and fetcher: gaps left on 2026-11-16 (decision 0007)

- **What:**
  - Parsing runs in a worker thread; when the time limit fires, the fetch is refused at once but
    the thread keeps parsing until it ends. A hostile document can hold a thread and memory
    past 10 seconds (bounded by the 3 MiB body, pypdf's limits and the unit's 768 MB cap).
  - robots.txt is read with the standard library parser, which applies the first matching rule
    rather than RFC 9309's longest match. It can refuse a page an `Allow` line permits (fails
    closed, never the reverse for one agent group).
  - The PDF decompression cap counts page content streams only; images and fonts are left to
    pypdf's own limits.
  - Every web page is trust `C`; a government, museum or university site is not yet ranked
    higher.
  - Search hits on plain http and URLs longer than about 490 characters are left out (ids are
    the URL and at most 500 characters).
  - The SearXNG and Brave fixtures are hand-written to the documented response shapes, not
    recordings: SearXNG runs only on the box and no Brave key was available on the laptop.
  - Only the planner calls the web search and the fetcher; `WebFetch` rows are not written;
    the fetcher service has not run on the box.
  - Each hop opens a fresh client (no connection reuse), which costs one TLS handshake per hop.
- **Why left:** no caller yet; a kill-able parser needs a subprocess pool; ranking by domain
  needs a reviewed list; recording needs the box or a key.
- **Clears it:** run the parsers in a process pool that can be killed on timeout; switch to a
  longest-match robots parser; record SearXNG and Brave fixtures from the box; add a reviewed
  domain trust list; write `WebFetch` rows from the answering service; smoke-test
  `kv-fetcher` on the box after the next deploy.

### Stored-knowledge retrieval: what is left (decision 0008, round 4)

- **What:** round 4 cleared stamps per embedding model with re-embedding, cleared vectors on a text
  change, embedding after the seeds on every release, the Indic text ranking and the seed import's
  passages (`docs/contracts/retrieval.md`). Left: knowledge pieces carry no stamp, and the
  candidate gates' neighbour search and the piece store's reuse distance compare vectors without
  it; the Wood Handbook import has no passages, because the repository holds no text of the cited
  edition (FPL-GTR-190); the HNSW indexes on `Claim.embedding` and `Chunk.embedding` are unused by
  the exact craft-scoped scan.
- **Clears it:** stamp pieces and filter the gates' and the piece store's neighbours on the current
  model; vendor the pages of FPL-GTR-190, or give FPL-GTR-282 its own source and re-cite the wood
  claims after a quote check; use or drop the HNSW indexes once a scope is large enough to need
  them.

## Checks not automated yet

- **Nesting depth** (budget 3) is not measured by the hygiene check.
- **Frontend size budget** (about 150 lines per component file): 33 `.tsx` files are over it on
  2026-11-16, the largest `components/ui/SearchableSelect.tsx` (1243),
  `app/(protected)/admin/access/page.tsx` (813), `components/forms/DateTimeField.tsx` (743).
  Many are ports from the designer portal.
- **Frontend import boundaries** are not linted.
- **Geo ETL tests** (`etl/geo/tests`) run, with ruff, only at the start of a Geo ETL dispatch
  (decision 0043); a push that changes `etl/geo` is not tested until the next dispatch.
- Clears it: a lint rule set for size and boundaries with a baseline for the existing files, a
  nesting count in `tools/hygiene/budgets.py`, and a push-triggered test job for `etl/geo`.

### Planner and tiered research: gaps left on 2026-11-16 (decision 0009)

- **What:** (1) `LiveCandidate`, `WebFetch` and
  `AnswerTrace` rows (queries and providers per answer, PLAN section 6) are not written; the
  answering service (`services/answering.py`) stores only the `Answer` row and its claims.
  (2) The pack holds documents, not quotes: the `WEB_READ` reader that extracts verbatim quotes
  for the composer is not built. (3) Coverage runs one stored search per facet, each embedding
  its target (up to eight embedding calls per question). (4) References are followed only as
  DOIs written in the text, through Crossref, which returns abstracts only; links in pages and
  reference lists without DOIs are not followed. (5) Facet coverage counts claims that share a
  word with the target; it does not judge whether they answer it. (6) Every query runs on every
  source of its tier, including Commons and PubChem for questions they cannot serve (each
  answers quickly with no hits).
- **Why left:** the `WEB_READ` reader and the trace tables are the next lanes; a better coverage
  judgement needs the known-answer checks to calibrate against.
- **Clears it:** the answering service writes the trace and candidate rows; the reader turns
  documents into quoted evidence; embed the facet targets in
  one batch; follow reference lists through OpenAlex `referenced_works` when that adapter
  exposes them; route facet types to the sources that can serve them once the checks show
  which do.

### Composer: gaps left on 2026-11-16 (decision 0010)

- **What:** (1) A read document longer than 4,000 characters gives the composer nothing until the
  `WEB_READ` reader fills its item's quotes. (2) Stored passages (T2 `ChunkHit`) are not composer
  candidates: a sentence can cite a claim or live evidence, and the stream's `Citation` names a
  claim. (3) A stored claim is offered as its text alone; its citations' quotes and sources are
  not in `ClaimHit`, so the model cannot quote the source behind a claim and the label says only
  "stored claim". (4) `ResearchSummary.services` lists searchers that returned evidence or
  failed, not every searcher asked.
- **Why left:** the reader and the answering service are separate lanes; chunk citations and
  claim sources need the stream and retrieval contracts to grow together.
- **Clears it:** the reader fills quotes for long documents; the answering service builds
  `compose_request` from the pack, joins each claim's sources and quotes from the database into
  its candidate, and records which searchers ran in the pack; add a chunk candidate kind with a
  source-only citation when the stream allows one.

## Live research write-back (decision 0011)

### The quote overlap reads English passages only (decisions 0013, 0023)

- **What:** answers are composed and checked in English and translated afterwards (decision
  0023), so the overlap holds for English sources. `UNRELATED_QUOTE` still compares the sentence's
  English content words with its quotes' words (`backend/app/research/quotes.py`,
  `quote_overlap`), so a sentence resting only on a Hindi Wikipedia or Wikidata passage, found by
  a native-language query, is dropped; such passages count only beside an English passage that
  carries the wording.
- **Why left:** the owner kept every existing check unchanged; a cross-language overlap needs a
  checked translation of the quote first.
- **Clears it:** translate a non-English quote into English with the TRANSLATE route, check it
  with `translation_problems`, and compute the overlap against that rendering while the citation
  keeps the verbatim quote.

### Licence allow-list is by string

- **What:** `open_licence` matches licence names and canonical URLs; national ports of CC
  licences (for example `CC BY 2.5 IN`) and licences named only in prose are closed, so their
  full text is stored for researchers only (`backend/app/research/licences.py`).
- **Why left:** closed is the safe side; the common spellings from the adapters are covered.
- **Clears it:** add each further spelling with a test when a source shows it.

### A re-chunked source can move a citation's chunk

- **What:** `ClaimSource.chunkId` points at the chunk that held the quote when it was written.
  When a live source is read again with different text, `replace_source_chunks` updates chunks
  by ordinal, so an older citation's `chunkId` may then point at a chunk that no longer holds
  its quote (`backend/app/services/live_source_store.py`). The quote and source stay correct.
- **Why left:** nothing reads `chunkId` yet; the quote is the citation.
- **Clears it:** re-point citations of a re-chunked source with `chunk_for_quote` in the same
  transaction, or clear `chunkId` for chunks whose text changed.

### Coverage counts only a craft's own concepts

- **What:** `least_covered_crafts` and the open-facet test count claims on concepts whose
  `craftId` is the craft; claims on the sub-category's shared concepts, which stored retrieval
  also reads, do not count (`backend/app/services/coverage_selection.py`).
- **Why left:** shared family claims are general; the job's purpose is craft-specific coverage.
- **Clears it:** weight shared claims (for example half) once family pages exist.

### The coverage job has no per-call spend cap

- **What:** the daily budget is checked before each question; a single question's planner,
  reading and composer calls are not capped, so a run can pass the day's budget by one question
  (`ENRICHMENT_QUESTION_RESERVE_USD` $0.25 is the assumed size). `router_structured_model` has
  no `request_budget_usd` parameter (`backend/app/providers/structured.py`).
- **Why left:** the overshoot is bounded and small, and production no longer runs the job (no
  monthly ceiling is set either, decision 0093).
- **Clears it:** pass the remaining day budget as `request_budget_usd` through
  `router_structured_model` and `router_embedder`.

## Science, region, voice and media contracts (decision 0014)

### Contracts ahead of their producers

- **What:** the models, golden files and contract tests exist; the process (decision 0015),
  region (decision 0016), voice (decision 0017) and media (decision 0018) routes produce theirs,
  and `services/naming.py` with `shared/naming-golden.json` names media files. The media
  sharing route is still unserved.
- **Why left:** decision 0014 is the contract lane; sharing belongs to the governance lane.
- **Clears it:** the governance lane serves `POST /api/media/assets/{id}/sharing`.

### ElevenLabs behaviour not yet verified

- **What:** the voice binding rests on `custom_llm.request_headers` substituting
  `{{system__conversation_id}}` and on `custom_llm.api_key` arriving as a bearer, neither on
  ElevenLabs' official pages; also unverified are the URL suffix, custom-LLM tool calls reaching
  `end_call` and client tools, Hindi in agents, CSP hosts and the plan's retention minimum
  (`docs/contracts/voice.md`). Relay text to speech cannot run with zero retention
  (`enable_logging=false` is enterprise only).
- **Why left:** only a recorded round trip against a test agent can settle them (PLAN 10.1). Lane
  0017 built the agent path on the contract's assumptions (`custom_llm.url` ending `/api/voice/llm/v1`,
  the bearer, the header template) and its adapter tests on the documented response shapes; the
  spike workflow is not written, because it calls the real account.
- **Clears it:** the spike on GitHub Actions with a test agent made by
  `app/scripts/provision_voice_agent.py`, replacing the fixtures in `backend/tests/voice/fixtures`
  with recorded responses; `voice.transport` stays `RELAY` until it passes. Retention: an
  enterprise plan, or the Gemini voice for relay speech.

### Contract tests read files their workflow does not watch

- **What:** `backend/tests/contracts` reads `etl/geo/geo_etl/catalog.py`, `infra/terraform/*` and
  `docs/PLAN.md`, but Backend checks do not run on a push that changes only those. Adding them to
  the push filter would make such a push deploy the backend. The frontend side is closed: Frontend
  checks (which deploy nothing) watch `backend/app/models/enums.py`, `backend/app/schemas/**`,
  `backend/app/core/roles.py`, `shared/roles.json` and `infra/terraform/variables.tf`, the files
  its unit specs read (decision 0022).
- **Clears it:** a separate contract-check job (or a paths filter on pull requests only) that runs
  `tests/contracts` when those files change.

### Region golden values are hand-written

- **What:** the district numbers in `shared/region.craft.golden.json` and
  `shared/region.layer.golden.json` are illustrative shapes for tests, not ETL output; only the
  dataset rows are real, and the layer's classes and version are computed from the hand-written
  numbers (decision 0016).
- **Clears it:** when the full `geo-etl` load exists, regenerate the layer fixture's values from
  it in a reviewed change.


## Region profile and map layers (decision 0016)

### A district place carries every stored value

- **What:** `GET /crafts/{slug}/region` sends every stored value of a district (about 300 with
  the full load: monthly normals, yearly forest loss, percentiles and uncertainty bounds) and
  every aggregable series of a state, and a craft practised in many states sends one such place
  per state. The panel lists them all.
- **Why left:** the contract (decision 0014) asks for every row; choosing a headline set is a
  product decision.
- **Clears it:** a curated set of headline variables per facet in the contract (the layer
  registry is a start), with the rest behind a "More" view or left to the map.

### State aggregates are computed per request

- **What:** each region request groups the state's district rows in Postgres (one grouped query
  per request over the states it shows); nothing is cached.
- **Why left:** correct and fast enough for a handful of states; a cache needs invalidation on
  every geo load.
- **Clears it:** a `StateEnvValue` table filled by `etl/geo/load.py` after each load, or a
  materialised view refreshed by it.

### Two region rules mirror how the geo ETL writes rows

- **What:** `geo/records.LITHOLOGY_TWIN_PREFIX` assumes GLiM writes each class share both as
  `lithology_<code>` and as a `DistrictGeology` row, and `geo/aggregation.ABSENT_MEANS_ZERO`
  that GLiM shares and MRDS per-commodity counts exist only where present. Migration 0005 also
  copies the GLiM legend (`geo_etl/layers/geology.GLIM_CLASSES`) to name rows loaded earlier.
  No test reads the ETL to keep them in step.
- **Clears it:** have the ETL write the share once with its name and write zero rows (or a
  coverage row per dataset), then drop both rules; or a contract test that runs the GLiM and
  MRDS row builders on a fixture.

### Dataset links of rows loaded before migration 0005

- **What:** `EnvDataset.url` is filled only by a geo load after the migration, so until the next
  `geo-etl` run with `load` the region and layer answers send `url: null` for every dataset.
- **Clears it:** the next Geo ETL run with `load` (any dataset), which upserts every dataset row.

### States of practice are matched in two places

- **What:** `geo/places.practice_states` and `services/knowledge_view.craft_locations` both
  match `Craft.stateOfPractice` to `AdminState.name` case-insensitively; only the region skips
  `All India` explicitly and logs other unmatched names.
- **Clears it:** have the profile use `practice_states` (or an `AdminState` lookup in one service)
  the next time `knowledge_view.py` is split.

## Geo ETL state gaps (decision 0027)

### An unreachable tile reads as an absent one

- **What:** `etl/geo/geo_etl/raster.exists` turns any open error, a timeout or a server error as
  much as a 404, into "no such file", caches that answer for the process, and `raster.read`
  mosaics only the tiles it found. A WorldCover, Hansen or Copernicus DEM district whose tile did
  not answer is computed from the tiles that did, with no failure listed; when the tiles under its
  polygon did not answer but another tile in its padded bounds did, it comes back without valid
  cells and, since the addendum to 0027, counts as accounted for, even as a state's only district
  (when no tile answers, the read fails); a CHELSA or CHIRPS file
  that did not answer fails its step for the whole shard (which now fails the part). After the
  CHIRPS year lookup, file reads still rely on GDAL's own retries (7 tries of up to 120 s per
  request in the workflow), so a stalled server can still hold a job for hours.
- **Why left:** run 43884310432's gaps all came from the district shapes; telling an ocean tile
  from an unreachable one needs each layer's tile index, a change to every tiled layer.
- **Clears it:** probe tiles over HTTP as the CHIRPS lookup does (only 404 means absent, other
  errors retried then raised), or list each dataset's tiles once and treat a listed tile that
  cannot be read as a failure; cap GDAL's retries with an overall deadline per file.

### A grid read as nodata everywhere counts as "no valid cells"

- **What:** since the addendum to 0027, `coverage_of` trusts `Result.districts_without_cells`. A
  read that returns a grid of nodata (a SoilGrids WCS answer of masked cells for a whole state, a
  grid registered in the wrong place) lists every district without cells, accounts for every
  state, and the part passes with no rows. Before, it lost those states and failed.
- **Why left:** telling such a read from a real gap (Lakshadweep in GLiM, Mumbai in SoilGrids)
  needs a reference the layers do not have; a guard on "no valid cell in the whole grid" would also
  fail a run that selects only Lakshadweep.
- **Clears it:** fail a step whose grid holds no valid cell at all while the selection has land
  cells in an independent mask (for example the Copernicus DEM or WorldCover land fraction), or
  keep a reviewed list of districts expected without cells per dataset and fail any other.

### A silent district does not fail the part when its state has another district accounted for

- **What:** a selected district with no row, no no-cells listing and no failure is listed only
  under `districtsWithoutValues`; its state is lost only when none of its districts is accounted
  for. That includes a state with no rows at all where one district is listed without cells and
  another is silent, which the rule before the addendum failed. Every raster path now lists its no-cells districts, so such a district means a defect, and
  can only be found as `districtsWithoutValues` minus `districtsWithoutCells` minus the failed
  districts.
- **Why left:** the addendum to 0027 keeps the state-level rule the owner asked for; failing on a
  single silent district is a stricter rule not yet agreed.
- **Clears it:** list such districts under their own key in the part JSON and fail the part when
  it is not empty, or at least lose a state without rows unless every one of its districts is
  listed without cells.

### Each shard resolves the CHIRPS period on its own

- **What:** every CHIRPS extract job calls `latest_year` itself. Should CHC publish a new annual
  file while a run is going, shards could end on different years, and the combined table would
  hold two periods for one dataset; `combine` keeps the last dataset row it reads.
- **Why left:** CHC publishes once a year and a run takes under an hour.
- **Clears it:** resolve the year once in the workflow's plan job, pass it to every shard
  (a `--chirps-last-year` option), and have `combine` refuse parts of one dataset whose rows
  differ.

## Craft page and region panel (decision 0019)

### The profile still sends stages and science the page no longer reads

- **What:** `GET /crafts/{slug}/profile` (`services/knowledge_view.craft_profile`) still returns
  `stages` (with the uncited `durationText`) and an always-empty `science`; the craft page now
  reads the process route instead, and uses `stages` only to keep the profile's citation numbers.
- **Why left:** lane 0019 does not edit backend files.
- **Clears it:** drop both fields from the profile route and `CraftProfile` in one change, and
  number sources from the overview, materials and the process route.

### Map layer values carry no district names

- **What:** `MapLayer.values` is keyed by LGD code only and the client holds no district names, so
  hovering or tapping a district on `/map` shows its value and not its name
  (`components/map/MapLayerView.tsx`).
- **Why left:** the region contract (decision 0014) fixes the layer body, and the backend is
  another lane's.
- **Clears it:** add district names to `MapLayer` (or a cached districts route) with the contract,
  golden file and both tests, then show "Kachchh · pH 8.1".

### Craft page and map layers not yet seen running

- **What:** the timeline, region panel and choropleths are checked by typecheck, lint and unit
  specs of their pure rules, not in a browser: there is no React renderer in the unit project and
  nothing runs on the laptop. Their contrast, wrapping at phone width and the KaTeX rendering of
  real reactions are unverified.
- **Clears it:** the Production build job, then a signed-in smoke spec (craft page tabs, `/map`
  with `?layer=`) with route fixtures from `shared/` at desktop and phone widths, and screenshots
  once the 0015-0016 routes are deployed.

### The boundary caption has two homes

- **What:** maps drawn without the layer list (the craft page) print the caption from
  `components/map/MapAttribution.tsx`; `/map` prints the server's `boundary.caption`
  (`research/datasets.BOUNDARY_CAPTION` since decision 0042). The two are equal today. Explainer
  map blocks carry the server's caption in the block.
- **Clears it:** have the craft page read the caption from `GET /map/layers` (or a shared
  boundary route) and delete the client constants.

## Voice backend (decision 0017)

### Voice in other languages is checked by text only (decision 0025)

- **What:** voice offers all thirteen answer languages from the ElevenLabs documentation, not from
  calls. Scribe's published accuracy is Scribe v2's, and Urdu's band is moderate (25-50% word error),
  so an Urdu question may often be misheard. The fixed spoken phrases in `voice/phrases.py` were
  written by the lane and not read by native speakers. In `AGENT` nothing yet tells the agent a
  session's language: the token takes none and client overrides are off, so the agent hears in its
  own language until `language_detection` switches; the presets are not provisioned.
- **Why left:** no provider call with a real key from the laptop, and no native reviewers in reach.
- **Clears it:** the spike records one relay turn per language and one agent call in Hindi; a
  native reader per language signs off the phrase table; if Urdu misses too often, drop `ur` from
  `STT_LANGUAGE_CODES` (voice then stops offering it) or try `scribe_v3` with Hindi as a
  `secondary_language_codes` hint; the spike decides whether the agent gets an `agent.language`
  override or one agent per language.

### The voice pack is claims only, ranked by words

- **What:** PLAN 10.3 asks for the T0/T1 pack with embeddings plus T2 passages; the pack is the
  craft's visible claims ranked by shared word stems (`voice/pack.ranked_claims`), without vectors
  or corpus chunks.
- **Why left:** a query embedding per turn is a second model call before the first sentence.
- **Clears it:** prefetch the claim vectors with the pack and embed the question in parallel with
  the filler; add T2 chunks as `EVIDENCE` candidates with their verified quotes.

### Voice upkeep rides the daily Coverage enrichment run

- **What:** purging transcripts after 30 days, closing calls left open and reconciling agent calls
  run as the first module of the daily box job in `coverage-enrichment.yml`; `kv-worker`
  (`app/worker.py`, decision 0018) runs only the media queue.
- **Why left:** the worker arrived with the media lane, which did not take on voice scheduling.
- **Clears it:** move `app.scripts.voice_upkeep` into the worker's schedule.

### Voice billing approximations

- **What:** a relay upload's floor is its bytes at 5 000 a second; compressed audio is not decoded,
  so a client encoding below the dock's 32 kbit/s (Opus goes down to 6 kbit/s) gets up to about
  6.7 times the floor's seconds of speech to text inside the 300 000-byte ceiling, still within
  the day's seconds. Parallel uploads are allowed; each holds its own minute under the row lock,
  so they cannot pass the day's seconds. An agent call cannot be hung up from our side: after its
  row ends the ElevenLabs call can run to the agent's 600 s, which reconciliation charges (the user
  may go below zero for that day). Refund and settle rows count on the day they are written, not
  the call's day.
- **Why left:** decoding needs ffmpeg on the box; ending a call needs an ElevenLabs endpoint the
  spike has not confirmed. Each is bounded by the day's seconds, the turn and replay limits and
  the 40-turn cap (decision 0022).
- **Clears it:** decode the upload's duration (ffprobe) before speech to text and bill that; end
  the ElevenLabs conversation when the row ends, once the spike shows how; date settlement rows to
  the call's day.

### Voice state held per process

- **What:** claim packs (10 minutes), relay reply audio (15 minutes, 32 replies) and the ElevenLabs
  reachability (1 minute) are held per API process. A reply missing from that process's cache
  (another worker, a handover, eviction) is synthesised again, only while the call is live or two
  minutes after it ended, billed under its own key and limited to 60 replays in 10 minutes
  (decision 0022).
- **Clears it:** keep reply audio in the media bucket under a short lifecycle rule, so a cache miss
  never calls text to speech.

### Voice settings have no screen

- **What:** `voice.transport`, `voice.max_live_sessions` and `voice.voice_id` are `AppSetting` rows set
  in SQL (`docs/RUNBOOK.md`); `voice.max_live_sessions` defaults to 5, an assumption about the bought
  plan's concurrent-call limit.
- **Clears it:** a master-admin voice block in Settings, and the limit from the plan once bought.

### A hand-written multipart reader

- **What:** relay uploads are read by `api/multipart_form.py` rather than `python-multipart`.
- **Why left:** the lockfile cannot be regenerated on this machine (no `uv`), and one field is
  enough.
- **Clears it:** add `python-multipart` with `uv add` where `uv` runs and read the form with
  Starlette's limits.

## Voice UI (decision 0020)

### The voice dock has not run in a browser

- **What:** the dock, orb, microphone recording, speech playback and the ElevenLabs WebRTC call
  are checked by typecheck, lint and unit specs that drive `VoiceCall` with fakes; no browser has
  recorded, played or joined a LiveKit room, and the dock's layout above the bottom island, its
  contrast in both themes and the transcript at phone width are unverified. The `AGENT` path also
  assumes the server writes each turn to the transcript as it is spoken.
- **Clears it:** after lane 0017 deploys, a signed-in smoke spec with a fake microphone
  (`--use-fake-device-for-media-stream`) on `RELAY`, route fixtures from `shared/` at desktop and
  phone widths, then one real `AGENT` call once the spike passes.

### The dock asks for a bit rate it cannot enforce

- **What:** the relay recorder asks `MediaRecorder` for the session's `audioBitsPerSecond`
  (32 kbit/s) and sends a turn at nine tenths of `maxAudioBytes`; a browser that ignores the asked
  rate (Safari's AAC is the likely case, unverified) sends shorter turns than a minute.
- **Clears it:** measure the recorded rate per browser in the smoke spec; if one ignores it, raise
  that type's byte ceiling in the contract with its measured rate.

### Audio worklets need `blob:` scripts

- **What:** `@elevenlabs/client` loads its AudioWorklet processors from `blob:` and `data:` URLs.
  The CSP has no `script-src` yet, so they load; the strict CSP of PLAN 15 would block them.
- **Clears it:** copy `node_modules/@elevenlabs/client/worklets/*` into `public/` at build time
  and pass `workletPaths` from `lib/elevenLabsAgent.ts`, in the change that adds `script-src`.

## Media UI (decision 0021)

### Sharing waits for the governance lane

- **What:** the client draws Share, Withdraw and Stop sharing only when an asset carries
  `sharing` (`docs/contracts/media.md`, Sharing), which no backend sends, and calls
  `POST /api/media/assets/{id}/sharing`, which no route serves. A second professor cannot reach
  an asset awaiting sign-off, because a job is visible to its requester only.
- **Why left:** lane 0021 does not edit backend files; the contract gave the route to the
  governance lane.
- **Clears it:** the governance lane adds `sharing` to `MediaAssetView` for `SHARE_MEDIA` holders,
  serves the route with the rules of the contract, adds the second professor's queue, and adds a
  golden asset with `sharing` that both contract tests read.

### Shared illustrations reach other readers only through the cache

- **What:** a `CRAFT_SHARED` asset is shown to another reader only when they press Image on the
  same stage and the prompt hash matches; no route lists a craft's shared assets, so the stage
  does not show them on arrival.
- **Clears it:** a route listing the shared assets of a craft's stages (with fresh URLs), read
  by the media store and drawn by `components/craft/StageMedia.tsx` before the buttons.

### The client's wait limit restates backend constants

- **What:** `MEDIA_WAIT_LIMIT_SECONDS` (900, `frontend/lib/mediaView.ts`) is three attempts of
  `JOB_TIMEOUT_SECONDS` (240) plus a queue's wait; a change to the backend's timeout or retries
  does not move it.
- **Clears it:** a deadline on the job view (for example `giveUpAt`) that the client reads
  instead, with the contract, golden file and both tests.

### No style hint

- **What:** `MediaJobRequest.styleHint` is always sent as `null`; the UI has no field for it.
- **Clears it:** a short field on the stage's media row (filtered with the contract's banned
  words, refusals shown beside it) when the owner asks for one.

### Media UI not yet seen running

- **What:** the buttons, progress, figure, downloads and sharing steps are checked by typecheck,
  lint and unit specs that drive the store with fakes and test the rules on the golden files; no
  browser has drawn an asset, played a video, saved a blob from the bucket (its CORS allows
  `https://kalavigyan.vercel.app`) or loaded every page under the new `img-src` and `media-src`.
- **Clears it:** after lane 0018 deploys, a signed-in smoke spec with route fixtures from
  `shared/` at desktop and phone widths (press, progress, figure, download name), and a pass over
  every page with the CSP report in the console.

## Science engine (decision 0015)

### Reactions and readings cover three crafts

- **What:** the science seed has reactions and condition readings for Kutch Ajrakh, Bagh and
  Machilipatnam only; Bagru, Sanganeri and Akola stages get materials but no reactions or
  readings. Nothing proposes species for new claims (no researcher form, no enrichment step),
  so reactions grow only through `app/data/science_seed.json`. Kaolinite dehydroxylation has
  no reaction: the terracotta seed is sub-category mechanism chains, not a craft process with
  a `FIRE` stage. Stage concepts without an upstream ordinal (Akola mud soaking and paste
  preparation, Machilipatnam and Sanganeri block carving) get no stage, although `PRECEDES`
  edges could place them. No seed claim states a temperature or pH, so no seeded reading is
  checked against an envelope yet.
- **Why left:** each reaction and reading is curated against its quote; a model proposal path
  needs the review queue and a writer that calls `science/reactions.check_reaction`.
- **Clears it:** a writer for proposed species (researcher form and enrichment), balanced only
  through `check_reaction`; a terracotta craft process; ordering stages by `PRECEDES`.

### Out-of-envelope readings are not in a review queue

- **What:** the contract lists every `OUTSIDE` reading in the review queue; no review queue
  exists, so they are only shown with their status.
- **Clears it:** the review-queue lane lists readings whose `envelope_check` is `OUTSIDE`.

### The science seed never deletes

- **What:** science rows are upserted by derived id, so a reaction, condition or reading removed
  from `science_seed.json` stays in the database.
- **Clears it:** delete seeded science rows whose derived id is no longer in the plan, in the
  same transaction as the upsert.

### One kind and role per material

- **What:** a seeded material has one curated `MaterialKind` and one `MaterialRole` for every
  stage that uses it, and tools (`TOOL` concepts) are not stage materials.
- **Clears it:** take the role per stage from the source when a stage uses a material
  differently, and show tools once the contract has a place for them.

### Kaolinite constant differs from PLAN 7

- **What:** PLAN 7 gives kaolinite dehydroxylation as 450–600 °C; the cited revision says it
  begins at 550–600 °C, which is the constant.
- **Clears it:** cite a scholarly thermal-analysis source and set the constant to what it says.

## Answers in Indian languages (decision 0023)

### Translations are checked for figures, not for meaning

- **What:** `research/translation.translation_problems` proves that numbers, formulas, mhchem,
  units and the script survive a translation and that no link or personal data was added; it does
  not prove the sentence still says the same thing. A unit or number written in words in the
  target language fails the check and the sentence falls back to English.
- **Why left:** a meaning check needs a second model call per answer and a judge to calibrate.
- **Clears it:** run the known-answer questions of PLAN 0 in Hindi and Tamil on the box, have a
  speaker of each read the answers, and add a back-translation check if they find drift.

### Verified headings and follow-ups stay English

- **What:** a Verified answer in another language translates only its claim sentences; the
  section headings and the templated follow-ups are the app's English labels, and the
  not-enough-evidence message, errors and status lines are English in every mode.
- **Why left:** translating them would cost a model call on every Verified answer, including one
  whose claims are all cached; UI strings stay English.
- **Clears it:** keep translated labels per language as reviewed data (not model output) and send
  them with the stream.

### Multilingual answers not yet seen running

- **What:** the language picker, the Noto Sans faces, right-to-left Urdu and the English toggle are
  checked by typecheck, lint and unit specs; no browser has drawn them, and no TRANSLATE call has
  run against a provider. Migration 0007 seeds the TRANSLATE routes and has run only offline.
- **Why left:** nothing runs on the laptop; the batch deploys once.
- **Clears it:** after the deploy, ask one Hindi and one Urdu question in each mode and look at the
  answer on a phone and a laptop.

## Media backend (decision 0018)

### Gemini media behaviour not yet seen live

- **What:** how a safety block reads on the Interactions API, the image output type when none is
  asked for (PNG assumed), `DELETE /v1beta/interactions/{id}`, the clip's exact duration and the
  interaction id alphabet are unverified; the fixtures in `backend/tests/media/fixtures/` follow
  the documented shapes, not captured traffic.
- **Why left:** no paid call runs from the laptop and nothing is deployed yet.
- **Clears it:** after the deploy, make one image and one video, read the `UsageEvent` and the
  worker logs, replace the fixtures with the recorded answers (key-free) and adjust
  `providers/gemini_media.py` where the shapes differ.

### Video without the stage image as its first frame

- **What:** PLAN 11 allows the generated stage image as the only reference; videos are
  `text_to_video` only.
- **Why left:** it needs an S3 read and an image input in the request, which the first live runs
  should shape.
- **Clears it:** pass the requester's image asset of the same stage as an `image` input with
  `video_config.task` `image_to_video`, read through `services/object_store`.

### Community and caste names caught by group words only

- **What:** a claim, stage name or style hint is kept out of a prompt when it uses a group word in
  the singular or plural (`schemas/media.NAMED_GROUP_WORDS`, decision 0022); a community named
  without one (a surname or cluster name alone) still passes, and
  `depictsNamedCluster` compares only the craft's located place names.
- **Why left:** no register of community and caste names exists; PLAN 13a names them only from
  cited sources.
- **Clears it:** the governance lane keeps the named practitioners per craft as data; the claim
  set and the named-cluster flag check against it.

### The KalaVigyan token is not in the cross-portal naming document

- **What:** PLAN 14.3 adds `KalaVigyan` and its entities to
  `C:/dev/IIT/docs/conventions/NAMING_2026-10-18.md`; only this repository's helper and golden
  rows know them.
- **Why left:** that document is outside this repository and shared with both portals.
- **Clears it:** add the token, the `Generated-Image` and `Generated-Video` entities and the
  `Step-NN` sequence there at the portals' next release.

### India time is written again outside the backend package

- **What:** `core/clock.INDIA_TZ` is the backend's one home (decision 0022), but the geo ETL keeps
  its own `IST` offset for its run date (`etl/geo/geo_etl/__main__.py`) and `Craft`'s
  `recordedTimezone` default names `Asia/Kolkata` in the model, which may import nothing.
- **Clears it:** let the ETL import the backend's clock when it gains a dependency on the backend
  package, and move the model default into the migration that next touches the column.

### Media spend and units approximations

- **What:** a refund row counts on the day it is written, so a job failing after midnight IST
  returns a unit to the new day; the creation hold stops counting after 15 minutes
  (`RESERVATION_TTL`) while a job waits; `MediaJob.costUsd` holds the successful call only (failed
  and abandoned calls stay in `UsageEvent`); text and thinking tokens are priced at the media
  output rate, which overstates cost slightly.
- **Why left:** each is bounded and small next to the daily allowance and the monthly cap.
- **Clears it:** date refunds to their job's day, renew holds while queued, and price output by
  modality once the token breakdown is seen live.

### No signal that the worker is running

- **What:** the options route cannot tell whether `kv-worker` is up; if it is stopped, jobs queue
  and the client stops polling after 15 minutes.
- **Why left:** the watchdog covers the API only and the unit restarts itself.
- **Clears it:** a worker heartbeat (Redis or `AppSetting`) that options read, and the watchdog
  checking the unit.

## Admin role (decision 0024)

### The roster screen judges an entry by its own role

- **What:** `accessEntryOffers` (`frontend/lib/accessRoster.ts`) hides roster actions by the
  entry's `admitRole`; the server also refuses when the account at that address holds a role at
  or above the viewer's, so such a row can show an action that answers 403 with a sentence.
- **Why left:** the roster row does not carry the account's role, and adding it means a second
  query per page.
- **Clears it:** the roster list sends the actions the viewer may take on each row, computed with
  the same guards as the routes, and the screen draws exactly those.

### Sorting users by role follows the enum, not the rank

- **What:** `UserRole` lists `ADMIN` last (Postgres appends a new value), so
  `GET /users?sort=role` puts admins after students.
- **Why left:** the web client never sends that sort, and moving the value means recreating the
  type.
- **Clears it:** order that sort by `ROLE_RANK` with a `CASE` expression.

### A partial role-cap update drops the other roles to the student cap

- **What:** `PUT /settings/ai-budget` replaces the whole `roleDailyUsd` map; a role it leaves out
  falls back to the student's $0.50 in `providers/budget.evaluate` and shows no cap in
  `/usage/me`.
- **Why left:** older than the admin role; the master admin sends the whole map today.
- **Clears it:** merge the sent roles into the stored map, or refuse a map that does not name
  every role.

### Admin role not yet seen running

- **What:** migration 0009 has been rendered offline only; the admin DB tests
  (`backend/tests/db/test_admin_role_db.py`) run on GitHub Actions, and no browser has drawn the
  hub, Manage users or the roster as an admin.
- **Why left:** nothing runs on the laptop; the batch deploys once.
- **Clears it:** Backend checks green on the batch, then sign in as an admin after the deploy and
  walk the hub, Usage, Manage users and the roster.

## Yahoo sign-in (decision 0026)

### Yahoo sign-in not yet seen running

- **What:** migration 0010 has been rendered offline only; the Yahoo DB tests
  (`backend/tests/db/test_oidc_sign_in_db.py`) run on GitHub Actions, and no real Yahoo account
  has signed in: the token endpoint's acceptance of the secret in the form body and of the PKCE
  parameters is taken from DR, where it has run since 2026-10-10.
- **Why left:** the Yahoo app is not registered yet and nothing runs on the laptop.
- **Clears it:** register the app (`docs/RUNBOOK.md`, Yahoo sign-in), deploy, and sign in once
  with a rostered Yahoo address.

## First-password proof (decision 0028)

### A recovery code is offered for a first password but not taken

- **What:** the Settings card's two-step entry (`ChangePasswordCard.tsx`, `allowRecovery`) lets an
  account with two-step on type a recovery code before its first password, but
  `POST /auth/change-password` checks the code with `two_factor.step_up`, which takes only an
  authenticator code, so a recovery code is refused as a wrong code. DR accepts one there.
- **Why left:** older than decision 0028, and whether a recovery code may add a password is a
  security choice for the owner.
- **Clears it:** either check the first-password code with `check_second_factor(...,
  allow_recovery=True)` and answer its lock as 429, or drop `allowRecovery` from the card.

### First-password proof not yet seen running

- **What:** migration 0011 has been rendered offline only; the route tests
  (`backend/tests/db/test_first_password_db.py`) run on GitHub Actions, and no browser has added a
  password through the Google or Yahoo round trip.
- **Why left:** nothing runs on the laptop, and Yahoo is not registered yet.
- **Clears it:** Backend checks green on the batch, then after the deploy add a password in
  Settings from a Google-only account (and a Yahoo one once Yahoo is registered).

## Explainer contract (decision 0030)

### The answer stream re-exports the citation shapes

- **What:** `SourceRef`, `Citation` and `AnswerSentence` live in `research/citations.py`;
  `research/stream.py` re-exports them so `geo/`, `science/records.py`, `schemas/region.py`,
  `schemas/voice.py`, `services/craft_process.py`, `services/region_records.py` and two test
  helpers keep importing them from the stream: two import paths for one home.
- **Why left:** those files belong to other lanes working in the tree at the same time; the move
  was needed only to break the stream-to-explainer cycle.
- **Clears it:** switch each importer to `research.citations` when it is next touched, then drop
  the three names from `stream.__all__`.

## Understanding and depth (decision 0031)

### Comparison questions research the lead craft only

- **What:** since decision 0064 a comparison sets up to three crafts beside the lead one and each
  section shows a `compare` block, but live research and composition still run for the lead craft;
  the compared crafts' cells come from what is already stored about them.
- **Why left:** researching every compared craft multiplies the answer's spend; the curation run
  fills the stored claims each craft's cells read.
- **Clears it:** a per-craft research share inside the answer's budget for compared crafts with
  few stored claims in the section's field.

### Any-craft claims are read only by any-craft questions

- **What:** research for any craft writes its claims on shared concepts (no craft, no
  sub-category). A later question about a particular craft does not read them, because the craft
  scope reads the craft's and its family's concepts only.
- **Why left:** which shared findings apply to which craft is a curation choice; reading all of
  them in every craft answer would mix crafts.
- **Clears it:** link shared concepts to the crafts they concern (through the concept graph of
  feature 7 or a reviewer's link), and let the craft scope read linked shared concepts.

### The answer cap follows the asked depth

- **What:** `AnswerSpend` is made for the depth the reader asked for; when the understanding step
  degrades Expert to Detailed past the degrade mark, the answer is still held to Expert's cap.
- **Why left:** the pipeline is built before the understanding runs; a degraded answer plans
  Hybrid and spends less anyway.
- **Clears it:** let the understanding step set the effective depth on the answer's
  `AnswerSpend` before research starts.

### A hold is not released when a call raises something unexpected

- **What:** the router releases an answer's hold on every provider failure, but an exception
  outside `ProviderError` (a bug, a cancellation) leaves the estimate held, so that answer has
  less room under its cap; the `UsageEvent` stays `RESERVED` and stops counting after the
  15-minute reservation window, as before.
- **Why left:** the call loop of `router.run` (181 lines, in the baseline) needs splitting before
  a `finally` can be added cleanly.
- **Clears it:** split `router.run` into reserve, call and settle steps and release the hold in a
  `finally`.

### Retired stream vocabulary still listed

- **What:** the answering flow no longer sends the `RESOLVING` status or the `match`, `section`
  and `sentence` events; all four stay in `research/stream.py` (and `RESOLVING` in the client's
  `lib/answerShapes.answerStatusShape`) for the contract golden `shared/answer-stream.golden.sse`,
  which only the backend reads now that the web client reads the explainer stream (decision 0037).
- **Why left:** dead vocabulary, harmless to readers; removing it rewrites the golden and its
  tests, outside the review fixes of 0038.
- **Clears it:** drop `RESOLVING`, `match`, `section`, `sentence` and their golden from
  `research/stream.py` and `answerStatusShape`.

### The AI budget is edited only through the API

- **What:** no AI cap is set for now (decision 0093), and the Settings hub has no AI budget
  screen, so a Master Admin who brings a cap back (a ceiling, a role's daily cap, a depth's answer
  cap, the degrade mark) does it only through `PUT /settings/ai-budget`.
- **Why left:** the owner set no caps for now on 2026-11-18; the budget screen was never built.
- **Clears it:** add the AI budget to the Settings hub, with "No cap" as each field's empty state.

### The understanding call shares the PLAN route

- **What:** the understanding call runs on the `PLAN` route, so Usage counts it as planning and
  the Settings hub cannot route it apart from the plan call.
- **Why left:** the `PLAN` route is already "Plan and craft choice" with Gemini Flash Lite first,
  as the plan asks; a separate task needs an `AiTask` value, a migration and its routes.
- **Clears it:** add an `UNDERSTAND` task if the owner wants it routed or reported apart.

## Asking screen (decision 0036)

### Dictation languages not yet tried on each browser

- **What:** the plan (2.5) asks for each answer language to be checked on each target browser
  before it is offered. The screen offers dictation in all 13 answer languages (`<code>-IN`
  locales, `lib/dictation.ts`) wherever the browser has the Web Speech API, hides a language the
  browser reports unavailable (`SpeechRecognition.available`) or refuses
  (`language-not-supported`), but nobody has yet dictated in Odia, Punjabi, Assamese or Urdu on
  Chrome, Edge and Safari, or checked Android Chrome's continuous mode, which is known to repeat
  final words.
- **Why left:** nothing runs on the laptop, and the production E2E drives a headless browser with
  no microphone.
- **Clears it:** after the deploy, dictate one sentence per language on Chrome, Edge and Safari
  (desktop and Android Chrome) and record what each does here; switch Android Chrome to
  single-utterance mode if its repeats show.

## Pictures and terms (decision 0034)

### Relevance is by text only

- **What:** plan 2.7 asks for one cheap vision call on the top candidates; every picture is
  chosen by its words against the claim text (`relevance: TEXT`), so a picture whose title and
  description happen to share two words with a claim is shown even if it depicts something else.
- **Why left:** the vision call needs an image route and per-answer spend; text relevance came
  first.
- **Clears it:** a `CAPTION` route call on the top two candidates per section, recorded as
  `VISION` on `MediaRefClaim`, dropping a picture the model says does not show the claim.

### Link cards need the page's own site to serve the picture

- **What:** a SearXNG image result is kept only when its image and page share a registrable name
  (`research/images.same_site`), judged by a short list of second-level labels (`ac`, `co`,
  `gov`, `org`, ...) instead of the Public Suffix List. Sites that serve pictures from a CDN on
  another name are left out, and a public suffix outside the list could pair two unrelated sites.
- **Why left:** owner O2 asks for the thumbnail from the source site; no dependency carries the
  Public Suffix List today.
- **Clears it:** vendor the Public Suffix List (or `tldextract` with a pinned snapshot) and use it
  in `site_of`.

### Brave image results are not used

- **What:** web image results come from SearXNG only; plan section 7 names Brave for image results
  too, and the Brave key already backs web search.
- **Why left:** one image search per service was enough for phase A.
- **Clears it:** an `images` method on `BraveAdapter` (`/res/v1/images/search`) used when SearXNG
  answers fewer than two link cards.

### Local words without a stated meaning are not terms

- **What:** the glossary takes a seed concept's local word only when the concept's name states
  what it means (`Kut (iron-water black paste)`, `Alum (fatakdi)`). Local words listed beside
  other names (`lokhand`, `gud`, `datla`, `mavi`, `gudh`) are not terms, and two spellings of
  one word become one term only when they are at least 80 % alike (`harde`, `harda`).
- **Why left:** the seed records those words without their meaning, and a guessed meaning would
  be an uncited fact.
- **Clears it:** a curated `localTerms` meaning in `etl/crafts` (or claims that define them), then
  the glossary plan reads it.

### The glossary seed never removes a term or link

- **What:** `seed_terms` upserts terms by key and adds craft and concept links; a term or link
  that a later seed no longer produces stays.
- **Why left:** the claim and science seeds behave the same way (see "The science seed never
  deletes"); no removal has been needed yet.
- **Clears it:** a seed step that deletes links the plan no longer has, and terms with no links
  and no cached summary.

### Term summaries and pictures written back are not embedded at once

- **What:** claims and sources kept by a term summary are stored without vectors; they get them
  from `app/scripts/embed_knowledge` (run by the daily Coverage enrichment workflow), so up to a
  day passes before semantic retrieval finds them.
- **Why left:** the term route has no embedder in its request path and the summary is already
  cached for the reader.
- **Clears it:** pass `router_embedder(principal)` into `SqlTermStore` and call `embed_written`
  after the write-back, as `store_live_research` does.

### Term summaries never expire while their claims stand

- **What:** a cached `TermSummary` is served until a claim it rests on is hidden, retracted or
  rejected; a better stored claim, or a newer Wikipedia revision, does not replace it.
- **Why left:** plan 2.8 asks for a cache per term and language; claim visibility is the guard
  that matters for accuracy.
- **Clears it:** an age limit (or a stored claim newer than `checkedAt`) after which the next tap
  builds the summary again.

### Image and term enums are check constraints

- **What:** `MediaRef.display`, `MediaRefClaim.relevance` and `TermSummary.basis` are strings with
  `CHECK` constraints built from `models/enums.py`, not Postgres enum types like the other
  vocabularies.
- **Why left:** the schema tests only know enum types the first migration declares, and lanes
  adding tables in the same batch would each have had to change that test machinery.
- **Clears it:** once the tests accept enum types created by later migrations, turn the three
  columns into `pg_enum` types in one migration.

## Pictures and terms in the stream (decision 0039)

### Translated sentences lose the spans the translation rewrites

- **What:** a translated sentence keeps a span only where the English span's text survives
  (`research/terms.spans_still_shown`). A term the translation renders in its own script (alum as
  फिटकरी) is not underlined, although the glossary may hold that local name.
- **Why left:** marking translated text needs word boundaries that hold in Indian scripts (their
  vowel signs are not word characters to Python's `re`) and a check that the local name is the
  translation's word for that term.
- **Clears it:** after translation, mark the glossary's local names in the answer's script with
  grapheme-aware boundaries, next to the spans kept, and check them like English spans.

### Reused sections search for pictures again

- **What:** each reuse of a stored section searches the image services anew, although the
  pictures chosen for the same claims are already stored as `MediaRef` rows with `MediaRefClaim`
  links.
- **Why left:** reading stored pictures needs a lookup by claim and a rule for when a stored
  picture is still current; a search costs no AI spend and is bounded by the 8 s wait.
- **Clears it:** read the `MediaRefClaim` rows of the cited claims first and search only when none
  are stored.

### The stored-only answer shows no pictures or terms

- **What:** when spend is refused, `services/stored_explainer` streams prose blocks with no spans
  and no `images` block.
- **Why left:** step 7 was wired into the sectioned flow; the stored-only answer is its fallback.
- **Clears it:** pass the answer's `Enrichment` to `stream_stored_answer` and mark and search as
  the sectioned flow does.

### The nightly rebuild searches pictures nobody sees

- **What:** `app/scripts/rebuild_pieces` answers through `build_answer_pipeline`, so each rebuilt
  section also searches pictures and stores them as `MediaRef` rows, though its stream is
  discarded.
- **Why left:** the rebuild needs the same term marking so its pieces carry spans; pictures cost
  no AI spend and stored ones serve the craft page later.
- **Clears it:** build the rebuild's pipeline with enrichment tools whose picture step answers
  nothing.

### Pictures and terms in the stream not yet seen running

- **What:** production answers stream pictures (each researched or reused section of the Kutch
  Ajrakh known-answer questions carried an `images` block on 2026-11-17); no browser has yet shown
  the credits, the underlined terms or the term sheet.
- **Why left:** nothing runs on the laptop.
- **Clears it:** after the deploy, load `/ask`, ask the Kutch Ajrakh known-answer questions and
  see each section's pictures with their credits and underlined terms that open their summary.

## Explainer view (decision 0037)

### Listen re-renders every sentence on each time update

- **What:** the word being read travels through the reading context, so each `timeupdate`
  (about four a second) re-renders every sentence of the explainer.
- **Why left:** not measured as slow on an Expert answer; memoising every sentence first would be
  a guess.
- **Clears it:** measure on a long answer on a phone; if it drops frames, give each sentence a
  selector on the mark (only the sentence being read re-renders).

### The understood line finds its controls by id

- **What:** a part of the understood line moves focus to its control under the question box
  through element ids (`components/ask/AskOptions.focusAskOption`), not refs.
- **Why left:** the controls live in the asking screen's components and the explainer only needs
  to hand focus over; threading refs through both trees for one focus call was heavier.
- **Clears it:** if the asking screen gains a focus API (refs from `useAskScreen`), call it
  instead.

## Listen and the switched-off call (decision 0035)

### Narration not yet heard from ElevenLabs

- **What:** `ElevenLabs.narration` follows the documented `/with-timestamps` shape; no request has
  reached ElevenLabs, so `eleven_v4` on that endpoint, the alignment spelling the text in every
  language, bracketed text read as text rather than as a v4 audio tag, and the real speaking rate
  behind the 1,000-characters-a-minute hold are unverified (decision 0035, Unverified).
- **Why left:** no provider call with a real key from the laptop; nothing is deployed by agents.
- **Clears it:** after the deploy, press Listen on one English and one Hindi Kutch Ajrakh answer;
  if `eleven_v4` is refused, set `NARRATION_MODEL` to `eleven_v4_turbo`; replace the fixture
  with the recorded answer.

### Two readers missing the same block both pay for it

- **What:** the narration cache is checked, then filled; two requests that miss the same block at
  the same moment both synthesise it and both are billed (the second write wins, both are valid).
- **Why left:** rare until many readers open the same new answer at once; a lock across processes
  needs a table or a lease.
- **Clears it:** an in-flight lease per cache id (a row with a short expiry, or an S3 conditional
  put with `If-None-Match`) so the second request waits for the first.

### Narration objects never age out

- **What:** `media/narration/<cacheId>/` objects stay forever; a block that changes (a claim
  retracted, a translation corrected) gets a new cache id and the old audio is orphaned.
- **Why left:** the bucket lifecycle is Terraform, which agents do not change; the cost is small.
- **Clears it:** a lifecycle rule expiring `media/narration/` objects not read for a year, or a
  sweep of cache ids no stored explainer or piece names.

### Listen has no fallback voice

- **What:** PLAN 10.6 reads aloud with the Gemini voice when ElevenLabs is down; Listen is hidden
  instead (`listen.languages` empty), because the Gemini voice gives no word timings.
- **Why left:** highlighting needs timings; a fallback without them is a second Listen.
- **Clears it:** a Gemini read-aloud that highlights by sentence only, if the owner wants Listen
  while ElevenLabs is down.

### The Listen route repeats the throttle shape

- **What:** `api/routes/listen.throttle` repeats the `Retry-After` arithmetic of the other route
  throttles (`terms`, `knowledge`, `voice`, `auth`, `password_change`).
- **Why left:** those routes belong to other lanes working in the tree at the same time.
- **Clears it:** one `core/rate_limit.refused(attempt, detail)` that raises the 429 with its
  `Retry-After`, used by every route.

## Sectioned composition (decision 0032)

### Sections share the depth's budget evenly

- **What:** `split_share` gives every section the same part of the depth's queries and documents
  (Basic: 2 queries over 3 or 4 sections), whether or not its stored claims already cover it; a
  section without a query share reaches live research only through the fresh retry, and only
  while the ledger has something left.
- **Why left:** which fields need live research is known only after each section's plan call.
- **Clears it:** plan every section first, then hand the budget to the sections with open facets.

### Two sections can read the same document

- **What:** each section runs its own planner and `DocumentReader`; the adapters cache searches
  for 600 s but not reads, so a paper found by two fields is fetched twice.
- **Why left:** a shared reader needs a per-answer cache passed through the planner.
- **Clears it:** one per-answer read cache (by evidence id) held by the answering service.

### A late failure drops the whole prose block

- **What:** a prose block is refused whole when one sentence has no stored citation after the
  write-back (for example a write-back skipped as invalid), although its other sentences passed;
  the model's one regenerate covers only what the composer's checks see.
- **Why left:** plan 2.1 drops a block with an uncited fact; such skips should be rare.
- **Clears it:** count refused blocks by reason in production; if they occur, regenerate the
  section once with the refused sentences named.

### Section titles and progress counts are generic

- **What:** a section's title is its field's label ("The chemistry"), not one written for the
  question; the `status` line's counts are the first section's to reach each step.
- **Why left:** `section_started` goes out before anything is composed and has no later title
  event; per-section progress is carried by `section_state`.
- **Clears it:** a title from the understanding call (validated like a heading), and a status
  line that sums the sections' counts.

### Schema counts are prompt lines

- **What:** with portable schemas, the whole-answer composer's six sections, the voice turn's one
  section of three sentences and the translation's length limit are no longer enforced by the
  schema; the section composer and the planner trim on our side, the voice turn and the coverage
  job's whole-answer composer do not.
- **Why left:** the voice call is switched off and the coverage job only writes claims.
- **Clears it:** trim in `parsed_answer` to its form's limits (sections, sentences, follow-ups).

### Stored plans and the explainer are not read back yet

- **What:** `Answer.plan` holds one plan per section and attempt and `Answer.mode` the first
  section's mode; the data migration wrapping older plans has no database test of an old row.
  The explainer is stored as the reader saw it (translated), not in English.
- **Why left:** nothing reads them yet besides Listen, which wants the shown language.
- **Clears it:** a DB test that seeds a pre-0014 plan and runs the upgrade, when a reader of
  `Answer.plan` is written.

## Stored knowledge pieces (decision 0033)

### Topic keys match only the same glossary terms

- **What:** a facet's topic is the glossary terms the question names (else the place or the
  craft), so "Why does alum fix alizarin?" and "How do alum and alizarin bond?" meet, but a
  rephrasing that names one more or one fewer term researches again; a question in an Indian
  script matches only the glossary's local names, so it falls back to the craft's topic.
- **Why left:** accuracy over speed; a model-chosen topic would be another model output to check,
  and rendering every question in English costs a TRANSLATE call before any reuse.
- **Clears it:** measure reuse in production; if near misses are common, add the planner's facet
  targets to the stored piece and accept a stored set whose terms are a subset of the question's
  when its vector is near the question's.

### Answers never grow the Process tab

- **What:** plan 2.2 wants process stages found by answers to land in the science tables, so the
  craft page's Process tab and later ladders use them. No answer writes `Process` or
  `ProcessStage` rows: stage concepts a `PROCESS` section cites stay concepts (their claims still
  appear in prose). Lane 0033 made the cited stages the process of a craft with none, numbered in
  the order the model wrote its sentences; decision 0038 removed that, since step numbers and
  order would have come from the model, not from a source.
- **Why left:** no source-stated order exists to build from: the write-back records claims on
  stage concepts, not which stage follows which.
- **Clears it:** a cited-order route: write `PRECEDES` edges between stage concepts only from
  claims that state the sequence, with their citations; create a live process only when those
  edges order every stage, taking ordinals from the edges; take stage names only from curated or
  seeded concepts, never from a planner's facet targets; or a professor places the stages from
  the review screen.

### A rebuild that composes nothing is tried every night

- **What:** a stale piece whose rebuild shows no block stays stale and unsuperseded, so the
  nightly job tries it again each night (within the budget, most-asked crafts first).
- **Why left:** a retracted claim usually leaves its topic answerable; a topic that cannot be is
  rare and bounded by the daily budget.
- **Clears it:** record each rebuild attempt on the piece and skip one tried in the last week.

### The rebuild may overshoot the day by one answer

- **What:** the rebuild checks the day's remaining budget before each group (at least
  `ENRICHMENT_QUESTION_RESERVE_USD`), and one Expert group can spend up to the Expert per-answer
  cap, above the reserve.
- **Why left:** the coverage job has the same shape; the cap bounds the overshoot.
- **Clears it:** hold each rebuild to the smaller of its depth's cap and what the day has left.

## Phase B contract (decision 0042)

### Months and seasons are read in English only

- **What:** `research/calendar` reads capitalised English month names, their abbreviations and
  ranges joined by `to`, `till`, `until`, `through` or a dash, and three season words. Indian
  month names (Shravan, Kartik), `between June and September` (read as the two months only) and
  other seasons (post-monsoon, spring) place nothing.
- **Why left:** a season row shows only what a source names; reading less is safe, reading more
  needs a cited calendar of regional months.
- **Clears it:** a cited table of regional month names and seasons with their Gregorian months
  (owner O5's rule, as for local units), read by `months_named`.

### The phase B fixture's river ids are placeholders

- **What:** `shared/explainer.phase-b.golden.json` names reach ids 1, 2, 3 and outlet 3 under
  `placeholders`; every other id resolves.
- **Why left:** the river lines are built (decision 0043) but load only on GitHub Actions after
  the deploy; the real ids come from that load.
- **Clears it:** after the first `riverlines` load (decision 0043), take the Kachchh river from
  `river_store.rivers_crossing(session, [449])` and `trace_river`, write its reach ids and outlet
  into the fixture, and remove `placeholders` from the fixture and its model.

### PubChem records stored before decision 0042 keep random ids

- **What:** `link_compounds` now stores a new record source under `record_source_id(cid)`;
  record sources it stored earlier keep their random ids, and it reuses them (found by URL).
- **Why left:** ids already cited by stored claims or pieces must not move.
- **Clears it:** nothing needed while every reader takes the id from `Compound.sourceId`; a
  migration could rewrite them if a reader ever derives the id from the CID.

## River lines, tracer and monthly rainfall (decision 0043)

### The river ETL has run only on synthetic networks

- **What:** `python -m geo_etl rivers` and `etl/geo/load_rivers.py` are tested on hand-made
  networks and files; neither has read the real HydroRIVERS Asia file, uploaded a topology or
  written `RiverReach`. The network checks may stop the first run on a real defect.
- **Why left:** the extraction and load run only on GitHub Actions, after the deploy that carries
  migration `0016_river_reaches`.
- **Clears it:** the first Geo ETL dispatch with `riverlines` and `load` (`docs/RUNBOOK.md`, Geo
  ETL); any problem it names is decided in an addendum to decision 0043.

### Districts reached are computed on every trace

- **What:** `river_store.trace_river` intersects every reach of the path with the district
  polygons each time it runs; a long main stem has about a thousand reaches.
- **Why left:** it always follows the stored district shapes and serves one story at a time; it
  has not been measured.
- **Clears it:** time it in production after the load; if slow, a reach-district table with entry
  fractions filled by the river load and refilled when districts are seeded again.

### The largest basin files are a few MB

- **What:** the Ganga-Brahmaputra and Indus topologies hold every stored reach of the basin (tens
  of thousands), estimated at a few MB of JSON each; the API sends them uncompressed and the client
  loads a whole basin to draw one path.
- **Why left:** the contract serves one file per basin (decision 0042).
- **Clears it:** read the sizes in the `rivers` job summary after the load; if too large for a
  phone, a per-path or per-district topology, a coarser threshold for the largest basins, or
  compressed responses, in a contract change.

### CHIRPS monthly normals are complete only after a full run

- **What:** the region story's seasons rainfall reads the twelve `monthly_precipitation` rows of
  the CHIRPS dataset row's period; districts whose CHIRPS shard failed in run 43884310432 (15
  states, decision 0027) have none until CHIRPS is loaded again, and a district with a month from
  another period has no rainfall.
- **Clears it:** the CHIRPS dispatch in `docs/RUNBOOK.md`, Geo ETL, then the count check there.

## Place renderers (decision 0048)

### Place renderers not yet seen running

- **What:** the river flow, the layer pills, the rainfall bars and the supply pins are checked by
  typecheck, lint and server-rendered unit specs, not in a browser: the lazy chunks under a Next
  build, the flow timing, touch targets on the map badges, and the contrast of the `errand` and
  `archive` tones in dark mode are unverified.
- **Clears it:** once the kinds are built, the production E2E asks the Kutch Ajrakh water question
  at 1440, 834 and 390 px, with screenshots of the story before, during and after the flow and
  with reduced motion on.

### The river spec reads a hand-written basin

- **What:** `e2e/place-renderers-unit.spec.ts` decodes a small quantized topology written for the
  test (reaches 1, 2, 3 and a tributary inside Kachchh), because no basin file exists yet.
- **Why left:** HydroRIVERS and the basin TopoJSON are lane 0043's.
- **Clears it:** when lane 0043 commits a golden basin file for the fixture's river, the spec parses
  it with `riverBasinOf` and draws the fixture story from it. Decision 0043 committed
  `shared/river.topology.golden.json` (the fixture's placeholder river 1, 2, 3 and a tributary,
  written by the geo ETL's encoder, reproduced by `etl/geo/tests/test_rivers.py` and parsed by
  `e2e/river-topology-golden-unit.spec.ts`); the place spec can now draw from it.

### Map layer blocks carry district codes without names

- **What:** a map layer's `highlighted` districts are LGD codes only, so the map layer reads
  "Outlined · pH 7.9" (as on `/map`, entry "Map layer values carry no district names"). The
  seasons rainfall names its district since decision 0050.
- **Why left:** version 1 of the kind is fixed (decision 0042) and the client holds no register.
- **Clears it:** a version 2 of `map_layer` with `DistrictRef`s, or the districts route of that
  entry, then "Kachchh · pH 7.9".

### A stretch is the reaches with a vertex inside the district

- **What:** a step's stretch and a district's entry point are found on the simplified basin lines
  (`regionStory.stretchOf`, `districtEntries`); a reach that crosses a district corner without a
  vertex inside it is left out of the stretch, and its district lights at the previous district's
  point.
- **Why left:** the server's order (`river.districtLgds`, PostGIS on full geometry) still decides
  the order, and the error is a few kilometres at district scale.
- **Clears it:** serve each reach's districts in the basin file (lane 0043 computes them already)
  and read them instead of testing vertices.

### A map chunk that failed to load stays hidden

- **What:** `lazyBlock` turns a failed import into a block that draws nothing, and `React.lazy`
  keeps that result, so a dropped connection while the chunk loads hides the map until the page
  reloads.
- **Why left:** a retry needs an error boundary per block; the answer is otherwise unaffected.
- **Clears it:** a per-block error boundary with Try again that re-creates the lazy component.

## Reaction player, material cards and 3D molecules (decision 0045)

### The reaction player shows no conditions or reaction energies

- **What:** version 1 of `ReactionStep` (decision 0042) has no conditions or ΔH, so the player
  shows species, equations and levels only; the Process tab still shows each reaction's cited
  conditions and ΔH.
- **Why left:** the kind's fields were fixed by decision 0042 and the matter renderers are built
  against them in parallel; a field change is a new version.
- **Clears it:** a version 2 step carrying the reaction view's cited conditions and `deltaH`, with
  its renderer, fixture and both sides' tests.

### A material card cites no PubChem record for its formula

- **What:** a card shows a formula and CID only from a compound linked to its PubChem record, but
  version 1 of `MaterialCardBlock` has no source field, so the record is not in the explainer's
  sources; the CID itself is the reader's link to the record.
- **Why left:** the kind's fields are fixed (decision 0042).
- **Clears it:** a version 2 card with the compound's record `sourceId`, cited like the molecule.

### Each matter builder reads the craft's matter again

- **What:** the reaction, card and molecule builders each call `craft_matter`, so a chemistry
  section reads the craft's process rows three times and a materials section twice.
- **Why left:** builders share nothing but `BuilderTools`; the reads are short and need no lock.
- **Clears it:** a per-answer matter read held by the builder tools and shared by the builders.

### Cards and molecules can repeat across a chemistry and a materials section

- **What:** a builder sees one section, so an answer with both a `CHEMISTRY` and a `MATERIALS`
  section can show the same material's card or the same molecule in both.
- **Why left:** the registry contract gives a builder its own section only.
- **Clears it:** `BuildAsk` carrying the blocks earlier sections were given, or a per-answer
  record of shown materials and compounds.

### A missing 3D conformer is never asked again

- **What:** `ConformerCache` keeps PubChem's "no 3D conformer" for good, so a conformer PubChem
  adds later is not seen until the object is deleted.
- **Why left:** PubChem computes conformers only for small, rigid, single-component molecules;
  a compound refused once is very unlikely to gain one.
- **Clears it:** re-ask a kept miss whose `checkedAt` is older than a few months.

### The compound lookup holds its session across PubChem calls

- **What:** `link_compounds` keeps one database session open while it asks PubChem for each
  pending compound (decision 0040's rule is never to wait on HTTP with a connection held).
- **Why left:** it is a nightly script with its own engine and a handful of compounds, not the
  answer path; its database test drives it with one transaction.
- **Clears it:** read the pending compounds, look them up with no session open, then write the
  links in a second short session; adapt `tests/db/test_compound_lookup_db.py`.

### Card local names come from the glossary only

- **What:** a card's `localNames` are its term's; a local name a cited claim states (for example
  "locally known as kachika") but the glossary lacks is not shown.
- **Why left:** the glossary is the one home of names; a name read from free text needs the same
  checks the glossary seed applies.
- **Clears it:** the glossary seed adding local names stated in claims about the term's concept.

## Expert panel (decision 0046)

### Panels spend only in the first half of a capped answer

- **What:** builders' plan and compose calls (panels, region stories, supply maps, material cards;
  decision 0050 added the plan calls) hold `AnswerSpend.headroom()`, so for every role but Master
  Admin such a call is refused once it would leave the answer less than half its depth's cap. At
  the starting caps ($0.25, $0.50, $1.00) a Basic answer hears a panel in its first section or
  two at most, and later sections of long answers hear none and get no story, map or cards.
- **Why left:** a panel call is about as dear as the section's own compose call, and a section
  refused for spend stops the whole answer; the caps are starting values (owner O3).
- **Clears it:** set the caps from measured spend (the debt "Per-answer caps are starting values"),
  then lower `OPTIONAL_WORK_KEEPS`, or let a section refused by the answer cap end `EMPTY` instead
  of stopping the answer.

### One failing take sentence drops the view, with no regenerate

- **What:** prose gets one regenerate for failing sentences; a panel take does not, so a view with
  one unquoted or unsupported sentence is not shown at all.
- **Why left:** the panel is optional work inside a 90 s wait (decision 0099).
- **Clears it:** one regenerate of the failing seats' takes when the wait and the headroom allow.

### A seat's own search reads stored claims only

- **What:** since round 4 each seat's search is filtered by its fields (`KnowledgeQuery.fields`),
  but a seat still keeps a found claim only when it cites a source of one of the seat's kinds;
  stored chunks the search returns are not offered (a take cites stored claims only), and no live
  search runs for a seat.
- **Why left:** stored evidence and the existing retrieval only (owner, 2026-11-19).
- **Clears it:** the live write-back of chunks a seat reads into claims.

### Experts differ only on claims stored on one concept

- **What:** "one subject" is the claims' stored concept, so two claims on different concepts that
  disagree about one fact (or a claim about a concept edge) are never shown as a difference.
- **Why left:** the concept is the only stored subject; a model's word that two claims concern one
  thing is not evidence.
- **Clears it:** the concept graph of feature 7 (shared-science explorer) linking concepts that
  name one thing, read as one subject.

### Reused expert views keep the seats that stored them

- **What:** a stored panel is reused with its section (one reuse set), so a later question that
  seated other experts sees the earlier answer's seats.
- **Why left:** dropping a view would break its mirrored difference; the set is reused whole.
- **Clears it:** reuse a set's views only for seats the new understanding seats, removing the
  differences and agreements that name a dropped seat.

### The reading share does not steer queries

- **What:** each seat's preferred kinds take every other early read of what was found, but which
  kinds are found depends on the queries the plan call writes; GI journals and government reports
  come mostly from the web tier and only when a query looks for them.
- **Why left:** the plan call is told each seat's kinds; reserving queries per tier would split an
  already small section share further.
- **Clears it:** a measured look at which kinds Expert sections read, then a tier share in
  `planned_queries` if seats' kinds are missed.

### The panel call has not met Claude Sonnet yet

- **What:** the prompt and schema were checked against the portable schema rules and recorded
  replies only.
- **Why left:** nothing runs against production models from the laptop.
- **Clears it:** the phase B known-answer question in production (Kutch Ajrakh, Expert, history)
  showing an "Experts differ" card, and Usage showing the panel's spend per answer.

## Matter and expert renderers (decision 0049)

### Matter renderers not yet seen running

- **What:** typecheck, lint and server-rendered unit specs check the player, the cards, the panel
  and the molecule's frame, not a browser: the 3Dmol.js chunk under a Next build, its first draw,
  the reveal turn, Explore on touch screens, the transparent canvas in dark mode, and the cast's
  `archive` tone in dark mode are unverified.
- **Clears it:** once the kinds are built, the production E2E asks a Kutch Ajrakh chemistry
  question at 1440, 834 and 390 px, with screenshots of the player playing and paused, a card, the
  molecule before and after Explore, and reduced motion on.

### 3Dmol.js keeps two listeners after a molecule is gone

- **What:** a 3Dmol.js viewer adds a `mouseup` and `touchend` listener on `document.body` and a
  `resize` listener on `window` that it never removes; disposing a scene clears the models, loses
  the WebGL context and removes the canvas, but those listeners stay until the page unloads.
- **Why left:** the library has no teardown for them, and an explainer draws at most one molecule
  per section.
- **Clears it:** a 3Dmol.js release with a viewer teardown, called from `MoleculeScene.dispose`.

### The conformer is fetched again on every draw

- **What:** `fetchConformer` goes through `apiFetch`, which never keeps responses, so a molecule
  drawn again (another answer, a reload) asks the route again, although the route allows a week's
  private caching.
- **Why left:** the route serves from the private bucket without calling PubChem, so a repeat
  costs one small request; `apiFetch`'s only cache opt-in revalidates by ETag, which the route
  does not send.
- **Clears it:** the conformer route sending an ETag (the record's hash), then
  `revalidateFromHttpCache` on the fetch.

### Keyboard readers can turn a molecule but not tilt or zoom it

- **What:** Turn rotates a quarter about the vertical axis; tilting and zooming need a pointer
  (Explore), because 3Dmol.js reads only mouse, touch and wheel input.
- **Why left:** the name, formula and record are text; the model is an illustration.
- **Clears it:** Tilt and Zoom buttons calling the viewer's `rotate` about `x` and `zoom`.

## Curation tooling (decision 0051)

### The LGD register is read in two places

- **What:** `services/district_seed.py` reads `lgd_register.json` itself to seed states and
  districts; `data/district_register.py` reads it for the curation checker's name lookup.
- **Why left:** the seed also builds geometry and is proven only by the database job; changing it
  was outside the curation lane.
- **Clears it:** `district_seed` taking its state and district names from
  `data/district_register`.

### Two atomic text writers in tools

- **What:** `tools/hygiene/baseline.write_baseline` and `tools/curation/output.write_text_atomically`
  both write through a temporary file and replace.
- **Why left:** `tools/` has no shared module, and the hygiene package should not import curation.
- **Clears it:** one `tools` module both import, when a third writer appears.

### Long HTML and plain-text sources are cut at 200,000 characters

- **What:** `tools/curation/reading.source_text` reuses `app.fetcher.extract`, which caps HTML and
  plain text at `FETCH_TEXT_MAX_CHARS`; a quote past the cap fails and the check file marks the
  source `truncated`. PDFs use curation's own caps (2,000 pages).
- **Why left:** one HTML reader for the live fetcher and curation; long books usually come as PDFs.
- **Clears it:** a cap option on `extract` that curation passes.

### Category dossiers are curated but not imported or shown

- **What:** dossiers with scope `CATEGORY` (`backend/app/data/curation/categories/`) pass the
  checker and the verifier, but nothing imports them (the importer reads only the top folder),
  no route serves them and no page shows them (`docs/contracts/curation.md`, Scope).
- **Why left:** the owner asked for category master documents to be curated now; the category
  page belongs to the app rebuild.
- **Clears it:** the rebuild's category page, with an import of category dossiers into their own
  rows and the member-craft links resolved by slug.

### The tools have not met a GI journal yet

- **What:** the PDF path is tested on a hand-built PDF, and the live and Wayback paths were run once
  on a Wikipedia page; no multi-hundred-page GI journal or Wayback-only source has been verified.
- **Why left:** the pilot (wave 0) is the first real use.
- **Clears it:** the pilot's verify runs, recording the largest PDF read and any extraction gap.

## Region story and map layers (decision 0044)

### Rivers are drawn unnamed

- **What:** HydroRIVERS names no river, so the region story builder always sends `river.name` null
  and the client labels the course generically, even when a step's claim names the river ("the
  river Saran in Dhamadka"). The contract allows a name stated by a step, but matching a claim's
  name to a traced path would be a model's identity claim about a path.
- **Why left:** no open, linked river-name dataset is loaded; owner rule: paths and places come
  from claims or datasets, never a model.
- **Clears it:** an open dataset that names reaches or basins (Wikidata rivers matched by mouth and
  source coordinates, or OpenStreetMap waterway names under ODbL after a licence decision), loaded
  by the geo ETL and offered to the builder as a dataset row the name cites.

### A researched geography section rebuilds a stored story

- **What:** a stored region story is reused only together with its facet's reused section; a
  researched geography section (a new craft in the same district, or a stale craft set) makes one
  plan-model call for a new story, which supersedes the stored one of its basin, even when the
  stored story still passes the reuse rule.
- **Why left:** the registry refuses a builder block with a reuse mark (decision 0042 point 9), and
  a stored block shown without its mark would hide that it is earlier research.
- **Clears it:** a registry path that places a reusable stored piece with its mark (the entry names
  the piece slot it reads), so the builder spends nothing when a current story exists.

### "No river data" is logged once per answer, not once per process

- **What:** the region story builder notes that the river lines are not loaded once per builder,
  and the registry is built per request, so every geography section logs it once until the load.
- **Why left:** no process-held builder state exists; the state would be module-level otherwise.
- **Clears it:** the Geo ETL `riverlines` load, after which nothing is logged; or a process-held
  notice passed in `BuilderTools`.

### Story steps are only the section's own claims

- **What:** steps are chosen from the fact-level stored claims the section's checked blocks cite
  (at most 12), so a story never adds a stored place or water claim the prose did not use, and its
  steps repeat sentences of the section's prose.
- **Why left:** those claims are already checked and cited for this question; searching place
  claims per district is a retrieval change.
- **Clears it:** an offer of the district's stored place claims (by `CraftLocation` district and
  the GEOGRAPHY concept headings) beside the section's, ranked by the question.

### Map layer subjects are a fixed English word list

- **What:** `geo/section_layers.LAYER_SUBJECTS` picks a section's layer by whole English words in
  its sentences (rain, monsoon, clay, pH ...); a subject the list lacks falls back to registry
  order, so a climate section about humidity shows the annual mean temperature.
- **Why left:** builders see English sentences, and a deterministic list keeps the model out of a
  value the server chooses.
- **Clears it:** glossary terms linked to layers (a `Term` per registry layer with its local
  names), marked by the existing `TermMarker` instead of a word list.

### Many-district stories are not stored

- **What:** a story without a river is keyed by every district (`lgd-<code>` joined by `+`); past
  `TOPIC_KEY_MAX_CHARS` (about 23 districts) the key is refused, the story is shown but not kept,
  and the lookup offers no district key for such a craft.
- **Why left:** crafts practised in more than 20 mapped districts are rare, and a key per district
  would let one story answer for another district's craft.
- **Clears it:** a stored district list on the piece (a `districtLgds` column with a GIN index)
  looked up by overlap instead of an exact key.

### The place builders have not run against loaded rivers

- **What:** the builders are tested on fixture reaches and, on GitHub Actions, on a hand-made
  network in Kachchh; no answer has yet traced a real HydroRIVERS basin, so the time of a large
  basin's trace (the Ganga's links and PostGIS district hits) inside the 20 s wait is unmeasured.
- **Why left:** the river lines load only after the deploy (decision 0043).
- **Clears it:** after the `riverlines` load, one Expert answer for a Ganga craft and one for Kutch
  Ajrakh in production, recording the builder's time; if a trace nears the wait, cache traces per
  crossing reach.

## Seasons and supply (decision 0047)

### A season gets months only from a quote the section offers

- **What:** a season row is given months only by a quote among the section's cited claims and the
  craft's stage claims that states the season's months; most climate sections cite none, so their
  rows show the season chip alone. No regional season calendar is stored.
- **Why left:** owner rule: a named Indian season maps to months only where a source states the
  mapping, and no cited calendar is curated yet.
- **Clears it:** cited regional season calendars per state or district (for example the India
  Meteorological Department's season definitions), stored as claims on a district concept and
  offered to the seasons builder with the section's claims.

### The season mapping reads short English word lists

- **What:** `calendar.season_months` maps a season only when the words between it and one month
  range are on short lists (`SPAN_WORDS_AFTER`, `SPAN_WORDS_BEFORE`) and no reference word
  (`POINT_WORDS`: after, before, end, onset, early ...) stands just before the season word; any
  other phrasing maps nothing, and an enumeration whose items share those words (`the monsoon, the
  summer months of June to September`) could still give a range to the wrong season.
- **Why left:** reading less only leaves a row with its season chip; a parser would be a new
  dependency for one rule.
- **Clears it:** tests on the real climate quotes the curation run stores, widening or narrowing the
  lists with each case found.

### Supply origins are placed through Wikidata only

- **What:** an origin is pinned only with a Wikidata item's P625; a district the register holds
  (with its polygon) whose name finds no single Wikidata item is listed without a pin, and a
  village with namesakes is pinned only when its sentence names a word of the right item's
  description.
- **Why left:** version 1 of `SupplyLink` has no field that cites a district row, and the client
  links every pin to its Wikidata item (decision 0047).
- **Clears it:** a version 2 link with `districtLgd`, placed at the register district's centroid and
  citing `DR_DISTRICT_SHAPES`, on both sides.

### Place lookups are asked again for every supply map

- **What:** each supply map searches Wikidata for every origin again (the source HTTP cache keeps an
  answer ten minutes per process); only a stored piece keeps its coordinates. The supply builder
  also reads the craft's matter again, after the material card and molecule builders of the same
  section (as in "Each matter builder reads the craft's matter again").
- **Why left:** a section has few origins, and stored pieces answer repeat questions.
- **Clears it:** a stored place table keyed by origin and context words with the item, its
  coordinates and revision, refreshed monthly; one matter read shared by a section's builders.

### Seasons are built for climate sections only

- **What:** the seasons builder runs for `CLIMATE` sections; a process section about when the work
  is done shows its ladder without a month strip.
- **Why left:** a process section's ladder already lists every stage, and a strip listing the cited
  stages again would repeat it.
- **Clears it:** a strip of timed stages only in process sections, once the production E2E shows how
  often a climate section is planned.

### The seasons and supply builders have not met production

- **What:** both are tested on fixtures, recorded Wikidata answers and, on GitHub Actions, the
  seeded claims; neither has run on production claims, and the supply builder's time inside its
  30 s wait (one plan-model call, up to 8 searches paced at 0.2 s and one SPARQL query paced at 1 s)
  is unmeasured.
- **Why left:** they reach readers with the next deploy.
- **Clears it:** the Kutch Ajrakh climate and materials questions in the production E2E, recording
  each builder's time and the rows and pins shown.

## Phase B review fixes (decision 0050)

### Prose and takes are not checked for river names

- **What:** `stated_names.unstated_names` refuses months, seasons and register states and districts
  a sentence names and no cited claim or quote states; a river name ("the Narmada") is not
  checked, because nothing lists river names.
- **Why left:** no open river-name dataset is loaded (entry "Rivers are drawn unnamed"); a
  hand-written list would be names without a source.
- **Clears it:** the river-name dataset of that entry, its names joined to `register_places_named`.

### Register place names are matched as written

- **What:** the check reads every state and district name of the LGD register as written, whole
  words: an alias (Kutch for Kachchh) is not read, so a story step naming Kutch stays unplaced and
  a sentence naming Kutch is not checked, and a district name that is also a common word or a
  person's name (Mon, Anand, Sagar, Korea) drops a sentence whose sources do not repeat it.
  District names made only of compass words (Delhi's North, South West) are skipped.
- **Why left:** the register has no aliases; failing closed drops a sentence rather than showing
  an unstated place.
- **Clears it:** a cited alias table for districts, read by `register_places_named` and by the
  step district check.

### A negation within five words rules a timing out

- **What:** `calendar.year_months` and `only_season` drop a month or season when a negating or
  excluding word stands within five words before it in its clause, so a sentence about the
  season that negates something else ("so they do not expand in the rainy season") places no row.
- **Why left:** telling the negated verb apart needs a parser; a wrong month on screen is worse
  than a missing row.
- **Clears it:** a dependency parse of the claim (spaCy, a recorded decision) that drops only
  mentions inside the negation's scope.

### Superseded river files stay in the bucket

- **What:** topology keys carry their SHA-256, so a load whose content changed writes new objects
  and leaves the earlier ones under `media/rivers/<edition>/<mainRiv>/<old sha256>/`.
- **Why left:** the river load role may write and read only; deleting needs a wider grant, and
  the files are small next to the bucket's media.
- **Clears it:** a lifecycle rule on `media/rivers/` expiring objects no `RiverBasin` row names,
  or a delete step in the load with `s3:DeleteObject` on that prefix.

### The stream's reaction event outlives the reaction player

- **What:** `research/stream.py` still declares the `reaction` event and the client still parses
  it into `ReactionsPanel`, although no server path emits it since the explainer (decision 0030)
  and reactions now arrive as `reaction_player` blocks.
- **Why left:** removing an event changes the stream contract on both sides and the frontend
  state; it shows nothing today.
- **Clears it:** drop `ReactionEvent`, the client's `reaction` event, `reactions` state and
  `ReactionsPanel` in one change with `docs/contracts/research.md`.

### The water question needs `rivers_loaded` set by hand

- **What:** the production E2E's water question fails a missing region story only when dispatched
  with `rivers_loaded` true; it cannot tell on its own whether the river lines are loaded.
- **Why left:** no route says whether rivers are loaded, and adding one for a test would be an
  admin surface with no reader.
- **Clears it:** dispatch with `rivers_loaded` true from the first run after the `riverlines` load,
  then make it the default.

### The answer route and the nightly rebuild each wire the answer's models

- **What:** `api/routes/knowledge.answer_pipelines` and `scripts/rebuild_pieces.rebuild_pipeline`
  each build the plan, compose, builder, translate and embedding models from an `AnswerSpend`; a
  new model must be added to both (decision 0050 added the builder plan model to both, and a test
  checks both).
- **Why left:** the route builds principals with the reader's id and role and the script without,
  and the models come from `providers`, which `services` may not import, so the shared builder
  is a new provider module.
- **Clears it:** one `providers/answer_models.answer_models(spend, user=)` returning the set, which
  `build_answer_pipeline` takes as one argument.

## Curated import and craft page (decision 0053)

### The ladder and the process route still number unordered curated stages

- **What:** curated stages no source orders are stored with `ProcessStage.ordered` false and an
  ordinal after the ordered ones. The craft page's Process tab shows them unnumbered (decision
  0071), but `GET /crafts/{slug}/process` (`schemas/science.ProcessStageView.ordinal`) and the
  answers' process ladder (`science/ladder`) still show every stage's ordinal.
- **Why left:** both read the science contract and its golden fixtures, which the import did not
  need to change; `science/records.StageRecord.ordered` already carries the flag.
- **Clears it:** an `ordered` field in the science contract and the ladder, and the composer told
  which stages have no stated order.

### A seeded craft keeps its seed process and seed claims beside the curated ones

- **What:** Kutch Ajrakh (and any other seeded craft once curated) keeps the "Seed process" next
  to the curated process, so `/process` lists both and an answer's ladder may choose either; its
  seed claims (edge sentences withdrawn) stay visible to answers and in All evidence, folded under
  a curated near-duplicate where one exists.
- **Why left:** the plan withdraws only the edge sentences; retiring the rest of a seeded craft's
  seed rows is a reading of the plan the owner has not made.
- **Clears it:** an owner decision, then the import superseding a curated craft's seed claims and
  process (status `SUPERSEDED`, rows kept).

### Facet search finds curated claims by their subject's concept type

- **What:** the planner's facets filter by `Concept.type`; curated places are
  `ENVIRONMENTAL_CONDITION` and communities `TRADITION` whatever the claim's discipline, so a
  history facet does not see a history claim about a place. Craft-level claims are typed by
  discipline (`curation_keys.DISCIPLINE_CONCEPT_TYPES`).
- **Why left:** concept types are the retrieval vocabulary the planner's schema enumerates;
  adding types or a discipline filter changes the planner contract.
- **Clears it:** retrieval filtering by `CuratedClaim.discipline` (or a claim discipline column)
  when the facet maps to a discipline.

### Curated materials link only to compounds already stored

- **What:** a dossier material's PubChem CID sets `Material.compoundId` only when a `Compound`
  with that CID exists; no compound row is created, so molecules and material cards do not see
  the other curated substances.
- **Why left:** a compound row needs a name and formula from PubChem, and the import makes no
  HTTP call.
- **Clears it:** the import adds `Compound` rows with the CID and name, and the nightly
  `link_compounds` fills their formula from PubChem.

### Two homes for GI facts

- **What:** the dossier's GI record lands in `CraftGiRecord`; the older `GiRegistration` table
  (PLAN section 4) is still never written.
- **Why left:** `GiRegistration` has no fields for the journal issue, filing date, proprietors
  as a list, the authorised-user count or the claims, and the market and GI builder reads only
  `CraftGiRecord` and the registry claims (decision 0066). Dropping the empty table needs a
  migration with its row-level security, which the GI lane did not batch with parallel lanes'
  migrations.
- **Clears it:** the next migration that touches the crafts' tables drops `GiRegistration` (its
  downgrade recreating the table and its policy) and removes the model.

### A dossier removed from the folder is not un-imported

- **What:** the import reads the dossiers present; deleting a dossier file leaves its claims,
  pieces and `CuratedCraft` row as they were.
- **Why left:** no dossier has been retired, and deletion would need its own supersession rule.
- **Clears it:** an explicit retire step that supersedes the claims and pieces of a craft whose
  dossier is gone.

### A curated glossary meaning does not reach the term route

- **What:** the page shows the dossier's meaning of each term, but `Term` rows are inserted only
  when the key is new (the seed glossary owns its rows and rewrites them on every deploy), and
  `GET /terms/{key}` builds its summary from defining claims, Wikipedia or a search.
- **Why left:** writing a cached `TermSummary` from the curated meaning needs the meaning checked
  as a cited sentence.
- **Clears it:** a `STORED` term summary built from the term's curated claims at import.

### The old colour reads the new claim statuses during the first deploy

- **What:** migration `0017_curated_dossiers` and the import run while the previous release still
  serves; its `ClaimStatus` list lacks `SUPERSEDED` and `WITHDRAWN`, so a request that loads a
  withdrawn edge claim (a stored piece citing one) can fail until nginx switches to the new colour.
- **Why left:** the seed step runs before the switch by design (blue/green), and the window is the
  health wait of one release.
- **Clears it:** nothing after the first deploy that carries the migration.

### The import's database tests have not run on a laptop

- **What:** `tests/db/test_curation_import_db.py` (full Kutch Ajrakh import, idempotence,
  supersession, seed-edge hiding, answers' claims untouched, the region builder's districts) runs
  only on GitHub Actions; it was written without a local database (owner rule).
- **Why left:** nothing heavy runs locally.
- **Clears it:** the first Backend checks run of this change passing; then delete this entry.

## Phase C contract (decision 0054)

### The static check reads script text by pattern

- **What:** `research/sandbox` parses the markup but scans script text with patterns, not a
  JavaScript parser. It refuses some good code (a string `"top"`, `"window"` or `"self"`, an
  English "this," inside a string, a local named `parent`, `view` or `location`, a `class`
  field read as `.constructor`), and it cannot follow every alias of the window (decision 0061
  refuses `window`, `self`, `globalThis` and `this` handed on as values, `.view`,
  `defaultView`, `contentWindow` and the reflection names, but a computed read of an object
  that is the window under another name still passes).
- **Why left:** no JavaScript parser runs on the server, and the frame's sandbox, policy and
  guard are the boundary; the check is a filter that fails closed.
- **Clears it:** a JavaScript tokenizer behind one adapter if production regenerations show the
  check refusing good explainers, or an escape attempt it misses.

### Numbers the explainer computes are not checked

- **What:** the static check reads the numerals a generated explainer writes (decision 0061 added
  figures against letters, list starts and CSS counters), not the numbers its code computes. A
  value worked out from data values and an input's position (the fixture's `n *
  data.fallLowFeet`, which shows 20 to 150 feet as the slider moves), a numeral assembled from
  allowed constants (`'1' + '8' + '6' + '8'`, `1000 + 12 * 12 * 6`) or a unit conversion
  (`data.depth * 9 / 5 + 32`) reaches the reader without being a cited value.
- **Why left:** a frame guard that refused every shown numeral missing from `kv-data` (a
  `MutationObserver` and wrapped `fillText`) would hide the fixture's own explainer the moment
  its slider moves, since 20 is not a data value; telling a derived figure from an invented one at
  run time needs a rule the plan does not have.
- **Clears it:** an owner rule for derived figures (for example, only products of a data value and
  an input step the data object names), then that runtime guard in `lib/sandboxFrame`'s prelude
  posting a refusal that `SandboxFrame` turns into hiding the block.

### Chromium ignores the frame policy's webrtc directive

- **What:** `SANDBOX_CSP` ends with `webrtc 'block'` (decision 0061), but Chromium 158 logs
  "Unrecognized Content-Security-Policy directive 'webrtc'." as a console error in every generated
  explainer and lets a peer connection reach a STUN server; there the client's `FRAME_GUARD` is
  what stops it (no constructor, no nested window, no nested frame), proved by
  `e2e/sandbox-frame-unit.spec.ts`. The production screens walk ignores exactly that console
  error from `about:srcdoc`.
- **Why left:** browsers that read the directive enforce it, and the guard covers the rest; the
  directive's support is the browsers'.
- **Clears it:** nothing in this repository; drop the screens walk's exception once Chromium
  recognises the directive.

### Years are read by pattern

- **What:** `research/timeline.years_named` reads any four-digit numeral from 1000 to 2099 as a
  year; the timeline builder offers `years_offered`, which drops a numeral followed by a plural
  lowercase noun ("1500 artisans", decision 0057), but a count before a singular or irregular
  noun ("1500 people", "1200 men") is still offered. Relative dates ("400 years ago") name none,
  so such claims never date a point.
- **Why left:** the history claims held state dates as years, ranges and centuries.
- **Clears it:** a short list of irregular counted nouns, or curation storing a claim's dates.

### Timeline places are placed by exact Wikidata label only

- **What:** places are placed with the supply origins' rule (decision 0047), so a spelling that is
  no item's label or alias stays unplaced (Ajrakhpur, Dhamadka), "Sindh" has three exact items none
  described by the claim's words, and "Kutch" matches only a family name, which has no
  coordinates. The fixture places only Fustat.
- **Why left:** a wrong pin is worse than none, and the rule is shared with supply maps.
- **Clears it:** the place register (decision 0047's entry) or a Wikidata id stored on the
  claim's place by curation.

## Generated explainers (decision 0055)

### Dataset rows are not offered to a generated explainer

- **What:** the builder offers only figures the section's cited quotes state; the contract also
  allows a value resting on a dataset row (`datasetCode`), such as a district's CHIRPS rainfall,
  but no dataset value is offered, so an explainer cannot show one.
- **Why left:** a section's dataset rows reach the builder only through other builders' reads
  (the region and climate rows), and an explainer resting on rows alone is no piece and would be
  paid for on every answer.
- **Clears it:** offer the rows of the craft's first district that the section's blocks cite
  (`DatasetRef` with its value), keyed apart from quoted values, and keep row-only explainers out
  unless they also rest on a claim.

### A redraft can run past the builder's wait

- **What:** the first draft and its one redraft share the registry's 60 s ceiling; a slow route
  can leave the redraft cut off, and the section then shows no generated explainer.
- **Why left:** the section waits for its builders before its pictures, and 60 s is the most a
  builder may hold it (decision 0042).
- **Clears it:** production timings of the first answers; if redrafts are often cut, build the
  explainer after `section_done` as a late block, which needs a stream event the contract does not
  have yet.

### A generated explainer reused inside a fresh section has no trail entry

- **What:** a stored explainer placed by the builder in a freshly researched section carries its
  reuse mark ("From earlier research") but adds no `trail FOUND piece:<id>` event; reused sections
  send one per piece.
- **Why left:** builders return blocks, not trail events, and the block's own mark tells the
  reader where it came from.
- **Clears it:** let `Built` carry the pieces a builder placed and send their trail events with
  the blocks.

### The generated explainer's database tests have not run on a laptop

- **What:** `tests/db/test_simulation_pieces_db.py` (the stored pieces query, reuse with a kept
  section, hiding, showing again, the 404 cases) and migration `0019_hidden_generated_explainers`
  run only on GitHub Actions; they were written without a local database (owner rule).
- **Why left:** nothing heavy runs locally.
- **Clears it:** the first Backend checks run of this change passing; then delete this entry.

## What-if lab (decision 0056)

### Alternatives are read from English words beside each other

- **What:** a stored text relates two materials only when an alternative word (`or`, `instead`,
  `replaced`, `superseded`, ...) stands within three words between their names
  (`research/alternatives`); "Alizarin, first synthesised in 1868, superseded madder" and "now
  alizarine has taken its place" relate nothing, and texts in other languages are not read. A
  material is named only by its stored name and glossary surfaces, so the seed's "Indian madder"
  is not named by a plain "madder".
- **Why left:** a wider gap joins co-ingredients ("clay, millet flour, gum and alum or lime"),
  which must never be offered as alternatives; the seed's contrast relations and the curated
  dossiers' "madder or al root" cover the crafts held.
- **Clears it:** curation storing alternatives as `CONTRASTS_WITH` relations (or a material's
  alternatives) so no text has to be read.

### Temperatures and water sources are not offered as inputs

- **What:** inputs are only a stage's stored materials. A temperature (a stage condition's
  readings) or a water source held only as a concept ("Iron content of process water") is never
  an input, so the plan's "temperature" and "river or well water" examples appear only when the
  waters are stored materials with alternatives.
- **Why left:** no stored row relates a condition's stated range, or one water source, to an
  outcome; a what-if over them would need numbers or outcomes a model would have to supply.
- **Clears it:** curation storing condition ranges with the outcomes a source ties to each, or
  water sources as materials with their relations; then an input kind over them in a version 2.

### Listen reads a hypothesis outcome without its label

- **What:** Listen speaks every outcome sentence of a what-if (all options, in reading order),
  and a hypothesis is spoken like a finding; on screen it carries the Hypothesis badge.
- **Why left:** the narration and its cache are decision 0035's and shared with film mode
  (0060); changing what is spoken changes every cached narration's hash.
- **Clears it:** Listen leaving hypotheses out, or a spoken "possibly" prefix, with the narration
  cache version raised.

### One answer can show the same what-if in two sections

- **What:** builders see only their own section, so a process and a chemistry section that both
  name madder can each show the red-dye what-if.
- **Why left:** the registry has no answer-wide view of what other sections built.
- **Clears it:** an answer-level set of inputs already shown passed to the builders, or the
  what-if kept to the first section that names its stage.

### The what-if database tests have not run on a laptop

- **What:** `tests/db/test_what_if_db.py` (the seeded relationships and own claims of the red
  dyes, their offer from the seeded rows, the builder rebuilding the fixture's options) runs only on
  GitHub Actions; it was written without a local database (owner rule).
- **Why left:** nothing runs a database locally.
- **Clears it:** the next Backend checks run passing; then delete this entry.

## Zoom story and timeline map (decision 0057)

### No open-access paper figure is searched for the fibre level

- **What:** the fibre level comes only from Commons and Openverse micrographs; the contract's
  "open-access figure whose `sourceId` is the stored paper" has no adapter (no figure search in
  Europe PMC or a publisher's open figures), so most crafts show no fibre level.
- **Why left:** no figure source exists to reuse, and a new adapter needs its own recorded tests
  and licence reading per figure.
- **Clears it:** one figures adapter over an open-access full-text source (for example the
  figures of Europe PMC's open-access articles, each with its article's licence), checked on
  recorded responses, and the fibre search asking it after Commons and Openverse.

### Picture levels are read from English words

- **What:** a picture's level is read from its title and description against short English word
  lists (`zoom_pictures.LEVEL_WORDS`), and the craft's fibre from a list of fibre names
  (`FIBRE_NAMES`); a picture titled in another language or with an unlisted word ("hand block
  print", "karigar") finds no level, and a fibre material named only by a local word ("kora")
  gives no fibre level.
- **Why left:** a vision call per candidate would spend from the answer for a picture the reader
  may never open; the lists hold the words the stored pictures use.
- **Clears it:** the glossary's terms tagged with a zoom level, or a vision check of the top
  candidate per level within the answer's headroom.

### Undated history claims are not on the timeline

- **What:** the plan lists undated or unplaced claims without a point; version 1 of the timeline
  (decision 0054) gives every point and route a span of years, so an undated history claim is not
  offered at all. Unplaced places are listed without a pin.
- **Why left:** the version-1 fields are fixed and a reinterpretation is not allowed.
- **Clears it:** a version 2 of `timeline_map` with an `undated` list of cited sentences and
  their place, built with lane 0060's renderer.

### The journey database tests have not run on a laptop

- **What:** `tests/db/test_journey_db.py` (the zoom's stored reads: kept open pictures, the
  craft's district claims, the boundary row) runs only on GitHub Actions.
- **Why left:** nothing runs a database locally (owner rule).
- **Clears it:** the next Backend checks run; this entry goes when it passes.

## ElevenLabs music, sound effects, image and video (decision 0058)

### ElevenLabs prices are unverified

- **What:** the API pricing page, its own FAQ and the scale-tier page disagree (music $0.150 or
  $0.275 a minute, sound effects $0.120 or $0.060 a minute or per generation); image and video
  prices appear only on the scale-tier page. The catalogue keeps the higher figure per second or
  image (`services/ai_providers.py`, `_ELEVENLABS`), so Usage may show more than ElevenLabs bills.
- **Why left:** no invoice exists yet and no paid call is made while building.
- **Clears it:** compare the first month's ElevenLabs invoice with Usage, set the confirmed prices
  and `price_verified` true, or set admin price overrides.

### The music bed is timed by an estimate of the narration

- **What:** `voice/film_scenes` times a narrated scene at 1,000 characters a minute (Listen's hold
  estimate), not by the narration's real length, so the bed can be shorter than the film; the
  client loops it.
- **Why left:** the score must not depend on whether Listen has run, and the cache keys on the
  length.
- **Clears it:** time narrated scenes from the stored narration manifests when every block is
  narrated, falling back to the estimate.

### Two asks for the same score can both make it

- **What:** two readers asking at once for an uncached score of the same explainer and language
  each call ElevenLabs; both store identical content-addressed clips and the last manifest wins,
  so the spend is doubled once.
- **Why left:** only the asker can read an explainer, so it needs the same reader in two tabs.
- **Clears it:** a per-answer and language advisory lock around the making, held without a
  database connection across the calls (decision 0040).

### The cue table reads section fields, not their words

- **What:** prose in a geography section gets running water and every process ladder tapping
  tools, whatever the section is about; other kinds and fields get no cue.
- **Why left:** prompts may carry no claim text or names, so a cue can only follow the block kind
  and field.
- **Clears it:** a version 2 table keyed by stored facets (water, dyeing, firing) once pieces carry
  them.

### A long score may outlast the request

- **What:** a 180 s bed and twelve cues can take longer than CloudFront's 120 s origin timeout; the
  making continues as shielded work and the next ask is served from the cache, but that first film
  plays without its score.
- **Why left:** ElevenLabs answers music synchronously and no job queue for audio exists.
- **Clears it:** make scores in `kv-worker` like stage media and let the client poll, if
  production shows first scores timing out.

### Flows content is fetched only from the host the reference shows

- **What:** since decision 0061 a finished image or video is fetched only from
  `storage.googleapis.com` (`providers/elevenlabs_download.DOWNLOAD_HOSTS`), the host of the
  reference's example; the OpenAPI document describes `content_url` only as a signed URL and
  promises no host, so a move to another host fails every ElevenLabs picture and clip loudly.
- **Why left:** an unpinned host could stream any body into the API box; ElevenLabs image and video
  are route choices no seeded chain uses.
- **Clears it:** the first production generation confirms the host; if ElevenLabs names another,
  add it to `DOWNLOAD_HOSTS` after checking the reference.

### Old score clips and manifests stay in the bucket

- **What:** a changed explainer writes a new manifest over the old one, and clips no manifest
  names any more are never deleted.
- **Why left:** clips are shared across explainers by content, so deleting needs a reference count.
- **Clears it:** a lifecycle rule or a sweep that deletes clips no manifest has named for 90 days.

### The score's database tests have not run on a laptop

- **What:** `tests/db/test_film_score_db.py` (the seeded routes, the media cap and the Master Admin
  through the real ledger) runs only on GitHub Actions.
- **Why left:** nothing runs a database locally (owner rule).
- **Clears it:** the next Backend checks run; this entry goes when it passes.

## Sandbox and what-if renderers (decision 0059)

### A generated explainer can choose its own frame height

- **What:** the frame's height comes from a message posted inside the frame (`FRAME_SIZER`);
  generated code that slipped a `postMessage` past the static check could post another height.
- **Why left:** the page cannot measure a frame of another origin, and the message moves nothing
  but that frame's height, clamped to 120 to 1,200 px.
- **Clears it:** nothing needed unless the bounds prove wrong in production.

### A frame may navigate itself to Google's sign-in path

- **What:** `frame-src` allows `https://accounts.google.com/gsi/` for the Google sign-in button,
  so a generated explainer that navigated itself there (refused by the static check) would load
  Google's page inside its own frame, still sandboxed.
- **Why left:** `frame-src 'none'` would break Google sign-in; no other URL loads.
- **Clears it:** a separate origin for the sign-in screens, or sign-in moving off the GSI button.

## Zoom, timeline and film renderers (decision 0060)

### A place beyond the India frame is a signpost, not a pin

- **What:** the timeline draws a placed point outside the India frame (Fustat in the fixture) as
  a signpost at the frame's edge pointing toward it, so the reader sees its direction and its
  Wikidata item but not its distance or neighbourhood.
- **Why left:** the frame is fixed by `components/map/projection.ts`; widening it for one point
  would shrink India on every timeline, and drawing other countries is refused.
- **Clears it:** an inset frame for points abroad (the same projection, its own bounds, the plain
  ground only), chosen by the timeline when it places a point outside the India frame.

### Film volumes do nothing on iPhones and iPads

- **What:** the film sets the music and effects volume through `HTMLMediaElement.volume`, which
  iOS Safari ignores, so there the bed plays at full level under the narration and the two
  volume sliders change nothing. Mute works there: since decision 0061 it sets `muted` on the
  narration, the bed and the cues.
- **Why left:** a Web Audio gain needs the score's audio served with CORS headers from the
  private bucket, and the bucket's CORS is infrastructure this lane does not change.
- **Clears it:** CORS `GET` from the site's origins on the media bucket, then the bed and cues
  through one Web Audio gain adapter in `components/answer/film/FilmSound.tsx`.

### The score's bed is cut from the server's estimate of the film

- **What:** the server sizes the bed and numbers the cues from scenes timed by an estimate of
  each block's narration (`voice/film_scenes.film_scenes`), while the client times the film by
  the Listen script's real durations; the bed loops or ends early and fades over the film's last
  2 s either way.
- **Why left:** the score is made before Listen's audio exists for that language, and the client
  rule (loop, fade, resync) covers both cases.
- **Clears it:** nothing needed unless readers notice; otherwise the score route times scenes
  from the Listen manifest when one is cached.

### Film mode has not met a browser end to end

- **What:** the unit specs render the player's parts and check the clock, captions, mix and keys
  as pure rules; no spec plays the narration, the bed or a cue in a browser, and the production
  E2E does not open Film.
- **Why left:** audio needs the deployed Listen and score routes and a signed-in browser.
- **Clears it:** a step in the production E2E that opens Film on a known-answer question, checks
  the caption and the played bar advance, and closes it with Escape; then delete this entry.

## Phase C review fixes (decision 0061)

### The phase C kinds have not met production

- **What:** `simulation`, `what_if`, `zoom_story` and `timeline_map` joined the built kinds on
  both sides; no production answer has built one yet, and the first generated explainer will be
  the production E2E's indigo question.
- **Why left:** nothing is deployed from a lane (owner rule).
- **Clears it:** after the deploy, dispatch E2E production with `questions=true`; the Indigo row
  passing (or noting that no concept was chosen) and a materials and a history answer showing a
  zoom and a timeline clear this entry.

### A hidden explainer is found by its content as well as its piece

- **What:** a read-back explainer marks a generated explainer hidden when the piece it was kept as
  or reused from is hidden, or when any hidden generated explainer piece has its content hash;
  hiding a block no piece holds keeps it as a piece first, with no vector until
  `embed_knowledge` fills it.
- **Why left:** a later version carries a block whose piece was kept under an earlier answer, and
  versions are never rewritten (decision 0063); two different explainers never share a content
  hash because each carries its own build time.
- **Clears it:** nothing needed unless pieces start being copied between answers.

### The 0061 database tests have not run on a laptop

- **What:** `tests/db/test_simulation_pieces_db.py` now also covers hiding an explainer never
  kept as a piece and hiding a block carried into another answer; it and migration
  `0024_piece_content_hash_index` run only on GitHub Actions.
- **Why left:** nothing runs a database locally (owner rule).
- **Clears it:** the next Backend checks run passing; then delete this entry.

## Phase D contract (decision 0062)

### No stored source states a regional unit conversion yet

- **What:** a `REGIONAL` measure needs a stored claim whose quote states the factor for a region
  (owner O5); no seed or curated claim does, so until one is curated only exactly defined units
  (inch, foot, yard, mile, square foot) convert, and the fixture's measure is a feet value. The
  regional path is built and tested on hand-written quotes (decision 0066).
- **Why left:** a regional value has to come from a source a curator verifies; inventing one would
  break O5.
- **Clears it:** a dossier claim quoting a regional table (a district gazetteer or a state's
  weights-and-measures record) as an equality ("a seer of Kachchh weighs ... kg") that names the
  district or state by its LGD register spelling; then the review adds a `REGIONAL` row to the
  fixture from that claim.

### The phase D fixture shows no price and no Kutch Ajrakh sign of imitation

- **What:** the market blocks show Kutch Ajrakh's GI record and Bagru's GI record with its GI
  journal imitation sign; no seed claim states an Ajrakh price or Ajrakh imitation from GI journal
  text. The curated dossier holds the 1975 Barmer price (C049), which the builder shows
  (`tests/answering/test_market_builder.py` reads it from the dossier); its screen-printing claims
  (C047, C138, C141) cite papers and a web page, not GI journal text, so they are not signs of
  imitation under decision 0066.
- **Why left:** the versions, lesson, quiz and citation goldens of both sides are built from the
  Ajrakh market block, so the price adds a source and renumbers every file built from them; the
  review (0070) fixed its findings and left this fixture refresh whole for one change.
- **Clears it:** add C049's price to `s5.b1` by `curation_keys.curated_id` and regenerate the
  goldens built from it, with the APA text of the new source checked by hand.

### Quizzes mostly vanish in other languages

- **What:** a quiz option is a glossary term marked in its sentence; a translated sentence keeps a
  span only where the English term still occurs, so most questions are dropped outside English.
- **Why left:** translating option terms and re-marking them needs term translations the glossary
  does not hold.
- **Clears it:** local-language names of glossary terms (`Term.localNames` by language) marked in
  translated sentences, then the quiz rebuilt from them.

### Author names are cited as stored

- **What:** citation exports write each stored author as written, so seed sources split on commas
  read oddly (the V&A as "Victoria, & Albert Museum"; the GI journal's applicant note as two
  authors).
- **Why left:** inverting or joining names would guess; the stored values are the seed's.
- **Clears it:** the seed and curated sources store organisation authors whole (the curation
  checker already keeps them whole); the export needs no change.

### Ask the map lists only crafts placed in the district by a cited location

- **What:** a district answers only crafts with a cited district or point location there; a craft
  the master list knows only by its state of practice is not listed for any district.
- **Why left:** placing a state-level craft in every district of the state would be a claim no
  source makes.
- **Clears it:** cited locations for more crafts (curation adds them district by district).

## Local measures, and market and GI (decision 0066)

### A region is named only by its register spelling

- **What:** a regional factor holds only where its quote or claim names an LGD register district
  or state as the register spells it, so "a seer of Kutch" gives no region and converts nothing.
- **Why left:** no alias table of district names exists; guessing that "Kutch" is Kachchh would
  be a place no source names in the register's terms.
- **Clears it:** a reviewed alias list per district in `app/data` (Kutch, Kachchh), read by
  `stated_names.register_places_named` for every region reader at once.

### Prices come only from curated rows

- **What:** a price is shown only from a `CraftPrice` row (a curated dossier's `market.prices`);
  seed and answer claims that state a price are not shown, because nothing records their date and
  place apart from the text.
- **Why left:** reading a date and a place out of free text would choose among several; the
  contract names the curated rows as the source.
- **Clears it:** the curation run adds `market.prices` for each craft whose sources state one.

### GI fields are read by their labels

- **What:** without a curated record, the registry fields come from labelled words in GI journal
  and government claims ("application 183", "Certificate Date 11-05-2011", "Journal Number 37");
  a claim phrased otherwise adds nothing, and two claims stating different values give no status.
- **Why left:** the registry offers no open API, and a curated record replaces the reading.
- **Clears it:** curated GI records for every GI craft (the curation run), after which the label
  reader serves only crafts without a dossier.

### Imitation and per are fixed word lists

- **What:** a sign of imitation must name one of the listed words (fake, imitation, counterfeit,
  spurious, knock-off, passed off, screen-printed, machine-made, power loom, mill-made);
  "duplicate", "copies" and "substitute" are left out because they also name other things. A
  price's `per` is read only after "per" or "/", so "Rs 1,500 a metre" shows no per.
- **Why left:** a model choosing either would spend on every economics section; the lists err
  toward showing less.
- **Clears it:** a dossier field naming the claims that are signs of imitation, read first, and
  a reviewed list of per words.

### The insight database test has not run on a laptop

- **What:** `tests/db/test_insight_builders_db.py` (imported GI records and prices, a craft's
  places, a stored regional quote) is written but runs only on GitHub Actions.
- **Why left:** owner rule: no local database.
- **Clears it:** the next Backend checks run on GitHub; then delete this entry.

## Climate and risk, and ask the map (decision 0065)

### Climate blocks wait for the trend load

- **What:** until the Geo ETL loads the 1981 series, no district has trend rows, so the climate
  builder adds nothing and the seasons rainfall keeps the last load's ten-year period.
- **Why left:** the load is an owner dispatch after the deploy that carries migration 0021.
- **Clears it:** the Geo ETL dispatch in `docs/RUNBOOK.md`, Geo ETL, step 2, with its checks.

### No groundwater values

- **What:** `climate_risk.groundwater` is always empty; groundwater reaches a reader only as cited
  claims.
- **Why left:** no open, key-free, machine-readable district groundwater dataset exists: CGWB's
  Dynamic Ground Water Resources tables are state PDFs and the India data portal's copies need an
  API key (`docs/DATA_SOURCES.md`, Groundwater).
- **Clears it:** an open district dataset (or the owner's choice to take the portal key into the
  ETL), loaded as `DistrictEnvValue` rows and read into `GroundwaterValue`.

### The region panel lists every year of the series

- **What:** the region route and ask the map list each district value, so Climate now shows 45
  years of CHIRPS annual means (with their 10th and 90th percentiles) and 45 years of GHCN CAMS
  means beside the normals and trends.
- **Why left:** the routes give a district's values as stored (contract); folding a series is a
  screen choice.
- **Clears it:** the region and map screens fold a yearly series into one row with a sparkline
  (each year a dataset value), or a contract change that leaves yearly rows out of the facets.

### The GHCN CAMS reader is tested on a hand-written file

- **What:** `ghcncams.read_months` is tested through GDAL on a small netCDF classic file the test
  writes; the real file is netCDF-4 (HDF5) and is first read by the Actions run.
- **Why left:** the real file is about 190 MB and nothing heavy is downloaded on the laptop.
- **Clears it:** the first `ghcncams` run; it fails loudly on non-consecutive months, other units
  or a grid that does not hold India, and `test_ghcncams` gains a check of the run's summary.

### Ask the map matches a prose piece by the district's name

- **What:** a place-facet prose piece's topic names its craft's districts by name slug
  (`water:kachchh`); only crafts placed in the tapped district are read, so a piece is shown for
  the wrong district only when one craft is placed in two districts sharing a name (Bilaspur in
  Himachal Pradesh and in Chhattisgarh).
- **Why left:** the topic keys of decision 0033 name districts by name; changing them is a piece
  contract change.
- **Clears it:** place-facet topic keys by LGD code (`water:lgd-449`, as region stories already
  use), with a piece rebuild.

### The 0065 database tests have not run on a laptop

- **What:** `tests/db/test_climate_map_db.py` (the trend read, the builder over stored rows, ask
  the map's crafts, stories, stale pieces and 404 cases) runs only on GitHub Actions.
- **Why left:** no local database (owner rule).
- **Clears it:** the next Backend checks run.

## Follow-ups, versions and alerts (decision 0063)

### The digest is in English

- **What:** the weekly digest mail is plain English text whatever the reader's answer language;
  each item links to its explainer (`/ask?explainer=<explainerId>`, decision 0070).
- **Why left:** the digest stays off until the owner verifies an SES sender, and its few fixed
  lines have no translation yet.
- **Clears it:** write the mail in the reader's answer language through the translation cache.

### A deepened section never repeats a kind it shows

- **What:** a follow-up does not build a second block of a kind the deepened section already
  shows, so a second map layer or region story that would fit is left out with the duplicate.
- **Why left:** blocks of one kind carry no shared identity to tell a duplicate from a new one.
- **Clears it:** compare per kind (a map layer's code, a story's basin, a reaction's equation)
  and drop only true duplicates.

### Only mapped fields are news

- **What:** the re-check counts a claim only through a curated discipline or a concept heading
  in `HEADING_DISCIPLINES`; mechanism, results, comparison and edge claims are never news.
- **Why left:** those headings span several fields and guessing one would misreport.
- **Clears it:** curated claims carry their discipline; as curation covers crafts, fewer claims
  rely on headings.

### A follow-up that loses a race keeps no text

- **What:** when two follow-ups build on one version, the second's answer row keeps no explainer
  (its research is still written back as claims).
- **Why left:** re-merging onto the newer version would renumber blocks the reader already saw.
- **Clears it:** merge the losing follow-up onto the newer version when its sections still fit,
  and stream the renumbered blocks.

### The alerts database tests have not run on a laptop

- **What:** `tests/db/test_alerts_db.py` and `tests/db/test_explainer_versions_db.py` run only on
  GitHub Actions (no local database, owner rule).
- **Why left:** the owner rule; the SQL is covered there with the rest of `tests/db`.
- **Clears it:** the next Backend checks run.

## Learning block renderers (decision 0068)

### Climate trends are drawn as slopes, not over the years

- **What:** `climate_risk` draws each trend as its slope per decade from zero, with the mean in
  words; there is no year-by-year line, because the block holds no annual series.
- **Why left:** drawing a line through the period would show values no dataset row states.
- **Clears it:** a later block version carrying the CHIRPS annual series (each year a dataset
  value, loaded by the geo ETL), then a line chart of the series with its trend.

### The concept graph is a hub, not the researchers' full graph

- **What:** the figure shows one term at a time with at most seven crafts and a count; on a phone
  long craft names on a crowded ring can touch. The list under it holds every craft.
- **Why left:** a force layout across terms and crafts needs a layout library or a measured
  label pass, and the hub answers the explainer's question.
- **Clears it:** a whole-graph view for researchers on the craft page's Shared science tab
  (decision 0070), with label collision handled.

### Quiz picks are kept in the page only

- **What:** a reload or a new visit clears the reader's answers and score.
- **Why left:** no route stores quiz attempts, and decision 0062 makes a quiz a rebuilt block.
- **Clears it:** an attempts route if the owner wants scores kept (for a class, with the lesson
  builder).

### Compare and the quiz options follow the viewport, not the block's width

- **What:** compare goes side by side at `sm`, `md` or `lg` by craft count, and the quiz options
  pair from `sm`, measured on the window rather than the section the block sits in.
- **Why left:** every other block uses viewport breakpoints, and the section fills the reading
  column at every width.
- **Clears it:** container queries for blocks drawn in narrower places (a lesson slide, a side
  panel).

## Quiz, compare and the shared-science explorer (decision 0064)

### A comparison is only of crafts the resolver listed

- **What:** the understanding reply names compared crafts by the slugs the craft resolver listed
  for the question; a craft the question names that the resolver did not list (it only reaches
  `craftNames`) is not compared, and a craft the reader picked is compared only with crafts listed
  beside it.
- **Why left:** resolving every named craft again for a comparison adds a lookup per name to every
  question, and the resolver lists the crafts a question names in most cases.
- **Clears it:** resolve `craftNames` when the reply also asks for a comparison, and add the
  `RESOLVED` ones to the compared crafts.

### Fixed rules, not a model, choose quiz questions and compare cells

- **What:** a quiz keys the first fitting term of each sentence and takes distractors walking on
  from it; compare and the concept graph take the best-ranked fact. A distractor that also fits
  the blank, or a cell that is true but off the point, is not caught.
- **Why left:** a model call per quiz or block spends the reader's caps on choosing alone, and the
  rules keep every value cited and the output the same for every reader.
- **Clears it:** an optional plan-model pass that may only drop offered distractors and reorder
  offered facts, measured against the rules on the known-answer questions.

### The explorer reads at most three claims per concept and 100 crafts per term

- **What:** a craft whose naming claim is its fourth about a concept, or a term shared by more
  than 100 crafts (by name after the focus craft), can leave a sharing craft out of a node.
- **Why left:** a term like cotton or indigo may be shared by most crafts once curation ends; the
  small EC2 box must answer the explorer in one short read.
- **Clears it:** a stored per-term summary refreshed by the curation import (crafts, concept ids
  and the chosen claim), read whole by the routes.

### A claim's field is its concept type's when it was not curated

- **What:** compare places uncurated claims by their concept type (as the craft page does): a
  mechanism falls in chemistry even when it is physics, and outcomes and comparisons fall in
  overview.
- **Why left:** curated claims carry their discipline, and the curation run covers every craft.
- **Clears it:** the curation of every craft (decision 0053), or a discipline column on `Claim`
  written by the import and by answers.

## Craft page rebuild (decision 0071)

### The register's description is no longer shown

- **What:** the old page showed the craft register's `description` above the claims. `PageCraft`
  has no description, so a craft without a dossier or claims shows only its register facts
  (category, kind, GI status, states).
- **Why left:** the field is not in the contract, and it is uncited register text, which the page
  otherwise never shows as a sentence.
- **Clears it:** an owner decision; if wanted, `description` on `PageCraft` (model, contract,
  fixture) drawn beside the register facts and marked as the register's.

### The stage media client is mounted nowhere

- **What:** the craft page no longer offers Image or Video on a stage. `lib/craftMedia.ts`,
  `lib/mediaJobMemory.ts`, `lib/mediaView.ts`, `components/craft/StageMedia.tsx`,
  `useStageMedia.tsx`, `MediaFigure.tsx` and `MediaShareButton.tsx` stay, with their specs
  (`e2e/craft-media-unit.spec.ts`, `e2e/media-view-unit.spec.ts`).
- **Why left:** whether generation returns on another surface or is retired with its routes is the
  owner's call, and the media contract (`docs/contracts/media.md`) is another lane's.
- **Clears it:** the owner's choice, then mounting the store where generation lives, or deleting
  these modules and specs with the media routes.

### The profile and process client shapes outlive their screen

- **What:** nothing in the frontend calls `GET /crafts/{slug}/profile` or `/process` any more; the
  profile client is deleted. `lib/scienceContract.craftProcessShape` and the process-route rules in
  `lib/processView.ts` (`checkedProcess`, `shownVariants`, `stageHasContent`, `readingClaim`,
  `readingRange`, `isUnbalanced`, `deltaHClaim`, `deltaHText`, `pubchemHref`, `citationsOf`) are
  used only by `e2e/process-view-unit.spec.ts` and `e2e/contracts-unit.spec.ts`.
- **Why left:** both backend routes stay; the specs keep the client half of the science contract
  checked against `shared/science.process.golden.json` until the routes are retired.
- **Clears it:** retiring `/profile` and `/process` in the backend, then deleting these shapes,
  rules and specs (the species helpers the answers use stay).

### Places abroad and rivers are listed, not drawn

- **What:** the Region map fills and tags Indian districts by LGD code only; a place abroad
  (Sindh) or a river (Dhamadka River) is listed with its roles but has no mark of its own.
- **Why left:** `PagePlace` carries no coordinates or river id, and the map has no geometry for
  places outside the district outlines.
- **Clears it:** coordinates (or a HydroRIVERS id) on `PagePlace`, drawn as pins or a river line.

## Learning screens (decision 0069)

### Two citation lookups for cited text outside the explainer

- **What:** `components/craft/useCraftReading` builds the same reading and citation contexts as
  `components/answer/CitedReading`, with the craft page's own numbering.
- **Why left:** the craft page was being rebuilt by lane 0071 in the same working tree.
- **Clears it:** `useCraftReading` keeps its numbering and hands it to `CitedReading`.

### Check yourself asks for a quiz on every finished explainer

- **What:** the explainer asks `GET /api/answers/{answerId}/quiz` once when it finishes, to offer
  Check yourself only when a quiz exists (a 404 draws nothing).
- **Why left:** the route is a read with no model call, and offering a control that then says
  there is no quiz would be a dead end.
- **Clears it:** a `quizAvailable` flag on the stored explainer or the stream's `done`.

### A lesson keeps the explainer's section order

- **What:** the builder chooses sections but sends them in the explainer's order; the contract
  allows any order.
- **Why left:** a reorder control needs the one drag and arrow implementation, which this app
  does not have yet (`lib/routing.moveRoute` is the AI routing page's).
- **Clears it:** a shared list-order helper and Up and Down controls on the builder's rows.

### An added section that found nothing shows until a reload

- **What:** during a follow-up an added section that ends `EMPTY` shows what was searched; the
  stored version leaves it out, so it is gone on the next visit.
- **Why left:** what was searched is useful in the moment, and the stored version is the
  record.
- **Clears it:** reload the stored version after `version` arrives, or drop such sections then.

## Lesson packs and exports (decision 0067)

### A paper's APA reference names no journal

- **What:** the APA style prints a journal article's venue from `container-title`, which no
  source stores; `Source.publisher` holds a journal for some adapters (Europe PMC, Semantic
  Scholar) and a publishing house for others (Crossref, OpenAlex), so CSL items pass it as
  `publisher` and a paper's reference ends with its DOI or URL, without the journal.
- **Why left:** naming the journal from a field whose meaning differs by adapter would guess.
- **Clears it:** sources store the container title apart from the publisher (each scholarly
  adapter fills it), and `citation_formats.csl_item` passes it as `container-title`.

### A file made while a picture could not be read keeps no picture for a week

- **What:** an export is filed under the hash of what it was made from, which does not include
  whether its pictures could be read, so a file made while Commons or Openverse failed is reused
  without the picture until the bucket's `exports/` rule removes it (seven days).
- **Why left:** knowing the pictures before checking the bucket would read them on every
  download, which the reuse is there to avoid.
- **Clears it:** file such a build under a short-lived marker (or skip storing it) so the next
  request tries the pictures again.

### The explainer PDF shows sentences and credits, not drawn blocks

- **What:** maps, river stories, players, molecules, charts and generated explainers appear in
  the PDF as their cited sentences and dataset credits only; the climate slopes, seasons and
  map values a reader sees on screen are not drawn.
- **Why left:** drawing them needs per-kind PDF renderers (and the district geometry) that this
  lane did not have time for; a picture of them would need a headless browser, which the box
  must not run.
- **Clears it:** small per-kind PDF drawings built from the block's own values (a table of
  trends, a month strip, a district outline from the shapes the client already has), each with
  its dataset credit and, for maps, the boundary caption.

### Slide text is sized by its length, not measured

- **What:** the PPTX picks a body size from the characters a slide holds (20 pt down to 11 pt);
  a slide with very long references can still run past its box, and PowerPoint does not shrink
  text it did not lay out itself.
- **Why left:** measuring needs the font metrics of every script per run; the pack keeps at most
  five bullets a slide and lists its sources on one slide by contract.
- **Clears it:** measure with the vendored fonts (python-pptx `fit_text` per script) or split the
  reading and sources slides in the files when they overflow.

### Exports are built one request at a time, without a queue

- **What:** a lesson file or report PDF is built in a worker thread of the request that first
  asks for it; two first requests for different files build at once, and nothing caps how many
  builds run on the box together.
- **Why left:** builds take well under a second for the fixtures and only Professors build packs.
- **Clears it:** a small per-process limit on concurrent export builds, if Usage shows memory
  pressure from them.

### The lesson database tests have not run on a laptop

- **What:** `tests/db/test_lessons_db.py` (building, listing, opening and deleting a pack, the
  owner rule, access days) runs only on GitHub Actions.
- **Why left:** nothing runs a database on the laptop (owner rule).
- **Clears it:** the next Backend checks run.

## Phase D review (decision 0070)

### The curation checks a curated GI date only by its year, and a price's date not at all

- **What:** `curation/entity_rules._gi_messages` (decision 0053) accepts a curated `filedOn` or
  `registeredOn` whose year a quote states, even when no quote states its day or month, and a
  curated price's `date` (`curation/records.Price`) is not checked against its claim's quotes. The
  market builder cuts such a date to the precision its quotes state before showing it, and drops
  a price whose quotes state none (`research/stated_dates.stated_precision`), so no unstated day
  reaches a screen, but the curation check does not report the record.
- **Why left:** the curation and importer files belong to lane 0053, which was running in the same
  tree.
- **Clears it:** the curation rules check each GI and price date with `stated_dates.states_date`
  at its own precision and report a record whose day, month or year no quote states.

### Lesson packs are not proved in production

- **What:** the production E2E builds no lesson pack: its account is a Researcher, and
  `BUILD_LESSONS` needs a Professor, a role that must use two-step sign-in, which the E2E cannot
  answer. The run checks the explainer's report PDF and its four citation files and notes the
  lesson step instead of failing.
- **Why left:** granting a role is the owner's decision (`docs/PROGRESS.md`, Waiting on the
  owner).
- **Clears it:** a Professor E2E account whose authenticator secret is a GitHub secret the run
  turns into a code at sign-in, or the owner's other choice; the run then builds the pack and
  checks its PPTX and PDF (`e2e/production/exportProof.ts` already does when the role allows).

## The lede on the page (decision 0077)

### Listen, film, the quiz and lesson packs leave the lede out

- **What:** the explainer page opens with the lede (`components/answer/LedeBlock.tsx`), and so do
  the report PDF and the citations export, but Listen narrates sections only
  (`voice/narration.spoken_blocks`): it starts at the first section and never marks a lede word.
  Film mode's scenes (`voice/film_scenes.film_scenes`, `lib/filmScenes.ts`), the quiz
  (`research/quiz.py`) and lesson packs (`research/lesson_builder.py`) also read sections only.
- **Why left:** decision 0077 kept these readers on sections; task 3-03 draws the lede and adds no
  Listen or film behaviour.
- **Clears it:** `spoken_blocks` yields the lede first for a whole-answer narration (the Listen
  golden and the narration cache keys change with it) and film opens on a lede scene; the quiz and
  lesson packs take the lede only if the owner wants the direct answer in them.

## Frontend audit exceptions

### picomatch ReDoS advisory excepted in development tooling

- **What:** Frontend checks run `frontend/scripts/audit.mjs`. It fails on any advisory in production
  dependencies, on any other advisory without an entry in `frontend/audit-exceptions.json`, and on
  an entry the audit no longer reports. GHSA-fc5q-39xc-vjpf (picomatch, high) is excepted: it
  reaches only ESLint tooling (`eslint-config-next`, `typescript-eslint`), never the built site.
- **Why left:** no fixed picomatch exists. 4.0.7 is the newest release and is affected, and npm's
  only suggestion is a downgrade of `eslint-config-next` to 14.
- **Clears it:** a fixed picomatch. The audit then stops reporting the advisory, the check fails
  on the stale entry, and removing the entry clears this.

### Field voices are stored and served, but not drawn on the craft page

- **What:** the craft page carries `voices`, `fieldPhotos` and `fieldVoicesTotal`, and the list
  route pages them (decision 0091), but no component draws "In the artisan's words" or "From the
  workshops" yet; only the signed-in reading page `/voices/<id>` exists.
- **Why left:** the answer and craft components were being edited by another lane in the same
  batch.
- **Clears it:** a Voices part and a gallery on the craft page, each with its first page and
  "Show all N" through `fetchFieldVoices`, and "Read the full interview" linking `/voices/<id>`.

### The field voices database tests have not run on a laptop

- **What:** `backend/tests/db/test_field_voices_db.py` (storage, idempotency, ACLs by reader, the
  craft page part, both tombstone cascades) and `test_field_voices_withdrawal_db.py` (the 7-day rule
  and hidden streams across claims, chunks, the page, the reading view and the image route; claims
  on a tombstone and on an edited turn; "Show all" over 60 quotes; re-keying; a stored explainer
  after a withdrawal) run only on GitHub Actions.
- **Why left:** nothing heavy runs locally (owner rule).
- **Clears it:** the first green Backend checks run with this file.

### The expert panel's artisan seat quotes only transcript chunks that back a stored claim

- **What:** since decision 0099 the artisan seat speaks from field transcript chunks (`PUBLIC` and
  `SIGNED_IN`), but only through a stored claim whose citation quotes the chunk; a chunk no claim
  cites is not quoted. It reads with the public reading ACLs, not the asker's own (a researcher's
  `RESEARCHER` chunks are not read), and it does not read KalaVigyan testimony (decision 0083).
- **Why left:** an `expert_view` sentence cites stored claims only, and the builder writes no
  claims; field quotes become claims through the live write-back.
- **Clears it:** the builder writing back a quoted claim for each chunk it would quote, and the
  asker's ACLs on `BuildAsk`.

### The seat search and the artisan's transcript read have no database test

- **What:** `seat_search.stored_seat_search` and `artisan_seat.stored_voices` past the retriever
  (the `ClaimSource`, `FieldSegment` and `FieldRecording` reads) are covered by unit tests with
  injected searches only; no test runs them against Postgres.
- **Why left:** the change was bounded to unit tests; database tests run only on GitHub Actions.
- **Clears it:** a `tests/db` test that stores a field recording, its chunks and a quoting claim,
  and checks the artisan's sentence, name, craft and district.

### The API index still names the single-call panel

- **What:** `docs/CORE_API.md` (the `research/expert_panel` and `services/expert_views` rows)
  still lists `compose_takes`, `PanelAsk`, `panel_message`, `panel_schema`, `parsed_panel` and
  `PanelDraft`, removed by decision 0099, and does not list `panel_seats`, `voiced_seats`,
  `kept_takes`, `compose_take`, `compose_differences`, `seat_search` or `artisan_seat`.
- **Why left:** the change was bounded to the panel's files, its contract and its decision.
- **Clears it:** rewrite both rows from `docs/contracts/explainer.md` ("Expert panel as built").

### Field images are not illustration candidates of their crafts' claims

- **What:** the field voices contract makes each stored field image an illustration candidate of
  its crafts' claims (`MediaRefClaim`, relevance `TEXT` from its caption and labels). No field voices
  module writes `MediaRefClaim` rows, so field images show only in the craft page's gallery, never
  beside a sentence (decision 0091, point 12).
- **Why left:** choosing which claims a photograph illustrates needs the caption-to-claim matching
  of the media lane, and the gallery already shows every image credited.
- **Clears it:** `field_voices_image_store` links each image's `MediaRef` to the visible claims of
  its crafts whose text its caption or labels match, and the cascade deletes those rows with it.

### A partly withdrawn explainer section shows no "quote withdrawn" note

- **What:** `services/field_voices_readback.py` drops the sentences and blocks of a stored explainer
  that cite a withdrawn or stale field interview when the explainer is read. A section left empty
  says so ("A field interview this section quoted is no longer shown."), but a section that keeps
  other sentences shows no note that one was taken out, as the contract asks.
- **Why left:** the explainer contract has a count of removed quotes only on `artisan_voice`, which
  is not a built section block; a note on any section is a new field in `docs/contracts/explainer.md`
  and its web shape, owned by the answer lane.
- **Clears it:** a `withdrawn` count on `ExplainerSection` (and the web shape), set by the readback
  and shown under the section.

### The field voices order check does not span runs

- **What:** `field_voices_sync` refuses a page whose first change is not after the last change of
  the page before it in the same view and run, but keeps no last (`updatedAt`, `id`) between runs;
  the first page of a run is checked only within itself.
- **Why left:** a run resumes at the portal's signed cursor, which already names the last change
  read; storing the stamp beside it needs two more columns per view and a reset on every re-read.
- **Clears it:** `FieldVoiceStream` keeps the last stamp and id of each view, cleared with the cursor,
  and `_read` starts from them.

## The design system migration (decision 0092)

### Retired classes still compile through migration aliases

- **What:** round 6 recorded the baseline (196 files down to 24) and deleted every alias whose
  use reached zero. Still counted: the purple, evidence and red ramps of
  `frontend/tailwind.migration.ts` and the neutral, type and radius aliases in
  `frontend/tailwind.config.ts`, whose last users were the retired tabbed craft page (its files
  are gone, so the next baseline run should bring them to zero); `SandboxFrame`'s `bg-white` (a
  white canvas for sandboxed HTML, deliberate) and the two theme-colour hex values in
  `lib/preferences.ts` that the spec requires.
- **Clears it:** dispatch **Design guard** on `main`, commit the baseline, delete the aliases that
  reach zero and `tailwind.migration.ts` when it is empty.

### The design guard does not see shadcn colour names or inline styles

- **What:** `frontend/e2e/designGuard.ts` counts retired and stock classes, hex and colour
  literals, aliases, physical utilities and CSS properties, off-list media queries and misplaced
  `var()` values per file. It does not count the shadcn names the approved config keeps
  (`primary`, `ring`, `border`, `input`, `background`, `foreground`, `popover`, `muted`,
  `destructive`), physical keys in inline `style` objects, or a class built by string
  concatenation, and it cannot tell a badge's indigo from a button's.
- **Why left:** the shadcn names are part of the approved config rather than migration aliases;
  inline positions are computed at run time (popover placement); job is a judgement.
- **Clears it:** add the shadcn names to the alias count once the components that use them move
  to the semantic names; review by job stays with the skill's section 11.

### The source dialog and the evidence badge outlive the new primitives

- **What:** citation clusters open their own popover or sheet (`editorial/SourcePanel.tsx`, which
  shows each source's attribution and licence beside the byline), so nothing opens
  `components/answer/SourceDialog` any more: `CitationLookup.onOpen` and the `SourceDialog` mounted
  by `ExplainerView`, `CitedReading` and `TermSheet` (through `onOpenCitation`) are dead wiring, and
  `CitationChip` ignores its `onOpen` prop. `components/answer/EvidenceBadge` (purple and amber
  badges) stands beside `components/editorial/EvidenceMark`; `craft/MediaFigure`,
  `craft/CraftTabs`, `craft/CraftOverview` and `craft/SourcesDiffer` are not yet drawn with
  `Plate`, `ChapterRail`, `FactGrid` and `SourcesDifferNote`.
- **Why left:** those files belong to the answer and craft page migrations running beside this
  one.
- **Clears it:** each page lane switches to the editorial primitives, deletes `SourceDialog`, the
  replaced components and `onOpen` from `CitationLookup` and `CitationChip`.

### The map hover card lost its shadow with the legacy aliases

- **What:** `shadow-panel`, `shadow-island`, `shadow-md` and `shadow-lg` now compile to none (only
  popovers, menus, toasts, dialogs, labels on photographs and the phone sheet cast a shadow). The
  menus and sheets this lane owns moved to `shadow-pop` and `shadow-sheet`; the map hover card
  (`components/map/MapHoverCard.tsx`) keeps only its ring.
- **Why left:** the map components belong to the maps lane running now.
- **Clears it:** `MapHoverCard` takes `shadow-pop`.

### The wordmark generator needs a package the backend environment lacks

- **What:** `tools/brand/wordmark.py` reads the WOFF2 fonts in `frontend/fonts`, which needs
  `brotli` beside `fontTools` and `uharfbuzz`; the backend virtual environment has the last two
  only, so the outlines in `frontend/components/brandOutlines.ts` were written from a scratch
  install.
- **Why left:** adding a dependency to the backend for a one-off asset was not worth a lock change.
- **Clears it:** add `brotli` to the tools' development dependencies, or read the fonts from TTF.

## No caps for now (decision 0093)

### Daily allowances are a code table, not a setting

- **What:** the daily voice seconds and media units are `core/roles.DAILY_ALLOWANCES`, unlimited
  for every role; bringing one back is a code change and a deploy, unlike the money caps in the AI
  budget. `QuotaPolicy` rows exist but no code reads them (`backend/app/core/roles.py`).
- **Why left:** the table was code before this change; the owner asked for no caps, not for a new
  setting.
- **Clears it:** read the allowances from `QuotaPolicy` (one loader, `None` unlimited) and drop the
  code table, or drop `QuotaPolicy`.

## Public transcripts and share links (decision 0097)

### The `SIGNED_IN` chunk ACL is read by everyone

- **What:** since the full field transcripts became public, `research/retrieval.chunk_acls_for`
  gives every reader `PUBLIC` and `SIGNED_IN`, so the `SIGNED_IN` value of `ChunkAcl` (migration
  `0027_field_voices`, written by `services/field_voices_records.py`) no longer means signed in.
  `OPEN_CHUNK_ACLS`, the loaders' default when no reader is named, still holds `PUBLIC` only.
- **Why left:** folding the value into `PUBLIC` needs a migration of the stored transcript chunks,
  the field voices writer and its tests, and the field voices lane was finishing its own changes.
- **Clears it:** a migration that sets every `SIGNED_IN` chunk to `PUBLIC` and drops the value,
  `field_voices_records` writing `PUBLIC`, and `SIGNED_IN_CHUNK_ACLS` removed.

### A stopped share's files stay in the bucket until they expire

- **What:** the report PDF and lesson files of a share are filed once under the neutral owner id
  (`services/share_links.SHARED_EXPORT_OWNER`) and kept until the `exports/` lifecycle rule
  removes them. Stopping the share ends the routes and every new link at once, but not the
  stored object.
- **Why left:** the key carries the SHA-256 of what the file was made from, so it cannot be
  guessed, and every signed link lasts 300 seconds; the owner's own exports work the same way.
- **Clears it:** delete the share's objects when it stops, by recording each file's key against
  the share.

### Reading-page metadata reads the version 2 craft page fields

- **What:** `frontend/lib/readingMetadata.craftPageMetadata` takes the description from
  `overview.lede` and the preview picture from the `HERO` entry of `pictures`, which craft page
  schema 3 keeps only until schema 4 (decision 0095, removal by 2026-12-18).
- **Why left:** the client contract for schema 3 (`lib/craftPageContract.ts`) belongs to the
  chapters lane and had not landed when the reading pages moved (decision 0097).
- **Clears it:** read `lede` and `masthead.picture` when the chapter screen replaces the tabs, in
  the same change that drops the flat fields.

### Shared answers draw in English reading metadata

- **What:** `/shared/answers/[token]` and `/shared/lessons/[token]` pass `[ENGLISH]` as the
  answer languages, so a shared Hindi or Urdu answer reads with English language metadata (script
  and direction) in its header and reading styles.
- **Why left:** the list of answer languages comes from `GET /answers/config`, a signed-in read
  (decision 0097 keeps asking signed in).
- **Clears it:** serve the answer language list from a public read (or ship it in the shared
  body) and pass it to the shared screens.

### Craft page chapters not built yet (decision 0098)

- **What:** the version 3 page (`services/chapter_*.py`) doesn't build `what_if`, `concept_graph`,
  `zoom_story`, `supply_map` or `measure` for a chapter. One reaction player holds every step
  instead of one per mechanism. `services/chapter_records.py` loads no concept pictures. The
  chapters job (`app.scripts.build_craft_chapters`) runs steps 1 (conformers and Wikidata points)
  and 6 (pages and the nightly holes check) only: no generated explainers, concept pictures, AI
  media copies or film score, and it runs nightly from Coverage enrichment, not after each
  deploy's import. Until its first run keeps conformers, live pages show no `molecule_3d`; the
  golden's seven molecules are the inputs fixture's kept conformers. An archived version
  (`?version=N`) is served without any field voice or testimony (decision 0098 item 14), so a
  still-consented quote is missing from it too.
- **Why left:** what-if and concept-graph offers need the relationship and shared-term rows that
  only answer builders load today, and a page builder may not search. Per-mechanism players wait
  on `science/mechanisms.craft_concepts`, which the CURATION lane didn't land. Steps 2 to 5 spend
  on models and media and need their own budgets and tests.
- **Clears it:** a rows loader for what-if evidence and shared terms in `chapter_records.py` and
  their pure builders. Cut `chapter_chem._player` by `craft_concepts`. Build job steps 2 to 5 and
  run the job after the deploy's import. Read archived bodies back through the live field-voice
  filters instead of stripping them.

### The timeline map has no pins for Kutch Ajrakh, and the region story never draws a river

- **What:** job step 1 stores a Wikidata point only for a dossier place with a `wikidataId`, and no
  Kutch Ajrakh place carries one, so every `timeline_map` place of its page is unpinned (the route
  Sindh to Kutch is drawn between named places). `region_story` never chooses a river: HydroRIVERS
  basins carry no name, so no offered basin's name can occur in a step's sentence or quote.
  Several curated `whyClaimId`s (C062, C080, C088) describe a step rather than explain it, and the
  page now leaves a stage's why out when its claim is already one of the stage's sentences (Scouring,
  Alum mordant printing, Indigo dyeing, Washing, Final wash show none).
- **Why left:** Wikidata ids for places, and better why claims, are dossier content (the curation
  lane, one agent per dossier); placing by name was tried against Wikidata and does not resolve
  Ajrakhpur or Dhamadka, picks a family name for Kutch and two items for Sindh. Basin names need a
  named river dataset.
- **Clears it:** the curation lane adds `wikidataId` to the Kutch Ajrakh places (Sindh Q37211,
  Kutch district Q1063417) and reviews its why claims; a river-name source joined to HydroRIVERS
  basins.

### The decision 0096 merge is the minimal novelty rule

- **What:** `services/craft_page_answer_assets.py` joins only pieces whose `craftId` is the craft
  and that came from an answer. A piece joins its chapter when every claim it cites is listed on
  the page and it adds something: its kind isn't in that chapter yet, or it cites a claim the
  chapter drafts don't show. Kinds the page rebuilds from rows keep the page's own. Within a slot
  (chapter, kind, topic) the piece showing more claims wins, then the newer one. Left out of
  decision 0096: cross-craft pieces and pieces of any-craft answers; a curated reading of a piece
  with no answer id; the evidence-floor comparison between a curated item and an answer piece; the
  question screen (`research/question_screen`), so `fromQuestion.text` is always null; and the
  `CraftPiece` table and `KnowledgePiece.origin`. The stamp reads the craft's pieces (count, latest
  `updatedAt`, stale, hidden and superseded marks).
- **Why left:** the CURATION lane, which owned the merge, stopped at 23:11 on 2026-11-18. The
  coordinator asked for a minimal rule with targeted tests only.
- **Clears it:** the rest of decision 0096's items 1 to 4 in the same module, with the question
  screen and its tests.

### AI media, film scores and media routes on the craft page

- **What:** AI images and videos made from a craft's claims don't join its page. Nothing builds
  `ai_media`. There's no `MediaAsset.pageKey`, no craft-neutral copy, no `GET /api/crafts/media/{assetId}`
  and no film-score route. The chapters job (`scripts/build_craft_chapters.py`) doesn't exist, so
  nothing sets `Compound.conformerKeptAt`, and a live page shows no `molecule_3d` until a job sets it.
- **Why left:** these were the CURATION lane's (decision 0096 item 5, the job and the media
  worker's page copy), and that lane stopped.
- **Clears it:** a migration adding `MediaAsset.pageKey`, the media worker's copy, the public
  redirect route, the job with its conformer step, and an `ai_media` loader in `chapter_records`.

### The craft page golden's climate series is synthetic

- **What:** `shared/craft.page.inputs.json` holds 45 yearly values per variable for Kachchh. They
  were generated around the stored trend (mean and slope from `explainer.phase-d.golden.json`),
  not read from CHIRPS or GHCN-CAMS.
- **Why left:** the geo ETL output on the laptop holds no Kachchh yearly rows, and nothing heavy
  runs locally.
- **Clears it:** replace the two series with the loaded `DISTRICT_MEAN` rows of district 449 once
  the ETL's yearly output is in the repository, then regenerate the golden.

## Track 1, round 1 (decision 0101, 2026-11-19)

### Contributed quotes from web pages are researcher-only

- **What:** a fact quoted from a fetched web page keeps the T4 page's researcher-only chunk access,
  so it is withheld from signed-out pages and `get_facts` even once approved.
- **Why left:** it is today's research write-back rule; changing it is a licence decision.
- **Clears it:** a public chunk access for a quote the gates verified from an openly licensed page.

### Gate thresholds are first guesses

- **What:** the duplicate gate's 0.8 cosine floor and its neighbour counts (8 compared, 12 for
  novelty) were chosen without data; facts with no embedding are matched only by identical text.
- **Clears it:** tune them on the first month of proposals and record the values in a decision.

### Small gaps in the MCP slices

- **What:** a component card's kicker and title stay English in non-English answers; a failing
  catalogue lookup is caught broadly and offers nothing, like a failing builder. (Browser CORS and
  the clean-up of abandoned registrations were built in round 4.)
- **Clears it:** each in the change that next touches its file.

## Track 1, round 2 (decision 0101, 2026-11-19)

### The review page's picture and testimony cards use their old routes

- **What:** on `/admin/review`, pictures and testimony are decided through
  `/api/contributions/images/review/...` and `/api/testimony/review/...`, which reach the same
  services as `/api/review-queue/{kind}/{id}/{action}`.
- **Clears it:** an optional decide prop on `PictureReviewCard` and the testimony card, then retire the
  old routes.

### Two frontend files over budget

- **What:** `frontend/lib/craftPageContract.ts` (531 lines) and `frontend/lib/craftChapters.ts` were
  over 400 lines before round 2.
- **Clears it:** split each by part (the round 3 template work touches both).

## Track 1, round 3 (decision 0106, 2026-11-19)

### Cited passages held outside text units

- **What:** 16 cited sentences of the Ajrakh page still sit outside any text unit (round 6 made 28
  of the 43 into units `u1087` to `u1113`). Their page text writes an apostrophe as `&#x27;` while a
  unit renders `'`, so a unit would change the approved page's bytes: the stage player's stage 11
  "Why", four timeline card lines, the shared-science atlas's three sentences, two Suran card lines,
  the climate map's side line and five in the shell. The answer's own sentences in the language
  panels, the generator and the structure diagrams are held too.
- **Clears it:** render a unit's apostrophe as the approved page writes it (or rebuild the approved
  page with plain apostrophes), then make the 16 units and reload.

### Fragments are a bridge

- **What:** 9 of Kutch Ajrakh's 79 components still draw from their fragments (70 are native since
  round 6, `monographs/Kutch-Ajrakh/native.json`): the stage player (its stage 11 "Why" is held
  text), the two structure diagrams (their descriptions are the answer's held sentences) and the six
  page tools, whose views draw their own markup on purpose. The kit's script still drives the
  native views' behaviour by ids and classes, and a generated page reuses another monograph's
  fragment for a shared component without a spec.
- **Clears it:** the stage player's held line as a unit, science specs that carry held text, then
  the kit's behaviour moved into the views and the fragments retired.

### What the document does not carry yet

- **What:** the React page takes chapter names from each chapter's kicker or heading (three differ
  from the approved rail), shows the page's sources as one numbered list (no source groups), and its
  masthead counts every cited source (64) where the approved page says 44 plus 24 for the kin crafts.
- **Clears it:** chapter names, source groups and the masthead counts in the `PageLayout` record or
  the document, found by the parity proof.

### A plate's crop is a class or a focal box

- **What:** Ajrakh's plates crop with CSS classes; a generated plate carries the layout's focal box,
  drawn as `object-position`. Two ways to say one thing.
- **Clears it:** express Ajrakh's crops as focal boxes and drop the crop classes.

### Generated picture units are numbered from u9001

- **What:** the plate spec's unit references are `u` and four digits (Ajrakh's ids), so a generated
  page numbers its picture caption and credit units from `u9001`.
- **Clears it:** one unit id pattern for authored and generated documents.

### Kutch Ajrakh's React page draws the authored shell

- **What:** `MonographDocument.shell` carries the approved page's main markup with every component
  inlined from its fragment, so the React page matches the approved one by construction while the
  React shell and the native views catch up (decision 0106, the first parity run).
- **Clears it:** a component joins `monographs/Kutch-Ajrakh/native.json` when its view passes the
  parity run; the shell retires when the React shell reproduces the masthead, the table of contents,
  the margin notes and the sources chapter.

### The authored shell keeps the app's CSS out by name

- **What:** the React page draws the approved markup inside the app, so the app's CSS reached it:
  Tailwind's preflight (heading sizes, sub and sup, button and list resets) and seven class names
  the shell shares with the app (`kv-btn`, `kv-tabs`, `kv-cite`, `kicker`, `panel` and the
  utilities `grid`, `inline`, `ring`). `components/monograph/authoredShell.css` reverts preflight
  in the base layer and gives the colliding names `all: revert` in a layer above the utilities,
  outside native views (`[data-kind]`). A new app class with a name the shell uses would leak
  again; the parity run's drift finder names it.
- **Clears it:** retire the shell (round 3c: every component a native view, the kit's styles in the
  views), or prefix the kit's classes so no name can collide.

### Curated craft documents: what they do not carry yet

- **What:** since round 6 every curated craft is drawn as its document (the tabbed `CraftScreen`
  is retired). The key facts and the record use the passage renderer's plain term list rather than
  the board's four-column FactGrid, and what answers and contributions added to the craft page (AI
  media, contributed plates, field photos, relatives) is not carried into the document. Left
  unused by the retirement: the voice call UI (`components/voice/*`, `lib/voice*.ts`,
  `lib/elevenLabsAgent.ts`), `useHasSession`, `useRevealRow`, `IndiaMapStage`, `MapPlaceList` and
  `MediaActionButton`.
- **Clears it:** a FactGrid component kind for the record; contributed media as document
  components; delete the unused files or give them a new caller.

## Round 6 (2026-11-20)

### The editorial stylesheet is over budget

- **What:** `frontend/app/editorial.css` holds the reading templates' shared styles for the landing,
  atlas, category hub, map and the craft without a monograph in one file of 937 lines; round 6's
  board matching added to it.
- **Clears it:** split it by template (landing, atlas, hub, map, craft record) and import each
  where its template is drawn.

### Structure proposals: what they do not reach yet

- **What:** a category page takes no structure proposals (crafts and families only), an approved
  glossary term has no shared glossary entry (`termKey` stays null) and an approved reaction gets
  no stored science row until the dossier is exported and imported again (decision 0108). The
  STRUCTURE review card has not been seen in a browser.
- **Clears it:** category structure, glossary and science rows written at approval, and a signed-in
  capture of the review screen.

### Defects the production E2E suite found in round 6

- **What:** on Kutch Ajrakh, the labels under the equation's species ("leucoindigo, on the fibre")
  overflow their 15ch box (`white-space: nowrap` on `.bx-chem .eq .side` in the kit's
  `monograph.css`), and at 360 the ion charges spill out of the formula; the Textiles category hub
  draws no family science because the families' monographs answer 404; Kutch Ajrakh's document
  carries aria-labels that begin "AI illustration:", which principle 9 (no AI imagery) may not
  allow. The answer essay check waits for one paid `questions=true` run to save an answer.
- **Clears it:** a kit fix proven by Monograph parity; family monographs for the categories; the
  owner's ruling on the illustrations' labels.

### Small differences from the boards left after round 6

- **What:** the map finding text sets about 5% narrower than the board's (the self-hosted Newsreader
  against the board's Google Fonts copy), so it wraps in two lines where the board has three; the
  hub's monographs shelf leaves two empty cells at 834 and 1440 with seven monographs; at 360 the
  landing's specimen label is 13px narrower because the board's label spills into the page margin;
  the Urdu answer keeps its interface words in English where the Urdu board shows Urdu.
- **Clears it:** compare the font files' metrics; a shelf rule for an odd count; interface words
  for the answer's languages.

## Round 5 (2026-11-20)

### Answer figures are not numbered

- **What:** the answer's figures carry their kicker but no "Fig. N": blocks render on their own and
  the essay does not yet pass numbers down.
- **Clears it:** the answer essay numbers its figures and passes the number to `AnswerFigure`.

### Fig. 1's equation needs leucoindigo's compound record

- **What:** the vat figure draws its balanced equation and atom count only when both leucoindigo
  and indigo have a compound record; only indigo blue (CID 10215) has one, so the equation is not
  drawn.
- **Clears it:** a sourced leucoindigo compound in the compound library.

### Old props and helpers kept for files outside a lane

- **What:** `PageHeader` still accepts an `icon` it no longer draws; `NotesInbox` keeps an ignored
  `reduce` prop for the saved page; `components/guide/guideMotion.ts` (retired springs) is still
  imported by 16 files; `SourceDialog`, `openedSource`, `EvidenceBadge` and `TermSheet`'s
  `onOpenCitation` stay for the restored tabbed craft page and the voice screens.
- **Clears it:** drop each when its last caller moves (the craft bridge's retirement clears most).

## Round 7 (2026-11-20)

### Live research write-backs skipped the candidate gates

- **What:** every live-research write-back of the 14 days to 2026-11-20 is `APPROVED` with no
  `CandidateCheck` rows, where `knowledge-writes.md` expects `IN_REVIEW` with checks under the
  RESEARCH `AUTO` switch. The last write-back ran on 2026-11-17; production has had no answers since
  2026-11-18, so the path has not been exercised since.
- **Clears it:** route write-back through the same gates as proposals (the contribution queue), prove
  it with one real question in production, and re-check the earlier write-backs.

### Nested proposal bodies keep camelCase keys

- **What:** MCP tool arguments use one set of snake_case names (`craft_slug`, `task_key`, ...), but
  `propose_structure` and `propose_source` take the Knowledge API's camelCase body, so their
  descriptions still say `taskKey`.
- **Clears it:** snake_case the MCP forms of those bodies with the old names accepted for a release.

### Leftovers of the map rebuild

- **What:** `answer/place/storyGeometry.ts` imports `boardBox` and `RANN_SALT_FLATS` from the
  pass-through `boardGeometry.ts`. The landing asks for field coverage once per monograph every five
  minutes (30 requests today). (`StateLines` draws the Survey of India state borders again on every
  map, as the owner asked on 2026-11-21.)
- **Clears it:** drop the import and the pass-through; a collection-wide coverage route.

### Speed left after the quality lane

- **What:** on a phone Kutch Ajrakh scores 90 with an LCP of 3.6 s, not 2.5 s. Before LCP it loads
  about 470 KB of fonts (Newsreader italic 144 KB, and Newsreader latin-ext 96 KB pulled in by the
  one arrow, U+2192, in the vat equation) and about 450 KB of JavaScript, because the craft route
  imports the uncurated-craft page and the full renderer statically. The Textiles hub inlines its
  whole category document (LCP 8.4 s, score 73), and `/ask` draws its picture only after hydration
  because the protected shell renders on the client.
- **Clears it:** subset the Newsreader faces and give the arrow a face whose latin subset holds it;
  dynamic imports for the uncurated page and the answer renderers; split curated documents the way
  Ajrakh's shell is split; a server-rendered shell for `/ask`.

### The reaction player's step buttons read as one word

- **What:** axe finds four label mismatches on the hub, because a step button's visible text reads
  "1In the leaf" with no space between the numeral and the name. The approved template and the native
  view both hold it.
- **Clears it:** change the template and the native view together, with a parity check.

### Source tools: what they do not cover yet

- **What:** the lookup allowances are counted in each process's memory, as the proposal limits are,
  so each worker keeps its own count. The production `LookupStore` (`source_lookup_store.from_live`)
  has no test, since every tool test uses fake adapters. PubChem synonyms come only from a stored
  Compound, because the PubChem adapter has no synonyms call. `kalavigyan://index.md` and the
  contributor skill are written by hand and must name every tool, which the tests enforce; the five
  contract copies in `backend/app/data/contributor/contracts` must stay byte-identical to
  `docs/contracts`.
- **Clears it:** allowances in the shared store the trust tiers use; a contract test of the live store
  against recorded adapter responses; a synonyms call on the PubChem adapter; the index generated from
  the server's registry.

### No MCP path for a new map layer's dataset

- **What:** a contributor can deliver a `general_map_layer` for one page, but a new layer of the
  site's own maps (groundwater, a soil series) is added only in `etl/geo` or `tools/maplayers` in the
  repository, as the datasets skill says.
- **Clears it:** a dataset proposal over MCP that carries the source, licence, version and the
  simplified geometry, checked by the same rules before an engineer ships it.

### Question anonymising is rules-based

- **What:** questions that become open work (decision 0113) are anonymised by rules with no model, so a lone first name with no honorific or self-introduction is not detected; the rules lean the other way elsewhere (a place outside the gazetteer written in capitals becomes [name], and a title-cased question may be dropped).
- **Clears it:** a named-entity pass with the cheapest model route on the few questions that survive the rules, run in the nightly step, never at request time.

## How this document is kept true

| Change | What to do here |
|---|---|
| A shortcut is taken | add its entry, with what is wrong, why it was left and what clears it, in the same change |
| A shortcut is cleared | delete its entry in the change that clears it |
| A round ends | the lead re-reads the round's entries and updates "Last reviewed" |

An entry is true only while its "What" still describes the code; when a change makes it untrue,
rewrite or delete the entry in that change.
