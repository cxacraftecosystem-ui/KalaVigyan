# Open work, reservations, component proposals and the method on the MCP server

Decision 0101's Knowledge API and MCP server: item 15 "Open work" and "The method travels with
the server", and item 16's `propose_component`. The endpoint, framing and read tools are in
`docs/contracts/knowledge-api.md`; `propose_fact`, `propose_layout` and `propose_structure` are in
`knowledge-writes.md`.

## Code

| Part | Where |
|---|---|
| Task contract, keys, filters, reservation constants | `research/open_work.py` |
| Task rules: per subject, review queues, priority, order, selection | `research/open_work_tasks.py` |
| Task wording (what is needed, acceptance) | `research/open_work_texts.py` |
| Source link rule (dead, unarchived) | `research/open_work_links.py` |
| Healing work: held, failing and rotting facts per subject, and their wording | `services/open_work_healing.py`, `services/open_work_healing_texts.py`, over `services/claim_holds.py` and `services/upkeep_links.py` |
| `propose_source` | `research/source_proposals.py`, `services/source_proposals.py`, `api/mcp_source_tools.py` (`SOURCE_TOOLS`) |
| Component proposal contract and the close-match rule | `research/component_proposals.py` |
| Subjects and filters | `services/open_work_subjects.py`; the family rule is `data/curation_scopes.is_family` |
| Facts and sections per field (the field coverage) | `services/coverage.py` (`coverage.md`) |
| Counts per subject (one source, sources differ, links, demand) | `services/open_work_counts.py` |
| Component kinds per craft | `services/open_work_components.py`, over the library's one applies-to query (`services/component_library.applies_to`, with `registered_pieces`) |
| The nightly refresh of field work | `services/open_work_refresh.py` |
| Pages in the monograph form | `services/open_work_pages.py`; the folder is `data/monograph_files.MONOGRAPHS_DIR` |
| Listing, standings, review queues, live reservations | `services/open_work.py` |
| Claim, claim several, release, complete | `services/task_reservations.py` |
| My tasks (held, completed, outcomes) | `services/contribution_queue_tasks.py`, contract `research/my_tasks.py` |
| Stewardship | `services/stewardship.py`, contract `research/stewardship.py`, table `CraftSteward` (`models/contributions.py`, migration `0048_contribution_queue`) |
| `propose_component` | `services/component_proposals.py`; the delivered spec `component_proposals_spec.py`, registration `component_proposals_register.py` (`component-specs-general.md`) |
| `propose_page` and `preview_page` | `research/page_proposals.py` (the bundle and its reports), `services/page_proposals.py` with `page_proposals_parts.py`, `services/page_preview.py` with `page_preview_parts.py`, `page_preview_additions.py` and `page_preview_links.py` |
| Tables | `models/open_work.py` (`TaskReservation`, `ComponentProposal`), migration `0038_open_work`; the delivered spec's columns and `models/page_previews.py` (`PagePreview`), migration `0049_delivered_components` |
| MCP tools | `api/mcp_work_tools.py` (`WORK_TOOLS`), `api/mcp_task_tools.py` (`TASK_TOOLS`), `api/mcp_steward_tools.py` (`STEWARD_TOOLS`) and `api/mcp_page_tools.py` (`PAGE_TOOLS`: `propose_component`, `propose_page`, `preview_page`), registered in `api/mcp_tools.py` |
| MCP prompts and resources | `api/mcp_prompts.py`, `api/mcp_resources.py`, dispatched in `api/mcp_tools.py` |
| HTTP routes | `api/routes/open_work.py`; `api/routes/page_proposals.py` (bundles and previews, `api/page_proposal_deps.py`) |
| The contributor skill | `data/contributor/SKILL.md`, served at `frontend/public/skills/kalavigyan-contributor/SKILL.md` |
| The design tokens resource | `data/design/tokens.json`, written by `tools/design_tokens.py` beside the design skill's `references/tokens.json` |

## Subjects

Every `ACTIVE` craft, and every category. A craft is a **family** when it is a catch-all or is
practised in `All India` only (the rule of `data/curation_scopes`); otherwise it is a **craft**.

