---
name: kalavigyan-craft-pages
description: How to make or deepen a KalaVigyan craft, family or category page to the Kutch Ajrakh bar through the KalaVigyan MCP server, by the same method and references every contributor follows - sources found, read and checked with the same registries, reader and quote matcher the gates use (search_sources, read_source, check_quote, lookup_compound, lookup_entity, find_pictures, archive_source), facts through propose_facts and get_proposal, structure (a stage's colour after and its why, native names, reactions, botanical names, the GI record, glossary, conflicts, open questions) through propose_structure, new sources through propose_source, components delivered finished as spec and units, whole pages through preview_page then propose_page, pictures through start_image_upload, and Commons pictures still placed through the dossier import - cheaply, one page per agent, with the gates, the checker and the preview as the judges. The rules are the shared references (the page checklist and its 26 rules, sources and licences, quotes and locators, the sixteen fields, components, datasets); the dossiers in backend/app/data/curation are the database's export, edited by hand only for a bulk import. Load it before creating, deepening, fixing or reviewing any page's content, dossier, check file or proposed fact, and before briefing an agent to do so.
---

# KalaVigyan craft and category pages

The database holds every page's knowledge, and every contributor reaches it the same way: through
the KalaVigyan MCP server, by the contributor skill's method and the shared references. This skill
is that method for the team's own agents, plus what only the team does: the bar a curated page
meets, its gaps, the dossier route for Commons pictures and bulk imports, the cost rules and the
briefing. `docs/contracts/knowledge-writes.md` is the write path and its gates,
`docs/contracts/curation.md` the dossier contract field by field, `docs/contracts/dossier-export.md`
the export. Read the section you need, never the whole file.

## The references

One source per rule, served to every contributor over MCP and read here from the repository:

| Reference | In the repository | Over MCP |
|---|---|---|
| The page checklist: the three lists a page derives first and its 26 rules | `backend/app/data/contributor/references/page-checklist.md` | `kalavigyan://skills/references/page-checklist.md` |
| What counts as a source: grades, recording, licences | `backend/app/data/contributor/references/sources.md` | `kalavigyan://skills/references/sources.md` |
| Quotes and locators, and one fact per sentence | `backend/app/data/contributor/references/quotes.md` | `kalavigyan://skills/references/quotes.md` |
| The fields and what each holds | `backend/app/data/contributor/references/fields.md` | `kalavigyan://skills/references/fields.md` |
| Authoring a component | `backend/app/data/contributor/references/components.md` | `kalavigyan://skills/references/components.md` |
| Datasets | `backend/app/data/contributor/references/datasets.md` | `kalavigyan://skills/references/datasets.md` |
| The contributor skill: the tools in order, proposals and their progress, tiers, allowances, structure, components, pages and pictures | `backend/app/data/contributor/SKILL.md` | `kalavigyan://skills/kalavigyan-contributor/SKILL.md` |
| The datasets skill | `.claude/skills/kalavigyan-datasets/SKILL.md` | `kalavigyan://skills/kalavigyan-datasets/SKILL.md` |

`references/page-checklist.md` beside this skill is the same file as the shared checklist, kept
identical by the tests for the documents that name it. The server also serves the contracts a
client follows, copied whole from `docs/contracts` (`kalavigyan://contracts/knowledge-writes.md`,
`open-work.md`, `component-specs-general.md`, `image-contributions.md`, `mcp-ask-and-upload.md`),
and `kalavigyan://index.md`, one line for each tool, prompt and resource.

## Connect

- The session's client adds the KalaVigyan MCP server at `<PUBLIC_API_URL>/api/mcp`
  (`docs/RUNBOOK.md`, MCP server), and the person running the session signs in as a Researcher or
  above when the client asks. The agent never sees or handles the sign-in.
- `tools/curation/propose.py` sends a working dossier's stand-alone facts through the Knowledge API
  and the same gates. It reads a signed-in session token of a Researcher or above from
  `KALAVIGYAN_TOKEN`, set by the person running the session: never print it, write it to a file or
  put it on a command line. Its address, `KALAVIGYAN_API` or `--api`, is the API origin
  (`PUBLIC_API_URL`), not the site, which refuses a write that does not come from its own pages.

## Where each change goes

| Change | Path |
|---|---|
| Finding a source | `search_sources` first (the registries, reference works and web search KalaVigyan's planner uses, each result graded with its licence and any open copy), then your own search |
| Reading it and taking quotes | `read_source`, which returns the text the gates will match, page by page or `around` given words, with locators; `archive_source` for a snapshot of a page that may vanish |
| A quote before it is sent | `check_quote`: the QUOTES gate's verdict, and the nearest passage when it misses |
| A compound's record and hazards, a plant's taxon name, a place's or craft's item | `lookup_compound`, `lookup_entity` |
| Finding open pictures | `find_pictures` (Commons and Openverse, open licences only, with author, credit and the site's widths), then the dossier route |
| A fact that stands alone | `propose_facts` (up to 25, each with an `idempotency_key` and the claimed `task_key`), then `get_proposal` until it is DONE; a working dossier's new facts in one run with `tools/curation/propose.py` |
| A new source for a held fact, or for a fact that lost its quotes | `propose_source`, naming the fact as `claim_id` |
| A stage's after or why, a native name, a reaction, a botanical name, a glossary term, an open question, the GI record, a conflict | `propose_structure`, one item with the fact and the quotes that state it |
| A component | `list_components` first, then delivered finished as spec and units (the component guide), in a page bundle or with `propose_component` |
| A whole page's additions: facts, structure, components, layout, pictures | `preview_page`, then `propose_page` with the same bundle |
| A picture a person took or made | `start_image_upload`, or `give_image` when it is in the chat, with the declaration the person confirms |
| A Wikimedia Commons picture: its placement, focal box, size and stand-in | the dossier route, a new dossier version imported on deploy, while it remains the import path for pictures from elsewhere |
| A new craft's first dossier, or any bulk import | the dossier route |
| What is held | `get_facts`, `get_section`, `get_coverage`, `get_layout`; against git, `export_dossiers --diff` (the lead) |

The dossiers in `backend/app/data/curation` (a category's under `categories/`), each with its
`.check.json`, are the database's versioned export: a backup, a diff and the bulk import. They are
edited by hand only to prepare a bulk import, and then only in a working copy (the dossier route).

## The bar (Kutch Ajrakh, version 3)

A finished craft page has:

| Part | Ajrakh | Bar for every craft |
|---|---|---|
| Pictures | 10, all placed | 8 or more where open-licence pictures exist, at most 16, every one placed |
| Masthead | 1, with focal box | exactly 1 `MASTHEAD`, with `focal` and `width`/`height` |
| Chapters with pictures | glance, made, chem, why, history, people | 4 or more; an `OPENER` per chapter where a fitting picture exists |
| Stage pictures | `STAGE` placements on key stages | the stages a reader would want to see |
| Material pictures | `MATERIAL` placements, `standIn` when not this craft | key dyes, ores, clays, fibres |
| Stage `after` | 8 of 14 | every stage whose result a source describes (text plus up to 3 colours) |
| Stage `whyClaimId` | 11 of 14 | two thirds of stages or more |
| Native names | Sindhi script and Latin | 1 or more, in the craft's own script where a source gives it |
| Reactions | 2, with reactants and products | every reaction a source states, formulas only as quoted |
| Botanical names | on plant materials | every plant material |
| GI record | full | every GI-registered craft (never a family or category) |
| Conflicts, open questions | recorded | every disagreement found; never settled |
| Fields | 13 of 16 (physics, geology and health missing; climate and ecology thin) | every one of the 16 fields a source covers; 12 or more for a curated craft; 3 or more cited claims in each covered field |

A category page has no stages, native names or GI record; it has pictures placed the same way,
`subCategories` on sentences and questions, and the family's reactions. The exemplar's dossier is
`Kutch-Ajrakh.json`; read it by field, never whole (it is large):
`python -I -c "import json;d=json.load(open('backend/app/data/curation/Kutch-Ajrakh.json',encoding='utf-8'));print(json.dumps(d['pictures'][:3],ensure_ascii=False,indent=1))"`

## See the gaps first

- `get_coverage` gives each field's cited facts, sources, sections and figures and its standing;
  `list_open_work` gives the page's tasks.
- `python -I .claude/skills/kalavigyan-craft-pages/scripts/gaps.py <dossier>` prints a dossier's
  counts against the bar (pictures and their placements, stages' after and why, native and
  botanical names, the GI record, fields), `--json` for machine output. Run it on the exported
  dossier, and on a working copy before and after a bulk import. It counts the facts structure
  cites (communities for SOCIETY, the GI record for POLICY) as `get_coverage` does.
- Search every field with no fact before calling it a gap, with `search_sources` and then your
  own search. The ones most often missing are botany,
  climate, health, geology, policy and ecology: look for dye and fibre plant monographs, district
  climate normals and hydrology, occupational health studies of the craft's materials, soil and
  mineral surveys, the GI journal and scheme documents, and ecological studies of the raw
  materials. A gap stays a gap only when you searched and found no source; record what you
  searched (a bulk import keeps it under `searched`).

## Method, cheapest first

1. **Read the page** and derive its three lists (the page checklist).
2. **Use what is held.** Structure that held facts already state goes in through
   `propose_structure`, each item with the fact and the quote that state it: a stage's after and
   its why, native names and botanical names that already sit in a quote. No new source is needed.
3. **Fill the remaining gaps from new sources**, open ones only (the source rubric), found with
   `search_sources` and read with `read_source`, every quote passed by `check_quote` before it is
   sent, compounds and taxon names from `lookup_compound` and `lookup_entity`: new facts
   through `propose_facts`, structure through `propose_structure`, a held fact's new source through
   `propose_source`, components by the component guide, figures from data by the datasets skill,
   and Commons pictures by the dossier route (`fetch.py --picture` gives a picture's address, size,
   author and licence).
4. **See the page before sending it.** Build the page's additions as one bundle, call
   `preview_page`, read the preview against the page checklist, fix and preview again, then
   `propose_page` with the same bundle.
5. **Follow every proposal** with `get_proposal` or `my_tasks`. A refused fact is fixed from its
   sources or dropped, never reworded past its quotes to slip a gate.
6. **Hand the lead what only the dossier route carries**: Commons pictures with their placements and
   focal boxes, or a new craft's first dossier, as the working dossier with its version raised by
   one and its `curatedAt` updated, verified and checked.
7. **Report** in under 150 words: gaps before and after, each proposal's outcome, sources added,
   what was searched and not found. No prose summaries of the craft.

## The dossier route

Copy the craft's dossier from `backend/app/data/curation` into your scratchpad as the working
dossier, under the same file name (a category's inside a `categories` folder there), and work only
on that copy. Never edit the dossier in git: it is the export, and the lead refreshes it. When the
lead says the git copy is behind the database, ask for a fresh export. Every new claim in it
follows the references; the verifier rejects a quote that is not verbatim in its source, as the
gates do.

From the repository root with the backend's Python (`backend\.venv\Scripts\python.exe`); `<work>`
is the working dossier in your scratchpad.

| Step | Command |
|---|---|
| gaps | `python -I .claude/skills/kalavigyan-craft-pages/scripts/gaps.py <work>` |
| read a source as the verifier will | `python tools/curation/fetch.py <https url>`, or `read_source` over MCP |
| find open pictures | `find_pictures` over MCP, with the craft's slug |
| a Commons picture's address, size, author, licence | `python tools/curation/fetch.py --picture https://commons.wikimedia.org/wiki/File:<name>` |
| verify quotes (network) | `python tools/curation/verify.py <work>` |
| offline checks | `python tools/curation/check.py <work>` |
| what would be proposed | `python tools/curation/propose.py <work> --dry-run` |
| propose the new facts | `python tools/curation/propose.py <work>`, with `KALAVIGYAN_TOKEN` set; `--only <claim id>` to send some |
| what the database holds against git (the lead) | from `backend`: `python -m app.scripts.export_dossiers --diff --slug <Slug>` |
| refresh the export in git (the lead) | from `backend`: `python -m app.scripts.export_dossiers --out app/data/curation` |
| index (the lead only, once per batch) | `python tools/curation/check.py --write-index` |

`propose.py` sends only the facts the dossier in git (the export, or the file `--stored` names)
does not hold, by claim id or by the same wording; the receipt beside the working dossier keeps a
fact from being sent twice. Never edit `index.json`.

## Cost rules (owner, 2026-11-18: a whole plan was spent on agents that ran too long)

- **One page per agent.** Never two pages in one agent, never two agents on one page.
- **Sonnet, not Opus**, for deepening; the gates, the verifier, the checker and the preview are the
  judges, so no critic or judge agents.
- **Stop at about 60 turns.** Send what stands, follow it to its outcome, report the rest as open.
- **Read narrowly**: one field of the exemplar, one reference or contract section, one source page
  at a time. Never read a whole dossier into context when a field will do; never open application
  code.
- **Run nothing else**: no backend or frontend test suites, no builds, no git, no export. The
  lead commits and exports.
- **Never edit code, schemas, other dossiers or the dossiers in git.** A tooling problem is
  reported, not fixed.

## Briefing an agent (the lead)

Give the agent this skill's name, the page (its kind and slug), its `get_coverage` or gaps output,
and for the dossier route its working copy of the exported dossier. Nothing else; the skill and the
references carry the method. Run the pages of one family together so their pictures and reactions
do not repeat. When the agents are done, the lead commits the dossier-route versions to
`backend/app/data/curation`, runs `check.py --write-index` once, the import on deploy stores them
(decision 0053), and `export_dossiers --diff` against the database then reports no change for those
dossiers.

## The exemplar page

The owner-approved Kutch Ajrakh page is served as built at `/crafts/Kutch-Ajrakh` from
`frontend/public/monographs/kutch-ajrakh/index.html` (decision 0100). Every other craft, family
and category page takes its form from it: the chapter order, the opening, the figures and their
players, the citation clusters and popovers, the media gallery, the coda and the sources. Read
it by section, never whole (it is about 3 MB). Its facts are Ajrakh's and never carry over:
every sentence on another page comes from that craft's own stored facts. The scripts that built it
are archived in `docs/design/monograph-build.zip` (`build.py` reads the boards and writes the page;
`ship_monograph.py` copies a rebuilt page into `frontend/public`).

## Order

Minister-facing first: the GI crafts with the most visual stages (Bidriware, Blue Pottery of
Jaipur, Kutch Bandhani, Machilipatnam Kalamkari, Madhubani, Orissa Pattachitra, Bastar Dhokra,
Channapatna), then the rest of the crafts, then the nine categories. The three with no pictures
(Bareilly Cane Bamboo, Sanganeri, Varanasi Soft Stone Jali) need pictures first.
