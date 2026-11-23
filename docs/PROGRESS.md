# Progress

Where work stands and what comes next. Update it in the same change that finishes or starts a
piece of work. The plan is `docs/PLAN.md` (section 0 overrides the rest); the build order is its
section 17. Everyone building KalaVigyan reads it; a new session starts at [NEXT.md](NEXT.md).

| For | Read |
|---|---|
| What is live and how a session starts | [NEXT.md](NEXT.md) |
| Why each piece was built as it was | [decisions/README.md](decisions/README.md) |
| What was left below standard | [TECH_DEBT.md](TECH_DEBT.md) |
| The rounds at a glance | [README.md](../README.md#status) |

Last updated: 2026-11-20.

## Done

- **Foundation (PLAN section 17, day 1).** Repository layout; FastAPI backend with the
  SQLAlchemy schema and the first migration; auth (password, Google with nonce, TOTP two-step),
  roles and capabilities, access roster, Manage users, consent and privacy notice; Settings hub
  (managed keys, model catalogue, per-task routing) and usage pages; AI router with ceilings and
  budgets; craft seed of the 455 master crafts with codes, spellings and aliases; seed claims;
  states and districts; the India map; the web client for sign-in, crafts, map, ask (verified
  answers from stored claims), settings and admin.
- **Data.** Craft data pipeline (`etl/crafts`: aliases, Wikidata links, seed claims) and the geo
  ETL (`etl/geo`: per-district soil, climate, land cover, forest, elevation, water, geology from
  open datasets).
- **Infrastructure.** EC2 box, CloudFront, private S3 bucket, Supabase project with RLS lockdown,
  blue/green deploy from `cxacraftecosystem-ui/KalaVigyan` `main` only (`docs/RUNBOOK.md`).
- **Practices.** The engineering, backend and frontend practice skills bind the repository, with
  KalaVigyan bindings; architecture, catalogue, decision log and debt register written; the
  hygiene check (import direction, encoding, no Python comments, ratcheted budgets) runs in
  Backend checks (decision 0001).
- **Research and answering contracts (decision 0002).** `backend/app/research/` holds the typed
  models, protocols and rules every later lane builds against: craft resolution, evidence items
  and the source-adapter protocol, the fetcher, retrieval plans and mode limits, composer output
  and its per-sentence post-checks, live-research write-back, and the answer stream with its
  60-second heartbeat (`docs/contracts/research.md`). `core/errors.py` is the shared error
  hierarchy (`ProviderError` and `RouterError` join it). The stored-answer route now validates
  every frame against the stream contract; `shared/answer-stream.golden.sse` was checked by the
  backend and frontend tests until decision 0146 retired it. No adapter, planner, composer or
  writer exists yet.

- **Craft sync from both portals (decision 0003).** `app/scripts/sync_portal_crafts` reads a
  signed craft feed from the designer and documentation portals, upserts crafts by slug with
  stable ids, keeps the master list as it is, records each craft's source portal, and adds
  portal names as `DR_SYNC` / `FR_SYNC` aliases and merges as redirects. It runs after the seeds
  on deploy and daily (`.github/workflows/craft-sync.yml`). The portals still have to ship the
  route (`docs/contracts/portal-craft-feed.md`); until then each run reports `not_found`.

- **Craft resolver (decision 0004).** The answer stream resolves the craft with
  `services/craft_resolver.DatabaseCraftResolver`: slugs, names, aliases, shared spellings and
  merge redirects matched exactly after Indic transliteration, rapidfuzz typos and family
  words, region hints from craft states and locations, and pgvector neighbours on craft
  name-and-alias embeddings when that leaves no clear winner; at most five ranked candidates
  with reasons. `AMBIGUOUS` now allows one candidate. Embeddings are filled by
  `app/scripts/embed_craft_descriptors.py` after the seeds on every release and first in the
  daily Coverage enrichment run (decision 0016).

- **Scholarly source adapters (decision 0005).** `app/sources/`: paced, cached HTTP with
  Retry-After handling and failure kinds; one `SourceAdapter` each for OpenAlex, Crossref,
  Semantic Scholar, CORE, Europe PMC, arXiv and DOAJ, dormant Elsevier and Springer Nature
  adapters, and an Unpaywall open-access locator (its title search is retired). Built by
  `sources.scholarly.registry.scholarly_sources` from the managed keys; tested on recorded
  responses. Called by the answering service and the coverage job.

- **Reference source adapters (decision 0006).** `app/sources/reference/`: Wikipedia (English
  and 25 Indian-language wikis, full article text, live licence and revision), Wikidata
  (search with label fallback, statements with labels and units through SPARQL, PubChem and
  CAS ids linked), PubChem (names and formulas, computed properties, GHS hazards attributed to
  their reporting source) and Wikimedia Commons file metadata with licence and attribution.
  Built by `sources.reference.registry.reference_sources`; tested on recorded responses.

- **Web search and the fetcher sandbox** (decision 0007): SearXNG with Brave fallback
  (`sources/web/`, one `WebSearch` the planner calls) and the separate `kv-fetcher` process
  (`app/fetcher/`): https only, address pinning with TLS checked for the named host, redirects
  and robots.txt re-checked, size and time caps, trafilatura and pypdf extraction, retrieved
  text cleaned and marked untrusted (`research/untrusted.py`). Tested with fixtures; not yet
  run on the box.

- **Stored-knowledge retrieval** (decision 0008): `retrieval/` searches a craft's claims (T1)
  and corpus chunks (T2) with Postgres full text and an exact pgvector scan fused by reciprocal
  rank fusion (k 60), scoped in SQL by craft, sub-category, mode levels, facets, sensitivity and
  chunk ACL; chunking and embedding fill for stored sources and claims
  (`python -m app.scripts.embed_knowledge`). Contract in `docs/contracts/research.md`. DB
  tests run on GitHub Actions.

- **Planner and tiered live research** (decision 0009): `app/planner/` drafts the plan with
  one `PLAN` call through the AI router (its routes, ceiling and degrade flag), checks stored
  coverage per facet (2 matching claims at the mode's level), searches every scholarly,
  reference and web source of the open facets in parallel within per-tier budgets, dedupes
  and ranks the evidence, reads the best documents through their adapters and the fetcher,
  and in deep mode reads open-access full text and follows cited DOIs; the result is an
  `EvidencePack` (`docs/contracts/research.md`). Tested with fake adapters.

- **Composer** (decision 0010): `app/composer/` turns an evidence pack into candidates (stored
  claims, and read documents whole when short or by their verified quotes), makes one `COMPOSE`
  call through the AI router (Claude Sonnet first, Gemini when there is no Anthropic key), and
  keeps only sentences that cite allowed sources with verbatim quoted spans and whose every
  number or formula is in one of those spans; failing sentences are regenerated once, then
  dropped; hypotheses become open questions; when nothing survives the answer lists what was
  searched. Retrieved text and model output reach the model only inside untrusted blocks.
  Tested with fake model replies, including injection attempts in sources and the question.

- **Claim write-back and coverage enrichment** (decision 0011): `store_live_research` keeps
  each read document as a `LIVE_RESEARCH` source with embedded chunks, turns composed sentences
  that cite live documents into claims (`PROVISIONAL` when quoted, `HYPOTHESIS` when inferred),
  deduped by derived ids, linked to the craft's concept or stage, with the question id and
  retrieval time on every citation (migration 0003). The daily **Coverage enrichment**
  workflow asks standard facet questions of the least covered crafts of every source within
  $2.50 a day. DB tests run on GitHub Actions.

- **The answer stream end to end** (decision 0012): `POST /api/answers/stream` runs the
  resolver, then for `HYBRID` and `DEEP` the planner, live research, the composer and the
  write-back, and streams `status` steps, cited sentences, sources, open questions, follow-ups
  or `not_enough_evidence`, and `done` as they are produced, with a heartbeat after 60 s of
  silence. `VERIFIED` answers from verified and reviewed claims with no model call. `DEEP` is
  for researchers and above; every model call runs as the asker, under the router's per-role
  daily cap and monthly ceiling. The web client shows each step, the cited answer with source
  chips and the source dialog (type, reliability, quote, locator, licence, link out), an empty
  state with "Research it live", and errors. Hand-written shared fixtures are produced byte for
  byte by the backend flow and parsed by the client.

- **Science, region, voice and media contracts** (decision 0014): typed models in
  `backend/app/schemas/` (`science.py`, `region.py`, `voice.py`, `voice_llm.py`, `media.py`) and
  matching client types with runtime shapes in `frontend/lib/` (`scienceContract.ts`,
  `regionContract.ts`, `voiceContract.ts`, `mediaContract.ts`, the shape kit `shape.ts`), pinned
  by hand-written golden files in `shared/` that the backend reproduces byte for byte and the
  client parses (`docs/contracts/science.md`, `region.md`, `voice.md`, `media.md`). `schemas`
  may now import `research`. Lanes 0015 to 0021 built the producers and screens against them.

- **Science engine** (decision 0015): `app/science/` parses formulas, balances reactions with
  the sympy integer null space (balanced only for one smallest positive solution; model
  coefficients are never read), normalises readings with pint and checks them against the PLAN 7
  stage envelopes, whose physical constants are cited claims quoting pinned Wikipedia
  revisions. Migration 0004 stores reaction citations, conditions and readings tied to one
  citation. The science seed (run by `seed_claims`) adds materials with kind and role for the
  six seeded crafts, compounds, the iron acetate, indigo and alizarin-lake reactions and the
  durations and concentration the seed claims state. `GET /api/crafts/{slug}/process` answers
  the contract and reproduces its golden file (DB test on GitHub Actions);
  `app/scripts/link_compounds` fills PubChem records through the existing adapter.

- **Region profile and map layers** (decision 0016): `GET /api/crafts/{slug}/region` answers a
  craft's cited district places (a point placed by the polygon that covers it) and states of
  practice with their stored environment: every district value with its grid and period, GLiM
  rock types by name, and for state places and districts without a polygon the state's
  area-weighted means, sums, minima and maxima with how many of its districts they cover (rock
  types and commodity counts absent from a district counted as zero). `GET /api/map/layers`
  lists the 21 registry layers that have values; `GET /api/map/layers/{layer}` sends district
  values, type 7 quantile classes and a content-hash ETag (304 on a match). Migration 0005 adds
  the per-row grid (now loaded by `etl/geo/load.py`), dataset links, rock names and a layer
  index, and fills the grid and rock names of rows loaded earlier. Everything answers before,
  during and after a geo load. The three golden files are reproduced from records and, on
  GitHub Actions, from stored rows; the layer file now carries the computed classes and version.
  The answer write-back now finishes when the learner leaves (`core/shielded`), and craft
  descriptor vectors are filled on every release and daily.

- **Craft page and region panel** (decision 0019): `/crafts/[slug]` has Overview, Region,
  Process, Materials and Sources. Process is a timeline of the process route's stages with their
  cited claims, materials, conditions (every reading with its citation, "Sources differ",
  "Outside usual range") and reactions in KaTeX mhchem (`trust:false`); Region shows the places
  on the India map with their districts and states filled, and per place the environment values
  with statistic, dataset, grid and period, the state-only and inherited wording and the dataset
  credits. `/map` adds a layer picker that draws the map layer routes as district choropleths on
  the existing shapes, with legend, caption and attribution. Evidence badges gained the scoped
  `evidence` ramp. Built against the golden files; the backend routes come from lanes 0015-0016.

- **Voice UI** (decision 0020): a voice dock on `/ask` (the mic in the ask box) and the craft page
  (Talk), shown only when the config's voice availability is on, at least 30 s remain and the
  browser can carry the transport. The voice notice is accepted before the first session; the
  call runs through `POST /api/voice/session` as `RELAY` (push to talk, the turn stream, the
  spoken reply) or `AGENT` (`@elevenlabs/client` 1.36.1 over WebRTC with the token only). Client
  tools are re-checked against what the page holds (the session's craft, drawn stages, answers
  in the transcript, media options) before they open the Region or Process tab or the sources;
  the transcript shows only our cited sentences with the answer view's chips and Sources list;
  ending, time up, refusals and dropped calls have their states. The CSP gains `connect-src`
  for the LiveKit host the SDK uses.

- **Media UI** (decision 0021): stages on the craft page's Process tab draw Image and Video exactly
  for what `GET /api/media/options` lists, with the units left today; a press creates a job with
  its own idempotency key (sent again unchanged when no answer came), polls it after the server's
  `pollAfterSeconds` with the ProgressBar, and shows the asset after the stage's evidence labelled
  "AI illustration" with model and day, the server's alt text and a Download saved under the
  server's file name. Expiring links are renewed, job ids survive a reload in session storage,
  and professors get the sharing step the asset lists once the governance lane serves it. The CSP
  names the media bucket for downloads, images and video.

- **Media backend** (decision 0018): `backend/app/media/` serves `docs/contracts/media.md`.
  `GET /api/media/options`, `POST /api/media/jobs` and `GET /api/media/jobs/{id}` derive each
  stage's claim set from stored rows (levels, quote checks, ACL, sensitivity, restricted sources,
  group words out), build the versioned prompt with the fixed bans and the filtered style hint,
  answer a shared asset with the same `promptHash` free and at once, hold units in the quota
  ledger and dollars through the router (media sub-cap and ceiling), and seal an HMAC bundle.
  `kv-worker` now ships (`app/worker.py`): it claims `Job` rows per queue (4 images, 2 videos),
  calls Gemini through the Interactions API with the router's fallback and settlement, checks the
  PNG or removes the clip's audio, names the file with `services/naming.py` (golden rows in
  `shared/naming-golden.json`), uploads it to the private bucket and labels the asset; failures
  retry twice within the 4-minute timeout and end with a refund. Migration 0008 adds
  `MediaJob.assetId` and `MediaAsset.model`. Unverified provider behaviour is listed in the
  decision; media stays hidden until `MEDIA_BUNDLE_HMAC_KEY` exists.

