# 0175. The production checks read what the page shows, the web parses every stream event, the answer control never asks again, and a section stores only what it showed

The production checks judge a document's chapter rail once its rest is drawn, a quantities row said
above where its sentence is said, a what-if one option at a time and an answer's actions as a reader
hears them; the web parses the stream's `paced` event; the release control operates only the
answer's own choices; a reused section rebuilds its zoom story rather than placing a stored one; a
section stores only the built blocks its page showed; stored pictures are read before the
search's sources are built; a term whose defining claims were retired is read from the curated
facts that name it; and the film control waits on the film's own state.

Date: 2026-11-23. Status: accepted (the lead's production E2E brief of 2026-11-23, from run
45161989142 on release da569eda and post-deploy run 45178938516 on main 4e1cecf7). It amends
[decision 0090](0090-reused-and-curated-sections-enriched.md) (what a reused section rebuilds and
stores) and [decision 0166](0166-pictures-terms-and-stored-pieces-kept-true.md) (item 3, stored
pictures first) and [decision 0142](0142-curated-crafts-read-only-curated-rows.md) (what a term
reads once its seed claims are retired). The contracts are `docs/contracts/explainer.md` (the
builders, Stream events, the terms route) and `docs/contracts/frontend.md` (the answer stream).

| For | Read |
|---|---|
| What a reused section rebuilds, which this amends | [decision 0090](0090-reused-and-curated-sections-enriched.md) |
| Stored pictures first, which this amends | [decision 0166](0166-pictures-terms-and-stored-pieces-kept-true.md) |
| The seed claims retired under a curated craft, which left terms undefined | [decision 0142](0142-curated-crafts-read-only-curated-rows.md) |
| The quantities row said above (`shownIn`) the check now reads | [decision 0168](0168-a-table-under-a-said-sentence-and-python-within-budget.md) |
| The scholarly pace the `paced` event reports | [decision 0139](0139-sources-and-providers-reach-outside-services-once.md) |
| A monograph's rest loaded after its first chapter | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| The E2E production run | [decision 0029](0029-e2e-production-run.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Run 45161989142 failed 11 of 38 checks; its report and the box's rows showed what each was.

- **The rail.** A generated document sends its first chapter and loads the rest after the load
  event, five seconds and an idle moment, or at once on a reader's scroll, touch or key
  (`DeferredShellSlot`, `useShellTrigger`). The check read the rail as soon as the page drew, so at
  widths where the placeholder was not in view every later chapter was missing; Wide 1920 passed the
  same pages. Decision 0162 is not involved.
- **The streamed sentences.** Every quantities row the report called missing had a sentence of the
  same text earlier in the stream that the page showed (a ladder stage, a card fact, a region step,
  a timeline point): the ledger set `shownIn`, and the page drew the row under that sentence, as
  decision 0168 says. Every what-if sentence it called missing belonged to an option not chosen:
  `WhatIfLab` draws one option's outcomes at a time.
- **Indigo's 32 frames.** Only the Expert indigo answer researched live, and the backend sends
  `paced` after a `FOUND` or `READ` trail entry whenever a scholarly service held a request back.
  The web's event table did not know `paced`, so `explainerEventOf` returned nothing for it, which
  the production build ignores and the check counts as a broken frame.
