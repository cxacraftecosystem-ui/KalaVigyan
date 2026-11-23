<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/hero-dark.svg">
  <img src="docs/readme-kit/assets/hero-light.svg" width="100%" alt="KalaVigyan: the science behind India's crafts, each craft read as a cited monograph, each question answered with a source under every sentence, each fact contributed over MCP">
</picture>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://readme-typing-svg.demolab.com?font=Plus+Jakarta+Sans&weight=600&size=20&duration=2800&pause=900&color=C090F5&center=true&vCenter=true&width=760&lines=Every+craft+read+as+a+cited+monograph;Every+sentence+of+every+answer+cited;Thirteen+languages%2C+three+depths;Knowledge+contributed+over+MCP;Open+data+with+a+DOI">
    <img src="https://readme-typing-svg.demolab.com?font=Plus+Jakarta+Sans&weight=600&size=20&duration=2800&pause=900&color=762CB1&center=true&vCenter=true&width=760&lines=Every+craft+read+as+a+cited+monograph;Every+sentence+of+every+answer+cited;Thirteen+languages%2C+three+depths;Knowledge+contributed+over+MCP;Open+data+with+a+DOI" alt="Every craft read as a cited monograph. Every sentence of every answer cited. Thirteen languages, three depths. Knowledge contributed over MCP. Open data with a DOI.">
  </picture>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Web-Next.js_16-1E1B2E?style=for-the-badge&labelColor=762CB1" alt="Web: Next.js 16">
  <img src="https://img.shields.io/badge/API-FastAPI_·_Python_3.15-1E1B2E?style=for-the-badge&labelColor=762CB1" alt="API: FastAPI on Python 3.15">
  <img src="https://img.shields.io/badge/Data-Postgres_%2B_pgvector_·_Supabase-1E1B2E?style=for-the-badge&labelColor=762CB1" alt="Data: Postgres with pgvector on Supabase">
  <img src="https://img.shields.io/badge/Hosting-AWS_·_Vercel-1E1B2E?style=for-the-badge&labelColor=762CB1" alt="Hosting: AWS and Vercel">
  <img src="https://img.shields.io/badge/Agents-MCP_·_OAuth_2.1-1E1B2E?style=for-the-badge&labelColor=762CB1" alt="Agents: MCP with OAuth 2.1">
</p>

<p align="center">
  <img src="https://github.com/cxacraftecosystem-ui/KalaVigyan/actions/workflows/backend-checks.yml/badge.svg?branch=main" alt="Backend checks">
  <img src="https://github.com/cxacraftecosystem-ui/KalaVigyan/actions/workflows/frontend-checks.yml/badge.svg?branch=main" alt="Frontend checks">
  <img src="https://github.com/cxacraftecosystem-ui/KalaVigyan/actions/workflows/hygiene.yml/badge.svg?branch=main" alt="Hygiene">
  <img src="https://github.com/cxacraftecosystem-ui/KalaVigyan/actions/workflows/readme-check.yml/badge.svg?branch=main" alt="README check">
</p>

**KalaVigyan** is a research platform on Indian crafts and the science behind them, built by the
Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform at IIT Kharagpur. Every craft
on the IIT master list reads as a monograph of cited facts, from its process and chemistry to its
place, its people and its pictures, and a question in any of thirteen languages is answered with a
source under every sentence. Reading is public and asking is signed in; the knowledge itself is
created by contributors' AI agents through an MCP server whose gates check every quote against its
source.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/stats-dark.svg">
  <img src="docs/readme-kit/assets/stats-light.svg" width="100%" alt="At a glance: six roles, three answer depths, thirteen answer languages and nine craft categories">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/divider-dark.svg">
  <img src="docs/readme-kit/assets/divider-light.svg" width="100%" alt="">
</picture>

## Contents