- **Voice backend** (decision 0017): `backend/app/voice/` serves the voice contract.
  `POST /api/voice/session` runs the contract's checks (capability, verified email, voice notice,
  craft, configuration, one live call, 30 s of `VOICE_SECONDS`, the platform's live calls) and
  answers `RELAY` (the default) or `AGENT` (an ElevenLabs conversation token whose conversation id
  is bound to the row by a server-held HMAC nonce). The custom LLM at
  `/api/voice/llm/v1/chat/completions` checks the bearer and the binding (every failure the same
  401), sends `end_call` at the call's length or turn cap, and speaks one turn: no
  planner, the craft's claim pack loaded at session start, stored claims (`VERIFIED`) or one
  checked `VOICE_TURN` compose (`HYBRID`), at most 60 words with spoken source labels, a filler
  after 0.7 s. Relay turns run speech to text, the same turn and text to speech, billing heard and
  spoken seconds. Transcripts are scrubbed of email addresses and phone numbers, Fernet-encrypted
  and purged after 30 days by the daily upkeep, which also reconciles agent calls. One ElevenLabs
  adapter (`providers/elevenlabs.py`), a resource-neutral quota ledger (`providers/quota.py`),
  migration 0006, `/answers/config` sends the availability block, and
  `app/scripts/provision_voice_agent.py` creates or updates the agent (not run). The spike has not
  run.

- **Answers in Indian languages** (decision 0023): English plus Hindi, Bengali, Tamil, Telugu,
  Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi, Assamese and Urdu, one line each in
  `research/vocabulary.ANSWER_LANGUAGE_SPECS`. Answers are composed and checked in English, then
  translated in one `TRANSLATE` call (Gemini first) with a post-check of numbers in any script,
  formulas, mhchem, units and script; a sentence failing twice stays English; citations are
  copied, quotes stay verbatim. Claim translations are cached per claim and language (migration
  0007, which also seeds the TRANSLATE routes and the `answerLanguage` preference). The planner
  adds native-language Wikipedia and Wikidata queries and an English rendering of the question;
  Wikidata and Commons fetch in the item's language. Ask has a language picker (Auto follows the
  question's script), answers carry `lang` and `dir` (Urdu right to left) in local Noto Sans
  faces, and a control shows the English original. The voice turn's entry point is
  `answer_translation.translated_sentences`.

- **Voice in every answer language** (decision 0025): the thirteen answer languages are offered for
  voice, derived in `voice/languages.py` from what `scribe_v3` and `eleven_v4_turbo` list on the
  ElevenLabs documentation (all thirteen); `/answers/config` sends them and the client keeps no list.
  A turn ranks with the English rendering of the question, composes and checks in English,
  translates the sentences it will speak through `translated_sentences` (cached per claim), caps 60
  words in the session language and leaves out a sentence that fails translation twice. Speech to
  text gets the session's Scribe code, speech its language code, and fillers and refusals come from
  one phrase table per language. The dock follows the Ask language preference, offers a picker
  between calls and draws the transcript with `lang` and `dir`. The agent lists the languages as
  presets (not provisioned).

- **Admin role** (decision 0024): `ADMIN` ranks 50, between Professor and Master admin, label
  "Admin". It holds everything a professor does plus inviting professors, changing roles and
  suspending accounts ranked below Admin, usage, the audit log and datasets; keys, routing,
  quotas, ceilings and anything done to an Admin or Master admin stay with the master admin.
  Two-step verification is required; daily allowances are 3600 voice seconds, 100 images, 20
  videos and $10 of AI spend. Every Manage users change now checks the target's rank, roster
  changes check the entry's role, and migration 0009 adds the enum value, the quota rows and the
  daily cap. The web client shows the settings hub and Usage to admins, offers only the actions
  each row allows, and checks its ranks and labels against `shared/roles.json`.
- **Yahoo sign-in** (decision 0026): "Continue with Yahoo" on the login page, drawn only when
  `NEXT_PUBLIC_YAHOO_CLIENT_ID` is set. DR's OpenID Connect module is ported for Yahoo and
  Microsoft (Microsoft off without keys): PKCE code flow through `/login/callback`, the code
  redeemed by the backend with `YAHOO_CLIENT_SECRET`, the ID token checked against Yahoo's issuer
  and keys with a single-use server nonce (`POST /auth/oidc/nonce`), a Yahoo-verified address
  required, admission through the access roster exactly as Google's, `authProvider` `YAHOO`, and
  two-step verification challenged as for every sign-in. Migration 0010 adds `MICROSOFT` and
  `YAHOO` to `AuthProvider` and `OIDC_SIGN_IN` to `AuthNoncePurpose`. `/auth/config` reports
  `yahooEnabled` and `microsoftEnabled`.
- **First password in Settings** (decision 0028): an account that signs in with Google,
  Microsoft or Yahoo adds a password after signing in again with its own provider. DR's provider
  proof is ported to `POST /auth/change-password`, with a fresh ID token for the account's address
  and a single-use `FIRST_PASSWORD` nonce bound to the account (`POST /auth/first-password/nonce`);
  migration 0011 adds the purpose.

- **Review fixes for lanes 0014 to 0021** (decision 0022): voice spend fails closed. A relay
  upload is measured before speech to text (a WAV by its own length, compressed audio by a byte
  ceiling of a minute at the dock's 32 kbit/s), claimed under the session row's lock with a
  minute held and one of its 40 turns used, and keeps at least its floor, so silence and noise
  are no longer free; relay turns and replays have per-user limits, and a reply is synthesised
  again only during the call or two minutes after, billed under its own key. An agent call holds
  its whole length at the start, reconciliation settles both ways, and an ended call keeps the
  user's slot until it is settled or 12 minutes pass (the user's ended calls are settled when the
  voice availability is read and at their next start). The style hint's banned words now match plurals and include the group words, the
  writing, people and override words, and the hint sits before the facts as a description with
  the bans last (`media-prompt/v2`). `CraftRegion` carries its places' sources, numbered on the
  Sources tab. One home each for HMAC keys (`core/security.secret_key`), India time
  (`core/clock`) and the first-citation walk; a frontend spec pins the client's vocabularies to
  the backend tuples, and Frontend checks now watch the backend files their specs read.

- **E2E production run** (decision 0029): **E2E production** (dispatch only) drives the deployed
  site with Playwright at 1440, 834 and 390 px wide as one Researcher account signed in through the
  login form, checks every screen (console, failed requests, sideways scroll, overflowing text,
  alerts, gap copy, the role's menu), screenshots it, and with `questions=true` asks the English and
  Hindi known-answer questions in Hybrid and checks them on the wire. `app.scripts.provision_e2e_account`
  creates or resets the account; `seed_admin` now shares its upsert (`services/password_accounts`).

- **Explainer contract** (decision 0030, phase A of `docs/plans/answer-experience.md`):
  `docs/contracts/explainer.md` and the typed models in `backend/app/research/` that the phase A
  lanes build against: the explainer document (ordered sections by discipline, each `READY` with
  blocks or `EMPTY` with what was searched), one block envelope with a version per kind for all 21
  kinds of the plan (prose, process ladder and images built; the rest declared with their fields
  and refused until built), term spans, glossary terms and pictures (`MediaRef`: inline only under
  an open licence with its author, else a credited link card), six stream events (`understood`,
  `trail`, `section_started`, `section_state`, `block`, `section_done`) beside today's, depth by
  role as data (Basic and Detailed over `HYBRID`, Expert over `DEEP`; Master Admin uncapped and
  never degraded), and stored knowledge pieces with topic-key normalisation, the reuse rule and
  staleness. Client types and runtime shapes in `frontend/lib/explainerContract.ts` and
  `explainerStream.ts`. Hand-written fixtures `shared/explainer.{document,piece,term}.golden.json`
  and `explainer.stream.golden.sse` for Kutch Ajrakh are built from the seed claims and sources,
  reproduced byte for byte by the backend and parsed by the client. The cited-sentence shapes and
  the first-citation walk now live in `research/citations.py`.

- **Asking screen** (decision 0036): `/ask` is a composer: the question box, dictation through the
  browser's Web Speech API in the answer language (interim words live, Stop, the mic drawn only
  where the browser has it and has not refused that language), and under it the craft (a
  searchable picker with Any craft, never required; after the `understood` event it reads
  "Kutch Ajrakh · detected", offers Any craft and the candidates one tap away), the depth (the
  config's Basic, Detailed, Expert starting at the role's default) and the answer language. The
  ask body sends `depth` (and `anyCraft` when chosen), never `mode`; changing the craft, depth or
  language re-asks the same question. The Mode choice, the live call from the ask box and the
  "Which craft?" stop are gone; the production E2E asks at Detailed.

- **Understanding and depth** (decision 0031): every answer starts with one understanding step,
  the craft resolver plus one `PLAN` call (Gemini Flash Lite first) that picks among ambiguous
  candidates, resolves crafts the question names, and lists the fields it touches and the experts
  to seat (kept on `Answer.understanding`, migration `0013_answer_understanding`, for the phase B
  panel). A craft is never required: the best match proceeds with the others offered, nothing
  found or `anyCraft` answers for any craft, and research, stored search, composition and claim
  write-back all run without a craft (shared concepts). `understood` is the first event. The
  request takes `depth` (role default otherwise, any depth for any known role; `mode` and
  `ASK_DEEP` are retired); Basic and Detailed run Hybrid with 2/5 and 4/10 queries and documents,
  Expert Deep with 8/20. Per-answer caps per depth live in the AI budget (`answerCapUsd`, $0.25,
  $0.50, $1.00 to start); Master Admins have no caps of any kind and are never degraded, and
  their spend still records on Usage. A spend refusal while understanding answers from the
  craft's stored findings.

