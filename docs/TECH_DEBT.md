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

Last reviewed: 2026-11-22.

## Infrastructure

### CloudFront to origin is plain HTTP

- **What:** CloudFront reaches nginx on the EC2 box over HTTP on port 80 (`docs/RUNBOOK.md`,
  `infra/terraform/cloudfront.tf`). The origin is protected by the CloudFront-only security
  group and the `X-Origin-Verify` header, but the hop between CloudFront and the box is not
  encrypted. The designer and documentation portals use the same pattern.
- **Why left:** TLS ends at CloudFront; there is no custom domain or origin certificate yet, and
  the pattern matches the portals so they can be changed together. Deferred by the owner on
  2026-11-22 ("we will take care of it later on") as D43 of the cross-portal list of decisions
  deferred to launch (`C:/dev/IIT/docs/DEFERRED_FOR_LAUNCH.md`).
- **Clears it:** an origin certificate (custom domain with certbot, already installed and
  unused on the box) and `https-only` origin protocol, done for all three portals in one change,
  with a certificate-expiry check in each post-deploy run.

## Backend structure

### Python code over budget

- **What:** recorded in `tools/hygiene_baseline.json`, 9 files over 400 lines, 46 functions over
  40 lines and 9 functions with more than 5 positional parameters on 2026-11-22 (12, 54 and 9 on
  2026-11-16). The largest files:
  `backend/migrations/versions/0001_initial_schema.py` (2853), `etl/crafts/wikidata_link.py`
  (1121), `backend/app/api/routes/auth.py` (784), `backend/app/services/two_factor.py` (703),
  `etl/crafts/seed_claims.py` (642), `backend/app/providers/router.py` (566),
  `etl/crafts/aliases.py` (543),
  `backend/tests/db/test_db_flows.py` (464), `backend/app/services/knowledge_view.py` (502),
  `backend/app/data/craft_master_loader.py` (433).
- **Why left:** most were ported from the designer portal with the same shapes so the portals
  stay mergeable; splitting them is a separate restructuring change.
- **Clears it:** split along responsibilities when a file is next changed; run
  `tools/hygiene_check.py --update-baseline` after each clean-up. The initial migration stays
  one file (migrations are not rewritten).

### Scholarly adapters: what waits on keys and the planner (decisions 0005, 0139)

- **What:**
  - Fixtures that are not recordings: `semantic_scholar_search.json` wraps two recorded paper
    records in the search envelope (search answered 429 without a key);
    `springer_nature_search.synthetic.json`, `springer_nature_jats.synthetic.xml`,
    `springer_nature_jats_none.synthetic.xml` and `elsevier_article.synthetic.xml` are hand-written
    from the documented shapes (`backend/tests/sources/fixtures`).
  - The configured `ELSEVIER_API_KEY` may search Scopus but not read abstracts or full text
    without an institution token, so `elsevier` fetch is `not_found` for every record.
  - OpenAlex without `OPENALEX_API_KEY` allows $0.10 a day per address, about 100 searches; after
    that it answers 429 until midnight UTC and the shared hold pauses every process.
  - Publisher full text (`ScholarlySources.publisher`, `sources/scholarly/publishers`) is built
    but nothing asks it: the planner reads only the open-copy locator.
  - Wiley TDM is not read: it serves PDF only, behind a redirect, with its token, and the fetcher
    sends no keys.
- **Why left:** no `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` or `SPRINGER_NATURE_API_KEY` and
  no Elsevier institution token exist yet; the planner belonged to the answer-composition lane of
  round 7, which ran beside the sources and providers lane.
