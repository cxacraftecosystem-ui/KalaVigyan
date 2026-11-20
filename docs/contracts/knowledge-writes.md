# Knowledge writes: proposals, gates, the review switch and limits (decision 0101, items 5, 8, 12, 14)

Every new fact, whatever its origin, is a candidate. It is published only through four automatic
gates, run in order, and the review switch then decides whether it goes live at once or waits for
a Professor or Admin. The same path serves a person on the site, the Knowledge API, an agent on the
MCP server and our own research write-back.

Code: `research/knowledge_writes.py` (the proposal and the reply), `research/candidate_gates.py`
(the pure gate decisions), `research/candidate_judge.py` (the judge's prompts, schemas and reply
rules), `research/review_switch.py` (the switch and where a fact is placed);
`services/candidate_sources.py` (fetching and grading the sources), `services/candidate_store.py`
(the subject's held facts), `services/candidate_gates.py` (running the gates with the adapters),
`services/candidate_writes.py` (the stored outcomes and sources differ),
`services/proposal_writes.py` and `services/fact_proposals.py` (`propose_fact`),
`services/write_back_gates.py` (the research write-back), `services/app_settings.py` (the switch
setting); `api/routes/knowledge_writes.py`, `api/mcp_fact_tools.py`, `api/proposal_deps.py`; the
limits `core/rate_limit.py` and `api/proposal_limits.py`; layout proposals `research/layout_proposals.py`,
`services/page_layout_proposals.py`, `services/review_queue_layouts.py`, `api/mcp_layout_tools.py`,
`models/layout_proposals.py`; structure proposals `research/structure_proposals.py` (the contract),
`research/structure_proposals_values.py` (the STATED check), `services/structure_proposals.py` (the
proposal), `services/structure_proposals_dossier.py` (the dossier's own rules),
`services/structure_proposals_page.py` (where an item lands on the page index),
`services/structure_proposals_write.py` and `services/structure_proposals_claims.py` (what approval
writes), `services/structure_proposals_review.py` (approve, reject), `api/routes/structure_proposals.py`,
`api/mcp_structure_tools.py`, `api/structure_proposal_deps.py`, `models/structure_proposals.py`.

## Who may do what

| Action | Capability | Roles |
|---|---|---|
| Propose a fact (`POST /api/knowledge/facts`, MCP `propose_fact`) | `PROPOSE_KNOWLEDGE` | Researcher and above |
| Propose a page layout (`POST /api/knowledge/layouts`, MCP `propose_layout`) | `PROPOSE_KNOWLEDGE` | Researcher and above |
| Propose page structure (`POST /api/knowledge/structure`, MCP `propose_structure`) | `PROPOSE_KNOWLEDGE` | Researcher and above |
| Read and set the review switch (`/api/knowledge/review-switch`) | `REVIEW_CONTRIBUTIONS` | Admin, Master Admin |

The MCP tools also need a signed-in connection holding the `contribute` scope
(`core/mcp_scopes.CONTRIBUTE_SCOPE`); without it the call is challenged (`mcp-oauth.md`) or answered
with a tool error naming the scope. The site's routes ask for the contribution terms first.

## The proposal (`FactProposal`, schema version 1, camelCase on the wire)

- `subject {kind: craft | category, slug}`: a craft by its slug (merged crafts follow their merge)
  or a category by its slug.
- `field`: one of the 16 fields (`list_fields`); `fields`: up to 3 secondary fields, distinct and
  without the primary one.
- `statement`: 20 to 1,000 characters, one fact, no personal data (emails, phone and
  Aadhaar-like numbers are refused).
- `sources`: 1 to 5, each named once (by canonical URL): `{url (https), title, licence?, quotes:
  [{text (at most 300 characters), locator?}] (1 to 6, each once)}`.
- `taskKey` (optional): the open-work task the proposer claimed for this fact
  (`docs/contracts/open-work.md`). It must be a field or corroboration task (`MISSING_FIELD`,
  `THIN_FIELD`, `SECOND_SOURCE`, `SOURCES_DIFFER`) of the same page (a craft subject takes a craft or
  family key, a category a category key) and name the primary field or a secondary one
  (`SECOND_SOURCE` and `SOURCES_DIFFER` may name none); otherwise the proposal is malformed
  (`research/knowledge_writes.fact_task_problem`). Once the gates have run, a fact that passed
  (published or waiting for review) ends the proposer's live reservation of that key `COMPLETED`, and a
  refused one gives it back (`RELEASED`, or `EXPIRED` past its time), so the task returns to the list
  (`services/task_reservations.complete_task`, `give_back_task`). Another account's reservation is
  never touched, and without a reservation nothing changes.

A malformed proposal is refused before any gate (422 on the site; a tool error on MCP).

## The gates, in order

A refusal stops the run; every gate that ran is stored as one `CandidateCheck` row
(`claimId, gate, passed, reasons[], relatedClaimIds[], model, checkedAt`, one per claim and gate).

1. **QUOTES.** Every source is fetched by our fetcher (`research/fetcher.Fetcher`, the same one
   live research uses) and every quote must be found verbatim in the fetched text
   (`research/quotes.quote_occurs`: NFKC, typographic dashes and quotes, line-break hyphens and
   whitespace folded) and be at least 20 characters. Every number or formula in the statement
   must appear in one of its quotes. A page that is refused (robots, size, type), missing or
   blank refuses its quotes with the reason. When our fetcher itself is down nothing is stored
   and the caller is asked to try again (503, or a tool error).
2. **SOURCE.** Each source is graded: a source already stored keeps its own reliability; a newly
   fetched page takes the grade the research pipeline gives a web page (C). A fact resting only on
   D sources is refused, except an ECONOMICS fact stating a price (the curation rule). A source
   stored as RESTRICTED is refused. A licence declared open (CC BY, CC0, public domain) that the
   page itself contradicts is refused. Otherwise the licence passes and is recorded; it decides
   only whether quotes are public: a fetched page's full text is stored for researchers
   (`chunk_acl`), so its quotes are withheld from public views and exports.
3. **DUPLICATE.** The statement is embedded in the stored document form and compared with the
   subject's held facts in the field (primary or secondary): shown or waiting statuses (`DRAFT`,
   `PROPOSED`, `IN_REVIEW`, `APPROVED`), open sensitivity. The same statement once case and final
   stops are folded is refused at once. Otherwise the 8 nearest held facts at cosine similarity
   0.8 or more go to the judge (the structured model, `EVAL_JUDGE`), which names each pair SAME,
   DIFFERS or DISTINCT with a reason. SAME refuses; DIFFERS passes and is kept as sources differ,
   never resolved; DISTINCT passes. Held facts without a vector are found only by the identical
   text.
4. **NOVELTY.** The judge decides whether the fact adds to or changes what the section says,
   against the subject's 12 nearest held facts in the field, and its reason is stored. A fact that
   differs from a held fact passes without the judge (it changes the section), and so does the
   first fact of a field. A refusal names the held facts that already say it.

The subject's facts are the craft's (its own concepts and its sub-category's), or a category's
(its curated claims and the shared concepts named for it). All text sent to the judge is quoted
data in `untrusted_source` blocks.

## The review switch

One admin setting, `knowledge.review_switch`, per origin:

| Origin | Who | Default |
|---|---|---|
| `RESEARCH` | the research write-back of answers and coverage enrichment | `AUTO` |
| `CONTRIBUTION` | the site and the Knowledge API | `APPROVAL` |
| `AGENT` | the MCP server | `APPROVAL` |

| Case | Claim status | Shown | In the review queue | Reply `outcome` |
|---|---|---|---|---|
| Passed, `AUTO` | `IN_REVIEW` (live, unreviewed) | yes, at its level | yes | `PUBLISHED` |
| Passed, `APPROVAL` | `DRAFT` (hidden) | no | yes | `WAITING` |
| Passed, proposed by a Professor, Admin or Master Admin | `APPROVED` | yes | no | `PUBLISHED`, `approvedAtOnce` |
| Refused at a gate | `REJECTED`, kept only for audit | no | no | `REFUSED` |

- The proposer's role is read from their account row at the moment of the write, never from the
  request or the token.
- A quoted fact is stored at `PROVISIONAL`; approval at once does not raise the level (only a
  review does). A fact refused at QUOTES is stored at `HYPOTHESIS`.
- Sources differ: when a differing fact goes live, it and every held fact it differs from get
  `sourcesDiffer`. A waiting fact is flagged when it is approved: the approving review calls
  `services/candidate_writes.mark_sources_differ(session, claim_id)`, which reads the stored
  DUPLICATE outcome.
- Who proposed it is kept privately: `Claim.createdById`, a `ReviewEvent` by the proposer whose
  note names the origin and the placement, and `ClaimSource.foundBy` (`CONTRIBUTION` or `AGENT`).
  A proposed claim's `origin` is `CONTRIBUTION` (`services/proposal_writes.PROPOSAL_CLAIM_ORIGIN`),
  whatever the channel: the channel stays in `ClaimSource.foundBy`. Migration `0044_contributed_origin`
  adds the value and moves the facts proposed before it (`RESEARCHER` claims written by a user with
  candidate checks) to it. The craft page shows a contributed fact with the provenance `RESEARCHER`
  (`services/craft_page.ORIGIN_PROVENANCES`): every proposer is a Researcher or above.
  A newly stored source is marked `origin CONTRIBUTION` with `addedById`.

## Routes

| Route | Body | Answer |
|---|---|---|
| `POST /api/knowledge/facts` | `FactProposal` | 200 `ProposalReply` (origin `CONTRIBUTION`) |
| `POST /api/knowledge/layouts` | `LayoutProposalDraft` | 200 `LayoutProposalResult` (origin `CONTRIBUTION`) |
| `GET /api/knowledge/review-switch` | none | `ReviewSwitchView {current, defaults}`, each `{research, contribution, agent}` of `AUTO` or `APPROVAL` |
| `PUT /api/knowledge/review-switch` | `ReviewSwitchUpdate`, any of `research`, `contribution`, `agent` | `ReviewSwitchView`; audited as `settings.review_switch_updated` |

Refusals: 401 or 403 without the capability or the contribution terms; 422 for a malformed proposal
or an unknown subject; 403 when the proposer's account no longer exists; 409 for a layout built on a
version the page has left; 429 with `Retry-After` when the account's proposal limit is spent; 503
when the fetcher, the embedding route or the judge could not run (nothing is stored).

`ProposalReply {schemaVersion 1, outcome, claimId, status, level, approvedAtOnce, inReviewQueue,
sourcesDiffer, differsFrom[], gates[{gate, passed, reasons[]}], message}`. A refused proposal is
still a 200: the reply's outcome and the failing gate's reasons say why.

## MCP

`propose_fact` (`api/mcp_fact_tools.py`, in `FACT_TOOLS`), scope `contribute`, annotations
`readOnlyHint false`. Arguments `{proposal: FactProposal}`; the result is `ProposalReply` as
structured content. Origin `AGENT`. A missing sign-in, scope or rank, a malformed proposal, a spent
limit or an outage comes back as a tool error the agent can act on. The `research_field` prompt tells
the agent to pass the task key it claimed.

## Proposal limits

Every proposal costs work (a fact a fetch per source, an embedding and up to two judge calls), so each
account has a sliding hour per kind (`core/rate_limit.proposal_attempt`, `PROPOSAL_WINDOW_SECONDS` =
3,600), counted in the API process like the other limits there:

| Kind (`core/rate_limit`) | Per hour (constant) | Counted at |
|---|---|---|
| `FACT_PROPOSALS` | `FACT_PROPOSALS_PER_WINDOW` = 30 | `POST /api/knowledge/facts` (after the terms), MCP `propose_fact` |
| `COMPONENT_PROPOSALS` | `COMPONENT_PROPOSALS_PER_WINDOW` = 10 | `POST /api/contributions/proposals/components`, MCP `propose_component` |
| `LAYOUT_PROPOSALS` | `LAYOUT_PROPOSALS_PER_WINDOW` = 10 | `POST /api/knowledge/layouts` (after the terms), MCP `propose_layout` |
| `STRUCTURE_PROPOSALS` | `STRUCTURE_PROPOSALS_PER_WINDOW` = 20 | `POST /api/knowledge/structure` (after the terms), MCP `propose_structure` |
| `IMAGE_UPLOADS` | `IMAGE_UPLOADS_PER_WINDOW` = 20 | `POST /api/contributions/images` (a picture declared on the site), MCP `start_image_upload` (a link and slot issued; the picture given through it is not counted again) |

- Admins and Master Admins are never limited. A proposal refused at a gate still counts. A request
  without the capability never counts; on the Knowledge API routes and over MCP neither does a
  malformed body or missing terms, while the site's component and picture routes count a request once
  the capability is checked, before its body.
- On HTTP a spent limit is 429 with `Retry-After` (whole seconds) and a detail such as "This account
  made 30 fact proposals in the last hour, the most one account may. Try again in 12 minutes."; over
  MCP the same sentence is a tool error (`api/proposal_limits.py`: `proposal_limit` for routes,
  `refuse_tool_when_spent` for tools).

## Layout proposals (decision 0101, item 14)

A page layout (`docs/contracts/page-layout.md`) can be proposed by anyone who may propose facts; it
waits in the review queue as kind `LAYOUTS`, and an Admin's approval writes it as the page's next
version.

- `LayoutProposalDraft` (schema version 1, camelCase): `subject {kind craft | family | category,
  slug}`, `baseVersion` (the version the proposer read, 0 when the page has none), `entries[]` (the
  whole layout, each a `PageLayoutEntry`, checked by the layout rules), `note?` (1 to 500 characters,
  why). MCP `propose_layout` (`api/mcp_layout_tools.py`, scope `contribute`, a write) takes
  `{proposal: LayoutProposalDraft}`, origin `AGENT`; the route's origin is `CONTRIBUTION`.
- `services/page_layout_proposals.propose_layout`: the subject is found as `get_layout` finds it (a
  family asked for as a craft is refused like an unknown slug: 422, or a tool error); a `baseVersion`
  that is not the page's current version is refused (`Refused("stale_layout")`: 409, or a tool error
  naming the current version). An account that reviews layouts (`REVIEW_CONTRIBUTIONS`, Admin and
  above) has its proposal written at once through `page_layouts.store_layout` (audited
  `PAGE_LAYOUT_WRITTEN`) and recorded `APPROVED` with the version; everyone else's waits `PENDING`.
- `LayoutProposalResult {schemaVersion 1, outcome STORED | WRITTEN, proposalId, status, subject,
  baseVersion, version (the written version, null while waiting), pageUrl, message}`.
- Table `LayoutProposal` (migration `0044_contributed_origin`): `proposerId`, `subjectKind`,
  `craftId` or `categoryId` (exactly one, matching the kind), `baseVersion`, `entries` (JSONB),
  `note`, `origin` (`CONTRIBUTION`, `AGENT`), `status` (`PENDING`, `APPROVED`, `REJECTED`),
  `reviewedById`, `reviewedAt`, `reviewNote`, `layoutVersion` (set exactly when approved), with row
  level security on and no grants to the public roles. Who proposed it is kept for moderation only.
- Review (`review-queue.md`): approving writes the next version through `store_layout` as the
  reviewer (audited `PAGE_LAYOUT_WRITTEN` and `review.layout_approved`) while the page is still at
  `baseVersion`, else 409 and the proposal can only be rejected; rejecting keeps the reason
  (`review.layout_rejected`).

## Structure proposals (round 6; debt "Structure still enters by bulk import")

The parts of a curated craft or family page that are not plain facts can be proposed one at a time,
each with the fact that states it, and pass the same gates; they wait in the review queue as kind
`STRUCTURE`, and approval writes them into the page index (`CuratedCraft.page`) and the rows the craft
page, the generated documents and the dossier export read. A craft without a curated page is refused
(422): its structure arrives with its first dossier.

`StructureProposal` (schema version 1, camelCase): `subject {kind craft, slug}` (a craft or family by
slug, merges followed), `item` (one of the kinds below, by `kind`), `field`, `statement` (20 characters
and up, at most 600 because it becomes a dossier sentence; no personal data), `sources` (1 to 5, each
named once: `{url, title, licence?, language (a language tag such as en or gu-Gujr), quotes [{text,
locator}]}`, every quote with its locator), `taskKey?` (a field or corroboration task of the same page
naming `field`, as for a fact), `note?` (1 to 500 characters). A `CONFLICT` item gives no field,
statement, sources or task.

| Item `kind` | Parts | The fact is about |
|---|---|---|
| `STAGE_AFTER` | `stageKey`, `text` (at most 120), `colours` (up to 3 colour words) | the stage's concept |
| `STAGE_WHY` | `stageKey`; `field` one of the dossier's why fields (CHEMISTRY, MATERIALS, PHYSICS, BOTANY, PROCESS) | the stage's concept |
| `NATIVE_NAME` | `text`, `language`, `script?` (ISO 15924) | the craft's concept for `field` |
| `REACTION` | `reactionKind`, `stageKey?`, `reactants` and `products` (1 to 8 `{name, formula?}`) | the stage's concept, else the craft's |
| `BOTANICAL_NAME` | `materialKey`, `botanicalName` | the material's concept |
| `GLOSSARY_TERM` | `term`, `meaning` (at most 600), `language?`, `script?` | a new term concept under the next `W` key |
| `CONFLICT` | `about`, `claimIds` (2 to 6 facts of the page's dossier) | none: no new fact |
| `OPEN_QUESTION` | `question`, `settledBy?` | the craft's concept for `field` |
| `GI_RECORD` | any of `applicationNumber`, `certificateNumber`, `filedOn`, `registeredOn`, `journalIssue`, `proprietors`, `authorisedUserCount` (at least one) | the craft's concept for `field` |

**Refused before any check (422, or a tool error):** a malformed body; an unknown craft or one with no
curated page; an item the dossier's own models refuse (`services/structure_proposals_dossier.py` builds
the dossier part: language and script patterns, sentence and name lengths, the why fields); an item that
does not fit the page (`structure_proposals_page.target_problem`): an unknown stage or material, a native
name the page already gives in that language, a glossary term or an open question it already holds, a
conflict naming a fact outside the page's claim order or one it already shows.

**Checks, in order** (`StructureCheck {check, passed, reasons[]}`; a refusal stops the run):

1. `STATED`: every name, colour and number the item gives is in one of the proposal's own quotes (case
   folded, whole words): the native name, the term, the botanical name, each reactant and product by
   name or formula, each colour word, and of a GI record its numbers, journal issue, proprietors, the
   count of authorised users and the year of each date. Nothing is fetched when it fails.
