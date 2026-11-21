# Project bindings

The only project-specific file of the three practice skills (`engineering-practices`,
`backend-practices`, `frontend-practices`). The rules live in the skills and do not change with
the project; the facts below do. Review this file whenever the layout, tooling or commands
change, and update the date. Every engineer and agent changing code here reads it with the skill.

| For | Read |
|---|---|
| The layers and the edges they may import, in full | [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md), Backend layers |
| The shared code's catalogue | [docs/CORE_API.md](../../../../docs/CORE_API.md) |
| Ids, names, deploys and the box | [docs/RUNBOOK.md](../../../../docs/RUNBOOK.md) |
| The design system every screen follows | [kalavigyan-design](../../kalavigyan-design/SKILL.md) |

Last reviewed: 2026-11-18; version control, the review rule, the commands' note and the living
documents checked on 2026-11-21.

## What this repository is

KalaVigyan (`science-behind-craft`): a web research platform on Indian crafts and the science
behind them. A learner asks about a craft; the platform resolves the craft, shows its region on
the India map with the region's environment, and answers with sentences that each cite stored
claims and their sources. The knowledge base grows: when stored claims cannot answer, live
research runs and what it finds is written back as cited claims. The plan is `docs/PLAN.md`;
its section 0 (owner direction) overrides everything else in it. Web only, no Android client.

## Layout and layers

