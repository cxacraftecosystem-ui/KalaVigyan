# 0193. A contributor withdraws or replaces its own registered component, an Admin's staged removal takes published content off its pages, a borrowed component that cannot pass is refused before it is proposed, and a trusted account's whole page waits for one confirmation

A registered component can now leave the pages that place it, kept in the record, by its own
proposer, a steward of its craft or an Admin, or give way to a better one that takes its place in
every layout; an Admin's AI stages that removal through a general action on published content that
a person confirms; placing a component borrowed from another page is refused at `edit_draft`,
`preview_page` and `propose_page` when its units cite facts the page does not hold; and a whole page
proposed by an account whose proposals reach readers at once is held until the person signed in to
that account presses Confirm once.

Date: 2026-11-24. Status: accepted (the owner, after judging the Sanganeri Hand Block Printing page
built over MCP far below Kutch Ajrakh; the lead's lane brief `lifecycle`, and the lead's note of the
same day that the Admin's removal is a general staged action on published content sharing the
withdrawal's code path). It amends [decision 0101](0101-knowledge-architecture-for-every-craft.md)
(item 8, only what waits can be withdrawn; item 12, a reviewer's own proposal approved at once),
[decision 0110](0110-contributor-supplied-sources.md) (the studio's drafts) and
[decision 0170](0170-review-over-mcp-staged-and-pages-refreshed-now.md) (what an Admin's AI stages).
The contracts are `docs/contracts/open-work.md` (Withdrawn, replaced, borrowed and held),
`docs/contracts/review-queue.md` (Staged over MCP), `docs/contracts/contribution-screens.md`,
`docs/contracts/knowledge-writes.md` (Trust tiers) and `docs/contracts/page-layout.md`.

Amended by [decision 0248](0248-what-the-fresh-agent-could-not-fix-on-sanganeri.md): a borrowed component citing facts the page does not hold is not drawn on the page either.

Amended by [decision 0254](0254-a-preview-refuses-what-the-confirm-refuses-a-layout-names-only-what-exists-and-a-duplicate-shows-the-same-thing.md): a layout placing a label nothing holds, a component its bundle failed to make among them, is refused with the labels named, and every part passes the confirm's own checks, the ones `preview_page` runs, before it writes.

| For | Read |
|---|---|
| Who may withdraw, and the consent rule it amends | [decision 0101](0101-knowledge-architecture-for-every-craft.md), items 8 and 12 |
| Drafts and bundles | [decision 0110](0110-contributor-supplied-sources.md) and [decision 0111](0111-fewer-mcp-tools.md) |
| Staged review and the one-click confirmation | [decision 0170](0170-review-over-mcp-staged-and-pages-refreshed-now.md) |
| Why no tool was added | [decision 0191](0191-room-for-the-page-quality-tools.md) |
| Every other kind's removal and the edit of published content | [decision 0194](0194-an-admin-removes-and-edits-published-content-over-mcp.md) |
| Where a borrowed component's sources are counted | [decision 0106](0106-one-monograph-template-for-every-page.md) |
| A held page refused while its latest preview fails its drawing checks | [decision 0195](0195-a-preview-drawn-seen-and-checked-before-it-is-proposed.md) |
| A steward asks instead of withdrawing or replacing at once, and a withdrawal names its bundle's page | [decision 0212](0212-a-steward-asks-an-admin-a-structure-edit-states-what-it-brings-and-a-removed-layout-stays-removed.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- The agent building Sanganeri wrote: "My earlier plain timeline and dot map stay on the page,
  because I can't remove a registered component. A KalaVigyan admin can hide them. The alizarin 3D
  model and indigo dip player I linked last round cite only Ajrakh's facts, so they now fail two of
  the page's checks." It kept its redesign as a private preview because "proposals from this
  account go live straight away".
- A contributor could withdraw a component only while it waited (`withdraw_component`); once
  registered it stayed, and the only control was the site's hide of a craft-owned piece. A link
  (`SUBJECT_LINK`) or a layout entry could place any library component whatever facts it cited, and
  the preview refused a link outright for carrying no spec. A Professor's or `PROVEN` account's
  page went live part by part as it was proposed.
- Adding a tool would leave the contributor skill naming fewer tools than the server offers, which
  `test_contributor_kit.py` refuses, and the skill is the lead's to merge.

## Decision

1. **One path takes a component off its pages** (`component_lifecycle.take_off_pages`): off every
   page by hiding its piece (`hiddenAt`, `hiddenById`; a proposer's own approved proposal becomes
   `WITHDRAWN`), or off one page by a `KnowledgePieceUnlink` row that the applies-to query and a
   category page's pieces leave out. Either keeps the record and audits `component.removed` with the
   label, the page, the reason and the proposal. Only the proposer, a live steward of its owning
   craft or an Admin may (`component_retirers.may_retire`).
2. **Withdrawing is a part, not a tool.** A contributor withdraws its registered component on the
   site (Withdraw on Your components) or over MCP as a draft's or bundle's `withdrawals[{label,
   reason?}]` (up to 10), checked when added, shown gone in the preview and run last by
   `propose_page`, each counting as a component proposal; the pages it applied to are refreshed. A
   bundle can hold withdrawals alone.
3. **Replacing** is a proposal with `replaces` naming a registered label the proposer may retire;
   the replaced one is never its close match. The change that registers it supersedes the old piece
   and writes the next version of every layout naming the old label with the new one in the same
   entry (`component_layout_swaps`), audited `component.replaced`. A retired piece keeps its label,
   so a new proposal of that label is refused with the reason.
4. **An Admin removes published content through staged review.** `remove` is a staged action on
   `COMPONENTS` (no new kind): it names the registered component (its id, or over MCP its label) and
   optionally the one page (`craft` or `family`), runs `take_off_pages` in the dry run and again when
   a person confirms on the Review page, and stays a removal (a person may change its reason and
   page, not turn it into a queue decision). `research/staged_reviews.PUBLISHED_ACTIONS` and
   `services/staged_published.PUBLISHED_KINDS` are the one place a later kind or action joins.
5. **A borrowed component that cannot pass is refused before it is proposed.** Another craft's
   component, or a shared one, placed by a link or named in a layout, is refused when its units'
   facts include any the page does not hold (the craft's claim scope with its family's science,
   merged crafts and linked shared concepts, and what its published sections cite; a category's
   curated facts, family science and sections), naming each fact and the way on: build the page's
   own component of that kind on its own facts. One whose facts the page holds is placed, and the
   preview now draws it.
6. **A whole page waits for one confirmation.** When a fact this account's agent proposed would be
   placed live (`trust_tiers.publishes_at_once`, the facts' own placement rule under the agent
   switch), `propose_page` with a draft or a bundle of more than one part stores a `PageHold` for 3
   days and returns its `confirm_url`; placements that cannot pass are refused first and nothing is
   held. The person, signed in to the same account on the site, presses Confirm once and the bundle
   runs then; Discard proposes nothing. The site's routes are the account's own and an MCP token
   cannot call them, so the agent cannot confirm for the person. Facts, parts alone and accounts
   whose parts wait for review are proposed as before.

## Consequences

- Migration `0103_component_lifecycle` (parent `0102_open_pictures`, decision 0192's, which reached
  main first) adds `ComponentProposal.replacesLabel` with its check,
  the tables `KnowledgePieceUnlink` and `PageHold` (row-level security on, no grants to `anon` or
  `authenticated`) and the staged action `remove`; the release before reads and writes every table.
- The web reads `OwnProposal.registered`, `ComponentReview.replaces` and the staged `remove`
  (optional on its side), and gains `/contributions/pages/[id]` for a held page.
- Over MCP nothing is listed newly: the tool list grows only by the `withdrawals` part, the
  `replaces` field and a removal's `label`, inside decision 0191's budget.
- Where the next lane plugs in: Admin removal of pictures, layouts, structure entries, readings and
  layers adds each kind's actions to `PUBLISHED_ACTIONS` (and the web's) and its entry to
  `PUBLISHED_KINDS` (a label, a lookup by label, one function per action); an `EDIT` action is a new
  action value in `STAGED_ACTION_VALUES` with a migration widening the check, and its before and
  after fields in the staged decision. Staging, the dry run, confirmation, audit and the batch view
  stay as they are.
- What waits outside the repository: the person's Confirm is a click on the site, and the
  Sanganeri page's earlier components are withdrawn or replaced by its contributor once this ships.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/research/test_component_lifecycle_rules.py`,
`backend/tests/db/test_component_lifecycle_db.py`,
`backend/tests/db/test_borrowed_and_held_pages_db.py`, `backend/tests/db/test_own_proposals_db.py`,
`backend/tests/mcp/test_mcp_page_holds.py`, `backend/tests/mcp/test_reference_limits.py`,
`frontend/e2e/staged-reviews-unit.spec.ts`, `frontend/e2e/page-holds-unit.spec.ts` and
`frontend/e2e/contribution-components-unit.spec.ts`.
