# The monograph document, the template split and the kit (decision 0106, items 1 and 2)

A page in the monograph form is a document: `research/monograph_document.MonographDocument`
(schema 1), which one React renderer draws. The approved Kutch Ajrakh page (decisions 0100 and
0105) is split into a shell, one fragment per component and a page-wide kit, and its static build
reassembles them so the served page stays byte for byte what the owner approved.

Last reviewed: 2026-11-20.

Code: `research/monograph_page.py` (slots, `render_page`, `render_fragment`,
`assemble_template`, the kit file format), `research/monograph_document.py` (the document,
`spec_file_name`, `fragment_file_name`), `services/monograph_document.py` (the authored files, the
document builder, storing and reading versions), `services/monograph_load.py` (stores the document
when it changed), `models/monograph_documents.py` and migration `0041_monograph_documents` (the
table), `api/routes/craft_monograph.py` (the route), `scripts/build_monograph.py` (the static page,
the served kit and the golden), `scripts/split_monograph.py` (the split); the web shapes are
`frontend/lib/monographDocument.ts` and `frontend/lib/componentViewContract.ts`. Migration
`0045_document_language` keys stored documents by language (all rows English).

## GET /api/crafts/{slug}/monograph

Public (`public_reader`, the anonymous read limit). The slug resolves like the craft page's (case,
merges); an unknown craft is 404 with the craft page's detail. Query: `lang` (optional, a language
tag of at most 16 characters) and `version` (optional, from 1).

- **200**: the latest stored document of that craft in the served language as JSON
  (`MonographDocument`, by alias, its `language` the row's), or, with nothing stored, the generated
  one (`generated_fallback(session, slug)`, the route's one adapter, which calls
  `services.monograph_generated.generated_document(session, "craft", slug)`) with the tag of its own
  hash and version. With `ETag: "v<version>-<contentHash>"`, `Content-Language`,
  `Cache-Control: public, max-age=300` for a signed-out reader (`private, no-cache` signed in) and
  `Vary: Authorization`, as every public read.
- **English only, room for translation** (owner, 2026-11-20): `served_language(lang)` serves only
  `SERVED_LANGUAGES` (`en`); a request for any other language gets the English document with
  `Content-Language: en`. Generated documents are English.
- **`version`**: that stored version, or the generated document when its version is that number;
  otherwise 404 `This craft's monograph has no such version.`. The web app's `/crafts/<slug>/v<N>`
  reads it, the address Cite this monograph gives.
- **304**: `If-None-Match` names the current tag (with `Content-Language`).
- **404** `This craft's page is not a monograph document yet.`: nothing is stored and nothing is
  generated. A craft needs `CRAFT_SECTIONS_MIN` (3) published sections for a generated document
  (`enough_sections`; a family or category needs one). The web app then draws the craft without a
  monograph.

## The document

| Field | Holds |
|---|---|
| `schemaVersion` | 1 |
| `subjectKind`, `subjectSlug` | `craft` (or `family`, `category`) and its canonical slug |
| `language` | the document's language, a BCP 47 tag (`LANGUAGE_TAG`), `en` unless written otherwise |
| `title` | the subject's name (`Craft.name`; the master list's name offline) |
| `version` | the stored version, from 1; a document built but not stored is version 1 |
| `content` | the page's `MonographContent` (decision 0105): sources, citations, citation facts, data, text units, components and layout |
| `specs` | for each component whose spec file exists, that spec (a JSON object) |
| `fragments` | for every other component, its markup with its unit and data slots filled |
| `pageUrl` | `<site>/crafts/<slug>`; the site is `PUBLIC_WEB_URL` when stored, `PREVIEW_SITE` offline |
| `coverage` | a generated document's field coverage (`coverage.md`); left out when absent, as in an authored document |