```
backend/app/core/        shared layer: settings, database sessions, security, roles, logging,
                         rate limits, request dependencies
backend/app/models/      SQLAlchemy models (DR's Prisma naming: PascalCase tables, camelCase columns)
backend/app/data/        vendored datasets and their pure loaders (craft master list, aliases,
                         LGD register, seed claims, craft text normalisation) and the vendored
                         export assets (reveal.js, the APA CSL style, Noto fonts; decision 0067)
backend/app/research/    research and answering contracts: typed models, protocols and
                         rules shared by the resolver, planner, source adapters, fetcher,
                         composer, claim writer and answer stream (docs/contracts/research.md),
                         and the explainer: document, blocks, terms, images, stored pieces,
                         depth by role (docs/contracts/explainer.md, decision 0030); dataset
                         rows, rivers, month and season words, reaction rules and the expert
                         panel (decision 0042); the phase C kinds, the generated explainer's
                         static check and the years and moves a text states (decision 0054);
                         the phase D kinds, unit conversion, follow-up versions, saved
                         explainers and notes, lesson packs, citation export and the
                         shared-science explorer (docs/contracts/learning.md, decision 0062)
backend/app/curation/    curated craft dossiers: the Pydantic model, the offline rules, the
                         check file and the index, shared by tools/curation and the importer
                         in services/curation_* (docs/contracts/curation.md, decisions 0051, 0053)
backend/app/sources/     adapters for external research sources: shared paced HTTP, record
                         rules and the adapter skeleton; sources/scholarly/ has one module per
                         scholarly service and the registry (decision 0005); sources/reference/
                         the Wikipedia, Wikidata, PubChem and Commons adapters (decision 0006);
                         sources/web/ the SearXNG and Brave adapters and their fallback, and
                         sources/fetcher_client.py the client of the fetcher (decision 0007);
                         sources/images/ the Openverse adapter and the image sources
                         (Commons, Openverse, SearXNG pictures; decision 0034)
backend/app/fetcher/     the separate fetcher process (python -m app.fetcher, kv-fetcher): no
                         database, no AWS, no API settings (decision 0007)
backend/app/planner/     the planner and tiered live research: plan call, facet coverage,
                         parallel search, dedupe, reading, references, evidence pack
                         (decision 0009); the understanding step before it (decision 0031)
backend/app/composer/    the composer: evidence pack to candidates, the COMPOSE call, the
                         post-checks, one regenerate, the not-enough-evidence answer
                         (decision 0010)
backend/app/retrieval/   stored-knowledge retrieval (T1 claims, T2 chunks): scope and ranking SQL,
                         reciprocal rank fusion, chunking, embedding fill (decision 0008)
backend/app/schemas/     pydantic request and response bodies, and the science, region, voice
                         and media contracts (decision 0014)
backend/app/science/     the science engine: formulas, balancing (sympy), units (pint, through
                         the one registry in research/unit_registry.py, decision 0066), stage
                         envelopes and the process view built from stored rows (decision 0015)
backend/app/geo/         the region profile and map layers: places, state aggregates, facets,
                         the layer registry and its classes, built from stored rows (decision 0016)
backend/app/voice/       voice calls: sessions and their binding, the custom-LLM turn, relay turns,
                         the encrypted transcript, daily upkeep, agent provisioning (decision 0017;
                         switched off by VOICE_CALL_ENABLED, decision 0035); Listen: narration of
                         finished explainers with word timings and its cache (decision 0035);
                         film mode's score: scenes, fixed prompts and its caches (decision 0058)
backend/app/media/       stage illustrations and clips: claim set, prompt, bundle, MP4 and PNG
                         checks, the job routes' steps, the worker queue and its SQL (decision 0018)
backend/app/worker.py    the kv-worker process (python -m app.worker): the media queue
backend/app/services/    domain services: crafts, knowledge, access, credentials, keys, routing
backend/app/providers/   model-provider adapters (and the one ElevenLabs adapter with its media
                         router wrapper, decision 0058), the AI router, the budget rules and the
                         quota ledger
backend/app/api/         entry points: router.py and api/routes/<area>.py (thin handlers)
backend/app/scripts/     entry points: seed commands run by the deploy (seed_crafts, seed_claims
                         with the science seed and the term glossary, seed_districts,
                         seed_admin), the curated dossier import (import_curation, decision
                         0053) and the portal craft sync
                         (sync_portal_crafts, also run daily), the portals' field voices
                         (sync_field_voices, daily, decision 0091), embed_craft_descriptors,
                         embed_knowledge, the daily coverage enrichment (enrich_coverage),
                         the nightly rebuild of stale knowledge pieces (rebuild_pieces),
                         the PubChem compound lookup (link_compounds), the nightly craft
                         chapters job (build_craft_chapters, decision 0098), the nightly re-check
                         of saved explainers (recheck_saved) and the weekly alert digest
                         (send_alert_digest, decision 0063), the daily voice upkeep
                         (voice_upkeep), the voice agent's provisioning (provision_voice_agent)
                         and the E2E account's provisioning (provision_e2e_account); shared
                         operator input in operator_input
backend/app/main.py      the ASGI app
backend/migrations/      Alembic migrations
backend/tests/           DB-free tests; backend/tests/db/ needs Postgres (marker `db`)
etl/crafts/              craft data pipeline (aliases, Wikidata links, seed claims); imports
                         backend/app/data as its shared home
etl/geo/                 per-district environment statistics from open datasets (package geo_etl),
                         and HydroRIVERS river lines with one TopoJSON per basin (decision 0043)
frontend/                Next.js App Router web client (npm)
infra/                   Terraform, deploy scripts and systemd units, secret seeding, Supabase lockdown
shared/                  files both sides check (craft-master.sha1, the *.golden.* contract files)
tools/                   developer tooling: the hygiene check, the curation tools (fetch, verify,
                         check, schema; tools/curation), the design token generator
                         (tools/design, run by tools/design_tokens.py; decision 0092) and their
                         tests
docs/design/             the design system's pixel boards, their pictures and the landing mask
docs/                    living documents, contracts, decisions
```

Imports in `backend/app` point one way. The allowed edges, enforced by `tools/hygiene/layers.py`
(`LAYER_IMPORTS`), are:

```
main      -> api, voice, providers, services, core, models
api       -> voice, media, providers, services, science, geo, retrieval, research, schemas, core, models, data
scripts   -> voice, providers, services, planner, composer, retrieval, research, core, models, data
voice     -> providers, services, composer, schemas, research, core, models
media     -> providers, services, schemas, research, core, models
worker    -> media, core
providers -> services, research, core, models
services  -> science, geo, planner, composer, retrieval, sources, curation, research, core, models, data
planner   -> sources, research, core, models
composer  -> research, core, models
retrieval -> research, core, models
sources   -> research, core, models
fetcher   -> sources, research, core
curation  -> research, models, data
research  -> core, models
science   -> schemas, research, core
geo       -> schemas, research, core
schemas   -> research, core
core      -> models
models    -> (nothing else)
data      -> (nothing else)
```

