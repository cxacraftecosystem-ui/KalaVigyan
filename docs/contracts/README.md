# Contracts

The interfaces between KalaVigyan's lanes: what each route answers, what each file holds and which
rules every value follows. Read the contract before changing either side of an interface, and change
the contract in the same change as the code. Engineers and contributors' agents read them; the MCP
server serves the ones a contributor needs.

| For | Read |
|---|---|
| Where a contract sits in the system | [ARCHITECTURE.md](../ARCHITECTURE.md) |
| Why an interface is the way it is | [decisions/README.md](../decisions/README.md) |
| The shared code a contract names | [CORE_API.md](../CORE_API.md) |
| Every other document | [docs/README.md](../README.md) |

## Platform

| Contract | Answers |
|---|---|
| [backend.md](backend.md) | Every API route's prefix, body casing, headers and error forms |
| [frontend.md](frontend.md) | The web client's routes, its one API client and what it reads from the backend |
| [infra.md](infra.md) | What the box and the deploy workflows assume from the backend, frontend and CI lanes |
| [nightly-upkeep.md](nightly-upkeep.md) | What the database looks after every night, and the nightly static build of the web app |

## Research and answers

| Contract | Answers |
|---|---|
| [research.md](research.md) | The interfaces that resolve crafts, plan research, search and fetch sources, compose and check answers |
| [retrieval.md](retrieval.md) | How stored claims and passages are found for a question, and how their vectors are kept |
| [explainer.md](explainer.md) | An answer as an explainer: ordered sections of typed blocks, streamed as they are built |
| [answer-components.md](answer-components.md) | The components an answer section draws, found by label in the component registry |
| [answer-eval.md](answer-eval.md) | How the ask agent seats experts for every field a question touches, and how that is measured |
| [learning.md](learning.md) | Follow-ups, versions, saved answers, alerts, lessons, exports, shared science and the map |

## Craft pages and documents

| Contract | Answers |
|---|---|
| [craft-page.md](craft-page.md) | What `GET /api/crafts/{slug}/page` answers: the craft page as a monograph in chapters |
| [category-page.md](category-page.md) | What `GET /api/categories` and `GET /api/categories/{slug}` answer for the nine categories |
| [coverage.md](coverage.md) | What a craft, family or category page holds in each of the sixteen fields |
| [monograph-document.md](monograph-document.md) | The monograph document, the template split into fragments, and the kit |
| [monograph-renderer.md](monograph-renderer.md) | How the web app draws a monograph document, and the page-tool kinds |
| [page-layout.md](page-layout.md) | A page's layout record and the generated monograph documents |
| [component-specs-science.md](component-specs-science.md) | The science group's component kinds as specs |
| [component-specs-data.md](component-specs-data.md) | The data and place group's component kinds as specs |
| [component-specs-plates.md](component-specs-plates.md) | The plates and media group's component kinds as specs |
| [component-specs-general.md](component-specs-general.md) | Components delivered finished through MCP, and the general kinds |

## Knowledge and contribution

| Contract | Answers |
|---|---|
| [knowledge-api.md](knowledge-api.md) | The Knowledge API and the MCP server's tools, served to any agent |
| [mcp-oauth.md](mcp-oauth.md) | How an agent signs in to the MCP server with OAuth 2.1 |
| [mcp-ask-and-upload.md](mcp-ask-and-upload.md) | The signed-in `ask` tool and the picture tools |
| [open-work.md](open-work.md) | Open work, reservations, component proposals and the method served over MCP |
| [knowledge-writes.md](knowledge-writes.md) | How a proposed fact passes the automatic gates, the review switch and the limits |
| [review-queue.md](review-queue.md) | One review path for facts, components, pictures and testimony that other people give |
| [contribution-screens.md](contribution-screens.md) | The site's screens for proposing a fact or a component, and a contributor's own list |
| [image-contributions.md](image-contributions.md) | Pictures given to a craft: photographs, drawings and illustrations, declared and screened |
| [roles-and-contributions.md](roles-and-contributions.md) | What Students and Artisans are asked at first entry, and how artisan testimony is handled |
| [curation.md](curation.md) | What a curated dossier holds, how its quotes are verified and what the offline checker refuses |
| [dossier-export.md](dossier-export.md) | The database as the source of curated knowledge, and the dossiers as its export |
| [open-data.md](open-data.md) | The versioned, citable open dataset under CC BY 4.0, deposited with a DOI |

## Crafts, places and voices

| Contract | Answers |
|---|---|
| [crafts.md](crafts.md) | The craft data lane: the master list, aliases, Wikidata links and seed claims |
| [portal-craft-feed.md](portal-craft-feed.md) | What the two portals' signed peer route gives KalaVigyan about their crafts |
| [field-voices.md](field-voices.md) | The portals' transcripts and craft images, by cursor with tombstones |
| [geo.md](geo.md) | The geo lane's per-district environment statistics and how they are loaded |
| [region.md](region.md) | What a craft's region panel and the map's choropleths receive |
| [science.md](science.md) | What `GET /api/crafts/{slug}/process` answers: stages, materials, conditions and reactions |
| [voice.md](voice.md) | How a two-way voice conversation is started, bound to one user and answered |
| [media.md](media.md) | Generated stage images and videos: what they are built from and how they are served |

## How this document is kept true

It is an index, so it is wrong in two ways only: a contract exists and is not listed, or a row names
a file that is gone. The links are checked by every reader and by the README check's render of this
page; the first is caught by comparing the tables with `ls docs/contracts`.

| Change | What to do here |
|---|---|
| A new contract | add its row, in the area it serves, in the same change that adds the file |
| A contract renamed, merged or retired | change or remove its row in the same change |
| A contract's scope moves | rewrite its "Answers" line from the contract's own opening |

Re-read the whole table when a round adds a lane, since a new lane usually adds a contract.
