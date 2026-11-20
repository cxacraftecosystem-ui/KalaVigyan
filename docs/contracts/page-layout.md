# Page layout and generated monograph documents (decision 0106 item 6; decision 0101 items 4 and 14)

Formatting is its own layer. A page's layout record says where each text unit and component of the
page sits and how a picture is cropped; it refers to them by unit id and component label only and
never holds a fact. Editing a fact never breaks a layout, and editing a layout never touches a
fact. Every craft, family and category without authored content gets a monograph document
generated from what the database holds, ordered by its layout record.

## The layout record (`research/page_layout.py`)

`PageLayout {schemaVersion 1, subjectKind (craft, family, category), subjectSlug, version (from 1),
entries[]}`, at most 4,000 entries. Each entry:

| Field | Rule |
|---|---|
| `ref` | a component label (`research/monograph_page.COMPONENT_LABEL_PATTERN`, it holds a `/`) or a unit id (`[A-Za-z0-9._-]+`, the slot key of the template) |
| `chapter` | a chapter key, `^[a-z][a-z0-9-]{0,39}$`: decision 0095's keys for generated pages, the approved page's own chapter ids for Kutch Ajrakh |
| `order` | from 1; no two entries share a chapter and an order |
| `role` | `HERO`, `OPENER`, `PLATE`, `FIGURE`, `SIDEBAR`, `PULL_QUOTE` or `BODY` |
| `crop` | optional focal box `{x, y, width, height}` in fractions of the picture, inside it (`research/craft_parts.Focal`) |
| `size` | optional `MARGIN` (the right margin of the spread), `COLUMN` (the measure), `WIDE` (the content width) or `BLEED` (full bleed); absent means the role's default |
| `caption` | optional caption override, 1 to 300 characters |

Rules, checked on every record and every write:
- each unit or component is placed once;
- a page has at most one `HERO`, and a chapter at most one `OPENER`;
- `HERO`, `OPENER`, `PLATE` and `FIGURE` place a component; `PULL_QUOTE` places a text unit;
  `SIDEBAR` and `BODY` place either;
- only a component takes a crop or a caption override.

**How a document is ordered** (`arranged_layout(default, layout)`): chapters come in decision 0095's
order (`research/chapter_keys.CHAPTER_KEYS`), then any other chapter a layout names. In each chapter
the entries the layout names come first, by `order`; then everything it does not name, in the
document's default order. An entry moves its unit or component to its `chapter`. Units that sit
within a component (`within`) travel with it; the layout orders top-level entries only. A layout
entry naming something the document does not hold is ignored, so a removed fact never breaks a
layout, and a new unit or component lands at the end of its chapter until a layout places it
(decision 0101 item 14).

## Storage, writes and the backfill

- Table `PageLayout` (migration `0042_page_layouts`, after `0041_monograph_documents`): `id`,
  `craftId` or `categoryId` (exactly one; a family is a `Craft` row), `version`, `entries` (JSONB,
  the entries without absent fields), `writtenByKind` (`USER`, `SYSTEM`), `writtenById`,
  `createdAt`. Unique per subject and version; append only. The newest version is the layout.
- `services/page_layouts`: `page_layout(session, kind, slug)` and `layout_of(session, subject)` read
  the newest version (`None` when there is none); `write_layout(session, kind, slug, LayoutWrite,
  actor=)` stores the next version only when `baseVersion` is the current one (0 when there is
  none), else refuses with `Refused("stale_layout")`; every stored version writes the audit record
  `PAGE_LAYOUT_WRITTEN` (target `PageLayout`, detail `subjectKind`, `subjectSlug`, `version`,
  `entries`). The subject is found by `services/open_work_subjects.subject_by_key`, so a family
  asked for as a craft, or the reverse, is refused like an unknown slug.
- `services/page_layouts_backfill.backfill_page_layouts(session)` gives every curated craft, family
  and category with pictures and no layout its first version, written as `SYSTEM`, from the
  dossier's pictures (schema 2, `docs/contracts/curation.md`), and reports `{written, kept}`:

| Dossier placement | Layout role | Chapter |
|---|---|---|
| `MASTHEAD` | `HERO` | `glance` |
| `OPENER` | `OPENER` | its chapter |
| `PLATE`, `MATERIAL` | `PLATE` | its chapter |
| `RECORD`, `STAGE` | `FIGURE` | its chapter |
| none, with a stage | `FIGURE` | `made` |
| none | `PLATE` | `glance` |

  In each chapter the hero or opener is order 1 and the other pictures follow in dossier order. The
  focal box becomes the crop. A picture's ref is its component label
  `<craft or category slug, lower case>/pictures/<dossier key, lower case>` (`picture_label`), for
  example `bagh-print/pictures/i02`.

## Routes and the MCP tool

| Method | Path | Who | Answer |
|---|---|---|---|
| GET | `/api/pages/{kind}/{slug}/layout` | anyone (public reading limits, ETag) | the newest `PageLayout`; 404 for an unknown page or one with no layout; 422 for another kind |
| PUT | `/api/pages/{kind}/{slug}/layout` | Admin, Master Admin | body `{baseVersion, entries}`; 200 the stored version; 409 when `baseVersion` is not the current version; 404 for an unknown page; 422 when an entry breaks a rule |
| GET | `/api/categories/{slug}/monograph` | anyone (public reading limits, ETag) | the generated `MonographDocument`; 404 for an unknown category or one with nothing published |
| GET | `/api/families/{slug}/monograph` | anyone (public reading limits, ETag) | the same for a family |

`kind` is `craft`, `family` or `category`. The routes are `api/routes/page_documents.py`.