Nothing imports `api`, `scripts` or `main` except the layers above them. A new package under
`backend/app` fails the check until it is added to `LAYER_IMPORTS` and to this list. The plan's
later packages (`websearch/`, `evidence/`,
`enrichment/`, `review/`, `governance/`) each get a row when they are created; those that build
on the research contracts list `research` among their allowed imports.

Frontend source (`frontend/`), as it is today:

```
app/                       routes: (reading)/ for pages anyone reads without signing in (crafts,
                           map, compare, field transcripts, shared answers and lessons; decision
                           0097), (protected)/ for asking and the signed-in tools, login, signup...
app/api/                   Next route handlers that proxy auth and session calls to the API
components/ui/             generic kit, no domain knowledge
components/editorial/      the design system's reading primitives (decision 0094): citation
                           cluster, evidence marks, specimen label, masthead, plates, chapter rail
components/motion/         the named-motion hooks; their keyframes are app/motion.css
components/<area>/         domain components grouped by area: answer, ask, craft, map, admin,
                           settings, auth, nav, voice, data, dialogs, forms, guide, hooks...
components/*.tsx           app-wide shell pieces (AppShell, providers, PageHeader, ErrorPanel...)
lib/                       the API client (api.ts), session, formatters, permissions, types,
                           the runtime shape kit (shape.ts) and the contract shapes (*Contract.ts)
lib/server/                server-only code (apiProxy.ts)
e2e/                       Playwright: *-unit.spec.ts (unit project) and smoke.spec.ts
e2e/production/            the E2E production run (decision 0029): projects exist only with
                           E2E_PRODUCTION=1, never in Frontend checks
public/, fonts/            static assets
```

`lib/api.ts` is the one API client; components and hooks call it. The frontend has no
`features/` folder: domain components live under `components/<area>/`, and a component used by
two areas belongs in `components/` or `components/ui/`, never copied.

The design system is the `kalavigyan-design` skill (Alum & Indigo, decision 0092): load it with
`frontend-practices` before any UI, styling, chart, map, picture, animation or reader-facing copy
work. Its tokens are generated and reach components as Tailwind classes; frontend-practices'
"design tokens defined once" means those tokens, never a typed hex. It replaced the portal skills
(`field-repo-frontend`, `gsap`, `motion`) and their purple, Plus Jakarta Sans and GSAP look on
2026-11-18.

Versions: the latest stable release of every dependency (owner rule), pinned in `backend/uv.lock`
and `frontend/package-lock.json`. When a version lags, upgrade the lagging side; never downgrade
to match. A package held back is recorded in `docs/TECH_DEBT.md` with its reason.

## Shared layer and its catalogue

The shared layer is `backend/app/core/`. Shared services that more than one entry point uses
live in `backend/app/services/`, shared datasets and their loaders in `backend/app/data/`, and
provider access in `backend/app/providers/`. The catalogue of all of it is `docs/CORE_API.md`:
check it before writing any helper.

Quick index (the catalogue is authoritative): settings (`core/config.py`), database sessions
and the pooler URL (`core/db.py`), passwords, JWTs and HMAC keys (`core/security.py`), India time
(`core/clock.py`), roles, ranks and capabilities (`core/roles.py`), the current user and capability guards (`core/deps.py`), JSON
logging, request ids and secret redaction (`core/logging.py`), sliding-window rate limits and
the client address (`core/rate_limit.py`), the error hierarchy (`core/errors.py`), Retry-After parsing
(`core/retry_after.py`), ETag revalidation (`core/http_cache.py`), work that outlives a leaving
caller (`core/shielded.py`), paced and cached source HTTP and record rules (`sources/http.py`,
`sources/records.py`, `sources/adapter.py`), JSON model calls (`research/structured.py`,
`providers/structured.py`, the schema helper `research/structured.schema_object`), the
composer (`composer/`), live research budgets (`planner/policy.py`), the MediaWiki Action API
(`sources/reference/mediawiki.py`), quote matching and strength (`research/quotes.py`), open
licences (`research/licences.py`), the craft claim scope (`retrieval/statements.py`), audit
records (`services/audit.py`), managed keys (`services/managed_secrets.py`), the model catalogue
(`services/ai_providers.py`), the AI router (`providers/router.py`), spend rules
(`providers/budget.py`), the quota ledger (`providers/quota.py`), the ElevenLabs adapter
(`providers/elevenlabs.py`), the media router and Gemini media wire
(`providers/media_router.py`, `providers/gemini_media.py`), generated names (`services/naming.py`),
the S3 adapter (`services/object_store.py`), personal-data patterns (`research/evidence.py`), the research and answering contracts (`research/`), the craft master
list and text normalisation (`data/craft_master_loader.py`, `data/craft_text.py`), LGD state and
district names (`data/district_register.py`), the curated dossier model and rules (`curation/`), the portals'
signed peer feed (`services/portal_peer.py`).

