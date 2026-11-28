---
name: kalavigyan-craft-pages
description: How to make or deepen a KalaVigyan craft, family or category page to the Kutch Ajrakh bar through the KalaVigyan MCP server, by the same method and references every contributor follows - sources found, read and checked with the same registries, reader and quote matcher the gates use (search_sources with its pictures, read_source with its quote checks and archive, lookup), facts through propose_facts and get_proposal, structure (a stage's colour after and its why, native names, reactions, botanical names, the GI record, glossary, conflicts, open questions) through propose_structure, new sources through propose_source, components delivered finished as spec and units, whole pages built in a draft (curate_page, edit_draft, preview_page's checklist report, propose_page) or given as one bundle to preview_page then propose_page, sources only the contributor can open through supply_source, pictures through give_pictures, open-licence pictures given by their page through give_pictures - cheaply, one page per agent, with the gates, the checker and the preview as the judges. The rules are the shared references (the page checklist and its 29 rules, sources and licences, quotes and locators, the sixteen fields, components, datasets); the dossiers in backend/app/data/curation are the database's export, edited by hand only for a bulk import. Load it before creating, deepening, fixing or reviewing any page's content, dossier, check file or proposed fact, and before briefing an agent to do so.
---

# KalaVigyan craft and category pages

The database holds every page's knowledge, and every contributor reaches it the same way: through
the KalaVigyan MCP server, by the contributor skill's method and the shared references. This skill
is that method for the team's own agents, plus what only the team does: the bar a curated page
meets, its gaps, the dossier route for a curated picture's focal box and bulk imports, the cost rules and the
briefing. Read the section you need, never the whole file.

| For | Read |
|---|---|
| The write path and its gates | `docs/contracts/knowledge-writes.md` |
| The dossier contract, field by field | `docs/contracts/curation.md` |
| The export | `docs/contracts/dossier-export.md` |
| The rules themselves | the references, below |

## The references

One source per rule, served to every contributor over MCP and read here from the repository:

| Reference | In the repository | Over MCP |
|---|---|---|
| The page playbook: the order a page is built in to the Kutch Ajrakh bar, what to read before each step | `backend/app/data/contributor/references/playbook.md` | `kalavigyan://skills/references/playbook.md` |
| The component cookbook: every kind, the tool that makes it, its Ajrakh example and its place | `backend/app/data/contributor/references/cookbook.md` | `kalavigyan://skills/references/cookbook.md` |
| The page checklist: the three lists a page derives first and its 29 rules | `backend/app/data/contributor/references/page-checklist.md` | `kalavigyan://skills/references/page-checklist.md` |
| The designer's critique: reading a preview's pictures against the design before proposing, and the notes recorded with the next preview | `backend/app/data/contributor/references/design-critique.md` | `kalavigyan://skills/references/design-critique.md` |
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