- **Pictures and terms** (decision 0034): Wikimedia Commons, Openverse (open licences with a
  creator only) and SearXNG image results are image sources, each the image method of its
  service's one adapter; a section's pictures are chosen by the words they share with the claims
  its blocks cite, inline under an open licence with the author, otherwise credited link cards
  whose thumbnail the page's own site serves, and stored once as `MediaRef` rows with their
  claims (`services/section_images`). The `Term` glossary (542 terms from the seed data: craft
  names with aliases and matched Wikidata labels, local names whose meaning the seed states, and
  compounds) is seeded by `seed_claims`; `research/term_marking` marks term spans on the server.
  `GET /api/terms/{key}?language=` answers a cited summary: the defining stored claims, else the
  Wikipedia lead of the term's item, else one web search and a checked `SUMMARISE` call (Gemini
  Flash Lite first), kept as quoted claims and cached per term and language. Migration
  `0012_images_and_terms` adds six tables and the `SUMMARISE` routes; pictures load with no
  referrer. The answer stream calls both since decision 0039 (below).

- **Explainer view** (decision 0037): `/ask` draws the answer as an explainer from the explainer
  stream (`lib/explainerStream.streamExplainer`, one reducer `lib/explainerState.reduceExplainer`;
  the old answer reducer and view are gone). It shows the understood line ("Answering for Kutch
  Ajrakh · Expert · in English", each part a button to its control), the research trail (live,
  then counts with Replay the trail), a section bar, and sections that build as blocks arrive with
  their working state: prose with citation chips, Verified and Reviewed badges and underlined
  terms that open a cited summary (`GET /terms/{key}`), the process ladder that fills as the reader
  scrolls (filled under reduced motion), the picture strip (credited inline pictures and link
  cards), the "From earlier research" mark, and an `EMPTY` section's note of what was searched.
  Listen's client (a dock that plays tracks per block and highlights the sentence and word being
  read) is drawn once the config lists the answer's language; its route is lane 0035's
  (`docs/contracts/explainer.md`, Listen). The production E2E reads the explainer events.

- **Listen, and the live call switched off** (decision 0035): `GET /api/answers/{answerId}/listen`
  reads the reader's own explainer (or one section) aloud through ElevenLabs
  (`/v1/text-to-speech/{voice}/with-timestamps`, `eleven_v4`): each block's cited sentences, each
  in its own language, in parts of at most 2,000 characters, with word timings for highlighting.
  Audio is cached per piece content hash, model, voice and language under `media/narration/` in
  the private bucket and served by one-hour presigned links, so a second listener costs nothing;
  misses are held and settled in `VOICE_SECONDS` (Master Admins never refused). `/answers/config`
  lists `listen.languages` only when the bucket, the key and ElevenLabs answer. The live call is
  off: `VOICE_CALL_ENABLED` (default false) makes every `/api/voice` route 404 and hides voice in
  the config; nothing is deleted. Listen reads the explainer sectioned composition (0032) keeps
  under `Answer.payload.explainer`.

