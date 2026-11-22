# 0145. Pages read what their screens draw: one coverage read, one decision route, one unit pattern, and renderers loaded when placed

The process route nobody read is retired, the craft page's client contract fits its budget in four
modules, the landing reads every monograph's coverage in one request, pictures and testimony are
decided only on the review queue, shared answers read their language from a public list, a
monograph loads the answer renderers only when it places an answer block, every spec names its
units by one pattern, and the boards follow the tokens where they broke them.

Date: 2026-11-22. Status: accepted (the lead's debt brief of 2026-11-22, monograph pages, craft
documents and speed lane). It amends [decision 0101](0101-knowledge-architecture-for-every-craft.md)
(round 2, the review page's cards), [decision 0097](0097-public-reading-everywhere-but-asking.md)
(the shared screens' language), [decision 0106](0106-one-monograph-template-for-every-page.md)
(generated picture units) and [decision 0092](0092-design-system.md) (two board rules). The
contracts are `docs/contracts/science.md`, `coverage.md`, `review-queue.md`,
`image-contributions.md`, `roles-and-contributions.md`, `backend.md`, `craft-page.md`,
`page-layout.md` and `component-specs-general.md`.

| For | Read |
|---|---|
| The review queue whose routes now decide every kind | [decision 0101](0101-knowledge-architecture-for-every-craft.md) |
| The shared screens and their reading metadata | [decision 0097](0097-public-reading-everywhere-but-asking.md) |
| One monograph template, its units and specs | [decision 0106](0106-one-monograph-template-for-every-page.md) |
| The design system and its boards | [decision 0092](0092-design-system.md), and [0141](0141-design-system-and-answer-screens-without-debt.md) for its last migration |
| Every decision, by group | [README.md](README.md) |

## Context

Twenty-two entries of `docs/TECH_DEBT.md` were the monograph pages', craft documents' and speed
debt. Several described screens that had since gone (the tabbed craft page and its Region map, the
profile and process clients), and some had been half cleared by other lanes (the Newsreader
subsets and the arrow's face, the uncurated page loaded on demand, curated documents split like
Ajrakh's shell, the fact grid). Each choice below had a real alternative.

## Decision

1. **`GET /api/crafts/{slug}/process` retires.** No screen read it since decision 0071; the
   ladder, the reaction player, the material cards and the chapters read the process view in the
   backend (`science/process_view`). The web client keeps only the process vocabulary and the
   reaction species its answer blocks carry (`lib/scienceContract.ts`, `lib/processView.ts`); its
   tests use hand-written species, not the golden view, which stays the backend's.
2. **The craft page's client contract is four modules by part**: the page's shapes
   (`craftPageContract`), its checks and what it shows (`craftPageChecks`), the version 2 process
   part (`craftPageProcess`) and what a chapter shows (`craftChapterReads`). The shape kit
   (`lib/shape.ts`) holds `ruled`, `count` and `positive` once. A craft's reading metadata reads the
   version 3 `lede` and `masthead.picture` now, so the flat fields can leave at schema 4 without it.
3. **One collection coverage read.** `GET /api/crafts/coverage` answers every curated craft's
   coverage in slug order, counted in one pass; the landing reads it once, tagged with every
   monograph's page tag so a page refresh refreshes it, and keeps the monographs its catalogue
   lists. A per-craft batch of requests was the alternative; it cost one request per monograph
   every five minutes.
4. **The review queue is the only place a picture or testimony is decided.** The cards call
   `/api/review-queue/{kind}/{id}/{action}` on every screen (the review page, the pictures page and
   the testimony page); the old decision routes are retired, while the testimony list, edit and
   corroboration reads stay (the queue has no equivalent). A testimony rejection may rest on its
   reason alone (`reason` optional only when `testimonyReason` is named), so an artisan never reads
   the reason's label twice, and a testimony approval may name up to five corroborating facts as
   the old route allowed.
5. **The answer languages are a public read.** `GET /api/answers/languages` gives the list
   `/answers/config` gives, so a shared answer or lesson reads with its language's script and
   direction without a session; when the list cannot be read the page reads in English, as the
   config's own parser does. Shipping the list in each shared body was the alternative; it would
   repeat one fixed list in every share.
6. **A monograph loads the answer renderers only when it places an answer block.** The
   `answer_block` view is a lazy client component (`kinds/blocks/LazyAnswerBlockView`), so the
   component views no longer pull `blockRenderers` and every answer renderer into each monograph's
   first load; a spec proves no eager path reaches them.
7. **Every spec names its units by one pattern from one home**: `u` and four digits
   (`research/unit_ids.py`, `lib/unitIds.ts`), in named ranges by origin: an authored page's own
   units `u0001` to `u5000`, delivered components' `u5001` to `u8999`, generated pictures' captions
   and credits `u9001` to `u9999`. Giving generated units free names was the alternative; every
   reader of a spec finds its units by the pattern, so free names would need a lookup in each.
8. **Where a board broke a token, the token won and the board was corrected**: the chart title
   takes the `text-h3` leading and tracking (the board's `.chart-title` used 1.25 and -0.005em),
   and the landing's specimen label keeps inside the 16px gutter (`min(390px, 100% - 12px)`, as the
   code had it). The two Newsreader copies were compared with fontTools: Google's served file and
   the pinned source are the same version 1.003 with the same advances. A hub shelf with an odd
   count fills its rows from the start, as the atlas shelves do, because it is the same shelf. The
   interface words of each answer language are the languages lane's.

## Consequences

- `GET /api/crafts/{slug}/process`, `POST /api/contributions/images/review/{id}/approve|reject`
  and `POST /api/testimony/review/{id}/approve|reject` answer 404; nothing in the web app called
  the first, and the cards no longer call the others.
- Two public reads join the route inventory: `GET /api/crafts/coverage` and
  `GET /api/answers/languages`.
- A generated page's picture units keep their numbers; a spec that names a unit outside `u` and
  four digits is refused where it was accepted (`u\d{4,}` in the science and tool specs).
- The entries left in the register say what each still waits on.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/db/test_craft_process_db.py`, `backend/tests/public/test_coverage_route.py`,
`backend/tests/db/test_coverage_db.py`, `backend/tests/review_queue/test_review_queue_rules.py`,
`backend/tests/db/test_review_queue_decisions_db.py`, `backend/tests/testimony/test_testimony_routes.py`,
`backend/tests/test_knowledge.py`, `backend/tests/research/test_unit_ids.py`,
`backend/tests/public/test_route_inventory.py`, `frontend/e2e/species-view-unit.spec.ts`,
`public-reading-unit.spec.ts`, `landing-collection-unit.spec.ts`, `review-queue-unit.spec.ts`,
`monograph-blocks-unit.spec.ts`, `atlas-collection-unit.spec.ts` and
`backend-vocabulary-unit.spec.ts`.
