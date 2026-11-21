# 0070. Phase D review fixes

Phase D's review fixed eleven issues: APA in the worker thread, export libraries loaded on the first
file, hidden marks on every served version, dates only as precise as their text, and BibTeX a stored
value cannot close. Notes belong to one account, an unknown craft and an empty comparison differ,
the digest links each explainer, and the explorer is a craft page tab.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| What it amends | [0063 Follow-ups that build, version history, saved explainers and alerts](0063-follow-ups-versions-and-alerts.md): the digest links each item to its explainer |
| What it amends | [0064 Quiz, compare and the shared-science explorer](0064-quiz-compare-and-shared-science.md): a comparison with nothing cited answers 204, and the quiz reads hidden marks |
| What it amends | [0066 Local measures, and market and GI](0066-local-measures-and-market-gi.md): GI and price dates are shown only as precisely as their quotes state them |
| What it amends | [0067 Lesson packs, the explainer PDF and citation export](0067-lessons-and-exports.md): APA in the worker thread, the export libraries loaded on the first file, hidden generated explainers left out |
| What it amends | [0069 Learning screens: follow-ups, saved answers, notes, lessons, exports, the map and compare](0069-learning-screens.md): item 3, notes held per account, and item 7, an unknown craft told apart from a comparison with nothing cited |
| The lanes it reviewed | [0063](0063-follow-ups-versions-and-alerts.md), [0064](0064-quiz-compare-and-shared-science.md), [0065](0065-climate-risk-and-ask-the-map.md), [0066](0066-local-measures-and-market-gi.md), [0067](0067-lessons-and-exports.md), [0068](0068-learning-block-renderers.md) and [0069](0069-learning-screens.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase D of `docs/plans/answer-experience.md` ("Learn and act", owner-approved, section 8 final) was
built by lanes 0063 to 0069 to the contract of decision 0062. The review found eleven issues:
APA formatting on the event loop, the export libraries loaded by every API process, a hidden
generated explainer still exported, quizzed and taught, curated GI and price dates checked only by
their year, BibTeX that a stored brace could break, a stale notes cache after a sign-out, an
unknown craft and an empty comparison given one answer, a digest linking to `/ask`, no screen for
the shared-science explorer, a quiz route importing through the voice package, and contract text
that no longer matched the code. The proof of the phase is a professor building a lesson pack
from one explainer, so the production E2E gains that step. Phase C's review (decision 0061) ran
in the same tree and owns the read-back routes of hidden explainers.

## Decision

1. **APA references are written in the worker thread.** `export_files.lesson_file_link` and
   `explainer_pdf_link` build the references and render the file in one `asyncio.to_thread` call,
   as the citation routes already did. The style is still parsed on every call: parsing takes
   about 2 ms of the 41 ms the six fixture references need (240 references take 1.9 s, all of it
   citeproc's rendering), and a parsed `CitationStylesStyle` keeps per-render state
   (`Layout.repressed`, `root.formatter`) that two worker threads would share. Caching it would
   save nothing measurable and add a race.
2. **The export libraries load on the first file.** `export_files` reaches `lesson_pptx` and
   `export_pdfs` (and through it `pdf_writer`) inside the renderer it calls, `apa_references`
   imports citeproc-py inside its function and `export_pictures.normalised` imports Pillow inside
   its own, so importing `app.api.router` loads none of python-pptx, fpdf2, uharfbuzz, citeproc-py,
   Pillow or fontTools (a test checks a fresh process). They are deferred at those four places
   only, which all run in worker threads; the heavy modules keep their imports at the top.
3. **Every served version carries its hidden marks.** `explainer_history.explainer_version` and
   `latest_version` pass the explainer through `simulation_hiding.with_hidden_marks`, so the
   explainer routes, the version PDF, its citations and lesson packs read one marked document; the
   explainer routes no longer mark it a second time. `follow_up_of` builds on the stored latest
   version unmarked, so a merged version never stores a mark that showing the piece again could
   not clear. The quiz route marks the explainer it reads. `blocks_play.hidden_block` is the one
   test: `export_files.explainer_cited` leaves a hidden block's sources and dataset rows out of the
   PDF's references and the citation files, and `export_pdfs`, `quiz.quiz_sentences` and
   `lesson_builder.section_bullets` skip a hidden block. A generated explainer cites through its
   values and states no sentence, so the leak was its sources and dataset rows; the quiz and lesson
   rules hold for any block that later carries sentences. `simulation_hiding`, `listen_store`,
   `film_store` and `learning_views` import `stored_explainer` from `explainer_payload`, its one
   home, and `answer_store` no longer re-exports it.
4. **Dates are shown only as precisely as a text states them.** `research/stated_dates.py` is the
   one reader of dates in stated texts: day dates (`22-04-2024`, `22nd April, 2024`, `April 22,
   2024`, `2024-04-22`) and month dates (`April 2024`, capitalised so the verb "may" is no month)
   as ISO partial dates. `GiStatus.filed_on`, `registered_on` and `PriceRange.priced_on` must be a
   date their sentence or quotes state at the precision shown (a year as a figure, as before).
   The market builder first cuts a curated date to the most precise form its texts state
   (`stated_precision`), so a record's `2024-04-02` against a quote of `22-04-2024` shows April
   2024 and a price dated past its sentence shows the year; a date its texts never state drops the
   price, and a GI date drops from the record. The GI label reader reads its dates through the
   same module. The curation checks are lane 0053's and are recorded as debt.
5. **BibTeX cannot be closed by a stored value.** Text fields write `{` and `}` as
   `\textbraceleft{}` and `\textbraceright{}` (BibTeX and biber count `\{` when matching braces);
   `doi` and `url` keep every character except `\`, `{` and `}`, written `%5C`, `%7B` and `%7D`
   by a fixed three-character table rather than `urllib.parse.quote`, which would also rewrite
   characters a stored link needs as they are. A test counts every brace as BibTeX does.
6. **Notes belong to one account.** `lib/notesStore.notesStore(load, now)` holds the notes with
   the account they were read for; `useNotes(account)` shows nothing for another account, asks at
   once when the account changes, and a late answer for the previous account is dropped. The nav
   passes `user.id`; `/saved` asks again on opening. This needs no hook in `AuthProvider`.
7. **An unknown craft and an empty comparison differ.** `GET /api/compare` keeps 404 `No craft has
   that address.` for an unknown slug and answers 204 with no body when nothing cited sets the
   crafts side by side. `fetchComparison` reads 204 as `{comparison: null}`; the page
   (`comparePage.compareState`) shows the route's own sentence for an unknown craft, one line, "No
   cited facts set these crafts side by side.", for an empty comparison, and a retry only for a
   failure.
8. **The digest links each explainer.** Each item's lines end with
   `PUBLIC_WEB_URL/ask?explainer=<explainerId>` (`alert_digest.explainer_url`), without `update=`:
   opening a mail link must not start a follow-up that spends the reader's caps; Update stays on
   `/saved`.
9. **The explorer is a craft page tab.** `components/craft/CraftSharedScience.tsx` draws
   `GET /api/crafts/{slug}/shared-science` with `ConceptGraphView` (the craft in focus) inside
   `CitedReading` and lists the route's numbered sources; `craftTabs` offers Shared science after
   Region only when the route names a node. A node does not link to `GET
   /api/shared-science/{termKey}`: the craft route's nodes already list every sharing craft up to
   the same 100 (`CONCEPT_CRAFTS_MAX`) the term route reads, and the view's Show all reaches the
   last of them, so a second read would add nothing.
10. **The production E2E proves the exports.** After the known-answer questions,
    `e2e/production/exportProof.ts` opens the English answer at `/ask?explainer=<id>` and
    downloads the report PDF and the APA, BibTeX, RIS and CSL-JSON citations through the Export
    menu; `exportFiles.ts` checks each opens (PDF header, pages and end; CSL-JSON a list; a PPTX a
    zip of slides) and carries every source the answer streamed (its DOI or URL link in the PDF
    annotations, APA and BibTeX, its title in RIS and CSL-JSON). A Professor account also builds
    the lesson pack and checks its PPTX and PDF against the pack's sources, which must be the
    explainer's. The E2E account is a Researcher and a Professor must use two-step sign-in, so the
    run notes the lesson step instead of failing; the choice is the owner's
    (`docs/PROGRESS.md`). The navigation check now expects Saved for learners, and a unit test
    keeps it equal to what the client draws. The screens run opens the Shared science tab.
11. **The documents match the code.** The explainer contract names the five built phase D kinds,
    the route-only quiz, `UNSTORED_BLOCK_KINDS` and `PIECE_BLOCK_ORDER` as they are; decisions
    0063, 0064, 0066, 0067 and 0069 carry amendment notes.

## Consequences

- No migration, no new dependency, no data run. Behaviour a reader sees: hidden generated
  explainers leave exports and lessons, GI and price dates may show as a month or year, the compare
  page tells an unknown craft from an empty comparison, the craft page gains Shared science, and
  notes never cross accounts.
- Left: the curation checks of curated dates (lane 0053), the C049 price fixture refresh (decision
  0062's debt entry) and the lesson pack proof in production (owner); all are in
  `docs/TECH_DEBT.md`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