- **Sectioned composition** (decision 0032): an answer is an explainer of sections, one per
  field the question touches (at most the depth's number), researched and composed in parallel:
  each section plans for its field and experts within its share of the depth's budget, streams
  its sources to the trail as they are found, read and quoted, and is composed by Claude Sonnet
  first, Gemini next. The server builds the blocks: a `process_ladder` from the stored process
  rows of the stages the model chose (refused unless every stage, sentence, material, condition
  and reaction is a stored row), and a `prose` block refused whole when a sentence is uncited or
  states a figure no cited claim or quote holds; a section left empty says what it searched, and
  one whose stored claims composed nothing researches live once more (finding 8a.2). Each checked
  block is translated on its own. Every structured-output schema now keeps to the keywords
  Anthropic accepts, and a refused format moves to the next route instead of free text (finding
  8a.1). The stored-only answer streams the same events. The plans of every section are kept on
  `Answer.plan` (migration `0014_sectioned_answer_plans`) and the explainer on
  `Answer.payload.explainer`.

- **Stored knowledge pieces and reuse** (decision 0033): every checked English block of a
  researched section (prose, process ladder) is kept as a `KnowledgePiece` with its craft, facet,
  topic key, depth, claims, sources, content hash and vector (migration `0015_knowledge_pieces`).
  Before planning, each section whose facet and topic (the glossary terms the question names,
  else the craft's districts for place fields, else the craft) hold a deep enough piece set whose
  claims are still visible as cited streams first, marked "From earlier research" with its date,
  and is not researched; the rest share the depth's budget. Research again (`fresh`) bypasses
  reuse and replaces what it bypassed. A trigger on `Claim` marks pieces stale when a claim they
  rest on is retracted, hidden, deleted or changes level or text, so the next answer rebuilds
  them; the Coverage enrichment run now rebuilds the stale pieces of the 10 most-asked crafts
  first, within its daily budget (`app.scripts.rebuild_pieces`). Stage concepts a process section
  cites stay concepts: no answer writes process rows (decision 0038).

- **Phase A review fixes** (decision 0038): Master Admins are no longer throttled when asking (30
  asks in 10 minutes for everyone else), and the term route shares `is_uncapped`. A failed craft
  lookup never blocks a question: without a chosen craft the question proceeds and the model's
  reply decides (any craft when nothing is found); only a spend refusal or a failed lookup of a
  chosen craft stops it, and no message tells the reader to name a craft. Reader-facing notes no
  longer name modes ("No live research ran.", "Research failed just now. Try again."). The
  OpenAI-compatible adapter now treats a refused `response_format` as a provider failure that
  moves to the next route, never free text, through one `providers/base.format_refused` shared
  with Anthropic and Gemini. Answers no longer write process rows ordered by the model. The trail's
  key prefixes and lengths have one home in `research/explainer.py`. No page's CSP lets web
  pictures in until the stream sends them. The production audit skips KaTeX's hidden MathML copy
  (finding 8a.4), checked in a browser by a unit spec, so Frontend checks install Chromium for the
  unit specs. Decision 0035 and the voice contract now say that enabling the call brings back the
  craft page's Talk dock only.

- **Pictures and terms in the stream** (decision 0039, plan 2.3 step 7): every English sentence
  of a section's prose and ladder is marked with the answer's glossary terms before translation,
  and stored pieces keep the marked blocks; a translated sentence keeps the spans whose text it
  still shows. Each section with blocks, researched or reused, searches its pictures from the
  claims its blocks cite while those blocks are sent and streams an `images` block after them
  (each image service 6 s, the step 8 s; a failure, a timeout or nothing relevant sends none and
  the section stays ready); pictures are never stored as pieces. An answer made only of reused
  sections offers the stored follow-ups. Every page's CSP `img-src` adds `https:`, so a move to
  `/ask` inside the app still shows pictures. The research golden now carries spans and pictures,
  and a unit spec draws them through the whole explainer view.
- **No connection held across a model call** (decision 0040): phase A's first production run
  (3b5cc6e, E2E run 43993673874) failed both questions on a pool deadlock, four parallel sections
  each holding a connection while the router waited for another. Stored search embeds first, and
  writing vectors and the craft resolver release their connection before embedding. The E2E now
  bounds a craft tab click at 30 s and records why it was refused.
- **One Gemini content per embedded text** (decision 0041): google-genai folded a list of texts
  into one content for `gemini-embedding-2`, so every multi-text embed returned one vector and all
  1,919 claims were stored without vectors (stored search ran lexical only). Each text is now its
  own content; the vectors are filled once on the box after the deploy.
- **Phone Process layout** (plan finding 8a.3): the reactions grid's implicit column grew to a long
  KaTeX equation and the Process page scrolled 114 px sideways at 390 px; the reaction, answer
  reaction and material grids are `grid-cols-1`, so each card holds the screen's width and the
  equation scrolls inside it.
- **Production proof of phase A (2026-11-17):** E2E run 44001978530 passes every screen at desktop,
  tablet and phone; both known-answer questions pass (27 cited sentences, 52 citations); the Hindi
  answer reused all five stored blocks of the English one; every section carried pictures. Claude
  Sonnet is COMPOSE route 1 again (Gemini 2, GPT 3) and composed 36 enrichment sections with no
  refusal. All 1,958 claims and the five pieces have vectors.
- **Enrichment fixes (2026-11-17, run 44001067308):** 10 of 12 crafts succeeded within the $2.50
  day. Two failed because a merged search result was fetched through the source that found it
  first rather than the source of the kept item (`'openalex:W…' is not an id of the crossref
  adapter`); the kept item's own source now leads `found_by`. CORE failed every search because
  `/v3/search/works` answers 301 to the trailing-slash path and source HTTP follows no redirects;
  the adapter now asks the slash path. Semantic Scholar is rate-limited until its key is added.
- **Craft sync from both portals is live (2026-11-17, run 44024826347):** the portals' release
  0.0.7 serves the signed craft feed with the flag on; the first sync verified both signatures
  (designer 459 crafts, documentation 462), synced 462, created none, merged one and found no
  name conflicts. It runs daily at 21:37 UTC.
- **Phase B contract (decision 0042, 2026-11-17).** The eight phase B kinds have their final
  fields and fail-closed validators (`research/blocks_place.py`, `blocks_matter.py`,
  `blocks_people.py`), with what the server fills and what a model may only choose; dataset rows
  and the boundary caption moved to `research/datasets.py`, the reaction rules to
  `research/reactions.py`; month and season words (`research/calendar.py`), the river data
  contract (`research/rivers.py`, `docs/contracts/region.md` Rivers) and the 18-seat expert panel
  (`research/expert_panel.py`). Each kind declares where its sentences sit, so translation, term
  marking and piece ids walk any kind. The block builder registry (`services/block_builders.py`)
  is called once from the sectioned flow and is empty; the renderer registry
  (`components/answer/blockRenderers.ts`) holds the phase A kinds. PubChem record sources get a
  stable id. `shared/explainer.phase-b.golden.json` (Kutch Ajrakh, river reach ids placeholders)
  is checked on both sides. Nothing a reader sees changes.
- **River lines, the tracer and monthly rainfall (decision 0043, 2026-11-17).** The geo ETL's
  `riverlines` step keeps every HydroRIVERS v1.0 reach of 100 km2 or more of each basin that
  crosses a district, checks the network and writes one TopoJSON per basin (junctions kept,
  quantized); its load uploads them to `media/rivers/` and replaces `RiverBasin` and `RiverReach`
  (migration `0016_river_reaches`). `services/river_store` traces a river through any reach (the
  largest upstream branch to the source, `NEXT_DOWN` to the mouth, bounded and cycle-safe) with
  the districts it crosses in path order from PostGIS, and offers the rivers crossing a district;
  `GET /api/rivers/{mainRiv}` serves a basin's file with its hash as ETag. The CHIRPS monthly
  normals the ETL already writes reach a `seasons` block through `services/monthly_rain`. The
  HydroSHEDS licence was checked and the dataset row now carries its Exhibit B statement. Every
  Geo ETL dispatch lints and tests `etl/geo` first. Nothing is loaded until the dispatch after
  the deploy (`docs/RUNBOOK.md`, Geo ETL).
- **Reaction player, material cards and 3D molecules built on the server (decision 0045,
  2026-11-17).** Three registry entries (`services/matter_builders.py`) for chemistry and
  materials sections: the craft's stored reactions in process order, re-checked against the
  process rows when built and reused; material cards from the stored material, its glossary term
  and compound, with stored claims sorted into facts and handling by one plan-model call; one
  molecule per section for a named compound whose 3D conformer PubChem has, fetched once through
  the PubChem adapter into the private bucket and served by `GET /api/molecules/{pubchemCid}/conformer`.
  The builder interface moved to `services/builder_interface.py`; only built kinds start; pieces
  of one answer no longer supersede each other; `link_compounds` runs nightly. The three kinds
  joined `BUILT_BLOCK_KINDS` on both sides with the review (decision 0050).
- **Place renderers (decision 0048, 2026-11-17).** The client draws `region_story` (the river
  from the basin TopoJSON of `GET /api/rivers/{mainRiv}`, water flowing from source to outlet and
  lighting each district in the server's path order, steps that outline their district and draw
  their stretch, layer pills, Replay; the full story at once under reduced motion), `map_layer`
  (the route's choropleth on `IndiaMap` with the highlighted districts outlined), `seasons` (a
  twelve-month strip with CHIRPS rainfall bars and month or season rows) and `supply_map`
  (origins by material, Wikidata-placed origins pinned). Map code loads only when a map block is
  drawn; every map carries the boundary caption; every layout is shrinkable columns for 390 px.
  All four are built (decisions 0044 and 0047).
- **Matter and expert renderers (decision 0049, 2026-11-17).** The client draws
  `reaction_player` (a cast of the reaction's species lit per step by role, the steps in order
  with each balanced equation through `ChemEquation`, its badges and citations; Play, Pause,
  Previous, Next and Replay; every step at once under reduced motion), `material_card` (stored
  name, local names, role, formula with its PubChem link, cited facts and handling) and
  `molecule_3d` (3Dmol.js 2.5.5 from npm, pinned, loaded only when the block nears the viewport,
  drawing the conformer route's SDF, which is checked as the PubChem adapter checks it; nothing
  is drawn without WebGL or a conformer; Turn and Explore; its record cited with a numbered chip).
  A section's expert views form one panel: seat cards with their cited takes and agreements, and
  one "Experts differ" card per pair with both citations side by side. The CSP is unchanged.
  The matter kinds joined `BUILT_BLOCK_KINDS` on both sides with the review (decision 0050), so
  readers see them after the next deploy.
- **Expert panel (decision 0046, 2026-11-17).** Each section hears the seated experts of its
  field (the stored understanding's seats, the depth's first 2, 4 or 10, never the artisan's
  voice before phase E). Its plan call names them with the kinds of source each reads, and its
  reads alternate between the facets' best items and each seat's preferred kind, within the
  section's own share; an Expert section now keeps only its share's part for references, so it
  reads what it found again. One `COMPOSE` call (Claude Sonnet first) writes each seat's take
  from the stored facts the section's checked sentences rest on; a take passes the prose checks
  or is not shown. "Experts differ" is kept only for two stored facts about one concept from two
  sources, both shown as stored with their citations, in both seats' views; two views citing one
  claim agree. Panel calls spend only while the answer keeps half its cap (Master Admins
  uncapped). `expert_view` joined `BUILT_BLOCK_KINDS` on both sides, so readers see it after the
  next deploy.
- **Region story and map layers built (decision 0044, 2026-11-17).** A geography section of a
  craft with cited districts gets a region story: the rivers crossing those districts, ranked by
  Strahler order and discharge and traced through the stored network, are offered with the
  districts and the layers that hold values there, and one plan-model call picks a river, the
  stored claims that become steps, their order and districts, and the layers, by ref only; the
  server fills every value and cites the boundary, HydroRIVERS and layer dataset rows, and draws
  the river unnamed (HydroRIVERS names none). Until the river lines are loaded it adds nothing.
  Geology and climate sections get the registry layer their sentences name, as the layer route
  answers it. Stories are kept as cross-craft pieces by basin or districts and reused with their
  facet's section while their river still follows the stored reaches. Both kinds joined
  `BUILT_BLOCK_KINDS` on both sides; map layers show after the next deploy, region stories after
  the Geo ETL `riverlines` load.
- **Seasons and supply built (decision 0047, 2026-11-17).** A climate section gets a seasons
  strip: the craft's stages in process order placed on the months or season their own stored
  claim names (a date is not a month of the year), a stage the section cites but no claim dates
  listed without a month, and the section's own claims that name a month or season; a season is
  given months only where a cited quote states them (`monsoon ... from June to September`), and
  the row then cites that quote too. The CHIRPS rainfall of the first craft district with twelve
  normals shows above it with its period and grid; without one the rows show alone. A materials
  section gets a supply map: one plan-model call picks, from the section's claims and its named
  materials' own claims, the material and origin words a statement states; origins are placed
  only with Wikidata coordinates (`wbsearchentities` and one P625 query through the Wikidata
  adapter, a namesake chosen only by a place its sentence names), and any other origin is listed
  without a pin. Both kinds joined `BUILT_BLOCK_KINDS` on both sides, so readers see them after the
  next deploy.
- **Phase B review fixes (decision 0050, 2026-11-18).** Every phase B kind is built: the reaction
  player, material cards and 3D molecules joined the built kinds on both sides. The conformer route
  releases its connection before the bucket and PubChem. Reused sections rebuild the kinds that are
  never pieces (map layers, molecules), and a section with nothing checked starts no builder.
  Phase B blocks have one order, and region stories are looked up only for geography. Supply links
  need a statement about their material; story steps are placed only in a district their sentence
  names; season rows ignore months and seasons their clause rules out; prose and expert takes drop
  a sentence naming a month, season, state or district no source states. Builder plan calls spend
  from the answer's headroom. River files are content-addressed and a changed one is not served;
  the river load assumes a scoped OIDC role. Rainfall names its district. The production E2E asks
  a third known-answer question about Kachchh's water.
- **Curation tooling (decision 0051, 2026-11-17).** The dossier of `docs/plans/dataset-curation.md`
  is one Pydantic model in `backend/app/curation/` with its JSON Schema in
  `shared/curation.dossier.schema.json` (`docs/contracts/curation.md`); `tools/curation/fetch.py`
  shows a source as the verifier reads it (live, else its Wayback snapshot), `verify.py` re-fetches
  every source and writes `<CraftSlug>.check.json`, and `check.py` runs the offline rules and
  regenerates `backend/app/data/curation/index.json`. Backend checks runs `check.py --check-index`
  on every dossier.
- **Curation pilot, wave 0 (2026-11-18).** Kutch Ajrakh, Bastar Dhokra and Tikuli Painting are
  curated as FULL dossiers in `backend/app/data/curation/`: 20, 22 and 22 sources, 132, 140 and
  112 claims, and 269, 231 and 207 verified quotes. Each had an independent critic, who
  re-fetched every source and found 14, 18 and 9 faults the checker cannot see. The faults were
  undated counts, unattributed pages rated too high, unrecorded conflicts, claims stretching their
  quotes and repeated facts, and all were fixed. Each craft cost about 0.9 to 1.1 million tokens of
  Claude Code subscription use, against the plan's 200 to 400 thousand. Wave 1 waits for the
  owner. The importer and the craft page rebuild (plan section 8) come next.
- **Opus 5.5 composes at medium effort (decision 0052, 2026-11-18).** Opus 5.5 leads the
  `COMPOSE` route (then Sonnet 5.5, Gemini 3.8 Flash, GPT-6.1 Terra). The router passes a
  per-route reasoning effort from `RoutePolicy.params.reasoningEffort`, defaulting to `medium`
  for composing. Saving a route order keeps each route's params. The paid nightly enrichment was
  removed (commit fdf478c), and the dataset is curated by Claude Code instead.

- **Curated dossier import and the craft page API (decision 0053).** `app.scripts.import_curation`
  runs after the seeds on every deploy (and in Backend checks after the database tests): it
  withdraws the seed's 557 edge sentences from every reader (status `WITHDRAWN`, the edge rows
  kept), and imports every checked dossier into `Source`, `Claim` and `CuratedClaim`,
  `ClaimSource`, `Concept`, `CraftLocation` (villages in their district, with role), the curated
  `Process` and stages (ordered only where a source orders them), materials, tools, reactions,
  `MediaRef`, the `Term` glossary, `CraftGiRecord`, `CraftPrice`, `CraftWorkforce` and Expert
  overview pieces; a new dossier version supersedes dropped claims (status `SUPERSEDED`, citations
  kept). Migration `0017_curated_dossiers`. `GET /api/crafts/{slug}/page` answers the craft page
  from those rows (`docs/contracts/craft-page.md`; fixture `shared/craft.page.golden.json`).
  The three pilot dossiers import; the DB tests run on GitHub Actions.

- **Phase C contract (decision 0054, 2026-11-18).** The four phase C kinds have their final fields
  and fail-closed validators (`research/blocks_play.py`: the generated explainer `simulation` and
  `what_if`; `research/blocks_journey.py`: `zoom_story` and `timeline_map`; client
  `lib/explainerPlay.ts`). The generated explainer's static check (`research/sandbox.py`, six
  named rules, an 86-case escape corpus in `shared/sandbox.corpus.golden.json`) and its frame
  (`sandbox="allow-scripts"`, a fixed `srcdoc` with the plan's policy and a `kv-data` element of
  cited values); the years and moves a text states (`research/timeline.py`); the simulation's
  cross-craft piece slot by concept and claim set, the hide route, film mode, the score route and
  payload (`schemas/film.py`, `lib/filmScore.ts`, `shared/film.score.golden.json`) and the
  ElevenLabs media routes (`docs/contracts/media.md`). `shared/explainer.phase-c.golden.json`
  (Kutch Ajrakh) is checked on both sides. Nothing a reader sees changes; lanes 0055 to 0060 build.

- **Zoom story and timeline map builders (decision 0057, 2026-11-18).** Registered in
  `BLOCK_BUILDERS` (`services/journey_builders.py`) for materials and history sections; they start
  once the review joins both kinds to the built kinds (their renderers are 0060's). The zoom (no
  model) captions each level with a distinct stored fact: the craft's mapped district (with the
  craft's claims naming it and the boundary row), workshop, cloth and fibre pictures under an open licence (kept
  `MediaRef` rows first, then Commons and Openverse, kept as rows), and a compound with a kept 3D
  conformer; a level without its matter is absent. The timeline offers the section's dated facts
  with the spans their texts state (a numeral counting a plural noun is not a year), one
  plan-model call picks points, routes and spans by ref, a route needs a text stating the move,
  and places are pinned only with Wikidata coordinates (the supply origins' rule, now shared as
  `supply_places.named_places`). Both reproduce the phase C fixture from recorded responses
  (`tests/journey`); the stored reads have database tests for GitHub Actions.

- **Generated explainers (decision 0055, 2026-11-18).** Sections of the mechanism fields
  (process, chemistry, physics, materials, geography and water, geology and soil, climate) get a
  generated explainer from the builder registry (`services/simulation_builder`): every figure the
  section's cited quotes state is offered with its own words and citation, one `COMPOSE` call from
  the answer's headroom (Master Admins uncapped) chooses the values and writes an HTML fragment,
  and the fragment must pass the value checks, the contract's static check over its data object
  and the block's validators, with one redraft listing the failed checks; a failure adds nothing
  and logs the rules. A stored explainer whose claims the section offers is placed before any
  model call, also in reused sections, and a placed one is never stored again; a newer one
  supersedes an older only for the same concept and claims. `HIDE_GENERATED` (Professor and above)
  and `PUT /api/answers/{answerId}/simulations/{blockId}/hidden` mark the piece hidden (migration
  `0019_hidden_generated_explainers`, audited); a hidden piece is never reused or built again.
  Model replies now name their model (`StructuredReply.model`). Nothing a reader sees changes until
  the review joins `simulation` to the built kinds with its renderer (0061). Tests drive every
  corpus escape attempt, every accepted fragment, an absent numeral and the size cap through the
  builder, reuse with no model call across two answers, and the Student refusal; database tests
  for GitHub Actions cover the pieces query, reuse, hiding and showing again.