Every component is drawn exactly once, from its spec or its fragment; a spec or fragment for a
component the content lacks is refused (`MonographDocument`'s validator). A fragment's unit slots
hold exactly the markup `render_nodes` writes (sentences, citation buttons, marks), so the
renderer's text units and the fragments agree.

**Components inside components.** A component whose element lies inside another component's
element stays inside the outer fragment as its own slot, `<kv-slot component="<label>"></kv-slot>`,
and its layout entry's `within` names the outer component (27 on the Ajrakh page). The renderer
draws the inner component (from its spec or fragment) where that slot is, and never at top level.
A fragment holds no other slot.

## Versions

`MonographDocument` (table): `id`, `subjectKind`, `subjectSlug`, `language` (default `en`),
`version` (unique per subject and language, at least 1), `document` (JSONB, the document with its
version and language), `contentHash`, `createdAt`. One row per version of a language; rows are
never changed. Migration `0045_document_language` added `language` (existing rows `en`, also
written into their JSON) and moved the unique key to subject, slug, language and version; its
downgrade keeps only the English rows.

- `store_document(session, document)` is the one writer. `contentHash` is the SHA-256 of the
  document's JSON (by alias, keys sorted, compact) without `version` and `language`, the row's key.
  When it equals the latest row's of that language, nothing is stored and it returns `None`;
  otherwise it stores the next version of that language and returns its number.
- `stored_document(session, subject_kind, slug, language="en")` returns the latest version as a
  `MonographDocument`, or `None`. `document_row(session, kind, slug, language=, version=)` returns
  the latest row, or that version's (the route serves its JSON without validating it again);
  `latest_document_row` is the latest.
- `load_monograph` (`python -m app.scripts.load_monograph`, and the nightly reload) stores the
  document of a craft with authored content after its sections and components; its report's
  `documentVersion` is the version it stored, or `null` when the document was unchanged or the
  craft has no authored folder. A folder named by another slug than the craft's is refused.

## The generated document

`services/monograph_generated_assembly.assembled_document` builds a page without authored content
from its published sections, registered components, curated pictures and `PageLayout`:

- chapter `opening` first: the masthead picture (the HERO role, its caption and credit units
  within it), the label units (`masthead-kicker` `p` with the "Monograph" and family spans,
  `masthead-title` `h1`, then `dt`/`dd` pairs `Place` and `GI`) and the lede: the first three
  sentences of the OVERVIEW section that the layout does not place elsewhere;
- every other chapter opens with its title, an `h2` unit `chapter-<key>` (`chapter_title`: "Why
  <first state>" or "Where it is made", "Market and GI" only with a GI), then its pictures, its
  sections (an `h3` section title unless it repeats the chapter's; a field's section, its fact grid
  and its components sit in the chapter `coverage_chapters.FIELD_CHAPTERS` names, rule 23 of the
  page checklist, `coverage.md`) and its components;
- a closing `sources` chapter with its `h2`, under which the renderer lists the sources.

A picture's spec is the full `PicturePlateSpec` (`checked_spec`, every field written); a picture
whose file is off the picture contract is left out.

## The authored files

```
backend/app/data/monographs/
  kit/monograph.css, kit/monograph.js       the page-wide styles and scripts, in parts
  <Slug>/content.json                       MonographContent
  <Slug>/template.html                      the shell
  <Slug>/fragments/<label>.html             one per component, "/" in the label as "__"
  <Slug>/specs/<label>.json                 a component's spec, when its kind has a view
```

**Slots.** `<kv-slot unit="u0001">`, `<kv-slot data="kv-cites">` (decision 0105),
`<kv-slot component="<label>">` (a component's fragment) and `<kv-slot kit="<file>#<part>">` (a
kit part), each followed by `</kv-slot>`. The shell holds the slots of the top-level components and
of the kit; a fragment holds unit and data slots and the slots of the components inside it, never a
kit slot.

**The kit.** Every `<style>` outside the components (the page styles and `kv-release-fixes`) and
every inline `<script>` of the body without `type` or `src` (the page script and the boxes' boots)
moved into the kit; the head's theme script, which runs before paint, stays in the shell, and the
model explainer's own `<style>` stays in its fragment. A kit file is its parts in order, each a
marker line (`@kv-part <name>;` in CSS, `"kv-part <name>";` in JavaScript), the part's text and a
newline that is not part of it. A part may not hold a marker line.

**The static page.** `python -m app.scripts.build_monograph` (from `backend`) writes
`frontend/public/monographs/kutch-ajrakh/index.html` from the shell, the fragments, the kit and the
content, and the served kit `frontend/public/monographs/kit/monograph.css` and `monograph.js`:
each the file's parts joined, without markers. The served `monograph.js` opens with one line,
`/* eslint-disable react-hooks/rules-of-hooks -- ... */`, because the web app's lint reads the
kit's plain `useSpeech` function as a React hook. `--check` lists every page or kit file that
differs from its build, and the backend tests fail until they agree. Never edit the served files.

**The split.** `python -m app.scripts.split_monograph Kutch-Ajrakh` ran once to cut the approved
template into the shell, fragments and kit. It reads the template the current files assemble, so it
can be run again and writes the same files. It refuses an anchor that is not `#id` or
`[attribute="value"]` or does not select exactly one element, a layout whose `within` differs from
where the page puts a unit or component, and a page whose page-wide blocks the kit does not name.
For the split two anchors were corrected to select the component's whole element (the GI card,
`[class="label-card gi"]`; how this answer was made, `[class="kv-made-fold"]`) and the nested
components' layout entries got their `within`.

## The golden

`shared/monograph.document.golden.json` is Kutch Ajrakh's document as the builder writes it, with
the preview site:

```
cd backend
python -m app.scripts.build_monograph --document Kutch-Ajrakh --out ../shared/monograph.document.golden.json
```

`tests/research/test_monograph_authored.py` fails until it matches; write it again whenever the
content, a fragment or a spec changes (a kind's spec landing moves that component from `fragments`
to `specs`).

## Tests

`tests/research/test_monograph_slots.py` (the slots and the kit format),
`tests/research/test_monograph_split.py` (the split's rules, its round trip on Ajrakh, one fragment
per component that is the element its anchor selects, every slot where the layout puts it, the kit
equal in the page and the served files), `tests/research/test_monograph_authored.py` (the builder,
specs over fragments, the hash, the golden), `tests/research/test_monograph_page.py` (the static
build byte for byte), `tests/public/test_craft_monograph_route.py` (the route) and
`tests/db/test_monograph_document_db.py` (a new version stored, an unchanged one not, each
language its own versions, the load), `tests/test_document_language_migration.py` (the key),
`tests/layouts/test_generated_document.py` and `tests/layouts/test_generated_chapters.py` (the
generated layout, chapter titles, the lede, the section minimum, the picture specs).