- **Clears it:** the owner sets the three keys (Springer Nature's with text-mining terms) and
  `ELSEVIER_INSTTOKEN`, each tested from the settings screen, and the fixtures are recorded then; give `planner/reading.LiveSources` a
  `publisher` field, set it in `services/live_sources` from `scholarly.publisher`, and let
  `DocumentReader.open_access_document` read a closed DOI the publisher holds; read Wiley's PDF
  once the fetcher can carry one host's token.

### Web search and fetcher: recordings and the box (decisions 0007, 0139)

- **What:** the SearXNG and Brave fixtures (`backend/tests/sources/fixtures/*.synthetic.json`) are
  hand-written to the documented shapes, and `kv-fetcher` with its parser processes has not been
  smoke-tested on the box.
- **Why left:** SearXNG runs only on the box, there is no Brave key on the laptop, and the box is
  reached only through a deploy.
- **Clears it:** after the next deploy, check `/health`, one HTML and one PDF fetch, the parser
  processes staying under the 768 MB cap and the `WebFetch` row an answer writes; then record one
  SearXNG and one Brave answer to replace the synthetic fixtures.

### Stored-knowledge retrieval: what is left (decision 0008, round 4)

- **What:** round 4 cleared stamps per embedding model with re-embedding, cleared vectors on a text
  change, embedding after the seeds on every release, the Indic text ranking and the seed import's
  passages (`docs/contracts/retrieval.md`). Left: knowledge pieces carry no stamp, and the
  candidate gates' neighbour search and the piece store's reuse distance compare vectors without
  it; the Wood Handbook import has no passages, because the repository holds no text of the cited
  edition (FPL-GTR-190).
- **Clears it:** stamp pieces and filter the gates' and the piece store's neighbours on the current
  model; vendor the pages of FPL-GTR-190, or give FPL-GTR-282 its own source and re-cite the wood
  claims after a quote check.

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

- **What:** (1) The pack holds documents, not quotes: the `WEB_READ` reader that extracts
  verbatim quotes for the composer is not built. (2) Coverage runs one stored search per facet,
  each embedding its target (up to eight embedding calls per question). (3) References are
  followed only as DOIs written in the text, through Crossref, which returns abstracts only; links
  in pages and reference lists without DOIs are not followed. (4) Facet coverage counts claims
  that share a word with the target; it does not judge whether they answer it. (5) Every query
  runs on every source of its tier, including Commons and PubChem for questions they cannot serve
  (each answers quickly with no hits). Every answer writes its `AnswerTrace` rows since decision
  0146.
- **Why left:** the `WEB_READ` reader is the next lane; a better coverage judgement needs the
  known-answer checks to calibrate against.
- **Clears it:** the reader turns documents into quoted evidence; embed the facet targets in
  one batch; follow reference lists through OpenAlex `referenced_works` when that adapter
  exposes them; route facet types to the sources that can serve them once the checks show
  which do.

## Live research write-back (decision 0011)

### The composer does not yet ask for quote renderings (decisions 0013, 0023, 0139)

- **What:** `research/quote_renderings.english_renderings` renders a draft's non-English quotes into
  English through the TRANSLATE route and keeps a rendering only when `translation_problems`, read
  from the quote's language, finds nothing; `research/composition.sentence_violations(...,
  renderings=)` then measures the overlap, the unrelated-source and the stance checks on the
  rendering while the citation keeps the verbatim quote. Nothing calls it yet: the composer's
  post-check (`composer/drafts.checked_sentence`) passes no renderings and the write-back's quote
  gate (`services/write_back_plan`) compares raw quotes, so a sentence resting only on a Hindi
  passage is still dropped.
- **Why left:** the composer and the write-back plan belonged to the answer-composition and
  write-back lanes of round 7, which ran beside the sources and providers lane.
- **Clears it:** in `composer/drafts`, collect the spans whose evidence item's `language` is not
  English as `QuotedIn`, call `english_renderings` with the TRANSLATE route's `ModelTranslator`
  once per draft, and pass the renderings to `sentence_violations`; let `write_back_plan`'s
  overlap read the same renderings.

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

## Voice backend (decision 0017)

### Voice in other languages is not yet heard or read by its speakers (decisions 0025, 0157)

- **What:** what a test can check is checked for every offered language: a relay turn sends Scribe
  and speech their codes and speaks the language's source word, and every phrase whose English says
  no carries its language's negation (decision 0157, item 7). No call with a real key has run in a
  language other than English, and Scribe's published accuracy is Scribe v2's: Urdu's band is
  moderate (25-50% word error), so an Urdu question may often be misheard. The spoken phrases (the
  `voice.*` entries of `backend/app/data/interface_words/`) were written by the voice lane and no
  native speaker has reviewed them. In `AGENT` nothing yet tells the agent a session's language: the
  token takes none and client overrides are off, so the agent hears in its own language until
  `language_detection` switches; the presets are not provisioned.
- **Why left:** a recorded turn needs the owner's ElevenLabs key, and a review needs a reader of
  each language.
- **Clears it:** a reader of each language records a review on the `voice.*` entries of its file,
  correcting any phrase first (decision 0157, item 5); the spike records one relay turn per language
  and one agent call in Hindi; if Urdu misses too often, drop `ur` from `STT_LANGUAGE_CODES` (voice
  then stops offering it) or try `scribe_v3` with Hindi as a `secondary_language_codes` hint; the
  spike decides whether the agent gets an `agent.language` override or one agent per language.

### An agent call cannot be hung up from our side

- **What:** after an `AGENT` call's row ends, the ElevenLabs call can run on to the agent's 600 s,
  which reconciliation charges, so the user may go below zero for the call's day (the settlement
  row counts on that day, decision 0140).
- **Why left:** ending a conversation needs an ElevenLabs endpoint the spike has not confirmed; it
  is bounded by the day's seconds, the turn and replay limits and the 40-turn cap (decision 0022).
- **Clears it:** end the ElevenLabs conversation when the row ends, once the spike shows how.

## Voice UI (decision 0020)

### The live agent call has not run in a browser

- **What:** the release check `e2e/production/voice.spec.ts` drives the dock on `/design/voice`
  at desktop and phone widths in both themes: the notice, a relay turn recorded from Chromium's
  fake microphone, sent, answered from the relay goldens and played, and the end, with the dock
  inside the screen and its contrast checked (decision 0140). The `AGENT` path (the ElevenLabs
  WebRTC call joining a LiveKit room, the server writing each turn to the transcript as it is
  spoken) has not run, nor has the dock above the bottom island, since no page with the island
  mounts it while the call is switched off (decision 0035).
- **Why left:** an `AGENT` call needs a real ElevenLabs agent and conversation (the spike); the
  dock's page comes back with the call.
- **Clears it:** one real `AGENT` call once the spike passes, and the same check run on the page
  that mounts the dock when `VOICE_CALL_ENABLED` brings the call back.

### The dock asks for a bit rate it cannot enforce

- **What:** the relay recorder asks `MediaRecorder` for the session's `audioBitsPerSecond`
  (32 kbit/s) and sends a turn at nine tenths of `maxAudioBytes`; a browser that ignores the asked
  rate (Safari's AAC is the likely case, unverified) sends shorter turns than a minute.
- **Clears it:** measure the recorded rate per browser in the smoke spec; if one ignores it, raise
  that type's byte ceiling in the contract with its measured rate.

## Science engine (decision 0015)

### Seeded crafts without a cited reaction, a firing stage or a stated temperature

- **What:** reactions now come from the science seed (Kutch Ajrakh, Bagh, Machilipatnam) and
  from the curated dossiers of nine crafts (those three, Bagru, Sanganeri, Bastar Dhokra, Agates
  of Cambay, Firozabad Glass, Cane and Bamboo, through `services/curation_structure`). What is
  left: Dabu (its dossier holds no reaction) and Akola stages have materials and tools but no
  reaction, because no source the seed or a dossier holds states one; no craft has a process with a `FIRE` stage, so kaolinite dehydroxylation has no
  reaction (the terracotta seed is sub-category mechanism chains); stage concepts without an
  upstream ordinal (Akola mud soaking and paste preparation, Machilipatnam and Sanganeri block
  carving) get no stage although `PRECEDES` edges could place them; and no seed claim states a
  temperature or pH, so no seeded reading is checked against an envelope.
- **Why left:** reactions and readings are written only as a cited quote states them; the
  sources still to find are a GI application or a chemistry paper on Dabu mud resist and on
  Akola's mud and indigo work, a curated clay craft's firing schedule, and a dyeing source
  stating a bath temperature or pH. Finding them is research through the KalaVigyan MCP server
  (`search_sources`, `read_source`, then `propose_structure` for a reaction).
- **Clears it:** a dossier or seed reaction for Dabu and Akola from such a source, a curated clay
  craft with a `FIRE` stage and its stated temperature, and `claim_seed.stage_rows` ordering a
  stage by its `PRECEDES` edges when no ordinal is stated.

### Out-of-envelope readings are not in a review queue

- **What:** the contract lists every `OUTSIDE` reading in the review queue; no review queue
  exists, so they are only shown with their status.
- **Clears it:** the review-queue lane lists readings whose `envelope_check` is `OUTSIDE`.

## Answers in Indian languages (decision 0023)

### The read-back check is not yet calibrated by readers

- **What:** a translation is read back into English and refused when its reading loses a figure,
  a negation or a hedge, adds one, or keeps fewer than half the English's terms (decision 0157,
  item 1). That half is the quote overlap floor, chosen without a reader: no speaker of Hindi or
  Tamil has yet judged which sentences drifted, so the check may refuse a faithful sentence (it
  then shows in English) or keep a drifted one whose reading happens to share the English words.
- **Why left:** the calibration needs a reader of each language.
- **Clears it:** a reader of Hindi and one of Tamil read a known-answer answer in their language
  (the production E2E's Known Answers report gives each translated sentence beside its English;
  the Tamil one is asked on the site), and for every sentence they record, as a case in
  `backend/tests/research/test_translation_meaning.py`, the English, their own literal English of
  the translation and whether it kept the meaning; `READ_BACK_TERMS_KEPT_MIN` is then set so the
  check decides every recorded case as its reader did.

### Interface words in other languages wait for their readers

- **What:** the fixed words of the answer screen (the provenance rail and the actions), a stored
  answer's headings and follow-ups and the status lines are shown in an answer language only from
  a reviewed entry of `backend/app/data/interface_words/` (decision 0157, items 3 to 6). The Hindi
  and Urdu essay words are sourced from the Kutch Ajrakh monograph and the Urdu board (جواب, ماخذوں
  سے, محفوظ کریں, اس جواب کا حوالہ دیں and the rest) but no entry is reviewed yet, "Saved",
  "Saving", "Removing" and one source have no source, and the other languages, the headings, the
  follow-ups and the status lines have no entries. The not-enough-evidence message and the errors
  are composed in English and have no entries at all. A craft's name stays as it is written in
  English, as the monograph writes it.
- **Why left:** a reviewed word needs a reader of its language; approving a design is not
  reviewing its words (the board and the monograph disagree on two Urdu words).
- **Clears it:** a reader of each language supplies the missing words and records a review on
  each entry they approve (decision 0157, item 5), the Urdu reader first, choosing between the
  board's and the monograph's readings; then the templates of the not-enough-evidence message and
  the errors join the lists the same way.

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

## Yahoo sign-in (decision 0026)

### Yahoo sign-in not yet seen running

- **What:** the Yahoo app is registered and live: `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET` and
  `NEXT_PUBLIC_YAHOO_CLIENT_ID` were set on 2026-11-16 and production's `/auth/config` reports
  `yahooEnabled` (checked 2026-11-23). No account has signed in with Yahoo yet (production has
  password and Google accounts only), so the token endpoint's acceptance of the secret in the form
  body and of the PKCE parameters is still taken from DR, where it has run since 2026-10-10.
- **Clears it:** one sign-in with a rostered Yahoo address on the production login page.

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

### Listen has no fallback voice

- **What:** PLAN 10.6 reads aloud with the Gemini voice when ElevenLabs is down; Listen is hidden
  instead (`listen.languages` empty), because the Gemini voice gives no word timings.
- **Why left:** highlighting needs timings; a fallback without them is a second Listen.
- **Clears it:** a Gemini read-aloud that highlights by sentence only, if the owner wants Listen
  while ElevenLabs is down.

## Sectioned composition (decision 0032)

### The voice turn's reply limits are prompt lines

- **What:** the voice turn's one section of three sentences and no follow-ups are lines of its
  prompt only: `voice/compose.voice_composed` calls `parsed_answer` without a form, so a longer
  reply is trimmed to the whole answer's six sections of eight sentences instead. The
  whole-answer composer and the translation are trimmed and checked on our side (decision 0138).
- **Why left:** `backend/app/voice/**` is the voice lane's, and the voice call is switched off.
- **Clears it:** `voice_composed` passes `form=AnswerForm(sections=1, sentences=VOICE_MAX_SENTENCES,
  follow_ups=0)`, with a unit test.

## Stored knowledge pieces (decision 0033)

### Topic keys match only the same glossary terms

- **What:** a facet's topic is the glossary terms the question names (else the place or the
  craft), so a rephrasing that names one more or one fewer term researches again, and a question
  in an Indian script matches only the glossary's local names. Reusing a stored set whose terms are
  a subset of the question's is safe only within a nearness of the question's vector to the
  stored piece's, and nothing in the code can tell that nearness.
- **Why left:** the nearness is a production measurement (checked 2026-11-22, decision 0142); a
  guessed one would serve a narrower set for a broader question.
- **Clears it:** the lead measures, over the answers of the last 30 days that researched a facet
  (`Answer.tiersUsed` holding `T3` or `T4`), how many researched facets had a current stored piece
  of the same craft and facet whose topic terms are a strict subset of the question's marked terms,
  and the cosine distance between the question's vector and that piece's `embedding`. If such near
  misses are common, accept a subset set within the distance below which those pieces' claims all
  reappear in the fresh answer (`piece_store.reusable`, `research/piece_topics`); if they are rare,
  delete this entry.

### Answers never grow the Process tab

- **What:** plan 2.2 wants process stages answers find to land in the science tables. No answer
  writes `Process` or `ProcessStage` rows (decision 0038). The cited-order route (order stages only
  by `PRECEDES` edges from claims that state the sequence, names only from curated or seeded
  concepts) can create nothing: every craft holding curated or seeded stage concepts already has
  its process (checked 2026-11-22: the six seeded crafts with stage concepts each have a seed
  process, every dossier with stages writes its curated process), and the stages answers find carry
  the names a planner chose, which the route may not use.
- **Why left:** an answer-found stage can only join a craft's existing process by a person's
  placing it (decision 0142).
- **Clears it:** the other route this entry named: a review-queue item for an answer-found stage
  concept and a review screen where a Professor places it in the craft's process or rejects it,
  writing the `ProcessStage` with the review's note. It waits on that screen (design and answer UI
  lane) and its review-queue item being scheduled together.

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

## River lines, tracer and monthly rainfall (decision 0043)

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

### A stretch is the reaches with a vertex inside the district

- **What:** a step's stretch and a district's entry point are found on the simplified basin lines
  (`regionStory.stretchOf`, `districtEntries`); a reach that crosses a district corner without a
  vertex inside it is left out of the stretch, and its district lights at the previous district's
  point.
- **Why left:** the server's order (`river.districtLgds`, PostGIS on full geometry) still decides
  the order, and the error is a few kilometres at district scale.
- **Clears it:** serve each reach's districts in the basin file (lane 0043 computes them already)
  and read them instead of testing vertices.

## Reaction player, material cards and 3D molecules (decision 0045)

### The zoom story reads the craft's matter on its own

- **What:** the reaction, card, molecule, what-if, supply-map and generated-explainer builders
  share one read of the craft's matter per answer (`BuildAsk.matter`, decision 0152); the zoom
  story builder (`services/journey_builders.ZoomStoryBuilder`) still calls `craft_matter` itself,
  so an answer whose chemistry or materials section shows a zoom reads the rows once more.
- **Why left:** `journey_builders.py` belonged to the time, market and figures lane in round 7's
  debt round, so this lane left it.
- **Clears it:** `ZoomStoryBuilder.build` reading `await ask.matter.read(self._tools.sessions,
  craft)`, with `tests/journey/test_zoom_story.py` patching `app.services.craft_matter` as
  `tests/matter/test_matter_reads.py` does.

## Expert panel (decision 0046)

### The reading share does not steer queries

- **What:** each seat's preferred kinds take every other early read of what was found, but which
  kinds are found depends on the queries the plan call writes; GI journals and government reports
  come mostly from the web tier and only when a query looks for them.
- **Why left:** the plan call is told each seat's kinds; reserving queries per tier would split an
  already small section share further.
- **Clears it:** a measured look at which kinds Expert sections read, then a tier share in
  `planned_queries` if seats' kinds are missed.

### The panel call has not met Claude Sonnet yet

- **What:** the seat, retake and difference calls are tested on their route (the builder compose
  model, `answer_routes.BUILDER_TUNING`, Claude Sonnet 5.5 on the answer's headroom;
  `tests/experts/test_panel_retakes.py`) and against recorded replies, but no production answer
  has been read for its views and an "Experts differ" card.
- **Why left:** it needs a paid production run, which only the lead dispatches.
- **Clears it:** the production questions run dispatched with `questions=true`: its Expert answer
  carries a note of the panel's views and Experts differ pairs (`e2e/production/expertPanel.ts`),
  read with the `COMPOSE` spend of that answer in Usage.

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

## Phase C contract (decision 0054)

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
  posting a refusal that `SandboxFrame` turns into hiding the block. Waits on the owner's rule
  (checked again on 2026-11-22: the static check covers code numerals since decision 0061).

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

## Generated explainers (decision 0055)

### A redraft can run past the builder's wait

- **What:** the generated explainer drafts within `SIMULATION_BUDGET_SECONDS` (60 s) and redrafts
  only when the time left is at least what the first draft took (decision 0142), so the registry's
  wait no longer cuts a redraft, but a slow route can still leave a section without its explainer:
  the builder then records `OUT_OF_TIME` or `NO_TIME_TO_REDRAFT` under `Answer.plan.builds`.
- **Why left:** how often that happens is a production measurement.
- **Clears it:** the lead reads `plan->'builds'` of a week of Expert answers on production. If
  `OUT_OF_TIME` and `NO_TIME_TO_REDRAFT` are a large share of the `simulation` outcomes, build the
  explainer after `section_done` as a late block, which needs a stream event the contract does not
  have yet; otherwise delete this entry.

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

## ElevenLabs music, sound effects, image and video (decision 0058)

### ElevenLabs prices are unverified

- **What:** the API pricing page, its own FAQ and the scale-tier page disagree (music $0.150 or
  $0.275 a minute, sound effects $0.120 or $0.060 a minute or per generation); image and video
  prices appear only on the scale-tier page. The catalogue keeps the higher figure per second or
  image (`providers/catalogue_specs.py`, `_ELEVENLABS`), so Usage may show more than ElevenLabs bills.
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

## Phase D contract (decision 0062)

### No stored source states a regional unit conversion yet

- **What:** a `REGIONAL` measure needs a stored claim whose quote states the factor for a region
  (owner O5); no seed or curated claim does, so until one is curated only exactly defined units
  (inch, foot, yard, mile, square foot) convert, and the fixture's measure is a feet value. The
  regional path is built and tested on hand-written quotes (decision 0066).
- **Why left:** a regional value has to come from a source a curator verifies; inventing one would
  break O5.
- **Clears it:** curation only; the code path is built, and since decision 0147 the region may
  be named by its register spelling or any other name `data/district_other_names.json` lists
  ("a seer of Kutch" now names Kachchh). For Kutch Ajrakh: a dossier claim quoting the weights and
  measures table of the Kutch district gazetteer (Gujarat State Gazetteers, Kutch District, 1971,
  or the Gazetteer of the Bombay Presidency, Cutch, 1880) as an equality ("a seer ... weighs ...
  kg", "a gaj is ... m"); then the review adds a `REGIONAL` row to the fixture from that claim.

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
- **Clears it:** curation only; the code path reads any cited district or point location. For
  each GI craft the master list places by state alone, a dossier place naming its district from
  the GI journal's "geographical area" passage or the district gazetteer, starting with the GI
  crafts no dossier covers yet (Tharu embroidery, Kutch embroidery, Kasuti embroidery and the
  other GI rows of `craft_master_list.json` without a dossier).

## Local measures, and market and GI (decision 0066)

### A price stated with several years, places or prices needs a curated row

- **What:** without curated rows, a price is read from a cited claim of the craft only when the
  claim states exactly one price, one year and one LGD district (decision 0147,
  `market_store.stated_price_offer`); a claim stating two prices, a range of years or two places
  ("a cotton bandhani cost Rs. 10 to Rs. 50 and a georgette one Rs. 50 to Rs. 250") shows none.
  19 prices in 12 dossiers are curated today.
- **Why left:** choosing among several dates or places in one sentence would be a guess.
- **Clears it:** curation only: `market.prices` rows for those claims, starting with the crafts
  whose GI journal or gazetteer prices state several items (Kutch Bandhani, Tikuli Painting,
  Uttarakhand Ringal Craft), each row naming its date and place.

### GI fields are read by their labels

- **What:** without a curated record, the registry fields come from labelled words in GI journal
  and government claims ("application 183", "Certificate Date 11-05-2011", "Journal Number 37");
  a claim phrased otherwise adds nothing, and two claims stating different values give no status.
- **Why left:** the registry offers no open API, and a curated record replaces the reading.
- **Clears it:** curation only: a `market.gi` record for each GI craft (21 of the master list's
  209 GI crafts have one), read from its GI journal and registry pages as the 21 are, starting with
  Tharu Embroidery, Kutch Embroidery, Kasuti Embroidery, Sandur Lambani Embroidery and Toda
  Embroidery; the label reader then serves only crafts without a dossier.

### Imitation is a fixed word list

- **What:** a sign of imitation must name one of the listed words (fake, imitation, counterfeit,
  spurious, knock-off, passed off, screen-printed, machine-made, power loom, mill-made);
  "duplicate", "copies" and "substitute" are left out because they also name other things. (A
  price's `per` is read after "per", "a", "an" or "/" since decision 0147.)
- **Why left:** a model choosing would spend on every economics section; the list errs toward
  showing less; a dossier field needs a stored column the curated import writes, and the import
  belongs to the curated-import lane, which was running in the same tree.
- **Clears it:** a dossier `market.imitation` list of claim ids (each citing a GI journal), stored
  by the curated import and read before the word list by `services/market_builder`.

## Climate and risk, and ask the map (decision 0065)

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

### Ask the map matches a prose piece by the district's name

- **What:** a place-facet prose piece's topic names its craft's districts by name slug
  (`water:kachchh`); only crafts placed in the tapped district are read, so a piece is shown for
  the wrong district only when one craft is placed in two districts sharing a name (Bilaspur in
  Himachal Pradesh and in Chhattisgarh).
- **Why left:** the topic keys of decision 0033 name districts by name; changing them is a piece
  contract change.
- **Clears it:** place-facet topic keys by LGD code (`water:lgd-449`, as region stories already
  use), with a piece rebuild.

## Follow-ups, versions and alerts (decision 0063)

### A follow-up that lost a race shows its old block numbers until a reload

- **What:** a follow-up that finds a newer version saved meanwhile is merged onto it and stored
  with its blocks renumbered (decision 0143), and its `version` event carries the new mark
  (`basedOn` the newer version); the reader still sees the blocks under the numbers they streamed
  with, beside the version they asked on, until the page is reloaded.
- **Why left:** the stream has no event that renumbers shown blocks, and the client's version
  reader (`frontend/lib/explainerVersions`) belonged to the design lane running at the same time
  (2026-11-22).
- **Clears it:** `reduceAnswerEvent` reloads the stored version when the `version` event's
  `basedOn` differs from the `builds_on` version it followed, instead of keeping the streamed
  sections.

## Learning block renderers (decision 0068)

### Quiz picks are kept in the page only

- **What:** a reload or a new visit clears the reader's answers and score.
- **Why left:** no route stores quiz attempts, and decision 0062 makes a quiz a rebuilt block.
- **Clears it:** an attempts route if the owner wants scores kept (for a class, with the lesson
  builder).

## Quiz, compare and the shared-science explorer (decision 0064)

### A shared-science node lists at most 100 of the crafts sharing its term

- **What:** the explorer and the concept graph now read every craft whose claims name a term, with
  all its naming claims (`SharedTermCraft`, rebuilt by `refresh_shared_terms` at each release and
  each night, decision 0143), but a node (`ConceptNode.crafts`, `CONCEPT_CRAFTS_MAX` in the
  contract) still lists at most 100 of them, the focus craft first and then by name, and does not
  say how many share the term.
- **Why left:** a term such as cotton or indigo can be shared by hundreds of crafts and a craft's
  explorer answers up to 24 nodes; a longer list or a count changes the shape the client draws
  (`frontend/lib`), which belonged to the design lane at the time (2026-11-22).
- **Clears it:** a node carries how many crafts share its term and the route pages a node's crafts,
  in the contract, the backend and the client together.

## Craft page rebuild (decision 0071)

### The register's description is no longer shown

- **What:** the old page showed the craft register's `description` above the claims. `PageCraft`
  has no description, so a craft without a dossier or claims shows only its register facts
  (category, kind, GI status, states).
- **Why left:** the field is not in the contract, and it is uncited register text, which the page
  otherwise never shows as a sentence.
- **Clears it:** an owner decision; if wanted, `description` on `PageCraft` (model, contract,
  fixture) drawn beside the register facts and marked as the register's.

### Places abroad and rivers are listed, not drawn

- **What:** the tabbed craft screen's Region map is retired; a craft's places are now drawn by its
  document's ground figure (`services/place_ground`, from the craft's located `CraftLocation`
  rows) and its timeline map. A place abroad (Sindh) or a river (Dhamadka River) that a dossier
  names has no located row, so it is listed in `GET /crafts/{slug}/page` (`PagePlace`, with its
  `wikidataId`) but has no mark of its own on any map of the document.
- **Why left:** the ground figure places only points inside India's district outlines; a place
  abroad needs the stored Wikidata point (job step 1, run on production) and a frame that reaches
  past the outline, and a river needs a HydroRIVERS id or a named-river dataset (see the timeline
  map entry below).
- **Clears it:** the stored Wikidata point carried to the ground figure as a pin outside the
  outline, and a river line from a named-river dataset, with a capture of Kutch Ajrakh's
  generated and authored maps.

## Lesson packs and exports (decision 0067)

### Papers from six adapters still name no journal

- **What:** a source now stores the journal it is in (`Source.containerTitle`, decision 0143), and
  a paper's APA, CSL, BibTeX and RIS name it; but only Europe PMC and Semantic Scholar papers carry
  one (their `publisher` is the journal, `JOURNAL_AS_PUBLISHER_ADAPTERS`). Crossref
  (`container-title`, already requested), OpenAlex (`primary_location.source.display_name`), DOAJ
  (`bibjson.journal.title`), Springer Nature (`publicationName`), Elsevier
  (`prism:publicationName`, which it now uses as a fallback publisher) and CORE (`journals[].title`)
  do not fill `EvidenceItem.container_title`, so their papers' references still end without it.
- **Why left:** the adapters (`backend/app/sources/scholarly/`) belonged to the sources lane
  running at the same time (2026-11-22).
- **Clears it:** each scholarly adapter fills `container_title` from the field above (Europe PMC and
  Semantic Scholar too, which retires `JOURNAL_AS_PUBLISHER_ADAPTERS`); sources stored before keep
  no journal until a script reads their DOIs again.

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

- **What:** Kutch Ajrakh's dossier places Khavda, Barmer, Sindh and Pethapur carry Wikidata ids, but
  their `timeline_map` pins appear only once job step 1 (`app.scripts.build_craft_chapters`, nightly
  from Coverage enrichment) has stored their points on production; Ajrakhpur and Dhamadka have no
  Wikidata item that names them. `region_story` never chooses a river: HydroRIVERS basins carry no
  name, so no offered basin's name can occur in a step's sentence or quote. Several curated
  `whyClaimId`s (C062, C080, C088) describe a step rather than explain it.
- **Why left:** storing the points is a run on production (the lead's); basin names need a named
  river dataset joined to HydroRIVERS, which is a new source with its licence (the datasets method,
  `kalavigyan-datasets`); the why claims are dossier content a reviewer rewrites (the curation
  lane, one agent per dossier).
- **Clears it:** the job's next run on production (then a capture of the timeline map); a recorded
  river-name dataset joined to the basins; the three why claims reviewed in the dossier.

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

- **What:** a generated craft document draws its curated plates, its contributed plates and its
  record (key facts as the fact grid, the record strip), but not the craft page's reviewed field
  photographs (decision 0112) or its kin crafts (`relatives`), which `GET /crafts/{slug}/page`
  still carries in its chapters. AI images and videos made from a craft's claims are not carried
  either.
- **Why left:** field photographs and kin crafts need a placement each in the document's layout
  (a `picture_plate` per reviewed photograph with its consent credit, a `related_crafts` component
  in the kin chapter) and a parity check of the generated pages; AI imagery on a page waits on the
  owner's ruling on principle 9 (see the production E2E defects below).
- **Clears it:** both as generated document components with their tests and a capture of a
  generated page; the owner's ruling for AI media.

## Round 6 (2026-11-20)

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
  `monograph.css`), and at 360 the ion charges spill out of the formula; Kutch Ajrakh's document
  carries aria-labels that begin "AI illustration:", which principle 9 (no AI imagery) may not
  allow. The answer essay check waits for one paid `questions=true` run to save an answer. (The
  Textiles hub draws its science from the category's own monograph, served since round 7.)
- **Why left:** the kit is the owner-approved page's stylesheet, so a fix changes the approved page
  at 360 and needs the owner's sight of it beside the parity run; the labels wait on the owner's
  ruling; the paid run is the lead's.
- **Clears it:** a kit fix shown to the owner at 360 and proven by Monograph parity; the owner's
  ruling on the illustrations' labels; the lead's paid run.

## Round 7 (2026-11-20)

### Live research write-backs skipped the candidate gates

- **What:** on production since 2026-11-21 every live-research write-back is `IN_REVIEW` with
  `CandidateCheck` rows (47 claims, 220 checks), so this is left only for the older approved
  write-backs, stored `APPROVED` with no checks before the write-back went through the gates.
- **Why left:** stored facts on production are a person's to review; no lane changes them.
- **Clears it:** a reviewer re-checks them with the filing report
  (`python -m app.scripts.write_back_filing`, whose summary lists the facts with no `CandidateCheck`
  rows, decision 0136) and `python -m app.scripts.write_back_report --gate-less`, then rejects or
  re-files each in the review queue.

### Speed left after the quality lane

- **What:** on a phone (Lighthouse at 360, median of three, 2026-11-22) Kutch Ajrakh scores 78 with
  an LCP of 5.7 s against the 2.5 s target: about 1 MB is requested before its masthead picture
  paints, namely the six first-screen font files the layout preloads (364 KB, Newsreader italic
  143 KB and roman 128 KB among them), the kit stylesheet (78 KB, render-blocking) and about
  400 KB of scripts. Signed out, `/ask` lands on the sign-in page (83, LCP 4.7 s), whose photograph
  shares the first round with Google's sign-in script (104 KB). The Textiles hub scores 100 (LCP
  1.5 s).
- **Why left:** what the entry named is in: Newsreader subset to weights 300 to 600 and its kept
  features (`tools/webfonts`), the arrow on Plex's symbols face, the uncurated page and (decision
  0145) the answer renderers loaded on demand, curated documents split like Ajrakh's shell, and
  `/ask` drawn before its scripts. Before and after this lane Ajrakh measured 78 and 5.7 s on the
  phone (TBT 112 ms to 83 ms, 1.39 MB to 1.35 MB). What is left is a choice of which first-screen
  bytes wait: the first-screen faces are preloaded by choice (round 7, so the first screen never
  swaps its type), and the kit stylesheet is the owner-approved page's.
- **Clears it:** the owner's or lead's choice of the faces to preload and of a kit stylesheet split
  by chapter, then the change proven by Monograph parity and Lighthouse at 360.

### Source tools: what they do not cover yet

- **What:** the production `LookupStore` (`source_lookup_store.from_live`) has no test, since every
  tool test uses fake adapters. PubChem synonyms come only from a stored Compound, because the
  PubChem adapter has no synonyms call. `kalavigyan://index.md` and the contributor skill are
  written by hand and must name every tool, which the tests enforce; the five contract copies in
  `backend/app/data/contributor/contracts` must stay byte-identical to `docs/contracts`.
- **Clears it:** a contract test of the live store against recorded adapter responses; a synonyms
  call on the PubChem adapter; the index generated from the server's registry.

### No MCP path for a new map layer's dataset

- **What:** a contributor can deliver a `general_map_layer` for one page, but a new layer of the
  site's own maps (groundwater, a soil series) is added only in `etl/geo` or `tools/maplayers` in the
  repository, as the datasets skill says.
- **Clears it:** a dataset proposal over MCP that carries the source, licence, version and the
  simplified geometry, checked by the same rules before an engineer ships it.

### Question anonymising is rules-based

- **What:** questions that become open work (decision 0113) are anonymised by rules with no model, so a lone first name with no honorific or self-introduction is not detected; the rules lean the other way elsewhere (a place outside the gazetteer written in capitals becomes [name], and a title-cased question may be dropped).
- **Clears it:** a named-entity pass with the cheapest model route on the few questions that survive the rules, run in the nightly step, never at request time.

### The geo ETL stays on Python 3.14

- **What:** the backend, the tools and the craft ETL run on Python 3.15 (decision 0118), but
  `etl/geo` and `geo-etl.yml` stay on 3.14, because `exactextract` 0.3.0, its newest release, has
  wheels for cp39 to cp314 only.
- **Why left:** building `exactextract` from source needs GEOS and GDAL headers on every runner.
- **Clears it:** when `exactextract` publishes a cp315 wheel, move `etl/geo/pyproject.toml` and
  `geo-etl.yml` together; `backend/tests/test_python_version.py` keeps the two agreeing.

### Leftovers of the design-conformance lane

- **What:** the Sources differ readings open in a `<details>` after their paragraph and the claim
  stores what they differ on (`Claim.differsOn`, decision 0156), but three seams are open. An
  answer sentence never receives it, because `knowledge_view.ClaimView` carries no `differs_on`
  (`section_blocks.explainer_sentence` reads it through `DIFFERS_ON_FIELD`), so answers show a plain
  "Sources differ" summary; a flag the write-back's duplicate judge sets stores no subject, because
  the judge names none; and the matter and what-if hosts (`components/answer/matter/
  ReactionStepList.tsx`, `StepDetail.tsx`, `components/answer/play/WhatIfLab.tsx`) draw a flagged
  sentence's tag without its readings. A drawing stored without server variants (the kind fixtures
  on `/design/kinds`) shows a sunk placeholder until it hydrates.
- **Why left:** `knowledge_view.py`, the gates and judges and the matter hosts were other lanes'
  files while decision 0156 ran; the fixtures are delivered specs, which may not carry `themes`
  (`component_specs_general_delivery`), and the page bundles them instead of asking the server,
  which adds the variants.
- **Clears it:** `ClaimView.differs_on: str | None` filled from `Claim.differsOn` in `cited_view`;
  the duplicate judge naming what two facts differ on and passing it as
  `candidate_writes.mark_sources_differ(..., about=)`; `SentencesDiffer` after the paragraph in the
  three hosts; serve the kind preview's specs through the backend, which adds the four variants
  with `services/drawing_themes.themed_spec` as it does for a delivered drawing.

### The fused order is weak on paraphrased English questions

- **What:** on release db09b9e7 the fused first-stage order scored recall at 5 of 0.414 and a mean
  reciprocal rank of 0.296 on the 58 generated English questions, against 1.000 and 0.855 reranked,
  because the full-text and named-concept rankings outvote the vector ranking. Decision 0151 weighs
  each claim ranking by `backend/app/data/eval/fusion.json` and adds `eval_retrieval --fusion`, which
  scores 60 weightings read-only and picks the best on the generated English questions that does not
  lower the hand-written ones; the committed file still weighs the three rankings equally, and the
  fused floors stand where they were (`releaseSample` fused recall at 5 0.38).
- **Why left:** the weights must be measured on the production knowledge base, which only the lead
  reaches.
- **Clears it:** after the release that carries decision 0151, the lead runs
  `eval_retrieval --fusion --out /tmp/fusion.json` on the box (RUNBOOK, Fusion weights), commits the
  picked file and raises the fused floors to its numbers less 0.05.

### Kutch Ajrakh's approved page does not yet carry the ground figure

- **What:** the API places the "why here" ground figure in Kutch Ajrakh's why chapter
  (`services/monograph_generated_why_here.with_why_here`), and the owner approved it on 2026-11-23
  (decision 0151), but the approved static page (`frontend/public/monographs/kutch-ajrakh`, built
  from `backend/app/data/monographs/Kutch-Ajrakh`) does not carry it. The Monograph parity run, which
  since decision 0151 compares the text and chapters after every deploy, reports the figure's 137
  lines (run 45049769331) and the headings below it, which sit a fraction of a pixel lower.
- **Why left:** the approved page draws a component from its fragment, and the figure's fragment
  must be the markup the React view draws from production's ground data, captured in a browser,
  then built with `build_monograph`; this lane's machine runs neither a browser nor the build.
- **Clears it:** capture the drawn `.kv-why-here` figure from `/crafts/Kutch-Ajrakh/monograph` as
  `fragments/kutch-ajrakh__geography__why-here.html`, add its component (kind `why_here`, its spec
  from the served document) to `content.json` and its slot to the why chapter of the template, run
  `python -m app.scripts.build_monograph` and `--document Kutch-Ajrakh --out
  ../shared/monograph.document.golden.json`, and after the deploy `load_monograph` on the box; the
  parity run then passes with the figure on both pages.

### The MCP call's client name is filled by a trigger for the release before

- **What:** migration `0075_mcp_call_name_filled` adds a `BEFORE INSERT` trigger on `McpToolCall`
  that fills a missing `clientName` from the grant's client, because production's release records
  MCP calls without it while migration 0074 made it required. The rule then has two homes:
  `services/oauth_bearer.record_tool_call` and the trigger.
- **Why left:** the trigger is needed only while the release before 0074 can still serve the
  migrated database (decision 0151).
- **Clears it:** in the first release after the one that carries 0074, drop the trigger and
  `kv_fill_mcp_client_name()` in a migration; the release-before check passes once the release
  before maps the column.

### Goldens that do not yet show every field

- **What:** 177 fields of 38 models the web is served (the craft page's field voices, field photos,
  contributed plates, AI media and searched parts, the people and component blocks, groundwater,
  monthly rain and dataset references, a source's journal name, a translated sentence's original,
  a reaction step's ΔH)
  appear in no golden in `shared/`, so the web's strict parse of the goldens does not test them.
  `backend/tests/contracts/unshown_fields.json` lists them; `test_golden_fields.py` fails on any
  other unshown field, so every field added since decision 0151 is shown (but for the step's ΔH of
  decision 0152, which no source a golden is built from states), and on a listed field that is
  shown, so the list only shrinks.
- **Why left:** the craft page goldens are the Kutch Ajrakh dossier and Farrukhabad Prints as the
  preview builds them, and neither has field voices, contributed or AI pictures, people blocks or a
  journal paper; showing them needs inputs for those builders, a change of its own.
- **Clears it:** give the preview builders inputs that carry each part (a recorded voice and field
  photo in `craft.page.inputs.json`, a contributed and an AI plate, a journal source), add the
  missing block kinds to the explainer fixtures, regenerate the goldens and empty the list.

### The question writer keeps few of the facts it samples

- **What:** generation run 44993519051 sampled 727 facts and dropped 580 questions because they
  reused their fact's distinctive words, so the generated set holds 169 questions, 58 in English.
  Decision 0151 asks the writer once more for each such fact, naming the words it reused, and
  reports `asked`, `keptEnglish`, `keptShare`, `askedAgain` and `rewritten`; the committed set was
  written before it.
- **Why left:** a generation run spends money on production and is the lead's to dispatch.
- **Clears it:** dispatch `eval-questions.yml` after the release that carries decision 0151, commit
  the set, compare its `keptShare` with run 44993519051's, and score the new questions in the fused
  order with `eval_retrieval --fusion`.

### The quantities table has not been measured by the judge

- **What:** in run 44994632550 the judge's figures part averaged 2.8 of 5 (36 of 65); the Ajrakh
  indigo (bed43e9f), Jaipur safe-handling (af3f7ac2) and Bandhani tie-and-dye (4978c466) answers
  scored 1 because dip times, kiln temperatures, tying days and lengths were only in prose.
  Decision 0147 built the `quantities` table for a section whose facts state three or more
  quantities and names each figure's kind and quantities in the judge's message, and re-based the
  rubric floor to the lowest mean the shown-sentence count can give (0.82); no run has measured
  either since.
- **Why left:** answer-quality spends money and only the lead dispatches it (owner rule).
- **Clears it:** the lead runs answer-quality on the same questions after the release, records the
  figures part of those three answers, and raises `rubricMean` in
  `backend/app/data/eval/floors.json` to the run's mean less 0.05, rounded down.

### Leftovers of the sentence-once lane

- **What:** a ladder stage's Sources differ readings are not checked against the stage
  sentences, so a reading may repeat a sentence the stage says. The supply heading lowers a later
  material name only when a block sentence writes its first word in lower case, so a name met only
  at a sentence's start keeps its capital ("Indigo and Alum"). (The rubric's shown-sentence count
  and the market block's GI and price sentences were cleared by decision 0147.)
- **Why left:** both are rare; the glossary holds no sentence-case name (its labels are title case
  for seeded and curated terms alike), so the payload cannot yet say which names are proper names.
- **Clears it:** `explainerView.stagesSaidOnce` leaves out a differ reading a stage sentence says;
  curation gives each glossary term its sentence-case name (a `Term` field the import fills), the
  supply builder carries it on `SupplyLink.material`, and `namesText` keeps a later name as carried.

### The answer did not name the oxides behind Khurja's blue and turquoise glazes

- **What:** answer 504968ea-49cc-469c-88f9-205a2ea90e8a was asked what gives Khurja's glazes their
  blue and turquoise colours and named no oxide. An open-source search on 2026-11-23 found none that
  names them for Khurja: the GI record (application 178) lists a statement of case of 2009 and a reply
  of 2013 as PDFs the text fetcher does not reach; the RIPA Khurja leaflet names only cupric oxide for
  the hand-painted designs and is all rights reserved; khurjaceramic.com (a maker's site) says
  "cobalt for blue" without a licence; the cobalt and copper account of blue and turquoise (imp-art.org)
  is about Jaipur blue pottery.
- **Why left:** the colourant must come from a source that names it for Khurja and can be cited, and
  Khurja Pottery's facts are written through the MCP server, not a dossier.
- **Clears it:** open the two statement-of-case PDFs of application 178 at search.ipindia.gov.in in a
  browser, read the glaze and colour section, and propose its sentence (cobalt, copper, or whatever it
  names) through `propose_facts` with `supply_source` for the PDF; let the planner search for the
  colourant by its element names when a question asks what gives a colour.

### Write-backs filed before decision 0135

- **What:** the 19 facts answer 504968ea-49cc-469c-88f9-205a2ea90e8a wrote stay under Khurja
  Pottery's concept in the review queue, among them the Khorezm, Nigerian, porcelain, kiln-schedule
  and polymer-clay sentences; earlier live-research facts were filed by the old rule too.
- **Why left:** stored facts on production are a person's to review; no lane changes a stored row.
- **Clears it:** a reviewer runs `python -m app.scripts.write_back_filing --answer
  504968ea-49cc-469c-88f9-205a2ea90e8a` (and `--since` for the older ones), which prints where each
  fact is against where today's rule files it (decision 0136), and approves each under the craft it
  names (approve with `craft`), approves it where it is, or rejects it.

### The places that block filing are word lists

- **What:** the regions and cultures abroad in `data/places_abroad.json` are kept by hand (its
  countries are now held to Natural Earth's sovereign states by a test), and the places of India that
  hold a fact for a reviewer instead of filing it are the LGD state and district names and the craft
  index's place labels. Since decision 0136 they are read in a quote's passage and its source's title
  too, so a district named like a common word in a paragraph holds a general fact that names nothing
  else, and a region abroad missing from the list lets one through.
- **Why left:** no open gazetteer of regions and cultures is vendored, and a model judging each
  sentence's places would cost a call per sentence.
- **Clears it:** read the held and refused write-backs the filing report lists after each round of
  live research, and add places, other senses and left-out names from what it shows.

### The review page does not show why a write-back is held

- **What:** a held write-back (decision 0136) waits in the review queue as a `DRAFT` researched fact
  of its suggested craft. Its reason is only in its `ReviewEvent` note and the filing report, and the
  Review page cannot file it under another craft, though the approve route takes `craft`.
- **Why left:** the web's unit specs parse the queue strictly (the production build ignores an
  unknown field since decision 0151), so the field and its shape land together, and frontend files
  were another lane's this round.
- **Clears it:** add `held {reason, suggestedCraft}` to `FactReview` and to `lib/reviewQueueContract.ts`
  in one change, and a craft picker beside Approve that sends `craft`.

### A held write-back found again stays held

- **What:** when research later files a sentence a reviewer has not yet decided, under the craft it
  was held for, the write-back is re-found by its key and keeps its `DRAFT` status: it gains the new
  citations but does not go live as a filed write-back would under the `AUTO` switch.
- **Why left:** a re-found write-back never changes status (decision 0124), and a reviewer sees it in
  the queue anyway.
- **Clears it:** when a filed write-back meets its held twin, move it to the switch's status with a
  `ReviewEvent` by `live_research`.

### The count of hidden facts has no admin screen

- **What:** the nightly count of approved facts a signed-out reader cannot see, by craft and reason
  (decision 0149), is in the night's report and at `GET /api/coverage/hidden-facts` for admins, but
  no admin screen shows it.
- **Why left:** the contributions-visible lane built the count, its route and the failing night;
  the admin screens belong to the design-system work, and a screen needs the kalavigyan-design
  review of a new admin card.
- **Clears it:** a card on the admin settings page that reads the route and lists each craft's
  hidden facts by reason, with the unexplained ones first, and a unit spec of its shape.

## How this document is kept true

| Change | What to do here |
|---|---|
| A shortcut is taken | add its entry, with what is wrong, why it was left and what clears it, in the same change |
| A shortcut is cleared | delete its entry in the change that clears it |
| A round ends | the lead re-reads the round's entries and updates "Last reviewed" |

An entry is true only while its "What" still describes the code; when a change makes it untrue,
rewrite or delete the entry in that change.
