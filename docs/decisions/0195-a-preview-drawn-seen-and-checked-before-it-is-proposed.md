# 0195. A preview is drawn in a sandboxed browser at a phone's width and a desktop's, the agent sees the pictures, the release's drawing checks run before proposing, and the page is set beside Kutch Ajrakh

`preview_page` now has its private link drawn by a headless browser on the box at 390 and 1440 px,
returns pictures of the first screen and of each chapter to the agent, runs the same drawing
checks the release runs on live pages, fails rule 28 of the page checklist with each component's
problem in words, and sets the page's pictures, figures, interactives and maps beside Kutch
Ajrakh's. `propose_page` refuses a page while its latest preview fails those checks.

Date: 2026-11-24. Status: accepted (the lead's page-quality round; the owner asked on 2026-11-24
for every page built over MCP to reach the Kutch Ajrakh standard and does not mind new tools). It
amends [decision 0110](0110-contributor-supplied-sources.md) (the preview and its checklist report)
and [decision 0193](0193-components-withdrawn-replaced-or-borrowed-and-pages-held-for-one-confirmation.md)
(a whole page held for one confirmation). The contracts are `docs/contracts/open-work.md` (Drawn as
a reader sees it, the checklist report) and `docs/contracts/infra.md` (Renderer); the operations are
in `docs/RUNBOOK.md`, Page renderer.

Amended by [decision 0252](0252-field-photographs-and-reaction-scenes-drawn-in-a-preview-and-on-the-page.md): the pass also opens `/drawn-field-photos/{id}`, so a placed field photograph is drawn in the preview's pictures.

Amended by [decision 0254](0254-a-preview-refuses-what-the-confirm-refuses-a-layout-names-only-what-exists-and-a-duplicate-shows-the-same-thing.md): the preview runs the confirm's own part checks on each part, with the same reasons, and names a published layout's missing labels.

