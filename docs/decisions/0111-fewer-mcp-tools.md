# 0111. Twenty-one MCP tools in six groups, with small schemas

The MCP server offers 21 tools in six groups with small schemas, merged at the API layer from the 35
whose `tools/list` the lead measured at 230 KB. Everything that names a tool uses the new names.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21: "Do you think all the MCP tools are justified?
If not, try and optimize and merge them. The ones that are needed, the ones that are not needed need
to be removed"). Amends decisions 0103, 0108 and 0110 where they name tools; their services, gates,
allowances and contracts stand.

| For | Read |
|---|---|
| What amended it | [0114 Component kinds any craft can use, and one dataset record](0114-kinds-and-datasets.md): the MCP tools, which gain a 22nd, `propose_dataset` |
| What built on it | [0117 A page in another language is the same page, translated passage by passage](0117-pages-in-other-languages.md): the MCP tools, at most 22, which gain no tool |
| What it amends | [0103 The MCP server, slice 1: public read tools over our own JSON-RPC framing](0103-mcp-server-read-slice.md): the tools it names; its services and contracts stand |
| What it amends | [0108 An approved structure proposal becomes a curated fact of its dossier](0108-structure-proposals-become-curated-facts.md): the tools it names; its gates and contracts stand |
| What it amends | [0110 Sources a contributor's AI can read and we cannot, and a studio to build a page in](0110-contributor-supplied-sources.md): the tools it names; its services, allowances and contracts stand |
| Every decision, by group | [README.md](README.md) |

## Context

The lead measured the production server: 35 tools, whose `tools/list` was 230 KB (about 57,000
tokens): 22 KB of descriptions, 88 KB of input schemas and 113 KB of output schemas, every tool's
description ending on the same data note. A client may load that list into every conversation, so
each turn of every contributor's agent paid for it before a word was read. Round 7 added seven studio
tools, 42 in all. Many were a single-item copy of a batch tool (`propose_fact` beside `propose_facts`,
`claim_task` beside `claim_tasks`, `give_image` beside `give_images`), halves of one pair
(`adopt_craft` and `drop_craft`, `claim_tasks` and `release_task`, `lookup_compound` and
`lookup_entity`), or parts of one read (`get_coverage`, `get_section`, `get_layout`, `list_fields`
for one page). No outside contributor used the server yet, so the names change now, with no aliases.

## Decision

1. **The set: 21 tools in six groups.** Each tool carries its group in `tools/list` as
   `_meta["kalavigyan/group"]`, so a screen groups the tools without a list of names.

   | Group | Tool | Replaces |
   |---|---|---|
   | reading | `find_crafts` | kept |
   | reading | `get_page {subject?, parts?, field?}` | `get_coverage`, `get_section`, `get_layout`, `list_fields` (no subject: the sixteen fields) |
   | reading | `get_facts`, `list_components`, `ask` | kept |
   | sources | `search_sources {kinds: scholarly, reference, web, pictures}` | `find_pictures` |
   | sources | `read_source {url or doi, around?, start?, quotes?, archive?}` | `check_quote` (each quote's gate verdict), `archive_source` (a Wayback save within the archive allowance) |
   | sources | `lookup {kind compound or entity, name or id}` | `lookup_compound`, `lookup_entity` |
   | sources | `supply_source` | kept |
   | work | `list_open_work`, `get_proposal` | kept |
   | work | `my_work` | `my_tasks`, `my_crafts` |
   | work | `reserve_tasks {claim?, release?}` | `claim_task`, `claim_tasks`, `release_task` |
   | work | `steward_craft {craft_slug, action adopt or drop}` | `adopt_craft`, `drop_craft` |
   | proposing | `propose_facts` (one to 25) | `propose_fact` |
   | proposing | `propose_structure`, `propose_source` | kept |
   | pages | `edit_draft {subject or draft_id, add?, remove?, lists?}` | `create_draft`, `add_to_draft`, `remove_from_draft`, `get_draft` |
   | pages | `preview_page {bundle or draft_id}` | `preview_draft` |
   | pages | `propose_page {bundle or draft_id}`, a bundle of one part too | `submit_draft`, `propose_component`, `propose_layout` |
   | pictures | `give_pictures {pictures: image_url, image_base64 or upload true}` | `start_image_upload`, `give_image`, `give_images` |

2. **Merged at the API layer.** Every merged tool calls the services its old tools called; no
   service is implemented twice. Every behaviour, allowance, gate, idempotency key, trust tier and
   message is kept:
   - `read_source` reads the text only when no quotes and no archive are asked for, or when `around`
     or `start` is named, so a call with quotes alone costs what `check_quote` cost and one with
     archive alone what `archive_source` cost; a step that fails after an earlier one answered is a
     notice, and a first step's failure is the tool error as before.
   - A pictures-only `search_sources` needs only the read scope, as `find_pictures` did: the scope a
     call needs is read from its arguments (`Tool.scope_for`), by the dispatch and by the HTTP
     challenge alike.
   - `propose_page` with a bundle of one part counts against that part's allowance alone, as
     `propose_component` and `propose_layout` did; a draft, or a bundle of more than one part, also
     counts as a page bundle, as before. A component part refused for a close match now carries its
     `matches` and the two `waysOn`, as `propose_component`'s reply did, and over MCP every component
     of a bundle or draft is delivered finished (a spec, but a `SUBJECT_LINK`), as `propose_component`
     required.
   - A spent part's allowance, a refused slot or a refused release is reported on that part (as
     `propose_page` and `claim_tasks` already did) instead of failing the call.
   - `edit_draft`'s first edit opens the account's draft of the page and every later one works on it;
     an edit with nothing to change returns it whole, and a `draft_id` reads one, a proposed one with
     its outcome too. Removals run before additions, facts last and each kind from its highest
     index, so each index is the one the draft listed.
   - `preview_page` stays read-only (`readOnlyHint`), so a client may allow it without asking; the
     preview row it keeps and a draft's last preview are committed by the dispatch
     (`Tool.records`), as `my_work`'s record of a steward's last look is.
   - The camelCase names inside a body keep working for one release and say so, as before.
3. **Small schemas.** `api/mcp_schemas` drops each generated `title` and every `null` default from
   the input schemas and folds a nullable simple type into one `type` list. A page's part schemas
   appear once, in `edit_draft`'s `add` (17 KB); `preview_page` and `propose_page` name a bundle's
   parts and their limits and point to it, while the server still validates the whole bundle, which
   took 32 KB off the list at the first measurement (85 KB of input schemas and descriptions down to
   about 55 KB). A component's spec stays
   an object, validated on the server by its kind's spec model, and each kind's JSON schema is a
   resource, `kalavigyan://components/<kind>.schema.json` (47 kinds, a template in
   `resources/templates/list`, listed in `kalavigyan://index.md` and named in the components
   reference). The data note is said once, in the server's `instructions`. Output schemas are listed
   only where a client reads the result (the reading tools, `ask` and `preview_page`) and are compact:
   the top-level fields and their types. `tests/mcp/test_tool_budget.py` fails when the list passes 22
   tools, 60 KB of input schemas and descriptions, or 120 KB in all.
4. **Everything that names a tool says the new names**: the server instructions, the prompts, the
   contributor, curation and datasets skills and the references, `kalavigyan://index.md`, the
   contracts and their served copies, the page preview view, the services' messages that name a
   tool, the release gate's MCP checks and the tests.

## Why nothing else was removed

Each of the 21 does one job no other tool does, and each is reached by a prompt or a contract:
`find_crafts` is how every agent learns a slug; `get_facts` is the cited claims a reader may see,
which no page part returns; `list_components` is the library search that keeps components from being
copied; `ask` is the only path to a finished answer in the person's name; `supply_source` is the only
way a paywalled or held source reaches the gates; `list_open_work` and `my_work` are the shared queue
and one account's view of it; `get_proposal` is the only way to follow a queued fact; the three
proposing tools write to three different gates, and `propose_structure` and `propose_source` take
bodies no bundle part replaces for a held fact; the three page tools are the draft, the preview and
the one proposal; `give_pictures` is the only way a person's picture arrives. Merging any of these
would join different scopes, hints or gates in one tool, and a client could no longer allow the
read-only ones without asking.

## Consequences

- Clients see 21 tools instead of 42; the measured list and the budget test hold it there.
- An agent built against the old names gets the unknown-tool error and the index of the new ones.
- The release gate's MCP checks call `get_page` and `propose_facts`; the connect page groups the
  tools by `_meta["kalavigyan/group"]`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