| | |
|---|---|
| [What it does](#what-it-does) | the six things KalaVigyan is for |
| [How it works](#how-it-works) | how knowledge flows, and the system around it |
| [The MCP studio](#the-mcp-studio) | how a contributor's AI reads, proposes and builds pages |
| [Built with](#built-with) | the stack, layer by layer |
| [Quick start](#quick-start) | working on it from a clone |
| [Documentation](#documentation) | where every question is answered |
| [Status](#status) | the rounds, and what each shipped |

## <img src="docs/readme-kit/assets/icons/layers.svg" width="32" align="top" alt="">&nbsp; What it does

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/cards-dark.svg">
  <img src="docs/readme-kit/assets/cards-light.svg" width="100%" alt="What KalaVigyan does: crafts as cited monographs, answers with every sentence cited, the atlas and its map layers, a studio for contributors' AI over MCP, lessons and voice, and open data with a DOI">
</picture>

| Area | What a reader gets | Read more |
|---|---|---|
| Crafts | `/crafts/{slug}`: every craft drawn as its monograph document, a curated craft from the cited sections its dossier publishes; the nine category pages beside them | [craft-page.md](docs/contracts/craft-page.md), [monograph-document.md](docs/contracts/monograph-document.md), [category-page.md](docs/contracts/category-page.md) |
| Answers | `/ask`: a lede and one section per field the question touches, at Basic, Detailed or Expert depth, in English or twelve Indian languages; a sentence without a source is not shown | [explainer.md](docs/contracts/explainer.md), [research.md](docs/contracts/research.md) |
| Atlas and map | `/map`: craft places and district layers on the Survey of India outline, with the Natural Earth base, relief, rivers and minerals | [region.md](docs/contracts/region.md), [DATA_SOURCES.md](docs/DATA_SOURCES.md) |
| The MCP studio | `POST /api/mcp`: tools in six groups for a contributor's AI, signed in with OAuth 2.1 | [knowledge-api.md](docs/contracts/knowledge-api.md), [open-work.md](docs/contracts/open-work.md), [mcp-oauth.md](docs/contracts/mcp-oauth.md) |
| Lessons and voice | lesson packs, the explainer PDF and citation files; a finished explainer read aloud, each word or sentence marked as it is read | [learning.md](docs/contracts/learning.md), [voice.md](docs/contracts/voice.md) |
| Open data | `/data`: a reproducible release of the open knowledge under CC BY 4.0, deposited on Zenodo with a DOI | [open-data.md](docs/contracts/open-data.md) |
| Access | six roles from Student to Master Admin; only accounts on the access roster sign in, and only Researchers and above propose knowledge | [roles-and-contributions.md](docs/contracts/roles-and-contributions.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md#students-and-artisans-decision-0083) |

## <img src="docs/readme-kit/assets/icons/workflow.svg" width="32" align="top" alt="">&nbsp; How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/pipeline-dark.svg">
  <img src="docs/readme-kit/assets/pipeline-light.svg" width="100%" alt="How knowledge flows: sources, gates, knowledge, pages and answers, and MCP contributors">
</picture>

Knowledge is stored as claims, each with its sources and an evidence level stored on the claim,
never inferred from model text; a fact rests on a quoted passage that passed the gates. Pages and
answers are built from those stored rows, so a page needs no question. The web app on Vercel reaches
the API through CloudFront; the API runs in two slots behind nginx, beside three more processes on
the same box: the media worker, the contribution worker and the fetcher.

```mermaid
%%{init: {"theme":"base","fontFamily":"Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif","themeVariables":{"fontSize":"15px","primaryColor":"#F2E9FE","primaryTextColor":"#1E1B2E","primaryBorderColor":"#9148D2","secondaryColor":"#FAEECD","secondaryTextColor":"#1E1B2E","secondaryBorderColor":"#CD9200","tertiaryColor":"#F3F1FA","tertiaryTextColor":"#1E1B2E","tertiaryBorderColor":"#A7A3BC","mainBkg":"#F2E9FE","nodeBorder":"#9148D2","nodeTextColor":"#1E1B2E","lineColor":"#AA69E9","textColor":"#857F9E","edgeLabelBackground":"#F9F5FF","clusterBkg":"#F9F5FF","clusterBorder":"#D6B6FB","titleColor":"#762CB1"}}}%%
flowchart LR
  subgraph Clients
    B["Reader's browser"]
    M["Contributor's AI<br/>an MCP client"]
  end
  subgraph Vercel
    W["Web<br/>Next.js 16"]
  end
  subgraph AWS["AWS ap-south-1"]
    CF["CloudFront<br/>HTTPS"]
    NG["nginx<br/>blue / green"]
    API["API<br/>FastAPI, MCP, OAuth"]
    WK["kv-worker<br/>media queue"]
    CW["kv-contributions<br/>queued gates"]
    FE["kv-fetcher<br/>sandboxed reads"]
    S3[("S3<br/>media bucket")]
  end
  PG[("Postgres 17<br/>Supabase, pgvector")]
  SRC["Open sources<br/>scholarly, reference, web"]
  AI["Model providers<br/>through one router"]
  B --> W
  W -->|server proxy| CF
  M -->|OAuth 2.1| CF
  CF --> NG --> API
  API --> PG
  WK --> PG
  CW --> PG
  API --> S3
  WK --> S3
  API --> FE
  CW --> FE
  API -->|search| SRC
  FE -->|read| SRC
  API --> AI
  WK --> AI
  CW --> AI
  classDef accent fill:#762CB1,stroke:#5F1C93,color:#FFFFFF
  classDef gold fill:#FAEECD,stroke:#CD9200,color:#1E1B2E
  class API accent
  class PG,SRC,AI gold
```

| Piece | What it does | Read more |
|---|---|---|
| Web | Next.js App Router on Vercel; reading pages never redirect to sign-in, while asking and the signed-in tools need a session | [ARCHITECTURE.md](docs/ARCHITECTURE.md#frontend) |
| Edge | CloudFront ends HTTPS; port 80 on the box answers CloudFront's prefix list only, and nginx refuses a request without the origin header | [RUNBOOK.md](docs/RUNBOOK.md#what-exists) |
| API | `kv-api@8000` and `kv-api@8001`: a release starts in the idle slot, passes `/health`, then nginx switches to it | [RUNBOOK.md](docs/RUNBOOK.md#deploy) |
| Workers | `kv-worker` (generated media), `kv-contributions` (queued proposals and their gates), `kv-fetcher` (address-pinned reads with no database and no AWS) | [ARCHITECTURE.md](docs/ARCHITECTURE.md#backend-layers) |
| Data | Postgres 17 on Supabase through the session pooler, with pgvector, PostGIS, pg_trgm, unaccent and citext; a private S3 bucket behind presigned links | [RUNBOOK.md](docs/RUNBOOK.md#connection-budget) |
| Sources | scholarly, reference, web and picture adapters, one per service, plus the field voices of both portals | [DATA_SOURCES.md](docs/DATA_SOURCES.md) |

## <img src="docs/readme-kit/assets/icons/bot.svg" width="32" align="top" alt="">&nbsp; The MCP studio

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/cards-mcp-dark.svg">
  <img src="docs/readme-kit/assets/cards-mcp-light.svg" width="100%" alt="The MCP studio in six groups: reading, sources, work, proposing, pages and pictures">
</picture>

Content arrives through MCP from many contributors at once, so every write is queued, batched and
idempotent, and the gates run off the request. A contributor's AI uses KalaVigyan's own source
registries, reader and quote matcher, so what it checks before proposing is what the gates check
after.

```mermaid
%%{init: {"theme":"base","fontFamily":"Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif","themeVariables":{"fontSize":"15px","primaryColor":"#F2E9FE","primaryTextColor":"#1E1B2E","primaryBorderColor":"#9148D2","lineColor":"#AA69E9","textColor":"#857F9E","noteBkgColor":"#FAEECD","noteTextColor":"#1E1B2E","noteBorderColor":"#CD9200","actorBkg":"#F2E9FE","actorBorder":"#9148D2","actorTextColor":"#1E1B2E","actorLineColor":"#AA69E9","signalColor":"#AA69E9","signalTextColor":"#857F9E","labelBoxBkgColor":"#F2E9FE","labelBoxBorderColor":"#9148D2","labelTextColor":"#1E1B2E","loopTextColor":"#857F9E","activationBkgColor":"#E7D5FE","activationBorderColor":"#9148D2","sequenceNumberColor":"#FFFFFF"}}}%%
sequenceDiagram
  autonumber
  participant A as Contributor's AI
  participant M as MCP server
  participant W as kv-contributions
  participant R as Review queue
  A->>M: Sign in with OAuth 2.1 and PKCE
  A->>M: search_sources, read_source
  A->>M: propose_facts, one to 25
  M-->>A: A ticket for each, QUEUED
  W->>W: QUOTES, SOURCE, DUPLICATE, NOVELTY
  Note over W,R: The review switch and trust tier<br/>publish it or hold it for review
  W->>R: A fact that waits
  A->>M: get_proposal
  M-->>A: Its state and reasons
```

| Step | What happens | Read more |
|---|---|---|
| Sign in | the access roster admits the account, and the MCP terms of use are accepted at the consent page | [mcp-oauth.md](docs/contracts/mcp-oauth.md), [mcp-terms-of-use.md](docs/legal/mcp-terms-of-use.md) |
| Propose | facts (one to 25 at a time), structure, sources, components and whole pages; a fact is checked at the door for its shape, subject, key and the hour's allowance, then queued | [knowledge-writes.md](docs/contracts/knowledge-writes.md) |
| Preview | a draft per page and a preview report on the page checklist, drawn in the chat before anything is submitted | [open-work.md](docs/contracts/open-work.md) |
| Review | one queue for facts, components, pictures and testimony from other people | [review-queue.md](docs/contracts/review-queue.md) |
| Method | the page checklist, source rubric, quotes, fields, component and dataset guides, served over MCP | [kalavigyan-craft-pages](.claude/skills/kalavigyan-craft-pages/SKILL.md) |

## <img src="docs/readme-kit/assets/icons/box.svg" width="32" align="top" alt="">&nbsp; Built with

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://skillicons.dev/icons?i=nextjs,react,ts,tailwind,py,fastapi,postgres,supabase,redis,nginx,aws,terraform,githubactions,vercel&theme=dark&perline=14">
    <img src="https://skillicons.dev/icons?i=nextjs,react,ts,tailwind,py,fastapi,postgres,supabase,redis,nginx,aws,terraform,githubactions,vercel&theme=light&perline=14" alt="Next.js, React, TypeScript, Tailwind, Python, FastAPI, Postgres, Supabase, Redis, nginx, AWS, Terraform, GitHub Actions, Vercel">
  </picture>
</p>

| Layer | Stack |
|---|---|
| Web | Next.js 16, React 19, Tailwind 4, framer-motion 14, 3Dmol.js 2.5, TypeScript 6; the Alum & Indigo design system |
| API | FastAPI on Python 3.15, SQLAlchemy 2.1 with Alembic and psycopg 3, pgvector, Pint, trafilatura and pypdf, citeproc-py, fpdf2 and python-pptx |
| Models | Anthropic, Gemini, OpenAI and DeepSeek behind one AI router, ElevenLabs for voice and sound |
| Data | Postgres 17 on Supabase with pgvector, PostGIS, pg_trgm, unaccent and citext; S3; Redis on the box |
| Delivery | GitHub Actions with OIDC, Terraform, SSM, systemd, nginx blue/green, Vercel |

## <img src="docs/readme-kit/assets/icons/terminal.svg" width="32" align="top" alt="">&nbsp; Quick start

A development machine writes code and runs formatters, linters and generators; it never runs tests,
type-checks, builds, dev servers or browsers (owner, 2026-11-20). Every suite runs on GitHub Actions.

1. Read the rules first: [project-bindings.md](.claude/skills/engineering-practices/references/project-bindings.md)
   binds the practice skills to this repository, and [PLAN.md](docs/PLAN.md) section 0 is the owner's
   direction.
2. Make the backend environment, Python 3.15 with uv:

   ```sh
   cd backend
   uv sync --locked
   ```

3. Run only what a development machine runs, from the repository root (`backend/.venv/bin/python`
   off Windows):

   ```sh
   backend/.venv/Scripts/python.exe -m ruff format <changed files>
   backend/.venv/Scripts/python.exe -m ruff check <changed files>
   backend/.venv/Scripts/python.exe tools/hygiene_check.py
   backend/.venv/Scripts/python.exe tools/repo_facts_build.py
   node docs/readme-kit/tools/build.mjs
   ```

   In `frontend/`, `npx eslint <changed files>`.
4. Push a branch to the `deploy` remote and open a draft pull request; Backend checks, Frontend
   checks, Hygiene and the README check run on it.
5. To see a branch before it ships, deploy a Vercel preview from the repository root and run
   **Capture screens** or **Monograph parity** on it ([RUNBOOK.md](docs/RUNBOOK.md#deploy)).

## <img src="docs/readme-kit/assets/icons/book-open.svg" width="32" align="top" alt="">&nbsp; Documentation

| Question | Answer |
|---|---|
| Where do I start? | [docs/README.md](docs/README.md), the index |
| How do the pieces fit? | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| What is the plan, and what did the owner direct? | [PLAN.md](docs/PLAN.md) |
| Which shared code exists before I write a helper? | [CORE_API.md](docs/CORE_API.md) |
| What does each interface promise? | [contracts/README.md](docs/contracts/README.md) |
| Why is it built this way? | [decisions/README.md](docs/decisions/README.md) |
| How do I deploy, roll back or switch something on? | [RUNBOOK.md](docs/RUNBOOK.md) |
| Which datasets, licences and citations? | [DATA_SOURCES.md](docs/DATA_SOURCES.md) |
| Where does the work stand? | [PROGRESS.md](docs/PROGRESS.md), [NEXT.md](docs/NEXT.md) |
| What is knowingly below standard? | [TECH_DEBT.md](docs/TECH_DEBT.md) |
| How do I bring a craft page to the Kutch Ajrakh bar? | [kalavigyan-craft-pages](.claude/skills/kalavigyan-craft-pages/SKILL.md) |
| How must a screen look and read? | [kalavigyan-design](.claude/skills/kalavigyan-design/SKILL.md), [master-board.html](docs/design/master-board.html) |
| What does a contributor agree to? | [contribution-terms.md](docs/legal/contribution-terms.md), [image-declaration.md](docs/legal/image-declaration.md) |
| How many tables, routes, tools and tests? | [REPO_FACTS.md](docs/REPO_FACTS.md), generated; no count is written by hand |
| How is this README built? | [readme-kit/README_STYLE.md](docs/readme-kit/README_STYLE.md) |

## <img src="docs/readme-kit/assets/icons/rocket.svg" width="32" align="top" alt="">&nbsp; Status

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/timeline-dark.svg">
  <img src="docs/readme-kit/assets/timeline-light.svg" width="100%" alt="Rounds: 1 fields, gates and OAuth; 2 the review queue and uploads; 3 one monograph template; 4 every craft a document; 5 the answer page and every field; 6 curated crafts as documents; 7 knowledge made over MCP">
</picture>

Before the rounds, the foundation and the answer experience's phases A to D were built by 18
November 2026 ([PROGRESS.md](docs/PROGRESS.md#done)). Decision 0101's track of rounds followed.

| Round | Date | What shipped |
|---|---|---|
| 1 | 19 Nov 2026 | retrieval by field, the gates, the review switch and nightly upkeep, MCP sign-in, terms and open work, nightly static builds and the bulk export |
| 2 | 19 Nov 2026 | the unified review queue, MCP `ask` and picture uploads, approved pictures on craft pages, contribution screens, the dossier export |
| 3 | 19 Nov 2026 | one monograph template for every page: the split, the document API, page layouts, generated documents, every component kind as a spec with its view |
| 4 | 20 Nov 2026 | MCP and retrieval finished, every craft as its English document, redesign wave 1B |
| 5 | 20 Nov 2026 | the answer page and every signed-in screen, every field everywhere |
| 6 | 20 Nov 2026 | curated crafts as documents, native Kutch Ajrakh views, the boards matched, the structure write path |
| 7 | 20 Nov 2026 | MCP as the place knowledge is created, the landing and the map rebuilt; its fix lanes then held every answer sentence to the quotes it cites, filed write-backs by what their sources say and made every release one the live side can read |
| Debt round | 22–23 Nov 2026 | the debt register cleared lane by lane, and kept so it can only shrink: rivers named from open datasets, film scores made once, Listen read by the Gemini voice when ElevenLabs cannot, translations read back, contributed facts on curated pages, write-backs judged cheapest first |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/divider-dark.svg">
  <img src="docs/readme-kit/assets/divider-light.svg" width="100%" alt="">
</picture>

## How this document is kept true

This file is the front page. Depth lives in [docs/](docs/README.md), and when the two disagree,
`docs/` wins and this file is the one to fix.

| Claim | Kept true by |
|---|---|
| Images, `<picture>` pairs and every mermaid block | `readme-check.yml`: the kit rebuilt from `kit.json` and diffed, every SVG checked, every diagram drawn by mermaid-cli and opened on github.com |
| The stack and its versions | `frontend/package.json` and `backend/pyproject.toml` |
| Roles, depths and languages in the stats | `backend/app/core/roles.py`, `backend/app/research/depth.py` and `backend/app/research/vocabulary.py` |
| The nine categories | the vendored master list, `backend/app/data/craft_master_list.json`, pinned by `shared/craft-master.sha1` |
| The deployed pieces | [RUNBOOK.md](docs/RUNBOOK.md), what exists |
| The rounds | [PROGRESS.md](docs/PROGRESS.md), Done |
| Counts of tables, routes, tools and tests | not stated here; [REPO_FACTS.md](docs/REPO_FACTS.md) is generated |

**Review triggers:** a round that ships, a new deployed piece or workflow, a change to the stack's
major versions, or a change to what a development machine may run.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-kit/assets/footer-dark.svg">
  <img src="docs/readme-kit/assets/footer-light.svg" width="100%" alt="The science behind every craft, cited. Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur.">
</picture>