| For | Read |
|---|---|
| The preview, the draft and the checklist report it changes | [decision 0110](0110-contributor-supplied-sources.md) |
| The hold that now also refuses a failed drawing | [decision 0193](0193-components-withdrawn-replaced-or-borrowed-and-pages-held-for-one-confirmation.md) |
| The sandbox the renderer's unit copies | [decision 0007](0007-web-search-and-fetcher.md), [decision 0173](0173-a-release-that-keeps-serving-and-its-way-back.md) |
| The room the tool list keeps | [decision 0191](0191-room-for-the-page-quality-tools.md) |
| The preview's pictures kept and shown to the page's reviewer beside the page as it stood | [decision 0236](0236-a-reviewer-sees-a-page-as-it-stood-and-as-it-will-be-and-decides-it-whole-by-chapter-or-by-component.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **The checks tested structure, not what a reader sees.** The Sanganeri Hand Block Printing page,
  built by a contributor agent over MCP, passed the preview's report and still looked poor to the
  owner: hand-drawn figures, no picture at the top, no sense of design. The agent said it could not
  open the images. The report read the document; nothing drew it.
- **The release caught what the preview let through.** On 2026-11-24 Monograph parity (run
  45373845030) failed on production because `sanganeri-hand-block-printing/chemistry/two-mordants-one-bath`,
  registered that morning, drew a 24-unit icon 239 px wide. `frontend/e2e/parity/parityComponent.ts`
  held that check (`sanityProblems`) and only the release ran it, after the page was live.
- **The box has no browser.** It is one t3.large (8 GB) running systemd units for the API, the
  worker, the fetcher and the contribution queue; the web app is on Vercel; a preview is private to
  the signed-in account that made it, and its pictures are served only to that account.

## Decision

1. **A renderer of its own on the box.** `kv-renderer` (`python -m app.renderer`, `backend/app/renderer/`)
   is a unit beside the fetcher and sandboxed like it: a user of its own, no secrets (`renderer.env`
   holds `PUBLIC_WEB_URL` and its own keys), link-local and private ranges blocked, `MemoryHigh`
   1200M, `MemoryMax` 1536M, no swap, 512 tasks. It starts one browser per render and kills its
   process group when the render ends, takes one render at a time (a second waits 5 s, then is told
   it is busy), and stops a render at 35 s; the API waits 45 s. The other designs were worse: a
   browser inside the API would share its ceiling, double with blue/green and take answering down
   with a leak; a hosted browser service would send private previews off our infrastructure behind
   a new vendor's key; a GitHub Actions run cannot answer inside one tool call; a Vercel function
   with a packaged Chromium has no memory ceiling of ours and cold starts past the tool call's patience.
2. **A pinned browser and no new dependency.** The browser is Chrome for Testing's
   chrome-headless-shell, pinned by version, download and SHA-256 in `infra/deploy/chromium.pin`
   (158.0.8127.88) and installed by `infra/deploy/install_renderer.sh` on each release that lacks
   it, with the Debian libraries its `deb.deps` names (GTK, wget and xdg-utils left out) and an
   `ldd` check. The renderer speaks the DevTools protocol over the `websockets` library already
   locked (`renderer/cdp.py`); Playwright for Python would have added a Node driver and a browser
   download of its own to the lock. Chrome's own sandbox is off (`--no-sandbox`), since Ubuntu
   restricts the user namespaces it needs and the unit is the sandbox.
3. **The browser reaches only the site.** Every request is paused and decided
   (`renderer/guard.RequestGuard`): a document only at the preview's link, the site's other
   requests with the pass, `upload.wikimedia.org` for pictures only (the one host a picture spec may
   name), everything else refused and named in the result's `blocked`; and no host name but those
   two resolves (`--host-resolver-rules`). A worker's own requests are not paused, but resolve no
   other host either. The renderer refuses a request that is not a preview link of its own site.
4. **A pass, not a session.** The API commits the preview, then mints a pass of the preview link's
   shape, signed for the account with a key of its own and alive two minutes. The renderer adds it
   as `x-kv-render-pass` to requests to the site only. The session routes stay as they were; the
   pass opens two routes of its own, classed as service routes in the route inventory: the web
   route reads the document from `/api/knowledge/pages/previews/{token}/drawn`, and the site's proxy
   sends a picture request that carries the pass to `/api/knowledge/pages/drawn-pictures/{id}`,
   which serves only a picture that preview shows, since a picture's address in the document is
   fixed by its spec. A session would have put the account's whole access into a browser, and one
   dependency taking either would have made the session routes open.
5. **One copy of the drawing checks.** Parity's checks moved verbatim into
   `backend/app/data/design/drawing-checks.js` (`kvDrawing.componentProblems`), with their limits
   (a 8 to 32 unit icon at most 64 px, figure text at most 96 px, an SVG label at most 48 px), under
   `backend/` because the box receives only `backend` and `infra/deploy`. Parity reads the same file
   (`frontend/e2e/parity/drawingChecks.ts`), and its `sanityProblems` answers as before. The preview
   adds, in the same file (`kvDrawing.review`): the first screen holds the masthead picture, loaded,
   and one headline (h1) that no other heading in it repeats; nothing runs past its column or the
   screen, and the page never scrolls sideways; no figure draws empty and no picture fails to load;
   a map draws its shapes and a chart its marks; a map, chart or interactive is not loading
   (`aria-busy`) and not moving (running animations) at rest, with motion reduced; and a picture,
   chart, map or interactive the layout places is drawn at all.
6. **Rule 28 decides, and `propose_page` listens.** The checklist gains rule 28, "The page draws
   whole at both widths". The report judges it until the page is drawn; a drawing problem at either
   width fails it as `<width> px, <label>: <problem>`; a page with none passes it; pictures that
   could not be made leave it judged with the renderer's reason, never passed. The verdict is kept on
   the preview (`PagePreview.drawing`, `drawingProblems`, migration `0108_render_review`, nullable,
   so the release before writes previews without them). `propose_page` (through
   `services/page_proposals.propose_page`) and a held page (`services/page_holds.hold_page`) are
   refused while the account's latest live preview of that page failed, naming the problems. A
   preview whose pictures could not be made does not refuse: the drawing checks guard how a page
   looks, which Monograph parity still checks after a release, not who may write what, and a
   renderer that is down would otherwise stop every contribution.
7. **The agent sees the page.** The reply carries, after its JSON, the first screen at 390 px
   (390 by 844) and at 1440 px (half size, 720 by 450) and each chapter at 1440 px from its top,
   its first 1600 px at two fifths size (576 px wide), JPEG at quality 55, kept in that order within
   1 MB in all, each with a caption.
8. **Measured against Kutch Ajrakh, as guidance.** The report's `bar` counts the pictures, figures,
   interactives and maps of the page and of Kutch Ajrakh (its vendored content: 9, 71, 14 and 8),
   chapter by chapter, from the documents themselves, Kutch Ajrakh's authored chapters read under the
   generated page's names. A count never passes or fails a page.

## Consequences

- A preview over MCP takes up to 45 s longer, and its reply holds up to 1 MB of pictures. The
  site's own preview form does not render, so its previews never refuse a proposal.
- The box gains a unit, a browser directory (`/opt/chrome-headless-shell`), `renderer.env` and the
  log group `/kalavigyan/kv-renderer`, which Terraform creates (`infra/terraform/logs.tf`). The
  first release that ships this installs the browser itself; the log group needs a `terraform
  apply`.
- The pictures are drawn in light only; the dark and high-contrast themes stay for the agent to
  judge on the private link, as rule 27 already draws each drawing in every theme.
- A new browser is a new pin and a release. Parity and the renderer now change their drawing
  checks together, in one file.
- Rules are 28, so the skills that name 27 change with this record (the Skill text of the lane's
  report).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`frontend/e2e/parity/parity-drawing-unit.spec.ts` (each check on fixture pages, and parity's own
messages unchanged), `frontend/e2e/preview-render-pass-unit.spec.ts`,
`backend/tests/research/test_page_render.py`, `test_page_report_drawing.py`, `test_page_counts.py`
and `test_page_report.py`, `backend/tests/renderer/` (the guard, the DevTools connection, the tab and
the server's time, queue and refusals), `backend/tests/pages/test_page_renders.py`,
`backend/tests/mcp/test_mcp_preview_pictures.py` (the pictures as image content),
`backend/tests/db/test_render_review_db.py` and `backend/tests/deploy/test_renderer_unit.py` (the
unit, its memory ceiling, the pin, the release step and the RUNBOOK section).