2. `QUOTES` and 3. `SOURCE`: the fact gates of the same name, on the statement and the sources.

The duplicate and novelty gates do not run: the item, not the sentence, is what is new. A `CONFLICT`
has no checks.

**Placement.** Passed: the fetched pages are kept (`keep_document`, a new page marked `CONTRIBUTION`
with the proposer) and the proposal is stored `PENDING`, or written at once (`APPROVED`) when the
proposer is a Professor, Admin or Master Admin (the role read from the account row). Refused: stored
`REFUSED` with its checks for audit, nothing kept. A claimed task is completed when the checks pass and
given back when they refuse, as for a fact.

**Approval** (`services/structure_proposals_write.write_structure`, the page row locked) re-checks that
the item still fits the page (409 otherwise, and the proposal can only be rejected), then:

- the fact becomes a curated fact of the dossier: claim id `curated_id(slug, C<next>)` (the next key
  after the craft's highest `C` key, three digits), `APPROVED` at `PROVISIONAL`, origin `CONTRIBUTION`,
  `createdById` the proposer, a `CuratedClaim` marker with the key and field, one `CandidateCheck` per
  QUOTES and SOURCE outcome, a `ReviewEvent` by the reviewer, and its place at the end of the page's
  claim order;
- each quote is a `ClaimSource` found by `curation` (the dossier's own citation; the channel stays on
  the proposal's `origin`), id `claim_source_id(slug, key, S<key>, quote)`, from a source the dossier
  keeps: one it already keeps by that address, else the kept page marked `externalIds.curation
  <slug>:S<next>` with the proposal's language and access `OPEN`, else, when another dossier keeps the
  page, a copy row `curated_id(slug, S<next>)` (refused with 409 when that page is named by its DOI);
- the item joins the page index under the next key of its letter (`R`, `W`, `O`, two digits): a stage's
  `after` or `whyClaimId` (replacing what was there), a native name, a reaction (no stored science row),
  a botanical name with its fact added to the material's, a glossary term (no shared glossary entry), a
  conflict (both facts marked `sourcesDiffer`), an open question; a GI record writes `CraftGiRecord`
  (the parts given replace, proprietors and facts are added); a concept missing for the fact is created
  as the import would (`curation:<slug>:craft:<FIELD>` or `curation:<slug>:W<nn>`);
- the proposal is `APPROVED` with the reviewer, the time, the note and `claimId`, audited
  `review.structure_approved`; a rejection keeps the reason, audited `review.structure_rejected`.

Exporting the dossier afterwards gives the new fact, its quote and its source under their keys, and the
item under its key (`tests/db/test_structure_export_db.py`); importing that export again moves the
fact's quotes to the dossier's own source rows.

`StructureProposalResult {schemaVersion 1, outcome STORED | WRITTEN | REFUSED, proposalId, status,
kind, subject, claimId, checks[], pageUrl, message}`. A refused proposal is a 200 whose checks say why.

Table `StructureProposal` (migration `0047_structure_proposals`): `proposerId`, `craftId`, `kind`,
`item` (JSONB), `field`, `statement`, `sources` (JSONB: each with its quotes, language and the kept
`sourceId`), `checks` (JSONB), `taskKey`, `note`, `origin` (`CONTRIBUTION`, `AGENT`), `status`
(`PENDING`, `APPROVED`, `REJECTED`, `REFUSED`), `reviewedById`, `reviewedAt`, `reviewNote`, `claimId`,
row level security on and no grants to the public roles.

| Route | Body | Answer |
|---|---|---|
| `POST /api/knowledge/structure` | `StructureProposal` | 200 `StructureProposalResult` (origin `CONTRIBUTION`); 401 or 403 without the capability or the terms; 422 malformed; 409 when an at-once write meets a moved page or a source named by DOI elsewhere; 429 when the limit is spent; 503 when the fetcher could not run |

MCP `propose_structure` (`api/mcp_structure_tools.py`, in `STRUCTURE_TOOLS`), scope `contribute`,
`readOnlyHint false`, arguments `{proposal: StructureProposal}`, origin `AGENT`; refusals are tool
errors. Approving a structure proposal, at once or from the queue, refreshes the craft's signed-out
pages (`review-queue.md`, Refreshing signed-out pages).

## The research write-back

`services/research_write_back.store_live_research(..., judge=None)` runs each new claim (one
whose dedupe id is not yet stored) through the same gates with origin `RESEARCH`, using the
documents the research already fetched for gate 1 and the evidence items' grades and licences
for gate 2. A claim already held is re-found as before (new citations, a level raised from
hypothesis), with no gates. A refused claim is not written: the write-back's `skipped` list
carries the gate and its first reason, and when the duplicate or novelty gate named held facts the
answer's sentence cites the first of them instead. A written claim's checks and its vector are
stored; its status follows the switch for `RESEARCH`.

Without a judge (the default until the callers pass one), the duplicate gate refuses only
identical texts and records that no judge compared the close facts, and the novelty gate is
recorded only when it needs no judge. When the embedding route or the judge fails, the write-back
falls back to the identical-text check and logs it; it never fails the answer.

## Versioning

`FactProposal` and `ProposalReply` carry `schemaVersion 1`. A change that removes or renames a
field, or changes its meaning, is a new schema version.
