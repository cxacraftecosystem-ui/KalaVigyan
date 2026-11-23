# 0143. Lesson packs open with the lede, exports name the journal and measure their slides, and follow-ups survive a race

A lesson pack's title slide carries the answer's lede; a paper's references name its journal; a
file made while a picture could not be read is never reused; files are made two at a time; slide
text is measured with the fonts it is written in; the explainer PDF draws each block; the production
run builds a lesson pack as a Professor; the digest speaks the reader's language; a deepened section
drops only true repeats; a follow-up that loses a race is merged onto the newer version; and
compare, the shared-science explorer and the re-check read what each claim is filed under.

Date: 2026-11-22. Status: accepted (the lead's debt-clearing brief of 2026-11-22, lessons, exports,
quiz, compare and follow-ups lane). It amends [decision 0067](0067-lessons-and-exports.md) (the
title slide, the export key, the build limit, the PPTX sizes, the citation fields, the PDF),
[decision 0063](0063-follow-ups-versions-and-alerts.md) (the digest, deepening and the version
race), [decision 0064](0064-quiz-compare-and-shared-science.md) (compare and the explorer) and
[decision 0077](0077-lede-headings-and-question-order.md) (the lede, which left lesson packs out).
The contracts are `docs/contracts/learning.md` and `docs/contracts/research.md`.

| For | Read |
|---|---|
| The lesson packs and exports it amends | [decision 0067](0067-lessons-and-exports.md) |
| The follow-ups, versions and alerts it amends | [decision 0063](0063-follow-ups-versions-and-alerts.md) |
| The compare and explorer rules it amends | [decision 0064](0064-quiz-compare-and-shared-science.md) |
| The lede it puts on the title slide | [decision 0077](0077-lede-headings-and-question-order.md) |
| The shapes and files | [learning.md](../contracts/learning.md), Lesson packs and Exports |
| Every scholarly adapter names the journal, and stored DOIs' journals are read again | [decision 0167](0167-answer-leftovers-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The debt register held thirteen open entries from decisions 0063, 0064, 0067 and 0070, and the
voice lane (decision 0140) left one more: the lede reached Listen, film and the whole-answer quiz,
but not lesson packs. Each was a shortcut taken when the phase D lanes were built: a journal no
source stored, a picture failure cached for a week, slide text sized by counting characters,
exports with no limit, a PDF without its drawings, a lesson pack never built in production, an
English digest, deepening that refused every second block of a kind, a follow-up that lost its
text in a race, and fields guessed from concept types.

## Decision

1. **The lede opens the title slide.** The `TITLE` slide holds the version's lede sentences that
   are facts whose claims are all still shown, at most five, as bullets under `blockIds ["lede"]`;
   it has no section, so the slide contract keeps its five kinds and the client's shape is
   unchanged. The deck, the PPTX and the PDF draw them under the title with their numbered
   citations, and the pack's sources include what the lede cites. We chose the title slide over a
   new `LEDE` kind, which every reader of the pack, the lesson screen among them, would have had
   to learn.
2. **A paper names its journal.** `Source.containerTitle` (migration 0068) holds the journal a
   work is in, from `EvidenceItem.container_title`, or from the `publisher` of the adapters that
   put the journal there (Europe PMC and Semantic Scholar, `JOURNAL_AS_PUBLISHER_ADAPTERS`); the
   migration fills it for the sources those two adapters stored. `SourceRef.containerTitle` carries
   it; CSL passes `container-title`, BibTeX `journal` (an article) or `booktitle` (a chapter), RIS
   `T2`, and the publisher is left out where it is the container title. We did not read the journal
   from any other adapter's `publisher`, which is a publishing house there; those adapters filling
   `container_title` is the sources lane's work.
3. **A file made without a picture is never reused.** When a picture could not be read, the file is
   filed under the hash of what it was made from plus the unread pictures' ids, so the next request
   misses the full key, reads the pictures again and files a complete file under the usual key. We
   chose a separate key over not storing the file, because a download is a signed link to a stored
   object; the `exports/` rule removes the partial file after seven days.
4. **Two files are made at once.** Each process holds one semaphore of `EXPORT_BUILDS_AT_ONCE` (2)
   in the export dependency; a request waits for a slot, looks in the bucket again and takes a file
   another request has just made. A picture that is not an image a document can hold is not unread:
   it would fail again.