Over MCP each reference is also paged (`get_page`'s `guide`, `contents/1`), and the page tools hand
an agent the page for its step; a page's first components wait for the design pages' `read_token`.
The server also serves Kutch Ajrakh worked chapter by chapter (`ajrakh-<chapter>/1`, every
component's spec, place and the sentences around it), the design skill and SYSTEM.md
(`kalavigyan-design/1`, `system/1`) and the kit's stylesheet and script (`kit-stylesheet/1`,
`kit-script/1`). Brief an agent with the page alone: the playbook it is handed first says the rest.

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
| Reading it and taking quotes | `read_source`, which returns the text the gates will match, page by page or `around` given words, with locators; `read_source` with archive for a snapshot of a page that may vanish |
| A quote before it is sent | `read_source` with the quote in its `quotes`: the QUOTES gate's verdict, and the nearest passage when it misses |
| A compound's record and hazards, a plant's taxon name, a place's or craft's item | `lookup`, with kind compound or entity |
| A photograph from KalaVigyan's own field portals | `list_field_photos` (each photo with a thumbnail and its `pictureUrl`), then place it by its label in the draft's layout (HERO for the masthead, OPENER, PLATE or FIGURE), captioned from what its thumbnail shows; the preview draws it (decision 0252), and these come before any searched picture |
| Finding open pictures | `search_sources` with kinds pictures (Commons and Openverse, open licences only, with author, credit and the site's widths), then `give_pictures` with its `page_url` |
| A figure of a stage, a material or a section | a composed `diagram` from the figure kit (`components.md`); a player's or card's scene as a kit scene in its slot |
| A map of the page's places, their years and moves | a declared `timeline_map` in the draft or bundle (the dataset guide, Maps of places); never a drawing |
| A fact that stands alone | `propose_facts` (up to 25, each with an `idempotency_key` and the claimed `task_key`), then `get_proposal` until it is DONE; a working dossier's new facts in one run with `tools/curation/propose.py` |
| A new source for a held fact, or for a fact that lost its quotes | `propose_source`, naming the fact as `claim_id` |
| A stage's after or why, a native name, a reaction, a botanical name, a glossary term, an open question, the GI record, a conflict | `propose_structure`, one item with the fact and the quotes that state it |
| A field's written section (its prose) from facts the page shows | a `sections` part `{field, sentences [{text, claim_ids}]}` in the draft (`edit_draft` add) or a bundle: `preview_page` draws it in place of the published section, then `propose_page`; reviewed as `SECTIONS` (decision 0250), followed with `get_proposal` by the part's id (decision 0251) |
| A reviewed section in the dossiers | never by hand: the lead's `export_dossiers --out` writes it once approved, and an import restores it only where the database holds no section a person wrote (decision 0251) |
| A component | `list_components` first, then delivered finished as spec and units (the component guide), in a draft or a page bundle, or alone in a bundle to `propose_page` |
| A picture for each stage of a stage player | every stage but the last carries its own kit `scene` (cookbook, `stage_player`); the player's `drawing` is the finished work it ends on (decision 0253) |
| A reaction species drawn without colour (rule 27) | give the part a `material`, or a `mark` of `clear`, `gas` or `ion`, and the lane the same swatch, with `edit_draft` (decision 0252) |
| A 3D molecule of a compound the facts name but no material holds | `lookup` for its CID, then `compose_component` with kind `molecule_3d` and `about.compound`; its `missing` names the fact to propose (decision 0253) |
| A climate chart or district climate map of the craft's place | the site's own district values: the map's district panel (`/api/map/districts/{lgd}`) holds monthly normals and 45-year series from CHIRPS, GHCN-CAMS and CHELSA, all in the dataset registry; key the figure to the place as a shared component, as Kachchh's are, so every craft of that district draws it (owner, 2026-11-28) |
| A map layer's dataset record | read each layer's source, licence and checksum with `get_page`, guide `map-layers/1`; nothing of it is sent or proposed (decision 0253) |
| A fact that reads as a gap (rule 26) | `propose_facts` for what its source does say; an Admin may stage its retraction with `stage_reviews` (decision 0252) |
| What a preview refuses before you send | every part check `propose_page` makes, in its own words, except those that call a model or read a source afresh: a fact's later gates, structure's QUOTES and SOURCE gates, and the section judge (decision 0254) |
| A label the cookbook marks page only | it lives on an authored page alone: never name it in `considered_labels`, `extends` or a layout (decision 0254) |
| A whole page built over many calls | the `curate_page` prompt: `edit_draft` part by part, `preview_page` with the draft and its checklist report until nothing fails, then `propose_page` with the draft |
| A whole page's additions given at once: facts, structure, components, layout, pictures | `preview_page`, then `propose_page` with the same bundle |
| A source only your own access opens: a paywalled paper, a book or PDF you hold, an archive, a site that refuses the fetcher | `supply_source`, then `read_source`'s quote checks against your text; cite it as its `cite_as` gives it |
| A picture a person took or made | `give_pictures`, in the chat or as an upload slot, with the declaration the person confirms |
| A searched picture shown beside a fact that may show something else | `check_pictures`: look at each picture of the batch and record `shows` or `does_not_show` with what it shows (12 to 300 characters); a refusal hides it beside that fact at once, a `shows` counts from a trusted account or two agreeing (decision 0222) |
| A curated picture's focal box and stand-in | the dossier route |
| A new craft's first dossier, or any bulk import | the dossier route |
| What is held | `get_page` with `parts: ["brief"]` (every fact in one line by chapter, decision 0240), `get_facts` (by `ids` for whole facts), `get_page` (coverage, sections, layout); against git, `export_dossiers --diff` (the lead) |

The dossiers in `backend/app/data/curation` (a category's under `categories/`), each with its
`.check.json`, are the database's versioned export: a backup, a diff and the bulk import. They are
edited by hand only to prepare a bulk import, and then only in a working copy (the dossier route)
of the export the lead makes first, since the import does not take a file that lacks structure a
reviewer approved in the database (decision 0171).

### Removing and editing published content (Admins)

Only an Admin's AI client with the review scope changes what is already published, and only by
staging it. Read `kalavigyan://admin/published-content.md` first. Find the item: `review_queue` with
`published` lists a page's pictures, layout, structure entries, readings and placed stages, or the
approved map layers; `get_facts` gives facts and sources; `list_components` gives components. Open
the item by `id` (or a component by `label`) to see the fields an edit changes. Stage `remove`, or
`edit` with only the changed fields, plus a reason of at least 12 characters, using `stage_reviews`;
add `entry` for a structure entry whose fact holds up more than one entry. A refusal quotes the gate
that refused; fix the change and stage it anew. Nothing changes until a person confirms the batch on
the Review page or in the form a client that shows forms puts to them at once; never answer that form
for them. Contributors withdraw their own components through a page's `withdrawals`, never
these tools.

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
| Colour key | 5 colours, each by its dye | drawn by the site from stage afters with colours, mordant and dye facts; two or more colours |
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

Every page exports as a PDF and a Word document. Readers download it from the page itself, on family and category pages too, with each open-licence plate's picture in its place. Each component is drawn there as its still at rest,
with every unit it holds and its credits. Say in a component's units what its motion shows: paper
keeps the words, the rest step and the drawing, not the play. Kit parts, kit scenes and declared
timeline maps draw on paper by themselves; a free drawing is drawn from its paths, shapes and text,
without its textures.

## See the gaps first

- `get_page` with its coverage gives each field's cited facts, sources, sections and figures and its standing;
  `list_open_work` gives the page's tasks.
- `python -I .claude/skills/kalavigyan-craft-pages/scripts/gaps.py <dossier>` prints a dossier's
  counts against the bar (pictures and their placements, stages' after and why, native and
  botanical names, the GI record, fields), `--json` for machine output. Run it on the exported
  dossier, and on a working copy before and after a bulk import. It counts the facts structure
  cites (communities for SOCIETY, the GI record for POLICY) as `get_page` does.
- Search every field with no fact before calling it a gap, with `search_sources` and then your
  own search. The ones most often missing are botany,
  climate, health, geology, policy and ecology: look for dye and fibre plant monographs, district
  climate normals and hydrology, occupational health studies of the craft's materials, soil and
  mineral surveys, the GI journal and scheme documents, and ecological studies of the raw
  materials. A gap stays a gap only when you searched and found no source; record what you
  searched (a bulk import keeps it under `searched`).

## Method, cheapest first

A redesign retires what it replaces in the same draft (withdrawals, or `replaces`), and borrows a
family figure only when the page holds every fact its units cite.

1. **Read the page** and derive its three lists (the page checklist).
2. **Use what is held.** Structure that held facts already state goes in through
   `propose_structure`, each item with the fact and the quote that state it: a stage's after and
   its why, native names and botanical names that already sit in a quote. No new source is needed.
3. **Fill the remaining gaps from new sources**, open ones only (the source rubric), found with
   `search_sources` and read with `read_source`, every quote passed by `read_source`'s check before it is
   sent, compounds and taxon names from `lookup`: new facts
   through `propose_facts`, structure through `propose_structure`, a held fact's new source through
   `propose_source`, components by the component guide, figures from data by the datasets skill,
   and open pictures through `give_pictures` by `page_url` (the server reads the licence and the
   author and returns a thumbnail to check). A picture an answer finds by search must name the craft, its places or its family's world in its title; pictures you give through `give_pictures` are never refused by that rule, so give the craft's own pictures, captioned by what they show. A page's masthead photograph is the first thing a phone waits for: the site preloads it first (`fetchPriority: "high"`) at the width the phone draws, 960 px at 360. Choose one whose 960 px rendition is light; the phone budget holds the first screen's pictures to their recorded bytes (decision 0209). Quote a colour change as the source states it, first
   colour and then the colour it turns. Answers then draw that stage from the kit, citing your fact.
4. **See the page before sending it.** Build the page in a draft (`edit_draft`),
   call `preview_page` with it, read its pictures, fix every rule its report fails (rule 28 names each
   drawing problem), preview again until rule 28 passes, then judge the rest on the private link at
   360 and 1440 px in both themes, preview again, then `propose_page` with it. A page given in one call
   goes through `preview_page` and `propose_page` the same way. Before composing a `dip_player`, give
   each bath stage its `STAGE_AFTER` with the colours its fact states and name its dyes, mordants and
   resists by substance; the dip then draws without a colour the team recorded. Compose the page's interactives with
   `compose_component`, never borrowed from Kutch Ajrakh; propose what `missing` names first. Preview
   the page with them and read its pictures: step every player, dip every dip, turn and zoom every
   molecule and choose every option at 360 and 1440 px before `propose_page`. A page's edition `/crafts/<slug>/v<N>` and the rest of a page drawn at that version stay readable after a rebuild, until something is removed, edited, withdrawn or retracted from the page, which drops its earlier editions (the one current then once the web has refreshed the page); a page drawn at a dropped version reads the rest of the current one, and Monograph parity names a page whose rest could not be read.
5. **Follow every proposal** with `get_proposal` or `my_work`. A refused fact is fixed from its
   sources or dropped, never reworded past its quotes to slip a gate.
6. **Hand the lead what only the dossier route carries**: a curated picture's focal box and stand-in,
   or a new craft's first dossier, as the working dossier with its version raised by
   one and its `curatedAt` updated, verified and checked.
7. **Report** in under 150 words: gaps before and after, each proposal's outcome, sources added,
   what was searched and not found. No prose summaries of the craft.

What the Sanganeri build taught (2026-11-28):
- **File each fact where a reader looks for it.** Community and livelihood facts filed under HISTORY,
  OVERVIEW or MATERIALS left SOCIETY with one fact, so its section was refused (FIELD); the GI's
  protection belongs under POLICY.
- **A section sentence carries nothing beyond its facts.** One sentence that added a publication date,
  a citation and a trend got the whole GEOLOGY section refused (FAITHFUL).
- **Pictures an Admin's own client gives wait for a second reviewer**: the site will not let an
  account decide its own contribution. Prefer the field photographs, and give searched pictures
  only where nothing of the craft's own exists.
- **Check the library before building**: a component that shows what a registered one already
  shows is refused, so place that one by its label instead.

## Pages in other languages

A component's labels are passages too: a step's name, a lane's species, a molecule's name, atoms and
key, a dip's strip label, a lab's and a toggle's choices. Their key is `<component label>#<path>`
(`…/patina-steps#steps.0.name`) and their tag `label`; translate each as a sentence, one text each.
Formulas, numbers, keys and a stage named in its own language are never offered: leave them as the
English page holds them.

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
| find open pictures | `search_sources` with kinds pictures over MCP, with the craft's slug |
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
- **Opus only** (owner, 2026-11-28), for every agent that researches, deepens or builds a page; the
  gates, the verifier, the checker and the preview are the judges, so no critic or judge agents.
- **Stop at about 60 turns** for research and structure, and at about 150 for a page build. Send
  what stands, follow it to its outcome, report the rest as open.
- **Comics**: their panels come only from Gemini or ChatGPT (owner, 2026-11-28). A page agent never
  makes one; the team does, for a page the owner has chosen.
- **Read narrowly**: one field of the exemplar, one reference or contract section, one source page
  at a time. Never read a whole dossier into context when a field will do; never open application
  code.
- **Run nothing else**: no backend or frontend test suites, no builds, no git, no export. The
  lead commits and exports.
- **Never edit code, schemas, other dossiers or the dossiers in git.** A tooling problem is
  reported, not fixed.

## Briefing an agent (the lead)

Give the agent this skill's name, the page (its kind and slug), its `get_page` coverage or gaps output,
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
Channapatna), then the rest of the crafts, then the nine categories. A craft whose open-licence
search finds little may still have field photographs: Sanganeri has 31, taken in Jaipur in June
2026 at 1800 by 2400 px, where searches found almost none of Sanganer itself.

## How this skill is kept true

| What | Kept true by |
|---|---|
| Every tool it sends a change through is one the server offers | `backend/tests/mcp/test_skill_references.py` |
| It names each reference by its repository path and its URI, and its checklist is the shared one | the same test, byte for byte |
| It restates no rule a reference owns and shares no heading with one | the same test |
| The bar's pictures, fields and claims are the gap script's and the server's | `backend/tests/mcp/test_reference_limits.py` |
| Agents find it by its `name` and `description` | the frontmatter above, which the same tests read |

Re-read it when a tool is added or retired, a reference is added, the bar moves, or a kind of
structure stops entering by the dossier route.
