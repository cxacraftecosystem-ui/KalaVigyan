# 0233. A whole page fits one draft, a generated page carries its reading and media chapters, an agent files what the site cannot do, the read token comes with the draft and a portal photograph is placed by its label

A draft holds a page as rich as Kutch Ajrakh's and is proposed whole within the hour; a generated page
draws a reading chapter and a media chapter before its sources, with Ask next and its languages by
default and the student version delivered; a contributor's agent reports a site gap where the lead
and the Admins read it; the design pages and their `read_token` come with the opening of a draft or a
read of either page, never only through a refusal; and a field photograph from the portals, already
published on its craft's page and never an artisan's identity photograph, is placed by its label.

Date: 2026-11-26. Status: accepted (the lead's UX round of 2026-11-26, lane journey; the playbook
lane's audit, items C1, C2, C6, C8, C9, C10 and C13). It amends
[decision 0110](0110-contributor-supplied-sources.md) (a draft's limits),
[decision 0111](0111-fewer-mcp-tools.md) (the tool list),
[decision 0112](0112-reviewed-field-photographs.md) (where a field photograph is shown),
[decision 0114](0114-kinds-and-datasets.md) (the page tools) and
[decision 0203](0203-the-guide-handed-over-page-by-page-at-the-step-it-serves.md) (the design pages
before a page's first components). Nothing here moves, so no owner instruction overrides the design
system. The contracts are `docs/contracts/open-work.md` (Drafts), `docs/contracts/knowledge-api.md`
(the tools and Admin reports), `docs/contracts/monograph-renderer.md` (The page-tool kinds) and
`docs/contracts/page-layout.md` (the chapters and the field photographs).

Amended by [decision 0252](0252-field-photographs-and-reaction-scenes-drawn-in-a-preview-and-on-the-page.md): a portal photograph placed by its label is seen by the agent as a thumbnail and drawn in the preview's pictures, and a generated masthead names its label for the drawing checks.

| For | Read |
|---|---|
| The audit this answers | `.lead/data/ux-1126/audit.md` |
| Drafts and bundles | [open-work.md](../contracts/open-work.md) |
| The MCP tools and Admin reports | [knowledge-api.md](../contracts/knowledge-api.md) |
| The page-tool kinds and their views | [monograph-renderer.md](../contracts/monograph-renderer.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **A draft held a fifth of a page.** A draft or bundle held 20 facts, 20 structure items, 10
  components, 10 pictures and 600 kB. Kutch Ajrakh holds 80 components citing 183 facts, and its 80
  spec files are 1.25 MB written compactly; its largest players and maps are 136 to 254 kB each, so
  three composed players filled a draft. Every part a page proposed also counted against its kind's
  allowance for one proposal (10 components, 30 facts an hour), so a page of 45 delivered components
  was refused after its tenth.
- **A generated page had nowhere to read, hear or test itself.** `CHAPTER_KEYS` ended at `kin` and
  `sources`. The page tools (quiz, Ask next, the language switch, the student version) were
  "built by the site for every page" yet built only into Kutch Ajrakh's shell, and a contribution of
  one was refused.
- **A site gap had no address.** The agent rebuilding Sanganeri told the owner the rest was "not
  fixable from here"; nothing let it say so to the team.
- **The read token came only through a refusal**, so every page's first components call failed once.
- **Sanganeri's 13 published field photographs** reach its craft page's field part and no page
  picture; no tool offered them.

## Decision

1. **Room for a whole page, an add of the old size.** A draft and the bundle a draft makes hold 200
   facts, 100 structure items, 100 components, 40 pictures, 100 withdrawals and 4 MB
   (`research/page_proposals.py`, `page_drafts.DRAFT_BYTES_MAX`); `fact:N` names up to `fact:999`.
   One call still adds at most 20 facts, 20 structure items, 10 components and 10 pictures
   (`*_PER_CALL_MAX`), and a bundle sent whole in one call holds no more (`one_call_problem`), so a
   page is built over calls in its draft. Every per-item check stands. Why each bound is safe:
   - **Database row**: a draft is one `PageDraft.parts` JSONB value; at 4 MB it is far under
     Postgres's 255 MB value limit and is stored compressed out of line. Each edit re-reads and
     rewrites the whole value, a few megabytes of JSON per call, as a preview already reads the page's
     whole document (Kutch Ajrakh's is 2.3 MB).
   - **Preview time**: a preview reads no source and draws the document the page would be, which is
     no larger than Kutch Ajrakh's, drawn now on every visit; the renderer's 35 s bound stands and
     answers a page it cannot draw in time as `TIMEOUT`.
   - **Review effort**: a page's parts count against an hour sized for one whole page
     (`PAGE_PART_LIMITS`: its facts 200, its structure 100, its components and withdrawals 200),
     sharing each kind's bucket with single proposals, so one account sends at most one whole page's
     parts an hour, each still reviewed alone, and the ten page bundles an hour stand.
2. **Two chapters for the reader's tools.** `CHAPTER_KEYS` gains `reading` ("Reading tools") and
   `media` ("Pictures, video and film") before `sources`, as Kutch Ajrakh's shell orders them. A
   component of a reading kind (`ask_next`, `audio_player`, `citation_tool`, `explainer`,
   `language_switch`, `quiz`, `reading_level`) or a media kind (`ai_video`, `film`, `generator`)
   stands in its chapter whatever its field (`kind_chapter`); a layout entry places it elsewhere, and
   any picture or figure in either chapter.
3. **What needs no agent is there by default.** Every generated craft page draws Ask next from its
   suggested questions (the same questions the craft page asks, up to 12), and every generated page
   with at least one translated passage draws the language switch of its languages: English and each
   language with a served translation, every option a link to the page in it, each name in its own
   script (`monograph_generated_reading.py`). The switch is the `language_switch` kind's linked form:
   every option carries `href` and the spec holds no English unit and no panel; Kutch Ajrakh's form
   of panels stands, and a half-linked switch is refused on both sides.
4. **The student version is delivered.** `reading_level` leaves the page tools and is contributable:
   its title and lede are units, the lede cited. A quiz stays the site's: its sentences are nodes cited
   in place, and a delivered form needs a rest state that shows its cited sentences, which the next
   lane on the reading tools gives it.
5. **A site gap is filed.** `report_site_gap` (work group, contribute scope, 20 an hour) takes the
   page, the gap's kind (`KIND`, `TOOL`, `LIMIT`, `DRAWING`, `OTHER`), what was wanted, what was
   tried and up to five pieces of evidence, and writes one audit record (`site_gap.reported`, no
   migration). Admins and the lead read them in `admin_reports` as `site_gaps`, newest first, by
   page, kind and client, with no account named.
6. **The read token where the agent first needs it.** `edit_draft` naming its page while the draft
   holds no component hands the design pages with their `read_token`, and `get_page` with either design
   page's address hands both with the token. A first components call sent without it is still
   answered with the pages, nothing changed.
7. **A portal photograph placed by its label.** `list_field_photos` (pictures group, read) lists a
   craft's field photographs that its page already publishes (`field_photo_scope.shown_field_photos`)
   and that name no artisan (`artisanLinked` false, whatever `field_voices.artisan_images` says), each
   with its label `<craft>/pictures/field-<12 hex>`, caption, alt text, credit ("Photo: names, via
   the portal") and size. A layout entry naming the label places it (chapter, order, role, size, crop,
   caption), the masthead too; the page draws it from `/api/field-voices/images/<id>`, which serves
   only a shown photograph, so one hidden later leaves the page at its next build. The held list is not
   reviewed and the setting stays off.

## Guidance for the playbook, the cookbook and the contributor skill

The playbook lane owns them; the text the agent needs is:

> When KalaVigyan cannot do what the page needs (no kind draws it, no tool makes it, a bound stops
> it, or the preview draws it wrongly), file it with `report_site_gap`, quoting the evidence you met,
> say once to the person that it is the site's gap, and go on building the rest.

> A page at Kutch Ajrakh's depth is built in one draft over many calls (each add up to 10 components
> and 20 facts) and proposed once: the draft holds 100 components, 200 facts and 4 MB.

> The reading chapter holds Ask next and the page's languages by default; deliver the student
> version (`reading_level`, a title unit and one cited lede) for the page's younger readers. A
> craft's published field photographs are listed by `list_field_photos`; place one by its label in
> the layout where its chapter's story needs it.

## Consequences

- `docs/contracts/open-work.md` gives the new limits, `knowledge-api.md` the 26 tools and the
  `site_gaps` report, `monograph-renderer.md` the linked language switch and the reading chapter,
  `page-layout.md` the chapter keys and the field photograph labels; `components.md` counts 24
  delivered kinds, and `shared/curation.dossier.schema.json` names the two chapters.
- `frontend/components/monograph/kinds/tools/LanguageLinks.tsx` draws the linked switch;
  `lib/componentSpecsTools.ts` and `lib/componentSpecsPlates.ts` mirror the shapes.

## How this is kept true

| Claim | Kept true by |
|---|---|
| A draft holds a page at Ajrakh's size; one call and a whole bundle hold the old bounds | `backend/tests/research/test_page_room.py` |
| A page's parts count against one whole page's hour | `backend/tests/mcp/test_proposal_limits.py` |
| The reading chapter, Ask next, the linked switch and the delivered student version | `backend/tests/layouts/test_generated_reading.py`, `backend/tests/research/test_language_links.py`, `frontend/e2e/reading-tools-unit.spec.ts` |
| A site gap filed, refused and read | `backend/tests/mcp/test_site_gaps.py` |
| The read token handed without a refusal | `backend/tests/mcp/test_read_token_handed.py` |
| A published field photograph offered and placed; a held, hidden or identity one never | `backend/tests/layouts/test_field_photo_plates.py`, `backend/tests/db/test_field_photo_plates_db.py` |