5. **Slide text is measured.** Each PPTX text box takes the largest size on its ladder at which its
   lines fit, wrapped by fpdf2 with HarfBuzz and the pack script's Noto font at 1.5 lines a point
   size (wider and taller than the theme fonts PowerPoint draws with, so the measure errs safe). A
   section's bullets or a reading or sources list that fits at no size runs onto further slides
   titled `<title> (n/k)`; the pack itself keeps one slide each.
6. **The report PDF draws each block** from its own values before its sentences: trend bars,
   rainfall bars and month strips, districts filled over their state's outlines from the vendored
   district shapes with the boundary caption, equations and labels, names, formulas and amounts.
   Figure words copy the screen's English wording, as the screen has no other; a timeline map's
   places and routes are listed with their years, not drawn on a map.
7. **The production run proves a lesson pack.** It signs in as the Professor E2E account, answering
   two-step sign-in from its TOTP secret, asks its own known-answer question (an explainer belongs
   to its asker), builds a pack and checks the HTML deck, the PPTX and the PDF; on production a
   missing secret, a wrong role or a bad file fails the run.
8. **The digest speaks the reader's language.** Its subject and fixed lines go through the answer
   translator once per language per run; a line with no translation stays English. We chose this
   over the stored translation cache, which holds claims only.
9. **A deepened section drops only true repeats.** Map layers (by layer), region stories (by river,
   else districts), reaction players (by reactions), molecules (by compound) and material cards (by
   material, compound or term) count as repeats only when everything they show is already shown;
   other kinds keep one per section.
10. **A follow-up that loses a race is merged onto the newer version.** When the version it built
    on is no longer the latest, it is laid out by field on the newer version (deepening that
    version's section of the same field), renumbered and stored, up to three tries; the `version`
    event carries the new mark. The reader's page renumbers only on reload (the register keeps that
    part for the client).
11. **Compare and the re-check read each claim's stored field.** A claim counts in every field it
    is filed under (`Claim.field`, then `Claim.fields`), which the importer, the seed and the answer
    write-back write and migration 0032 filled for every older claim; the concept-type and
    heading-map fallbacks are gone, and a claim filed under no field is placed nowhere rather than
    guessed.
12. **A comparison may name a craft the resolver did not list.** The understanding's `compare` list
    may hold a name the question gives (`craftNames`); each is looked up once, with the lookup the
    understander already makes for named crafts, and only a `RESOLVED` craft is compared, so a
    craft the reader picked is compared with a named one. We kept one `compare` list rather than add
    a second reply field.
13. **The explorer reads a stored summary of each term.** `SharedTermCraft` (migration 0068) holds
    one row per term and craft whose own claims name the term, with its concept ids and every
    naming claim; `refresh_shared_terms` rebuilds it whole in each release right after the curation
    import and in the nightly upkeep, and the explorer routes and the concept graph read it whole,
    without the three-claims and hundred-crafts read caps. Hidden or lowered claims drop out at
    once; new claims arrive at the next refresh. We chose the release and the nightly upkeep over a
    refresh inside the curation import (another lane's files at the time) or on read (a GET that
    writes). A node still lists at most 100 crafts, as its contract says; the register keeps that
    part.

## Consequences

- Migration 0068 adds `Source.containerTitle` and fills it for Europe PMC and Semantic Scholar
  sources, and creates `SharedTermCraft` with row-level security on, as every table; the first
  release after the merge fills it before the pages are rebuilt.
- A lesson file made while Commons or Openverse failed costs a build on every request until the
  picture reads; a pack with many long references has more PPTX slides than the pack lists.
- The production run with `questions=true` asks one more Detailed answer, as the Professor.
- The register keeps four parts for other lanes: six scholarly adapters filling
  `container_title`, the lesson screen drawing the title slide's bullets, the client reloading a
  version a follow-up was merged onto, and a node's count and paging of the crafts sharing a term.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/learning/test_lesson_lede.py`, `test_paper_journals.py`, `test_export_store.py`,
`test_export_threads.py`, `test_slide_text.py`, `test_pdf_figures.py` and `test_pdf_figure_text.py`,
`backend/tests/alerts/test_digest_language.py`, `test_deepening_identity.py` and
`test_version_remerge.py`, `backend/tests/answering/test_follow_up_race.py`,
`backend/tests/db/test_alert_digest_language_db.py` and `test_version_race_db.py`,
`backend/tests/learning/test_shared_term_crafts.py`, `backend/tests/alerts/test_recheck_rules.py`,
`backend/tests/planner/test_understanding.py`, `backend/tests/db/test_alerts_db.py` and
`test_learning_views_db.py`, `backend/tests/test_deploy_page_order.py`,
`frontend/e2e/export-proof-unit.spec.ts` and the production run's lesson step.