## Tasks

`OpenTask {key, kind, priority, subject {kind, slug, name, pageUrl} | null, field, need, needed,
acceptance, count, factIds[], sourceIds[], prompt, reservedUntil}`. `factIds` and `sourceIds` carry
at most 20 ids; `count` is the whole number.

| Kind | When | Key | `count` | Prompt |
|---|---|---|---|---|
| `MISSING_FIELD` | a field holds no cited facts and no section | `MISSING_FIELD:<subject>:<slug>:<FIELD>` | facts wanted | `research_field` |
| `THIN_FIELD` | a field holds facts or a section but fewer facts than the target | `THIN_FIELD:...:<FIELD>` | facts still wanted | `research_field` |
| `SECTION` | a field meets its facts target, but its published section is missing or shorter than the target | `SECTION:...:<FIELD>` | facts held | `write_section` |
| `MISSING_COMPONENT` | a craft or family has no registered component of a need's kinds | `MISSING_COMPONENT:...:<need>` | 0 | `propose_component` |
| `PAGE_FORM` | the page is not in the monograph form | `PAGE_FORM:<subject>:<slug>` | 0 | none |
| `PAGE_LAYOUT` | in the monograph form without a layout | `PAGE_LAYOUT:<subject>:<slug>` | 0 | none |
| `SECOND_SOURCE` | facts cited by one source only, per primary field | `SECOND_SOURCE:...[:<FIELD>]` | facts | `research_field` |
| `SOURCES_DIFFER` | facts marked sources differ, per primary field | `SOURCES_DIFFER:...[:<FIELD>]` | facts | `research_field` |
| `DEAD_SOURCE` | cited sources with no archive whose last fetch answered 404 or 410 | `DEAD_SOURCE:<subject>:<slug>` | sources | `research_field` |
| `UNARCHIVED_SOURCE` | cited sources with a link and no archive, not dead | `UNARCHIVED_SOURCE:<subject>:<slug>` | sources | `research_field` |
| `RESOURCE_FACT` | facts held from the page because none of their quotes is found any more, per primary field | `RESOURCE_FACT:...[:<FIELD>]` | facts | none (`propose_source`) |
| `CORROBORATE_FACT` | shown facts with a quote that failed and another that holds, per primary field | `CORROBORATE_FACT:...[:<FIELD>]` | facts | none (`propose_source`) |
| `FIND_ANOTHER_SOURCE` | shown facts resting only on rotten sources (`nightly-upkeep.md`, 1a); `factIds` the facts, `sourceIds` the sources | `FIND_ANOTHER_SOURCE:<subject>:<slug>` | facts | none (`propose_source`) |
| `REVIEW` | a review queue holds items, shown to its reviewers only | `REVIEW:<QUEUE>` | items waiting | none |

`<subject>` is `craft`, `family` or `category`. A fact with no primary field gives a key without
the field part.