The registered vocabulary: role names and capabilities in `core/roles.py`, enums in
`models/enums.py`, evidence levels in `docs/PLAN.md` section 1, craft names and slugs from the
master list, and the naming skill (`.claude/skills/naming/`) for every generated name.

## Budgets

| Unit | Budget (a trigger to split, not a wall) |
|---|---|
| Python file | about 400 lines |
| function or method | about 40 lines |
| parameters | 5, options keyword-only |
| nesting depth | 3 |
| UI component file | about 150 lines |

Existing code over budget is recorded in the hygiene baseline (`tools/hygiene_baseline.json`)
and may only shrink.

## Commands

Run from the repository root. Nothing heavy runs on the laptop: no Docker, no local database,
no dev servers. Database tests, migrations and seeds run on GitHub Actions (Backend checks). Since
the owner's rule of 2026-11-20 a development machine runs only the formatters and linters below,
and the hygiene check; the tests, type checks and builds run on GitHub, on the pull request.

| Purpose | Command |
|---|---|
| backend lint | `backend\.venv\Scripts\python.exe -m ruff check backend` and `... -m ruff format --check backend` |
| backend DB-free tests | `cd backend; .venv\Scripts\python.exe -m pytest -q -m "not db"` |
| hygiene check (ratchet) | `backend\.venv\Scripts\python.exe tools\hygiene_check.py` |
| design tokens (write, or `--check` that nothing was edited by hand) | `backend\.venv\Scripts\python.exe tools\design_tokens.py` |
| accept a lower baseline after a clean-up | `backend\.venv\Scripts\python.exe tools\hygiene_check.py --update-baseline` |
| tools lint and tests (hygiene, curation, design tokens) | `backend\.venv\Scripts\python.exe -m ruff check tools` and `... -m pytest -q tools\tests` |
| curation checks and index (offline) | `backend\.venv\Scripts\python.exe tools\curation\check.py` (`--check-index` in CI); fetch and verify in `docs/RUNBOOK.md` |
| craft data tests | `cd etl\crafts; .venv\Scripts\python.exe -m pytest -q tests` |
| geo ETL tests | `cd etl\geo; python -m pip install -e .` in a venv, then `python -m pytest -q tests` |
| frontend type check | `cd frontend; npm run typecheck` |
| frontend lint | `cd frontend; npm run lint` |
| frontend unit specs | `cd frontend; npm run test:unit` (Playwright's Chromium: `npx playwright install chromium` once) |

The hygiene check enforces what a tool can decide: import direction in `backend/app`, UTF-8
without a byte-order mark and LF line endings for every tracked or new text file, and the
ratcheted counts of Python files over 400 lines, functions over 40 lines and functions with more
than 5 positional parameters. Every count must equal its baseline: a rise fails, and a fall
fails until `--update-baseline` records it, so the baseline only moves down.

The frontend's size and import-boundary rules are not yet automated (see `docs/TECH_DEBT.md`).

## Version control

Git. `main` is what ships; a round integrates on its own `round<N>` branch, its lanes open pull
requests into it, and the round merges into `main` (Backend checks and the README check run on
pushes to `main` and the round branches). Commits are authored and committed as ankits1802
(`ankits1802@gmail.com`) with no co-author trailers. Agents do not commit or push unless the
owner asks. Only a push to `main` of `cxacraftecosystem-ui/KalaVigyan` (remote `deploy`) deploys:
Backend checks, then Deploy backend; the web app is built from that `main` through the Vercel
deploy hook (`docs/contracts/infra.md`), never from Vercel's Git link.
`ankits1802/science-behind-craft` (remote `origin`) is a mirror and deploys nothing. Text is
stored with LF line endings (`.gitattributes`); environments, build output and `.env` files are
not tracked (`.gitignore`).

## Living documents

| Document | Must stay true about |
|---|---|
| `docs/PLAN.md` | the product plan; section 0 is the owner's direction and overrides the rest |
| `docs/ARCHITECTURE.md` | layers, module map, import direction, how a question flows |
| `docs/CORE_API.md` | the catalogue of shared components |
| `docs/contracts/*.md` | interfaces between lanes: API routes, craft data, geo, frontend, infra, research and answering, the explainer, the portals' craft feed and field voices, process science, region, voice, media, curated dossiers, learning (follow-ups, alerts, lessons, exports, the map) |
| `docs/decisions/` | decision log: one short file per decision, numbered |
| `docs/TECH_DEBT.md` | debt register |
| `docs/PROGRESS.md` | where work stands and what comes next |
| `docs/RUNBOOK.md` | what is provisioned, deploy and roll back (ids and names, never secret values) |
| `docs/DATA_SOURCES.md` | datasets, licences, attribution and citations |
| `docs/README.md` | the index of every document, and where each reader starts |
| `docs/REPO_FACTS.md` | counts of tables, routes, tools and tests, generated by `tools/repo_facts_build.py`, never edited by hand |

## Rules from the owner that override the skills

- **No code comments at all**, and no docstrings. The skills' "comment the why" and "comment the
  exception at the spot" become: record the why in `docs/decisions/`, and an exception in
  `docs/TECH_DEBT.md` naming the file and the rule. Only functional directives stay (`noqa`,
  `type: ignore`, `eslint-disable` with a reason in the decision log). `tools/hygiene_check.py`
  enforces it across the whole repository (`tools/hygiene/comments.py`): Python comments and
  docstrings; `//` and `/* */` in TypeScript, JavaScript and CSS; `#` lines in YAML, shell, TOML,
  Terraform, systemd units, `.gitignore` and `.env.example`; and `<!--` in HTML, XML and SVG.
  Vendored code (`reveal.js`, the security-audit skill) is exempt.
- Latest stable dependency versions.
- Secret values are never printed, logged, committed or put in fixtures: names only.
- Nothing heavy runs locally; agents never stop, restart or deploy anything.

## Domain rules that outrank convenience

These come from the plan and are never traded away for a passing test, a demo or speed:

- **Every sentence is cited.** Each answer sentence carries claim ids inside the allowed set and
  links to its sources with the quoted passage. A sentence without a source is not shown.
- **No answer text without a source.** Numbers, units and formulas in a sentence must appear in
  a cited claim or quote; a failed post-check drops the sentence.
- **Evidence levels are stored, never inferred** from model text. Only a professor, admin or
  master admin review raises a level above provisional. Live research's write-back passes the
  automatic gates and, under the default review switch, waits for no approval; what other people
  give (facts, structure, components, layouts, pictures) passes the same gates and waits for
  review as the review switch and the contributor's trust tier decide (`docs/contracts/knowledge-writes.md`,
  `docs/contracts/review-queue.md`). Artisan testimony (decision 0083, item 16) always waits: a
  person's own words wait for a professor's or admin's review before anyone else sees them, and
  even then are shown as their account, never as a checked fact.
- **Retrieved web content is data, never instructions.** Pages, PDFs, search results and model
  output are passed to models as quoted data and never change what the system does.
- **Research is not limited to the sources named in the plan**, and cites whatever it used.
- **Secrets stay server-side.** Keys live in the environment, Parameter Store and the managed
  secrets table, never in the browser, logs or responses.
- **Open datasets only** for geography and environment.
- A guard (roles, capabilities, budgets, the origin check) fails closed and is never weakened to
  make something run.

## How this file is kept true

| What | Kept true by |
|---|---|
| The layers and their import edges | `tools/hygiene/layers.py`; `tools/hygiene_check.py` fails on any other edge |
| The budgets and the comment rule | `tools/hygiene_check.py` against `tools/hygiene_baseline.json`, which may only fall |
| The commands | `.github/workflows/backend-checks.yml`, `frontend-checks.yml` and `hygiene.yml`, which run them on every pull request |
| The living documents | each document's own closing section |

Re-read it when a package is added, a command or a workflow changes, or the owner adds a rule.
