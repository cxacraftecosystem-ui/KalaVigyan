# 0067. Lesson packs, the explainer PDF and citation export

A Professor or above turns one version of their explainer into a lesson pack built by fixed rules,
with APA through citeproc-py, BibTeX and RIS by stated rules, a PDF by fpdf2, and a PPTX and a
reveal.js deck. Files are built once into the private bucket and answered as short-lived links, and
pictures come only from the open-image hosts.

Date: 2026-11-18. Status: accepted. Amended by 0070 (APA references are written in the
worker thread; the export libraries load on the first file; hidden generated explainers are left
out).

| For | Read |
|---|---|
| What amended it | [0070 Phase D review fixes](0070-phase-d-review-fixes.md): APA in the worker thread, the export libraries loaded on the first file, hidden generated explainers left out |
| What it amends | [0069 Learning screens: follow-ups, saved answers, notes, lessons, exports, the map and compare](0069-learning-screens.md): item 5, with lesson files and the report PDF as signed links |
| What it amends | [0062 Phase D contract: learning blocks, versions, alerts, lessons, exports and the map](0062-phase-d-contract.md): item 10, with APA written by citeproc-py while BibTeX and RIS keep the stated rules |
| The contract it was built to | [0062 Phase D contract: learning blocks, versions, alerts, lessons, exports and the map](0062-phase-d-contract.md) |
| The contracts it names | [learning.md](../contracts/learning.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase D lane 0067 (plan section 4 feature 11; section 3, PDF export and the lesson builder)
builds what decision 0062 fixed in `docs/contracts/learning.md`: a Professor or above turns one
version of their explainer into a lesson pack (slides, a reading list of its sources, the quiz of
decision 0064), downloads it as an HTML deck with a vendored reveal.js, PPTX and PDF; any reader
exports their explainer as a PDF and its citations as APA, BibTeX, RIS and CSL-JSON. The box is a
small, memory-bound EC2 instance: no headless browser, LibreOffice or system packages. The plan
asks for citeproc; decision 0062 had chosen hand rules instead, on the view that a processor adds
nothing when author names are kept as written.

## Decision

1. **The pack is built by fixed rules, never a model.** `research/lesson_builder.lesson_pack`
   reads the stored version: each chosen `READY` section's cited fact sentences in reading order
   (quiz blocks left out), only while every claim they cite is still shown, five a slide under the
   section's title, the section's first open picture on its first slide; the quiz is decision
   0064's one `quiz_block` over the same sentences (id `lesson.quiz`); then one slide per
   question, the reading list and the sources (`reading_list`, `cited_source_ids`). The fixed
   slide titles come from a hand table per answer language (`research/lesson_words.py`). An
   unknown section answers 404, an unfinished one, nothing left to teach or a pack past 60
   slides 422 with the reason. A long question is cut at a word for the title.
2. **The lesson fixture is regenerated from the quiz fixture.** `learning.lesson.golden.json` was
   written before decision 0064 fixed the quiz rules and held three questions those rules never
   ask; its quiz is now `learning.quiz.golden.json`'s nine questions (ids under `lesson.quiz`),
   with 16 slides and reading-list counts counted by hand. The builder reproduces it byte for
   byte; the contract test and the lesson screen spec follow it.
3. **APA through citeproc-py and the APA 7 CSL style; BibTeX and RIS by the stated rules.**
   citeproc-py 0.12.3 (BSD, pure Python on lxml, already locked) applied to the official
   `apa.csl` ("APA Style 7th edition", id `http://www.zotero.org/styles/apa`, updated
   2026-02-07, CSL styles repository commit `3c6698d7`, CC BY-SA 3.0) reproduced five of the six
   hand-written references of the citation fixture byte for byte; the sixth, an undated web page,
   is where APA 7 asks for a retrieval date. CSL items now carry `accessed`, the India-time day the
   source (or dataset row) was retrieved (`Source.retrievedAt`, `EnvDataset.retrievedAt`), so that
   reference reads "Retrieved October 14, 2026, from …" as the style requires; the fixture and the
   client shape gained the field. The style is vendored under `app/data/exports/csl/` with its XML
   comments removed (owner rule; the licence is the style's `rights` element), not taken from
   citeproc-py-styles (93 MB of styles for one file). No CSL style writes RIS, and the BibTeX style
   does not write the fixed multi-line form, so both keep decision 0062's rules
   (`research/citation_formats.py`). A dataset row's own citation text still wins.
4. **PDF: fpdf2 on the server, not a client print path.** A print path cannot answer the PDF
   route the client already offers, cannot write the lesson handout (slides as pages, then the
   answers) and would differ by browser. fpdf2 2.9.0 (LGPL, pure Python, with Pillow and
   fontTools) writes both PDFs in well under a second for the fixtures; uharfbuzz 0.57.0 (a pip
   wheel with HarfBuzz inside, no system package) shapes Indic and Urdu text, and fpdf2 falls back
   to Latin for numbers and names. Fonts are Noto Sans and its script families for every answer
   script, Regular and Bold (SIL OFL 1.1, unhinted, from the notofonts repository), vendored under
   `app/data/exports/fonts/`. Right-to-left languages are set right-aligned. ReportLab (no shaping
   in the open edition) and WeasyPrint (Pango and Cairo system libraries) were set aside.
5. **PPTX through python-pptx 1.0.2; the deck through reveal.js 6.0.2.** The PPTX is 16:9, one
   slide per pack slide, bullets with their citation numbers, the picture with its credit, quiz
   answers in the speaker notes, references as APA. The HTML deck inlines `reveal.js` and
   `reveal.css` 6.0.2 (MIT, from the npm package, header and full licence kept in the file),
   carries a content security policy of `default-src 'none'` with inline scripts and styles and
   `data:` images only, embeds pictures as data, reveals quiz answers as fragments and holds no
   other script.
6. **Pictures are read only from the open-image hosts.** A slide's open picture is fetched from
   `upload.wikimedia.org` or `api.openverse.org` (the hosts the Commons and Openverse adapters
   name) through the paced source HTTP with no redirects and no response cache
   (`sources/images/picture_files.py`), flattened to a JPEG of at most 1,600 px and 40 megapixels
   (`services/export_pictures.py`). A picture that cannot be read is left out with its credit;
   the bullets stand alone.
7. **Files are built once into the private bucket and answered as short-lived links.** A file's
   key is `exports/<builder>/<sha256>/<name>` (`naming.export_key`), the hash taken over the
   rendering version, the format and what the file is made from (the stored pack, or the version
   document, and the access days), so an unchanged pack or version is never built twice and a
   changed one gets a new key. The route answers `ExportLink {schemaVersion 1, format, fileName,
   url, expiresAt}` with a five-minute signed GET whose `Content-Disposition` carries the
   `naming.py` name (`KalaVigyan_Lesson_<date>_<craft>_<title>_Slides.pptx` and `.html`,
   `..._Lesson.pdf`, `KalaVigyan_Explainer_<date>_<craft>_<question>_Report_v<n>.pdf`); the client
   fetches the link and saves it under `fileName`, which supersedes item 5 of decision 0069 for
   these two routes. The bucket's existing `exports/` rule expires files after seven days and the
   media key may not delete there, so deleting a pack stops its routes at once and its files
   expire. Building runs in a worker thread after the request's database connection is released
   (decision 0040). Citation files are small and answered directly with `Content-Disposition`
   (`..._Citations_v<n>.bib`, `.ris`, `.txt`, `.json`), clearing decision 0069's debt entry.
8. **One home for visible claims.** `services/visible_claims.visible_claim_ids` is the quiz
   route's and the lesson builder's one read of which cited claims are still shown.

## Consequences

- New routes `POST/GET /api/lessons`, `GET/DELETE /api/lessons/{id}`,
  `GET /api/lessons/{id}/files/{html|pptx|pdf}` (all `BUILD_LESSONS`, the builder's own),
  `GET /api/explainers/{id}/versions/{n}/pdf` and `.../citations[/{bib|ris|txt|json}]`
  (`SAVE_EXPORT`, the asker's own). Migration `0023_lesson_packs` adds `LessonPack` (row-level
  security on, public roles revoked).
- New dependencies: citeproc-py, fpdf2, python-pptx, uharfbuzz (with Pillow, fontTools, XlsxWriter,
  defusedxml), and bibtexparser and rispy for tests only, so BibTeX and RIS are parsed back by
  independent readers. About 3.3 MB of fonts and 170 KB of reveal.js are vendored.
- Nothing needs provisioning: the `exports/` prefix, its expiry and the media key's rights exist.
  After the deploy that carries migration 0023, a professor's lesson pack is the phase D proof.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