**Targets** are the curation targets (`curation/limits.py`, the contract's Coverage table): a field
wants `DISCIPLINE_CLAIMS_MIN` (3) facts and a section of `SECTION_SENTENCES_MIN` (3) sentences;
every one of the 16 fields is a core field of every craft, family and category (owner, 2026-11-20:
a missing field is research, not a hole), so each field without cited facts is a `MISSING_FIELD`
task and each under 3 a `THIN_FIELD` task; quotes are 25 to 300 characters.

**What is counted.**
- Facts and sections per field are the field coverage (`coverage.md`): cited claims shown on the
  page, a craft's those about its open concepts, a category's those its dossier links
  (`CuratedCategoryClaim`), under the primary field and each secondary field, with the communities'
  claims counted for `SOCIETY` and the GI record's for `POLICY`; the `PUBLISHED` `ArticleSection`
  per field and its sentence count.
- One source: distinct `ClaimSource.sourceId` equal to 1. Sources differ: `Claim.sourcesDiffer`.
- Sources with a link: an archive is a stored snapshot (`Source.snapshotKey`) or a curated
  `externalIds.archivedUrl`; dead is the latest `WebFetch` of the link answering 404 or 410.
- Held facts (every cited quote `FAIL`, `services/claim_holds.held_claim`) are left out of every count
  above, the field coverage among them: a held fact is research, not a fact the page shows. They are
  counted for `RESOURCE_FACT`. Failing facts (a `FAIL` quote, not held) for `CORROBORATE_FACT`. Rotten
  sources (`SourceUpkeep.failures` at least 3, no archive of any kind) for `FIND_ANOTHER_SOURCE`, over
  the facts that cite nothing else.
- Components: registered pieces (a label, not hidden, not superseded) of the craft, linked to it, or
  keyed to its concepts (its own, its stages', its materials'), its materials' compounds or its
  districts, as the library search reaches them. Needs and the kinds that meet them:

| Need | Kinds |
|---|---|
| `what-if` | `what_if` |
| `molecules` | `molecule_3d` |
| `map` | `map_layer`, `region_story`, `timeline_map`, `supply_map`, `map_sequence` |
| `reaction-player` | `reaction_player`, `indigo_vat`, `mordant_bath`, `lost_wax`, `firing`, `dip_player` |
| `pictures` | `images`, `picture_plate`, `specimen_plate` |

  A category has no component tasks: the registry keys components to crafts, concepts, places and
  compounds, never to a category.
- Monograph form: a folder `data/monographs/<slug>` with `content.json`; a layout is a non-empty
  `layout` in it. Only `Kutch-Ajrakh` is in the form.
- Review queues and who sees them: `FACTS` (claims `PROPOSED` or `IN_REVIEW`, and every shown held
  claim; `MARK_CLAIM_LEVEL`, Professor and above), `TESTIMONY` (pending artisans' testimony; `REVIEW_TESTIMONY`), `IMAGES`
  (pending pictures; `REVIEW_CONTRIBUTIONS`, Admin and above), `COMPONENTS` (pending component
  proposals; `REVIEW_CONTRIBUTIONS`), `LAYOUTS` (pending page layout proposals;
  `REVIEW_CONTRIBUTIONS`), `STRUCTURE` (pending page structure proposals; `MARK_CLAIM_LEVEL`,
  Professor and above). Queues are listed only without a subject filter.

**Priority** per subject, then ordered:
- `HIGH`: on the owner's first list (`kalavigyan-craft-pages` skill, "Order": Bidriware, Blue Pottery
  of Jaipur, Kutch Bandhani, Machilipatnam Kalamkari, Madhubani, Orissa Pattachitra, Bastar Dhokra,
  Channapatna), or 25 or more stored answers about the craft. Every review queue is `HIGH`.
- `MEDIUM`: GI-registered (`Craft.giStatus` `GI`), curated (a `CuratedCraft` or `CuratedCategory`
  row), or 5 or more stored answers.
- `LOW`: every other craft and family, and every category.
- Order (the subject's prominence): priority; then the owner's list order; GI before not; curated
  before not; then reader demand, most first; crafts, families, categories; name. Within a subject:
  healing first (re-source, corroborate, find another source; fields in vocabulary order), then
  fields in vocabulary order, components, page, corroboration, links. A page that lost a fact is
  the first repair of its subject. Review queues lead the `HIGH` tasks.
- **The nightly upkeep** (`services/open_work_refresh.refresh_field_work`, the `fieldWork` part of
  its report) counts every open `MISSING_FIELD` and `THIN_FIELD` task by kind and priority and ends,
  as `COMPLETED`, each live reservation of a field task that is no longer open (its field was filled
  by an import or another way). Tasks themselves are computed on every call, so they are never
  stale.

**Filters**: `craftSlug` (one craft; a family's slug is refused), `familySlug` (the family's page
and the crafts sharing its sub-category), `categorySlug` (the category's page and its crafts and
families), at most one of the three; `field`; `kind`; `priority`; `limit` 1 to 200, default 50.
`OpenWork {schemaVersion 1, filters, total, reservationMinutes, tasks[]}`: `total` counts every
matching task before the limit.

A task reserved by another account is left out until its reservation ends; the caller's own carry
`reservedUntil`. A `MISSING_COMPONENT` task is closed while a `PENDING` or `APPROVED` proposal names
its key.

## Reservations (`TaskReservation`)

- `claim_task` reserves an open task for 2 hours; claiming it again renews it from now. The key must
  name a task open now (computed for its subject) and not closed by a proposal; a review queue is
  never reserved. How many live reservations one account holds at once is set by its trust tier
  (`knowledge-writes.md`, Trust tiers: `NEW` 5, `ESTABLISHED` 10, `PROVEN` 20; Professors and above
  20); the refusal names the tier. The reservation length (2 hours) and renewal are unchanged.
- `claim_tasks` claims up to 10 keys in one call, each in its own savepoint: a key taken, closed or
  over the cap is refused with its reason and the rest are held (`TaskClaims {schemaVersion 1,
  held[TaskHold], refused[{taskKey, problem}], tier, holding, holdingMax, message, notices[]}`).
- A live reservation of another account refuses the claim with its end. An expired one is ended
  (`EXPIRED`, at its expiry) by the next claim, and the task returns to the list by itself.
- `release_task` ends the caller's own reservation (`RELEASED`, or `EXPIRED` once past its time).
- A `propose_component` naming its `task_key` ends the proposer's reservation `COMPLETED`.
- A `propose_fact` (or `POST /api/knowledge/facts`) naming a field or corroboration task as its
  `taskKey` ends the proposer's reservation `COMPLETED` once the fact passes the gates (published or
  waiting for review), and gives it back (`RELEASED`) when the fact is refused, so the task returns
  to the list (`knowledge-writes.md`). The `research_field` prompt asks the agent to pass it.
- A `propose_source` naming a `RESOURCE_FACT`, `CORROBORATE_FACT`, `FIND_ANOTHER_SOURCE`,
  `SECOND_SOURCE` or `DEAD_SOURCE` task ends the proposer's reservation `COMPLETED` when its quotes
  pass and gives it back when they refuse; the task must be open and list the fact (or one of its
  sources, for `DEAD_SOURCE`), or list more than it shows (`knowledge-writes.md`, Source proposals).
- A `propose_structure` (or `POST /api/knowledge/structure`) naming a field or corroboration task of
  its page and field ends the proposer's reservation `COMPLETED` once its checks pass, and gives it
  back when they refuse (`knowledge-writes.md`, Structure proposals).
- One live reservation per key: a partial unique index on `taskKey` where `endedAt` is null.
  `userId` is kept for the reservation only and never shown to another account.

## Component proposals (`ComponentProposal`)

Arguments: `label` (`<craft-or-shared>/<field>/<name>`, the registry's pattern), `title`,
`description` (40 to 600 characters, written for a model), `kind` (a piece kind), `field`,
`fields[]`, `craft_slug?` (the owning craft; none for a shared component), `subjects[{kind, key}]`
(1 to 20: a craft by slug, a concept or compound by id, a place by `lgd:<code>` or `basin:<id>`),
`considered_labels[]` (registered labels only), `extends?` with `extension` (`SUBJECT_LINK` keeps the
extended label; `VARIANT` takes a new one), `task_key?`, and the delivery: `spec` (the kind's spec
data, any of the 42 kinds or a general kind) and `units` (`{u0001: {text, claimIds}}`), required on
MCP except for a `SUBJECT_LINK`, which carries none (`component-specs-general.md`).

- Checks, failing with a sentence the agent can act on: a `task_key` names a `MISSING_COMPONENT`
  task whose need the proposal's kind meets and whose craft the proposal is keyed to (so a proposal
  never closes another task); every considered or extended label is registered; every subject exists
  (a concept must be open); no live proposal holds the label (a subject link excepted, and a
  concurrent duplicate is refused by the partial unique index on `label`).
- **The library search**: `component_library.library_components` on the title and description, and
  for the owning craft and each craft subject with the proposal's kind, plus the registered piece
  holding the same label.
- **A close match**, any of: the same label; the same kind keyed to the same concept, compound or
  place; the same kind with titles sharing half their content words or more; a title and
  description sharing 60 % of their content words or more (words of three letters or more, common
  words dropped, overlap as shared over all). The extended component is never its own match.
- A close match returns `{outcome REFUSED, matches[{component, reasons[]}], waysOn[2]}` and stores
  nothing. The two ways on: place the existing component by its label, or propose an extension (a
  new subject link or a variant). Never a copy.
- A delivery is then checked (`component-specs-general.md`, The checks): the spec against its
  kind's model, its units against the spec, every cited fact stored and shown, every number a unit
  states in its facts. A refusal names every problem in one sentence and stores nothing.
- Otherwise it is stored: `PENDING` for review by an Admin, or `APPROVED` at once when the account
  is a Professor, Admin or Master Admin (decision 0101 item 12, the role read from the signed-in
  account). The proposer is kept in `proposerId` for moderation only and never shown (item 13).
- **Approval registers it** (no builder step): a delivered component becomes a `KnowledgePiece` of
  the library that every page it applies to draws from its spec, and a `SUBJECT_LINK` keys the
  registered component to its new subjects; approved at once means registered at once. A proposal
  without a spec (the site's form) is approved for a builder as before.

## MCP

Last reviewed: 2026-11-20 (round 7: delivered components and pages).

| Tool | Scope | Hints | Returns |
|---|---|---|---|
| `list_open_work` | read | read-only | `OpenWork` |
| `claim_task` | contribute | writes | `TaskHold {schemaVersion, taskKey, held, reservedUntil, task}` |
| `release_task` | contribute | writes | `TaskHold` with `held` false |
| `claim_tasks` | contribute | writes | `TaskClaims` |
| `my_tasks` | contribute | read-only | `MyTasks {schemaVersion 1, tier, holding, holdingMax, reservationMinutes, claimed[{taskKey, reservedUntil, task (OpenTask, or null once closed)}], completed[{taskKey, ending COMPLETED, endedAt}] (the last 30 days, at most 50), outcomes[ProposalTicket] (the latest 20)}` |
| `adopt_craft` | contribute | writes | `StewardPackage` |
| `drop_craft` | contribute | writes | `Stewardship {schemaVersion 1, craftSlug, adopted false, message}` |
| `my_crafts` | contribute | writes (records what was seen) | `MyCrafts {schemaVersion 1, crafts[StewardPackage], adopted, adoptedMax, message}` |
| `propose_component` | contribute | writes | `ComponentProposalResult {schemaVersion, outcome, proposalId, status, label, message, matches, waysOn}` |
| `propose_source` | contribute | writes | `SourceProposalReply {schemaVersion, outcome, claimId, quotesAdded, held, gates, message}` |
| `propose_page` | contribute | writes | `PageProposalResult {schemaVersion, subject, pageUrl, accepted, refused, parts[], message}` |
| `preview_page` | contribute | writes (a preview, never a proposal) | `PagePreviewResult {schemaVersion, subject, pageUrl, previewUrl, expiresAt, chapters[], components, sources, parts[], message}` |

The three page tools need an account of Researcher or above (`PROPOSE_KNOWLEDGE`).

- A write tool's changes are committed by the dispatch when it succeeds and rolled back when it
  refuses (`InvalidInput` or `Refused`, both a tool result with `isError`).
- Review queues reach `list_open_work` only on a connection holding the review scope, and then by
  the account's role.
- `initialize` declares `tools`, `prompts` (`listChanged` false) and `resources` (`subscribe` and
  `listChanged` false).
- `prompts/list` and `prompts/get` (`api/mcp_prompts.py`, steps in `api/mcp_prompt_steps.py`):
  `research_field {craft_slug, field}`, `write_section {craft_slug, field}`, `propose_component
  {craft_slug, need?}`, and (round 7) `deliver_page {subject_kind, slug}` and `give_picture
  {craft_slug}`, the prompt of `MISSING_PICTURE` tasks. Each returns one user message: the task, the
  steps naming the tools in order (`list_open_work`, `claim_task` or `claim_tasks`, `get_facts` and
  `get_section`, `list_components` first for a component, the agent's own search, `propose_facts`
  with idempotency keys and the claimed task as `task_key`, then `get_proposal` or `my_tasks` for
  the outcome; a component or page is built finished and seen with `preview_page` before
  `propose_page` or `propose_component`; a picture is given with `give_image` only after the person
  confirms the declaration in their own words) and the method sections of the contributor skill
  (Proposals and their progress, What counts as a source, Quotes and locators, One fact per
  sentence, The fields, The page checklist, Never; plus Writing a section, Components, Pages,
  Structure and sources or Pictures). A wrong prompt or argument is `-32602`.
- `resources/list`, `resources/read`, `resources/templates/list` (empty):
  `kalavigyan://skills/kalavigyan-contributor/SKILL.md` (`text/markdown`) and
  `kalavigyan://design/tokens.json` (`application/json`). An unknown uri is `-32002`.

## HTTP

- `GET /api/knowledge/open-work?craftSlug&familySlug&categorySlug&field&kind&priority&limit`:
  anyone, counted against the public read limit when signed out; a signed-in reviewer also sees
  the review queues. Wrong filters 422.
- `POST /api/knowledge/open-work/claim` and `/release`, body `{taskKey}`: `PROPOSE_KNOWLEDGE`
  (Researcher and above). A reservation conflict or the held maximum 409, a key that is not open 422.
- `POST /api/knowledge/open-work/claims`, body `{taskKeys}` (1 to 10): `TaskClaims`.
  `GET /api/knowledge/open-work/mine`: `MyTasks`. Both `PROPOSE_KNOWLEDGE`.
- `GET /api/knowledge/stewardship` (`MyCrafts`), `PUT /api/knowledge/stewardship/{slug}` (adopt,
  `StewardPackage`), `DELETE /api/knowledge/stewardship/{slug}` (drop, `Stewardship`):
  `PROPOSE_KNOWLEDGE`; more than 10 crafts 409, a craft not stewarded or not known 422.

## Stewardship (round 7)

A contributor adopts crafts and families (`adopt_craft {craft_slug}`, at most `STEWARD_CRAFTS_MAX` =
10 live at once) and drops them (`drop_craft`). A steward sees each craft's open work as one package:
`StewardPackage {craft (TaskSubject), adoptedAt, seenAt (the steward's last look, null before the
first), stewards (how many accounts steward it; never who), newTasks[OpenTask] (open now and not open
at the last look: the craft's new gaps, first), tasks[OpenTask] (the rest), total}`, the tasks
`list_open_work` gives for the craft (a family with its crafts) to that account, at most 200. Each
look records the keys it showed (`CraftSteward.seenTaskKeys`, `seenAt`), so the next look's new gaps
are those opened since; at adoption every gap is new. Stewardship never reserves a task and never
blocks anyone: other accounts list, claim and complete the craft's tasks as before, and a craft has
any number of stewards. Table `CraftSteward` (`userId`, `craftId`, `adoptedAt`, `droppedAt`,
`seenTaskKeys`, `seenAt`; one live row per account and craft by a partial unique index).

## Pages delivered whole (`propose_page`)

One bundle builds one page: `PageBundle {schemaVersion 1, subject {kind craft, family or category,
slug}, facts[] (each a `propose_fact` proposal, at most 20), structure[] (each a `propose_structure`
proposal, at most 20), components[] ({proposal, cites}, at most 10), layout? ({baseVersion,
entries, note?}), pictures[] ({stageId?, claimIds, declaration?}, at most 10), note?}`, holding at
least one part. A component's `cites` names, per unit, the bundle's facts it rests on besides its
`claimIds`, as `fact:0`, `fact:1` and on (the facts' places in `facts`); a picture's `claimIds` may
name them the same way. A reference beyond the bundle's facts, or to a unit the component lacks, is
an argument error.

Parts run in order (facts, structure, components, layout, pictures), each in its own savepoint and
checked exactly as its own tool checks it: a fact through the gates (`knowledge-writes.md`), a
structure item through its checks, a component through the delivery checks and the library search,
the layout against the page's current version (stored for review, or written at once by an
Admin), and a picture by starting its upload (`start_image_upload`'s link and slot, reported in
the part's `upload`). Each part counts against its own kind's hourly limit. A part is also refused
when it names another page (a fact's or structure item's subject), when a category's bundle carries
structure or pictures, when a component is keyed to another craft (`craft_slug` or a `CRAFT`
subject), or when it cites a bundle fact that was refused. A refused part rolls back only itself:
the others stand, and one report lists every part `{part, index, outcome ACCEPTED or REFUSED,
status, id, message, upload?}` with the counts. A component citing a bundle fact that waits for
review is stored, and its approval waits until that fact is shown. HTTP: `POST
/api/knowledge/pages` (`PROPOSE_KNOWLEDGE`, the contribution terms accepted), 422 for an argument
or subject error.

## Previews before submitting (`preview_page`)

`preview_page` takes the same bundle and assembles the document it would produce, without
proposing anything: the page's generated document (`page-layout.md`) built from the stored page
plus the bundle (`PageAdditions` into `monograph_generated.generated_parts`):

- each fact, and each structure item that states a fact, is one more sentence at the end of its
  field's section, citing its proposed sources (unstored sources, numbered after the page's); a
  conflict is listed only;
- each component is drawn from its delivered spec where the page will draw it once registered;
  the delivery checks run, so a component that would be refused is refused here;
- the layout replaces the page's own as its next version, refused when its base version is stale;
- pictures are listed: they are drawn once uploaded and approved.

No source is fetched, so the gates' verdicts are only known when the bundle is proposed. Each part
reports `SHOWN`, `LISTED` or `REFUSED`. A page with authored content (Kutch Ajrakh) is not
previewed, and a page that would still hold too few published fields to be a monograph (3 for a
craft, 1 for a family or category) is refused with how to grow it.

The document is kept as a `PagePreview` row (`userId`, subject, `document`, `expiresAt` 24 hours
on; an account keeps at most 20 live previews and expired ones are deleted when it previews again)
and reached through a private link, `<site>/preview/<token>`. The token is
`<preview id hex>.<expiry epoch>.<HMAC-SHA256>`, signed for the account with a key derived from the
JWT secret (`page_preview_links.preview_key`); `GET /api/knowledge/pages/previews/{token}` returns
the document only to that signed-in account before it expires (404 otherwise, never saying which),
with `Cache-Control: private, no-store` and `X-Robots-Tag: noindex, nofollow`. HTTP: `POST
/api/knowledge/pages/preview` (`PROPOSE_KNOWLEDGE`). The web route `/preview/<token>`
(`app/(reading)/preview/[token]`) reads it with the reader's session and draws it with
`MonographPage` exactly as the site draws its pages, `noindex`; signed out it sends the reader to
sign in and back, and any other answer is the not-found page.

## The contributor skill

`data/contributor/SKILL.md` is the one copy that is written; `frontend/public/skills/
kalavigyan-contributor/SKILL.md` is served from the site, and `tests/mcp/test_contributor_kit.py`
holds the two byte for byte, the field table equal to the vocabulary, and the tokens resource equal
to the design skill's `tokens.json`. After editing the skill, copy it to its served place; the tokens
are regenerated into both places by `tools/design_tokens.py`.

## Around open work

- Facts and structure proposals close their tasks (above); page layouts are proposed with
  `propose_layout` and wait in the `LAYOUTS` queue, page structure with `propose_structure` in the
  `STRUCTURE` queue (`knowledge-writes.md`).
- Component and layout proposals are decided on the review page, `/admin/review`
  (`review-queue.md`). An approved delivered component is registered in the library at once and
  drawn by every page it applies to; a proposal without a spec still waits for a builder; an
  approved layout is written at once.
- The nightly upkeep re-verifies quotes, archives sources at risk and counts dead links
  (`nightly-upkeep.md`), which feed the `DEAD_SOURCE` and `UNARCHIVED_SOURCE` tasks, and its verdicts
  and failure counts feed the three healing tasks; the site's contribution screens parse the kinds
  in `frontend/lib/ownProposalsContract.ts` (`TASK_KINDS`).
- Proposals are limited per account and hour (`knowledge-writes.md`, Proposal limits).