- **What-if lab builder (decision 0056, 2026-11-18).** Registered in `BLOCK_BUILDERS`
  (`services/what_if_builder.py`) for process, chemistry and water sections; it starts once the
  review joins `what_if` to the built kinds. An input is a stage's materials that a stored contrast
  relation or a stored text ("madder, al or alizarin") relates as alternatives, offered once a
  section sentence names one; each option is offered the relation claims on its concept
  (`CONTRASTS_WITH`, `CAUSES`, `DEPENDS_ON`, ...), its own fact claims and the claims of reactions
  of its compound that name it, all read in short sessions before one plan-model call that chooses
  the input, its words and the outcomes by ref. An option without evidence is shown unknown, a ref
  that is not one of the option's claims is dropped, a reply touching two inputs is refused, and a
  relationship that is a hypothesis keeps its level and shows the Hypothesis badge (the what-if
  validator now accepts stored findings at their level). Stored what-ifs are re-checked against
  the process rows when built and reused. Tests rebuild the fixture's madder and alizarin options
  from the seed and a recorded reply; database tests for GitHub Actions read the seeded relations.

- **Generated explainer and what-if renderers (decision 0059, 2026-11-18).** Drawn through
  `components/answer/play/playRenderers.tsx`; they show once 0055's and 0056's builders join both
  kinds to the built kinds (0061). A generated explainer is a `sandbox="allow-scripts"` `srcdoc`
  frame whose document opens with the sandbox policy and carries the cited values as `kv-data`,
  sized by a height message the page bounds, with "Generated explainer · model · date", its
  title, what it was built from (each value with its quoted words and citations, or its dataset
  row) and View code as text only; Professors and above can hide one, and a hidden one is not
  drawn for anyone else. The what-if lab offers each option with its count of cited outcomes and
  shows the chosen one's cited sentences, or "Unknown"; reduced motion swaps them in place. The
  site policy gains `frame-src https://accounts.google.com/gsi/` (Google sign-in keeps working,
  any other frame navigation loads nothing), proved in Chromium under the real header.

- **ElevenLabs music, sound effects, image and video (decision 0058, 2026-11-18).** The official
  reference (read 2026-11-18) publishes music (`POST /v1/music`), sound effects (`POST
  /v1/sound-generation`) and an Image and Video API (`/v1/flows/image`, `/v1/flows/video`), so
  all four are built. `ELEVENLABS` joins the providers on the Listen key and `MUSIC` and
  `SOUND_EFFECT` the media tasks (migration `0022_elevenlabs_media` seeds the provider and the two
  routes, `music_v2_5` and `eleven_text_to_sound_v3`, since v1 and v2 are deprecated); ElevenLabs
  `gemini-3.1-flash-image` and `veo-3.1-fast-generate-001` are further `IMAGE` and `VIDEO` choices
  in Settings with every media rule unchanged. `GET /api/answers/{answerId}/film-score` makes one
  instrumental bed and up to twelve fixed-prompt cues for the reader's explainer through the media
  router (media sub-cap and ceiling, Master Admins never refused), stores content-addressed clips
  and a manifest per explainer and language in the private bucket, and serves them with one-hour
  links; `/answers/config` offers `film {score}`. Tests on hand-written responses that follow the
  docs: a cached score makes no second call, a refused reservation adds no score, a failed call
  adds nothing, a Master Admin past every cap is served, and the score for the phase A document
  reproduces `shared/film.score.golden.json`. Owner step: give the restricted key the Music, Sound
  Effects and Image and Video permissions (Image and Video needs a Pro plan); nothing a reader
  sees changes until lane 0060 draws film mode.

- **Zoom, timeline and film renderers (decision 0060, 2026-11-18).** The zoom story and the
  timeline map are drawn through the registry, their code loaded on demand
  (`components/answer/journey/`); they show once the review joins both kinds to the built kinds
  (0061). The zoom shows one level at a time under a rail: the district on the India map with the
  register's polygon and the map moving into it under the boundary caption, a picture with its
  author and licence, the molecule in 3D with its PubChem record, each with its cited sentence;
  reduced motion lists every level. The timeline lists points and routes in time order with their
  spans as the texts state them and their citations, beside a slider over the dated moments; placed
  places are numbered pins linked to Wikidata, a place beyond the India frame a signpost at its
  edge, a stated move between placed ends a route. Film mode sits beside Listen: a dialog, loaded
  on demand, plays the drawn blocks as scenes timed by the Listen script or a hold per kind (the
  server's `FILM_SCENE_SECONDS`), each block's own animation following the scene (the ladder
  fills, the reaction steps, the zoom levels, the time slider), the sentence being read marked and
  captioned in the answer language, a silent scene captioned with its section's title; previous,
  play, next and mute by button or key; and, where `/answers/config` offers it, Music and sound
  (asked once, music and effects volumes, a fade over the last 2 s, the AI credit). Reduced motion
  swaps scenes still and shows every end state. Unit specs check both renderers against the phase
  C fixture and the film against the phase A document and the Listen and score goldens.

- **Phase C review fixes (decision 0061, 2026-11-18).** The generated explainer, the what-if lab,
  the zoom story and the timeline map joined `BUILT_BLOCK_KINDS` on both sides, so their builders
  start and readers see them after the deploy. The generated explainer's frame blocks peer
  connections in every browser: the policy gains `webrtc 'block'`, and since Chromium ignores it
  the frame's own first script (`FRAME_GUARD`) removes the peer connection constructors and keeps
  nested frames out, proved against a STUN server on the test's loopback. The static check reads a
  self-closed `<script/>` as a browser does, refuses reflection over the window, the window under
  other names, STUN and TURN addresses and an unclosed `url(`, reads shown figures as
  `quotes.numbers_in` does (`500km`, `18th`), list starts and CSS counters, runs in linear time
  and refuses a draft past 12,000 characters as `SIZE` (108 refused cases in the corpus). Every
  generated explainer shown can be hidden and stays hidden: it is kept as a piece from any section
  (any-craft answers and deepened follow-ups too), hiding one never kept keeps it first, and the
  read-back routes mark it hidden by its piece or its content hash, so a later version's copy hides
  too (migration `0024_piece_content_hash_index`); readers below Professor see nothing of it. The
  ElevenLabs Flows download is pinned to `storage.googleapis.com` and cut at 64 MB while it
  streams. The ask screen passes the film offer, so Music and sound appears; Mute silences the bed
  and cues on iOS; a failed score says why; a zoom district missing from the shapes draws no map.
  The production E2E asks a fourth question at Expert depth, how indigo turns blue on Kutch Ajrakh
  cloth, and checks its generated explainer in the sandboxed frame with every frame request
  blocked and recorded.

- **Phase D contract (decision 0062, 2026-11-18).** The six phase D kinds have their final fields
  and fail-closed validators (`research/blocks_learning.py`: the cloze `quiz`, `compare` of two to
  four crafts by facet, the shared-science `concept_graph`; `research/blocks_insight.py`:
  `measure` by an exact definition or a stated regional value, `market_gi`, `climate_risk`;
  `research/measures.py`; client `lib/explainerLearning.ts`, `lib/explainerInsight.ts`), four new
  `BLOCK_KINDS` with migration `0018_learning_block_kinds`, the rebuilt-each-time kinds
  (`UNSTORED_BLOCK_KINDS`), follow-ups that build (`research/explainer_versions.py`, the stream's
  `builds_on` and `version`, `version_problems`), saved explainers, notifications and the weekly
  digest (`research/alerts.py`), lesson packs (`research/lessons.py`) with the new
  `BUILD_LESSONS` capability, citation export (`research/citation_export.py`), the shared-science
  explorer (`research/shared_science.py`) and ask the map (`schemas/district_crafts.py`); every
  route in `docs/contracts/learning.md` with a fixture (`shared/explainer.phase-d.golden.json`
  and six `learning.*` and `map.*` goldens) checked on both sides. Nothing a reader sees changes;
  lanes 0063 to 0069 build, 0070 reviews.

- **Follow-ups, versions, saved explainers and alerts (decision 0063, 2026-11-18).**
  `POST /api/answers/stream` takes `buildsOn`: the follow-up runs the usual sections, deepening
  the explainer's own (new blocks numbered after its own, already-cited sentences and shown kinds
  left out) and adding new fields after them, streams `builds_on` and `version`, and stores the
  merged document as the next version (`Answer.explainerId` and `explainerVersion`, migration
  `0020_explainer_versions_alerts`, a unique pair so a racing follow-up is refused); earlier
  versions are never touched. `GET /api/explainers/{id}`, `/versions` and `/versions/{n}` read
  them for the asker only. Saving reuses `SavedItem` (`/api/saved-explainers`); the nightly
  Coverage enrichment job ends with `app.scripts.recheck_saved`, which writes one "This answer got
  better" note per explainer with new cited claims in its saved fields, no model call
  (`/api/notifications`, read and read-all). The weekly digest (`app.scripts.send_alert_digest`,
  workflow **Alert digest**, Mondays 09:00 India time) is built behind `ALERT_DIGEST_ENABLED`
  (off) and a per-reader opt-in (`alertDigest` in preferences). Tests: a follow-up keeps the older
  version intact and merges into the versions fixture byte for byte, deepens and adds sections in
  the stream, stores nothing when nothing is new; a re-check with no new claims or a claim on
  another field makes no note; notes are private to their reader; no digest is sent while the
  setting is off (database tests for GitHub Actions cover storage, saving, the re-check SQL and
  the digest). The screens are lane 0069's.

- **Learning block renderers (decision 0068, 2026-11-18).** The client draws the six phase D
  kinds through the registry: the quiz (blanked prompts, options in alphabetical order, the first
  pick marked right or wrong in colour, icon and words, then the keyed sentence with its
  citation; score and Start again), compare (stacked cards on a phone, side by side by facet
  where the columns fit, crafts linked, empty cells a dash), the concept graph (the term at a hub
  with up to seven sharing crafts and a count, over the linked list of every craft with its cited
  sentence), measures (the stated words, the metric value and the conversion with its basis,
  region, citation or definitions row), market and GI (status, registry facts and dates as
  stated, proprietors, signs of imitation, prices with per, place and date) and climate and risk
  (slopes per decade from zero, solid when significant, with mean, period, resolution and the
  dataset row and method; groundwater where loaded; what it means for the craft). Every layout
  holds at 390 px; reduced motion draws each end state. The kinds join `BUILT_BLOCK_KINDS` with
  their builders (lanes 0064 to 0066).