MCP read tool `get_page {subject {kind, slug}, parts ["layout"]}` (`api/mcp_page_read.py`, any connection):
its `PageRead` carries `layout` (PageLayout or null) and `pageUrl` (`knowledge-api.md`); an
unknown slug or a wrong kind is a tool error naming `find_crafts`.

## Generated documents (`services/monograph_generated*.py`)

`generated_document(session, subject_kind, slug) -> MonographDocument | None` builds the document
of a craft without authored content, a family or a category. An unknown subject or a wrong kind
raises `InvalidInput`; a subject with no published sentence whose facts are all public gives
`None`. The craft monograph route calls it for every craft without authored content.

What it holds (`MonographDocument`, `docs/decisions/0106`):
- **Text units, one paragraph per section sentence.** The published `ArticleSection` of each field
  gives one `p` unit per sentence whose every claim is public and cited
  (`knowledge_view.claims_by_id`); a sentence resting on a hidden or uncited claim is left out.
  Unit id `<field, lower case>-<first 10 hex of the SHA-256 of its sorted claim ids>` (a `-2`, `-3`
  suffix when two sentences of a field rest on the same claims), so an id survives rewording and a
  layout keeps pointing at it. Each field with a sentence opens with an `h3` unit `h-<field>` holding
  its title (`research/sections.DISCIPLINE_TITLES`). A unit sits in its field's chapter
  (`research/chapter_keys.DISCIPLINE_CHAPTERS`); `claimIds` are the stored claim ids.
- **Citation marks** in the shape `render_nodes` reads: `[{"m": "s", "c": ["<sentence but its last
  word> ", {"m": "cite", "key": "<unit id>", "g": ["g2", "g1"], "c": ["<last word>"]}]}]`.
  `citations[<unit id>]` lists `{source, locator, quote}` for each quote of its claims and
  `citationClaims[<unit id>]` its claim ids.
- **Sources** are the stored claims' sources (`CitedSource`, `grade` the source's reliability),
  keyed `g1`, `g2`... and numbered in reading order, after the layout is applied; one source cited
  by two sentences keeps one number. A reused fragment's sources follow, matched to the page's by
  URL (or title).
- **Masthead and label card** from the subject's record, in `glance`: `masthead-kicker`
  (`Monograph` and the family and kind labels), `masthead-title` (`h1`, the reader's name of the
  craft), and the label card as `dt`/`dd` pairs `label-place-term`/`label-place` (states of
  practice) and `label-gi-term`/`label-gi` (`Registered geographical indication`, for a GI craft
  only). They sit within the hero picture when there is one, as on the approved page.
- **Pictures** are the curated dossier's inline pictures, each a `picture_plate` component labelled
  as in the backfill, in its placement's chapter with its role, drawn from a spec: `{media
  (MediaRef), caption (the layout's override or the dossier's), standIn, focal (the layout's crop or
  the dossier's focal box), role, size, claimIds}`.
- **Registered components** that apply: for a craft or family
  `services/component_library.library_components` with its slug; for a category every labelled,
  visible component keyed to a concept its curated or section facts are about, or resting on one of
  those facts. Of these only the subject's own components and shared ones (no owning craft) are
  placed: another craft's own component that shares a place or a concept stays on that craft's
  page. Each is placed at the end of its field's chapter, sorted by label, and drawn from its
  delivered spec when it has one (`payload.delivered`, a component a contributor delivered and an
  approval registered, its units renamed `u5001` and on and cited within it;
  `docs/contracts/component-specs-general.md`), else from
  `backend/app/data/monographs/<registering monograph>/specs/<label with / as __>.json` when that
  spec exists, else from that monograph's fragment
  `backend/app/data/monographs/<registering monograph>/fragments/<label with / as __>.html`, its
  unit and data slots filled from that monograph's `content.json` with each cite renamed to the
  page's source keys and its citation key prefixed `<monograph, lower case>:`. The registering
  monograph is the `monograph` the component's stored payload names. A component with neither is
  left out of the page.
- **Order**: by chapter, the hero with the masthead, then each chapter's pictures (hero and opener
  first), its text by field, then its components; then the page's layout record as above.
- **Data**: `content.data["page-layout"]` is the layout record the page was ordered by, so a
  renderer applies roles, sizes and crops; absent when the page has no layout.
- **Version**: the sum of the subject's published section versions, so a new version of any
  section moves it. `title` is the subject's name; `pageUrl` is `/crafts/<slug>` for a craft or
  family and `/categories/<slug>` for a category on `PUBLIC_WEB_URL`.

**A page and a bundle.** `generated_parts(session, subject, additions)` takes optional
`PageAdditions` (`services/page_preview_additions.py`): sentences added to their fields' sections
(a new section at version 0), the facts and sources they rest on, delivered components that join or
replace the registered ones by label, and a layout that replaces the page's. `preview_page` builds
a bundle's preview with it (`open-work.md`, Previews before submitting); without additions the
document is the page's own.

## The nightly static build

`GET /api/site/pages` (`services/static_pages.py`) lists every craft and family with an `OPEN`
snapshot, a published section (so a generated document) or authored monograph content, by slug,
and every category in master order. The shape is unchanged (`StaticPages {schemaVersion 1,
crafts[], categories[]}`): a family's page lives at `/crafts/<slug>`.

## Tests

`tests/research/test_page_layout.py` (rules, labels, ordering), `tests/layouts/` (backfill rules,
the generated document with a spec, a reused fragment and a layout, the routes),
`tests/mcp/test_mcp_layout_tools.py`, and the database tests
`tests/db/test_page_layouts_db.py` (versions, audit, kinds, backfill, static pages) and
`tests/db/test_generated_documents_db.py` (a seeded craft, family and category).