- **The actions.** The quiet button lays its busy verb over its resting label, hidden and
  `aria-hidden`, so its width never changes (the design system's Button). The check read
  `textContent`, which joins the two ("SaveSaving"); the reader sees and hears "Save".
- **The pictures control.** The control opened the account's newest saved answer and pressed every
  segmented control in `main`, including the Depth group above the answer, which asks the question
  again by design (`useAskScreen.choose`). It replaced the saved essay with two fresh answers on
  production each run; until 11:22 that day the account had nothing saved, so the step never ran.
- **Materials' zoom story.** Answer 2b853532 reused a group for every section. Its PROCESS group
  held zoom story 485253be, so the builder skipped the kind for the whole answer (`note_shown`), and
  the ledger then dropped the placed story: its district, workshop and molecule captions were the
  texts of two ladder stages and a supply link the answer had already said, leaving one level.
  The story had been stored from a section whose page never showed it either: a fresh section stored
  every block its builders made.

## Decision

1. **A document's rail is judged once its rest is drawn.** `documentOutcome` waits up to 30 s for
   the deferred placeholder to leave the page, and the document shape says whether it is still
   there (`restWaiting`); a rest that never draws is its own problem, not missing chapters. We chose
   waiting over having the check scroll, so the page's own trigger is what is proven, and over a
   rail that lists only drawn chapters, which would hide the chapters a reader can jump to.
2. **The page-sentence check reads what the page shows.** A quantities row carrying `shownIn` counts
   as shown where that sentence is (`pageSentences.blockSentenceRecords`), and `what_if` is a stepped
   block like `zoom_story` and `concept_graph`. A refused frame is reported by its event name.
3. **The web parses `paced`.** `lib/explainerStream` holds its shape and the reducer draws nothing
   for it. We chose this over the check skipping event names it does not know: an unknown name is
   the drift the strict parse exists to catch, and the contract already lists the event.
4. **An answer's actions are read as heard.** The essay shape drops `aria-hidden` parts of a button
   before reading its label; the Button keeps its overlaid busy verb.
5. **The answer control presses only the answer's own choices** (`answer-view`), never the ask
   options, and counts the pictures the reader sees in the answer (a single picture is drawn in the
   margin at desktop width, its strip hidden).
6. **A reused section rebuilds its zoom story.** `zoom_story` is `rebuilt_on_reuse` and
   `replaces_stored`, like the reaction player, so a stored story never takes the answer's one zoom
   before the ledger has judged it. The rebuild reads stored rows, stored pictures and stored
   conformers and makes no model call. We chose this over keeping the stored story and letting the
   builder also run, which would build a second story for every reused answer whose stored one
   stands. **Its levels are captioned away from what the section's figures state**: a level is not
   captioned by a claim whose text a card, link, ladder stage or other figure of the section
   already shows word for word (`Captions.without_said`), since the ledger would drop it as said;
   the section's prose is composed in the composer's words and is not compared, which keeps the
   builder's goldens.
7. **A section stores only what it showed.** `reuse_enrichment.shown_builds` keeps a section's
   composed prose and ladder and the built blocks whose ids its page showed; `SectionOutcome` applies
   it to every section's stored blocks and `kept_with_reuse` before it decides that a reused group
   gained anything. A story the ledger dropped is never stored, so no group carries a block no
   reader saw.
8. **Stored pictures are read before the search's sources are built.** `SectionImages` takes its
   sources as a call made only when no picture is stored, so a section's stored pictures never wait
   on the live sources' build. **A zoom level takes its picture before its section's images block**:
   a section, fresh or reused, admits its built blocks before its pictures, so the images block
   skips a picture the section's zoom shows. Across sections a picture is shown once, where it
   first appears; we chose this over reserving the zoom's pictures for the whole answer, which
   would hold every section's pictures until every section's builders finished. Answer 2b853532's
   workshop picture went to its images block only because the placed story had already been
   dropped for its repeated captions.

9. **A term whose defining claims left is read from the curated facts that name it.** Alum's five
   concepts each kept only seed claims, all retired by decision 0142 when Kutch Ajrakh's dossier
   took over, and 0142 links no seed claim to a curated successor; alum then answered 404 to every
   reader. On production (2026-11-23) 118 terms had lost every visible defining claim this way, 85
   of them with no English summary at all, against 250 that still had one. When no defining claim is visible, the stored English summary reads the curated facts of
   the term's crafts that name it as a whole word (label, aliases and local names, the glossary
   marker's rule), those opening with it first, at most three shown (`term_store.curated_naming`).
   It makes no model call and serves signed-out readers too. We chose this over pointing each
   retired seed claim at a successor, a link 0142 never recorded and no dossier states.
10. **A researched term sentence keeps the sources that back it.** The term summary dropped a
    sentence when one of the pages it cited did not relate to it (`UNRELATED_SPAN`), though another
    page backed it; it now drops only the unrelated page's quotes and checks the sentence again
    (`term_summary.without_unrelated`). A sentence no page backs is still dropped.
11. **The control waits on the film's stated state.** On 37c0f9bb, `GET /listen` answered 200 after
    99.6 s, the time the first narration took. The control now waits until the film says it is ready
    or shows its failure line, up to the API's own 300 s, and reports which it saw.

## Consequences

- No migration, no model call and no token is added to an answer; a reused section with a zoom
  field now waits for the zoom builder (at most its 20 s, reading stored rows).
- Groups stored before this change may still hold a story their page dropped; a reused section no
  longer places one, so they are harmless and leave as their groups are superseded.
- The page's sideways scroll on three answers at phone width (3 to 6 px) was not reproduced from the
  report; the audit now names the outermost boxes past the screen, so the next run says which.
- A reader who presses Listen or Film on a new answer still waits while every block is narrated at
  once (about 100 s on a 63-sentence answer); playing the first block while the rest are made is
  queued as a follow-up, since it changes the listen route's contract and the dock.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`frontend/e2e/production-pages-unit.spec.ts`, `frontend/e2e/production-page-sentences-unit.spec.ts`,
`frontend/e2e/production-checks-unit.spec.ts`, `frontend/e2e/page-audit-unit.spec.ts`,
`frontend/e2e/release/answer-controls-unit.spec.ts`, `backend/tests/answering/test_reuse_enrichment.py`,
`backend/tests/answering/test_block_builders.py`, `backend/tests/journey/test_zoom_story.py`,
`backend/tests/images/test_section_images.py`, `backend/tests/db/test_terms_db.py` and
`backend/tests/terms/test_term_summary_spans.py`.