- **Local measures, and market and GI (decision 0066, 2026-11-18).** `MeasureBuilder` adds a
  `measure` block to any section whose cited facts state a quantity in a fixed unit word: feet,
  inches, yards, miles and square feet by their exact NIST definitions; the fifteen Indian units
  (defined in the one Pint registry, now shared with the science engine, each as its own
  dimension so Pint never converts one) only by a factor a stored quote states as an equality in
  a metric unit of the same quantity for one LGD register district or state holding the craft,
  the district's value first, none when values differ; otherwise the quantity stays as written.
  `MarketGiBuilder` adds one `market_gi` block per craft (the answer's and each compared one) to
  economics sections: the curated GI record with its registry claims, else the registry fields
  read by label from the craft's GI journal and government claims (none on any disagreement, none
  for "registered" without a date or certificate), up to three GI journal claims naming imitation
  or passing off, and the curated prices whose year and place their sentences state. Neither asks
  a model. Both kinds join `BUILT_BLOCK_KINDS` on both sides and the piece order; only the answer
  craft's market block is kept as a piece. Tested on the phase D fixture's seed claims, the
  Kutch Ajrakh, Bastar Dhokra and Tikuli dossiers and hand-written conversions; a database test
  (CI only) reads the imported records and a stored regional quote. No migration or data run.

- **Climate and risk, and ask the map (decision 0065, 2026-11-18).** The geo ETL's CHIRPS layer
  runs from 1981 (one dataset period for the yearly series, the annual and monthly normals and
  the trend); a new `ghcncams` layer reads NOAA's public-domain GHCN CAMS monthly temperature
  (0.5 degree) into yearly means, a normal and a trend; each district with a complete series of
  30 years or more gets the Theil-Sen slope per decade and the Mann-Kendall p-value
  (`geo_etl/trend.py`, tested on hand-computed series and on a netCDF file read through GDAL).
  Migration `0021_climate_trend_stats` adds the two stats. `ClimateRiskBuilder` adds a
  `climate_risk` block to Climate sections from the trends of the craft's districts, paired with
  the section's cited claims about water, rain, heat or groundwater that one plan-model call
  picks; the kind joins `BUILT_BLOCK_KINDS` with decision 0068's renderer. `GET
  /api/map/districts/{districtLgd}` answers a district's located crafts, its stored region story
  and its crafts' place prose pieces with their reuse marks, and its soil, climate, water and
  terrain values, with no model call; the assembler reproduces the fixture. The Geo ETL gains
  `ghcncams` and a `prune` input. No open groundwater dataset exists, so none is loaded. Waits on
  the owner's Geo ETL dispatch after the deploy.

- **Quiz, compare and the shared-science explorer (decision 0064, 2026-11-18).** The quiz is made
  for an explainer on request (`GET /api/answers/{answerId}/quiz`, the asker, any version, chosen
  sections) and by lesson packs through the one `quiz_block`: a cloze per cited fact, round the
  sections in turn, the key a marked term, two or three distractors marked in sentences that cite
  none of the keyed claims and are not named by the keyed sentence or its quotes, a sentence whose
  claim is no longer shown left out. The understanding reply names the listed crafts a question
  compares (`Understanding.compared`, up to three beside the lead craft); a comparison answer shows
  each section's field side by side (term rows for shared glossary terms, then the field's best
  remaining fact, two filled cells or no row, a stored piece's sentence leading its field), and
  `GET /api/compare` shows every field for two to four crafts. The concept graph adds, to
  chemistry, physics, materials and geography sections, up to four terms the section marks that
  the answer's craft shares with others, each craft backed by its own cited claim about its
  concepts of that term; `GET /api/crafts/{slug}/shared-science` and `GET
  /api/shared-science/{termKey}?craft=` answer the explorer with bounded reads. Nothing here asks a
  model. `compare` and `concept_graph` joined `BUILT_BLOCK_KINDS` on both sides; rebuilt kinds are
  never stored as pieces. Fixtures `learning.quiz.golden.json` and `learning.compare.golden.json`
  are checked on both sides; database tests for GitHub Actions cover the seeded explorer and
  comparison.

- **Craft page rebuild (decision 0071, 2026-11-18).** The craft page reads
  `GET /api/crafts/{slug}/page` (`lib/craftPageContract.ts`, cross-checked as the backend model
  does) and the region route, and no longer calls `/profile` or `/process`. Overview: lede, key
  facts, credited pictures, discipline sections with chips and tappable terms, "Where sources
  differ" with every side cited, open questions, glossary, and the register's facts when a craft
  has no lede. Process: stages numbered only where the response orders them, the rest apart, with
  materials, tools, timing, reactions and stage pictures; the Image and Video generators are gone
  from the page. Region: districts where the craft is made on the outlines, places with all their
  roles, people and groups, district datasets. Sources by reliability A to D. All evidence for
  researchers and above, every claim once with its provenance, near-duplicates folded, hypotheses
  apart. Unit specs parse the golden page (curated, uncurated and empty), and the production
  Overview check requires a curated craft's lede and key facts on screen.

- **Learning screens (decision 0069, 2026-11-18).** The explainer offers Save, Export (Report as
  PDF; citations as APA, BibTeX, RIS and CSL-JSON, named by the server) and, for professors and
  above, Make a lesson. "Ask a follow-up", the Ask next suggestions and a term's Ask about it
  extend the stored explainer as its next version (`buildsOn`, the `builds_on` and `version`
  events read), with a version picker that says what each version changed. Stored explainers
  open at `/ask?explainer=`. `/saved` holds the "This answer got better" notes (Update asks the
  follow-up for the facets with news) and the saved answers; the Saved entry of the navigation
  carries the unread count. `/lessons`, `/lessons/new` and `/lessons/{id}` (professors and
  above) choose sections, build the pack, preview every slide and download PPTX, PDF and HTML
  with the citation menu. On `/map` a tapped district shows its cited crafts, the stored land
  story, its values and credits; `/compare` sets two to four crafts side by side, reached from
  the explainer's candidates and the district panel. A finished explainer offers its quiz as
  Check yourself. The weekly email switch on Settings is drawn only while the digest is offered.
  Unit specs drive every screen's states from the learning goldens.

- **Lesson packs and exports (decision 0067, 2026-11-18).** `POST /api/lessons` builds a pack
  from one version of a professor's own explainer with no model (cited fact sentences still
  shown, five a slide, each section's first open picture, the one quiz rule, reading list by
  reliability then citations, sources); `GET /api/lessons`, `/lessons/{id}`, `DELETE` and
  `/lessons/{id}/files/{html|pptx|pdf}` are the builder's own (`BUILD_LESSONS`; migration
  `0023_lesson_packs`). Files are built once into the bucket's `exports/` prefix under the hash
  of what they are made from and answered as five-minute signed links: an offline reveal.js
  6.0.2 deck, a python-pptx deck with answers in the notes, and fpdf2 PDFs shaped by HarfBuzz
  with the Noto font of every answer script; no headless browser or system package. Any reader
  exports a version as a PDF (`.../versions/{n}/pdf`) and its citations
  (`.../citations[/{bib|ris|txt|json}]`, named by the server): APA through citeproc-py and the
  official APA 7 CSL style, BibTeX and RIS by the contract's rules, each CSL item with the day
  its source was retrieved. The lesson fixture now carries the quiz fixture's nine questions.
  Tests: a Student cannot build, list, open or download a pack; every slide bullet is the
  explainer's own sentence with its citation numbers in the PPTX, deck and PDF; the reading list
  is the explainer's cited sources; BibTeX and RIS parse back through bibtexparser and rispy; the
  PPTX opens with python-pptx and holds the expected slides; the citation route reproduces its
  fixture; database tests for GitHub Actions cover storing, listing and deleting packs.

- **Phase D review (decision 0070, 2026-11-18).** Report PDFs and lesson files write their APA
  references in the same worker thread as the render, so a source-heavy first export no longer
  stalls the event loop; python-pptx, fpdf2, uharfbuzz, citeproc-py and Pillow load on the first
  file instead of at start-up (a test imports the API router in a fresh process and finds none of
  them). Explainer versions are served with their generated explainers' hidden marks wherever they
  are read (`services/explainer_history`), so a hidden simulation, its sources and its dataset rows
  leave the report PDF, the citations, lesson packs and the quiz; a follow-up still builds on the
  stored version. GI and price dates are shown only as precisely as a cited text states them
  (`research/stated_dates.py`; a curated date is cut to that precision, 2024-04-02 against a
  quote of 22-04-2024 shows April 2024). BibTeX writes a source's braces as `\textbraceleft{}`
  and `\textbraceright{}` and percent-encodes `\ { }` in `doi` and `url`, so no stored value
  can close a field or start an entry. The weekly digest links each item to its explainer.
  `GET /api/compare` answers 204 when nothing cited sets the crafts side by side and keeps 404 for
  an unknown craft; the page tells the two apart. Notes are held per account, so the next reader
  in a tab never sees the last one's, and `/saved` reloads them on opening. The craft page gains
  a Shared science tab drawn from `GET /api/crafts/{slug}/shared-science`. The production E2E
  proves the exports from the English known answer (report PDF and four citation files, each
  opened and checked for every streamed source; a lesson pack's PPTX and PDF when the account may
  build one), and its navigation check expects Saved. No migration.

- **Release, data loads and production proof (2026-11-18).** The curation import, the rebuilt
  craft page and phases C and D are live (migrations to 0024; revision
  `0020_explainer_versions_alerts` renamed to fit Alembic's 32-character column, which a test now
  checks). The Geo ETL loaded the river lines, then CHIRPS and GHCN CAMS over `1981-2025` with
  prune in run 44204618054 (three attempts, the CHIRPS server timing out on some shards): 752
  districts with twelve monthly normals and a rainfall trend, 752 with a temperature trend, and no
  ten-year rows left. The loader now matches NOT NULL key columns by equality, so the prune is a
  join Postgres can hash inside the statement timeout. The phase D fixture's Kachchh trend is the
  loaded row (mean 449.36 mm/year, +70.76 mm/year per decade, p = 0.005, significant), reproduced
  from its 45 stored yearly means outside the ETL. E2E production 44202269606 (`questions`,
  `rivers_loaded`) passes every screen at the three widths, the four known-answer questions
  (English, Hindi, Water with its river story, Indigo at Expert) and the exports.

- **Content, answer integrity and public reading (2026-11-18, 6ba5291 and 3a29b84).** Live:
  29 curated crafts (wave 1 batch 1's twelve GI crafts and every craft of the field repository's
  2nd, 3rd and 4th workshops, three of them FAMILY entries) and nine CATEGORY master dossiers, all
  verified and critic-fixed, with the curation tools of decision 0051's wave 1 changes (portal
  register, FAMILY and CATEGORY scopes); the claim ledger (decision 0080), the cited lede, narrative
  headings and question order (decision 0077), drawn on the page by `LedeBlock`; public reading
  of craft, category, map and science routes with chunk ACLs on quotes (decision 0079); craft page
  contract v2 (0081), catalogue v2 with concept search (0082), category pages (0078, migration
  `0026_curated_categories`), signature block kinds registered (migration
  `0025_signature_block_kinds`); reader-facing dataset names and one normal per place (0075); the
  release gate of decision 0076, which on its first production run (44301935063) fails, as
  designed, on the half-drawn landing headline and the Region tab's length, and found two defects
  (the Hindi answer's quiz route 404 and the unknown-craft page); the field-voices contract and
  reader, off (0072). The Geo ETL run 44302045906 stores the reader-facing HydroRIVERS and CHELSA
  rows. The audit of 18 November (score 3/10 against the owner's "magnificent" bar) and the owner's
  decisions that follow from it are in the redesign plan below.

- **Craft page v3, field voices v2, students and artisans, no caps (2026-11-19, integrated, to
  release).** Migrations `0027_field_voices` to `0031_craft_page_chapters`, one head.
  - Craft page v3: nine chapters in the monograph's order with numbered figures and tables,
    snapshots and archived versions (`?version=N`), professor hide routes, and reader pieces
    joining their craft's page with their provenance (decisions 0095, 0096, 0098).
  - Public reading of everything except asking; Ask leads to sign-in; server-rendered craft pages
    with preview metadata; share links (Share, Copy link, Stop sharing) for answers and lesson
    packs (`0030_share_links`, decision 0097).
  - Field voices v2: the portals send everything above the legal floor, artisan-linked images
    held hidden; `FIELD_VOICES_ENABLED` off until release (decisions 0084, 0091).
  - Students and artisans: roles, contributions and testimony review, artisan conversations off
    until provisioned (`0028_roles_and_contributions`, decision 0083).
  - No caps on any role, money or tokens; output tokens at each model's maximum; spend still
    recorded (`0029_unlimited_ai_use`, decision 0093).
  - Answer richness: Opus 5.5 at high for Expert compose, richer reused and curated sections
    (decisions 0089, 0090); the wider expert panel, one call per seat, up to 12 seats at Expert,
    the artisan seat from field transcripts (decision 0099).
  - Design foundation: tokens, self-hosted fonts, primitives, the citation system, `/design` and
    the design and craft-page skills (decisions 0092, 0094).
  - The hygiene check finds comments in every checked language, repo-wide.
  - Kutch Ajrakh v2: ten placed pictures, stage colours, native names, botanical names; the page
    golden carries the real Kachchh CHIRPS and GHCN CAMS yearly means for 1981 to 2025.

- **Knowledge fields, step 1 of decision 0101 (2026-11-19, to release).** Migration
  `0032_knowledge_fields`, decision 0102.
  - The field vocabulary gains `SOCIETY` and `POLICY` (16 fields) across chapters, expert seats,
    cues, titles, follow-ups, the planner's guidance, the dossier schema and the web client.
  - `Claim.field` and `Claim.fields`, backfilled from curated, category and testimony disciplines,
    then the first stored piece's facet, then the concept type; every claim writer stamps it.
  - `ArticleSection` (one subject's prose per field, versioned, one published) and its tagged
    rendering for a model's context; the component registry's `label`, `title`, `description` and
    `fields` on `KnowledgePiece`, and `KnowledgePieceSubject` links to crafts, concepts, places
    and compounds.

- **MCP server, slice 1 (2026-11-19, to release, off).** Decision 0103,
  `docs/contracts/knowledge-api.md`: `POST /api/mcp` serves the public read tools `list_fields`,
  `find_crafts`, `get_facts`, `get_section` and `list_components` to any agent, anonymous and
  counted like a public page read, behind `MCP_SERVER_ENABLED`.

- **Release night of 2026-11-19 (live).**
  - **Craft page hotfixes:** every curated page answers 200 again. Before, the region story's and
    the timeline's choices went over their limits, link-card pictures were made into plates, and
    the ladder cited claims and sources the page did not list.
  - **Portals 0.0.8** released, with field voices on: KalaVigyan holds 501 field transcripts and
    615 images.
  - **The MCP read server** is switched on.
  - **Switches:** the alert digest and artisan conversations are on.
  - **Ajrakh:** the critic's design fixes that change no words.
  - **E2E:** the Professor and Admin accounts are provisioned. The specs read the monograph and
    type the two-step code at a person's pace.

- **The component library search (2026-11-19).** `list_components` searches the registry by words
  over label, title and description, and a craft brings its own components plus every shared one
  keyed to its concepts, compounds and districts, each naming what it is keyed to
  (`services/component_library.py`, decision 0101, item 16). Decision 0101, item 17 records how
  contributed images, AI-made ones included, reach the library.

- **The monograph route answers the app's router (2026-11-19).** The rewrite of a craft
  monograph's address to its static file skips requests from the app's router (the `rsc` header),
  so the app answers them with a skeleton that reloads the page, and the browser then loads the
  monograph itself. Before, the router's prefetch of `/crafts/Kutch-Ajrakh` answered 404
  (`lib/craftMonographs.ts`, `components/craft/MonographHandover.tsx`).
- **The API's database pool is 12** (from 5), after the owner raised the Supabase pooler from 15
  to 30; the runbook's Connection budget explains the arithmetic.

- **Image contributions, backend (2026-11-19).** Decision 0104, `docs/contracts/image-contributions.md`:
  a picture is declared, then uploaded; its type, size and AI mark are read from its bytes and its
  location and camera metadata dropped; it is stored privately and shared on approval, at once for
  Professors, Admins and Master Admins, by an Admin for everyone else (`REVIEW_CONTRIBUTIONS`).

- **The Ajrakh page as structured content (2026-11-19, decision 0105).** The approved page is now
  content (1,086 text units with fields and citations, 68 sources, 348 citations with quotes, 79
  registered components and a layout) plus a template, and `app.scripts.build_monograph` rebuilds
  the served page from them byte for byte. Loaded into production on 2026-11-19: 11 sections
  with 262 cited sentences and 35 registered components; 44 components wait for stored facts.

- **Decision 0101 track 1, round 1 (2026-11-19, integrated on `track1`, to release).** Five lanes
  built in parallel, plus the lead's own steps:
  - **Step 3, retrieval by field:** each answer section searches stored facts in its own field
    (primary or secondary; unfielded facts always kept; the overview reads every field), with a
    third ranking for the concepts a question names (`docs/contracts/research.md`).
  - **Step 3, components by label:** a section is offered at most six registered components from
    the library and places the ones it names as `component` blocks linking to the figure; a
    builder of the same purpose is skipped (`docs/contracts/answer-components.md`, migration
    0035).
  - **Step 4, gates and the review switch:** every new fact passes the quote, source and licence,
    duplicate and novelty gates (each outcome kept in `CandidateCheck`, migration 0036), then the
    switch per origin (`AUTO` for research, `APPROVAL` for contributions and agents); reviewers'
    own facts publish at once. `POST /api/knowledge/facts` and the MCP tool `propose_fact`
    (`docs/contracts/knowledge-writes.md`).
  - **MCP slice 2:** OAuth 2.1 with the API as issuer and the consent page at `/oauth/authorize`,
    versioned MCP terms, connected apps with Revoke in Settings, per-connection limits and an
    audit of every tool call (`docs/contracts/mcp-oauth.md`, migration 0037).
  - **MCP slice 3:** `list_open_work`, `claim_task`, `release_task`, `propose_component` with
    duplicate refusal, MCP prompts and resources, and the `kalavigyan-contributor` skill
    (`docs/contracts/open-work.md`, migration 0038).
  - **Nightly upkeep and static builds:** quote re-checks, Internet Archive saves, monograph and
    snapshot rebuilds, orphaned concepts reported then removed, one nightly production build and an
    admin "Build pages now" (`docs/contracts/nightly-upkeep.md`, migration 0039).
  - **Bulk export (item 9):** `GET /api/knowledge/crafts/{slug}/export` and
    `app.scripts.export_knowledge`.
  - **Fixes:** a craft page now rebuilds identically under an unchanged stamp (the flaky chapters
    job test: chemistry cards were numbered in an unordered query's order), and MCP clients reach
    `/api/mcp` through the site's proxy.

- **Decision 0101 track 1, round 2 (2026-11-19, integrated on `track1`, to release).**
  - **The review queue:** `/admin/review` and `GET /api/review-queue` list every pending fact,
    component proposal, picture and piece of testimony from other people, with approve, reject
    (reason kept), raise and retract; erased testimony removes the concepts nothing else rests on
    (`docs/contracts/review-queue.md`).
  - **MCP `ask` and `start_image_upload`:** an agent gets our answer as structured data with its
    link and a drawn view, plus the answer design kit; a single-use upload link (and a presigned
    slot) lets a person add the picture an agent made (`docs/contracts/mcp-ask-and-upload.md`,
    migration 0040).
  - **Approved pictures on craft pages:** contributed plates in their chapters, credited without a
    name and an AI image always labelled an illustration, served from a public asset route
    (`docs/contracts/craft-page.md`).
  - **Contribution screens:** propose a fact, propose a component after searching the library,
    accept the contribution terms, list and withdraw one's own waiting proposals
    (`docs/contracts/contribution-screens.md`); the site's fact route now requires the terms.
  - **The dossier export:** `app.scripts.export_dossiers` writes each curated dossier from the
    database, and `tools/curation/propose.py` sends a dossier's new facts through the gates; the
    craft-pages skill now writes through the API (`docs/contracts/dossier-export.md`).

- **Decision 0106, one monograph template (2026-11-19, integrated on `round3`, to release).**
  - **The split:** the Ajrakh template is a 61-line shell, 79 component fragments and a kit
    (`monograph.css`, `monograph.js`); the static build still writes the served page byte for
    byte (`docs/contracts/monograph-document.md`).
  - **The document:** every page is a `MonographDocument`, stored per version for authored
    content (migration 0041) and generated for every other craft, family and category from
    its sections, registered components and dossier, ordered by a `PageLayout` record per page
    (migration 0042, `docs/contracts/page-layout.md`); `GET /api/crafts|categories|families/
    {slug}/monograph` serve them and the MCP tool `get_layout` reads a layout.
  - **Component kinds as specs:** all 42 kinds of Ajrakh's 79 components have a typed spec and a
    React view (`docs/contracts/component-specs-*.md`); every Ajrakh component now draws from its
    spec.
  - **The React renderer** at `/crafts/<slug>/monograph` and `/categories/<slug>/monograph`, not
    indexed until the parity proof passes (`docs/contracts/monograph-renderer.md`); the proof is
    the **Monograph parity** workflow (text, chapter screenshots at 360, 834 and 1440 in light
    and dark, a citation and Fig. 1).

- **The parity proof passes (2026-11-20, run 44617385866).** `/crafts/Kutch-Ajrakh/monograph`
  matches the approved page at 360, 834 and 1440 in light and dark: no line of text differs, all
  31 chapters match (pixel tolerance 2 per cent), the citation popover and Fig. 1 answer alike, and
  no chapter drifts. What it took:
  - the self-hosted web fonts carry the fix-unhinted `prep`, which the hygiene check now requires;
  - the authored shell draws as the approved page does (`text-rendering` and font smoothing
    `auto`) and keeps the app's CSS out (preflight reverted, seven shared class names reverted);
  - the parity run draws both pages with the site's faces, aligns their device-pixel phase, and
    names the cause of any difference (`styles.json`, `layers.json`, `offsets.json`, `drift.json`).

- **Round 4 (2026-11-20): MCP and retrieval finished, every craft as its English document,
  redesign wave 1B.** Five lanes, one worktree each, every test on GitHub.
  - **Retrieval** (`docs/contracts/retrieval.md`): vectors stamped with their embedding model and
    re-embedded on a change (migration 0043), vectors dropped when text changes, the release embeds
    what its seeds wrote, expert seats filtered by their fields, Indic questions ranked on their
    English rendering, about 1,930 seed passages searchable, and an evaluation (22 golden questions,
    recall at 5 0.94, MRR 0.74, floors 0.9 and 0.7) with `eval_retrieval` for the live database.
  - **MCP and writes:** facts close the task they answer, per-account proposal limits, streamed
    `ask` replies (Streamable HTTP with progress every 15 s), CORS for browser MCP clients, nightly
    removal of abandoned OAuth registrations, a `CONTRIBUTION` claim origin and layout proposals
    (`propose_layout`, review kind `LAYOUT`, migration 0044), one copy of the MCP terms, and
    contracts rewritten to the built state.
  - **Craft pages:** every craft reads as its stored or generated document at `/crafts/<slug>`,
    Kutch Ajrakh included after the parity proof; a craft without a monograph gets its template;
    documents carry their language and are served in English (decision 0107, migration 0045);
    CraftScreen, its tabs and 29 other craft components are retired.
  - **Redesign wave 1B:** the appbar and its sheet replace the island navigation, the institution
    footer and shells on ground with the grain, the landing as the master board's first screen
    (photograph and dyed-region mask, vat moment, ribbon, four chemistries, how to read, where the
    crafts are practised), the sign-in screens, the atlas (search, index, collection shelves), the
    category hub, the paper map with its variables, legend, ranked list and table, and the compare
    page.

- **Round 5 (2026-11-20): the answer page and every signed-in screen, and every field everywhere.**
  Five lanes, integrated by the lead after the session stopped (one lane resumed from its branch).
  - **The answer essay:** the question as h1, the cited three-sentence lede, Save and Cite this
    answer as quiet buttons, the signature figure, numbered sections in the spread with margin
    notes; citations as one cluster per sentence; the source dialog and evidence badge replaced by
    the editorial primitives on answers.
  - **Answer figures:** every player and figure (place, matter, insight, journey, play, learning)
    on the chart kit, map and specimen tokens, complete at rest.
  - **Settings and admin** on the signed-in tool template; the contrast preference has its third
    state (system, standard, high; migration 0046).
  - **Learning, voice, contributions** and the shared components on the system.
  - **Every field** (`docs/contracts/coverage.md`, `answer-eval.md`): field coverage per page is
    data (in the document, at a route, over MCP `get_coverage`); missing and thin fields are ranked
    open work refreshed nightly; the planner seats an expert per relevant field; generated
    documents place each field in its chapter with fact grids; MCP facts and sections group by
    field; an answer-quality evaluation across all 16 fields is dispatchable (`answer-quality`).

- **Releases of 2026-11-20 after rounds 4 and 5.** The first web builds after round 4 failed on
  42 family pages (the craft route asked for a craft subject); fixing that alone would have turned
  about 40 curated pages into the craft-without-a-monograph template, so the tabbed page was
  restored for curated crafts as a bridge (debt), and a failed server read of a craft page now
  draws the tabbed page instead of a cached 404. The embedding pass skips registered components.
  **Capture screens** photographs live pages beside the master board at every width and theme;
  Vercel builds previews from the command line and Capture and parity pass their protection, so a
  branch is compared with its boards before it ships. Parity passes on the live site after both
  rounds.

- **Round 6 (2026-11-20): curated crafts as documents, native Ajrakh views, the boards matched,
  the structure write path.** Five lanes on `round6`, released backend first.
  - **Curated documents:** the curation import publishes one cited section per field from each
    dossier's claims (one shared section writer with `load_monograph`; backfill
    `publish_curated_sections`); the craft page's stages, reactions, region story, places,
    materials, market and GI record and pictures become document components (`answer_block`,
    drawn by the answer's own renderer); the tabbed `CraftScreen` and 30 files only it used are
    gone. Database tests prove every cited claim of the tabbed page appears in the document.
  - **Kutch Ajrakh native:** 70 of 79 components drawn by their native views in a React shell,
    proven element by element against the approved page; 27 more cited sentences are text units.
  - **Visual proof:** previews captured beside the master board at 360, 834 and 1440 in both themes;
    the landing, atlas, category hub, map, sign-in, phone appbar and the craft without a monograph
    match their boards (what still differs is in the debt register).
  - **Structure writes (decision 0108):** `propose_structure` and its route take a stage's after
    and why, native names, reactions, botanical names, glossary terms, conflicts, open questions
    and the GI record through the gates and a STRUCTURE review; approval writes a curated fact.
    Hiding, retracting and approving refresh signed-out pages at once (`WEB_REVALIDATE_SECRET`).
    Open work shares one applies-to query, one monographs folder and one family rule.
  - **Proof and guard:** the production E2E suite and the design guard follow the redesign.

- **Round 7 (2026-11-20): MCP as the place knowledge is created, the landing and map rebuilt.**
  The owner's rule: content arrives through MCP from many contributors at once, at minimal cost to the
  centre, and every MCP gap is resolved.
  - **Contribution at scale:** proposals queue for the `kv-contributions` worker and answer at once
    with an id (`get_proposal`); `propose_facts` takes 25 facts with idempotency keys; `my_tasks`,
    `claim_tasks` and trust tiers (proven contributors publish, one in five sampled for review);
    craft stewardship; a cost ledger per account and day; one set of argument names; `find_crafts`
    ranks by what a craft holds.
  - **Delivered pages:** `propose_component` takes the full spec and units for any of 42 kinds or
    five general kinds (drawing, chart, table, timeline, map layer), registered on approval with no
    builder; `propose_page` checks a bundle part by part; `preview_page` returns a private link to
    the assembled page.
  - **Pictures:** an imaging library (HEIC, TIFF, BMP to WebP; AVIF; GIF; SVG cleaned), upload by
    URL or inline after the person confirms the declaration, screens before review (duplicates by
    perceptual hash, ID documents, faces in AI images, unsafe content), picture tasks and targets
    (decision 0109).
  - **Healing and experts:** a fact whose quotes stop verifying is held and re-sourced, link rot and
    lone quotes become tasks, pages refresh as their facts change, and an expert seat whose field is
    thin runs one capped live search and read (decision 0099 amended).
  - **Home and map:** reading leads from the landing for everyone, sixteen fields with real counts,
    the whole collection; the map drawn from Natural Earth on the Survey of India outline, no state
    lines, pressable places listing their crafts, every state in the ranking.
  - **Releases:** round 6 went live after two fixes: generated documents carry the units a borrowed
    spec names, and each deploy rebuilds stale page snapshots (curated crafts first) before the web
    build.

## Next

0. The redesign, owner-approved 2026-11-18: Direction A "Alum & Indigo" as the system with
   Direction C's specimen labels and collection wall and Direction B's photographic opening and vat
   moment (boards: the KalaVigyan Design Directions artifact); public reading in the frontend;
   the whole application in one release, every screen matched to its board at 360, 834 and 1440 in
   both themes. In flight: the design system, the answer engine's richness (reaction steps,
   generated explainers, the answer map's layers and India locator, Expert depth), transcripts and
   images from both portals (field voices v2), students' first-entry profile and the Artisan role
   with voice testimony. After them: Expert auto-generated media, comic stories, the minister
   showcase questions with an answer-quality evaluation loop.

1. Retire `/profile` and `/process` in the backend once the redesigned frontend stops calling
   them. Further curation only for crafts the owner names.
2. The first live media jobs to confirm decision 0018's unverified items; the ElevenLabs spike of
   PLAN 10.1 on GitHub Actions (lane 0017's open item), which also records a relay turn's real
   billing; the governance lane serves the sharing route of `docs/contracts/media.md`. Science
   engine follow-ups are in `docs/TECH_DEBT.md` (decision 0015).
3. Clear the answer stream gaps in `docs/TECH_DEBT.md` (answer and trace rows, researcher chunk
   access).
4. The phase D proof of a professor building a lesson pack from one explainer needs the owner's
   E2E choice below; the owner verifies an SES sender before `ALERT_DIGEST_ENABLED` is set.
5. The `WEB_READ` reader for long documents.
6. Clear debt as files are touched (`docs/TECH_DEBT.md`), lowering the hygiene baseline.

## Curation targets

Each target below waits on curated content only: its code path is built and tested, and what it
lacks must come from a source a curator verifies (decision 0163). A dossier that meets a target
narrows or removes its line.

- **A regional measure.** No stored claim states a regional unit's factor, so only exactly defined
  units convert (decision 0066). For Kutch Ajrakh: a dossier claim quoting the weights and measures
  table of the Kutch district gazetteer (Gujarat State Gazetteers, Kutch District, 1971, or the
  Gazetteer of the Bombay Presidency, Cutch, 1880) as an equality ("a seer ... weighs ... kg", "a
  gaj is ... m"); then the review adds a `REGIONAL` row to the phase D fixture from that claim. The
  region may be named by any name `data/district_other_names.json` lists.
- **Districts for the GI crafts placed by state alone.** Ask the map lists a craft for a district
  only from a cited district or point location. For each GI craft the master list places by state
  alone, a dossier place naming its district from the GI journal's "geographical area" passage or
  the district gazetteer, starting with the GI crafts no dossier covers yet (Tharu embroidery,
  Kutch embroidery, Kasuti embroidery and the other GI rows of `craft_master_list.json` without a
  dossier).
- **Prices stated with several years, places or prices.** Such a claim shows no price without a
  curated row (`services/market_store.stated_price_offer`, decision 0147). `market.prices` rows for
  those claims, each naming its date and place, starting with the crafts whose GI journal or
  gazetteer prices state several items (Kutch Bandhani, Tikuli Painting, Uttarakhand Ringal Craft).
- **GI records.** Without a curated `market.gi` record the registry fields are read from labelled
  words in claims. A `market.gi` record for each GI craft, read from its GI journal and registry
  pages, starting with Tharu Embroidery, Kutch Embroidery, Kasuti Embroidery, Sandur Lambani
  Embroidery and Toda Embroidery.

## Waiting on the owner

- Weekly alert digest (decisions 0062, 0063): verify a sender identity in SES (`MAIL_FROM_ADDRESS`,
  region `MAIL_SES_REGION`) and request production access out of the SES sandbox; only then put
  `ALERT_DIGEST_ENABLED=true` at `/kalavigyan/env/ALERT_DIGEST_ENABLED` in Parameter Store and
  re-render the box `.env` (`docs/RUNBOOK.md`, Alert digest). Until then the Monday **Alert
  digest** run sends nothing. In-app notes need nothing.

- Professor and Admin E2E accounts: apply the box role's `/kalavigyan/e2e/*` read, run
  `infra/scripts/seed_e2e_accounts.py`, and after the next backend deploy dispatch **E2E accounts**
  (`docs/RUNBOOK.md`, Professor and Admin E2E accounts). Until then E2E production skips the
  `/lessons` and `/admin` screens, and a `questions=true` run fails its lesson pack proof.

- Free OpenAlex, Semantic Scholar and Springer Nature API keys (Settings, API keys); without
  them OpenAlex shares a small daily allowance per IP, Semantic Scholar's shared pool answers
  429 often, and Springer Nature stays off. An Elsevier institution token lets Elsevier return
  abstracts.

- Media (lane 0018): re-run `infra/scripts/seed_secrets.py` once so it generates
  `MEDIA_BUNDLE_HMAC_KEY` (with the voice keys below); media stays hidden until it exists.

- Voice (lane 0017): re-run `infra/scripts/seed_secrets.py` once so it generates
  `VOICE_LLM_BEARER`, `VOICE_SESSION_HMAC_KEY` and `TRANSCRIPT_ENCRYPTION_KEY`; voice stays hidden
  until `TRANSCRIPT_ENCRYPTION_KEY` and `ELEVENLABS_API_KEY` exist. For `AGENT`: run
  `python -m app.scripts.provision_voice_agent` on the box, store the printed agent id as
  `ELEVENLABS_AGENT_ID`, run the spike, and set `AppSetting` `voice.transport` to `AGENT` only if
  the custom-LLM request proves to carry the conversation id (`docs/contracts/voice.md`); it stays
  `RELAY` otherwise.

- Yahoo sign-in is registered and live: sign in once with a rostered Yahoo address on the
  production login page to prove the whole round trip.

## How this document is kept true

| Change | What to do here |
|---|---|
| A piece of work finishes | its entry under Done, in the same change, with its decision and contract |
| A round is integrated | one entry naming its lanes and what each made work |
| The owner has a step to take | an entry under Waiting on the owner, removed when it is done |
| A dossier meets a curation target | narrow or remove its line under Curation targets in the same change |

Re-read Next and Waiting on the owner at every release; "Last updated" says when it was last done.
