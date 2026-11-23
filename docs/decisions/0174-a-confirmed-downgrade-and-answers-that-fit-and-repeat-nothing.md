# 0174. A production downgrade undoes one revision unless its count is confirmed, an answer fits its limits, repeats nothing its explainer shows and outlives a source that cannot be built, and the rubric's cited part is a share

In production `alembic downgrade` undoes at most one revision unless `CONFIRM_DOWNGRADE_STEPS`
names exactly how many it would undo, and no document tells anyone to undo a data step with a
downgrade; a translated section title, composed heading or component title longer than the field
it lands in leaves the English in place; a follow-up's sections are held to everything its
explainer already shows, as a later section of a first answer is; the note of a section that
found nothing lists only as many queries as `section_done` can carry; a source whose document
cannot be built is skipped with its reason logged, and a document is hashed as it is stored; and
the rubric's everyCited part is the share of shown sentences that are resolved and on the
question.

Date: 2026-11-23. Status: accepted (the lead's brief for the fix lane "answers and docs" of
2026-11-23, from that day's adversarial review of the whole codebase; the guard at the owner's
request; the source failure and the rubric from the lead's answer-quality run 45161982883 of the
same day). It amends [decision 0143](0143-lessons-exports-and-follow-ups-kept-true.md), item 9 (a
region story is no longer a keyed repeat that a deepened section may add again),
[decision 0147](0147-time-market-and-figures-kept-true.md) (the rubric it re-based) and
[decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) (the off-question part it left
to the lead), and changes the everyCited part [decision 0138](0138-answers-composed-from-the-asked-fields.md)
set. The contracts are `docs/contracts/learning.md` (Follow-ups, Stream),
`docs/contracts/research.md` (`ResearchSummary`; the answering service, item 4; source documents),
`docs/contracts/explainer.md` (sections) and `docs/contracts/answer-eval.md` (the rubric); the
operator's side is `docs/RUNBOOK.md` (AI spend and token limits; Roll back).

| For | Read |
|---|---|
| The deepened section's repeats it amends | [decision 0143](0143-lessons-exports-and-follow-ups-kept-true.md), item 9 |
| Follow-ups and versions | [decision 0063](0063-follow-ups-versions-and-alerts.md) |
| One claim, one rendering across an answer | [decision 0080](0080-claim-ledger.md) |
| Craft-level stories built once per answer | [decision 0090](0090-reused-and-curated-sections-enriched.md), item 6 |
| A section that found nothing says what it searched; failures stay in their section | [decision 0032](0032-sectioned-composition.md) |
| The data step the old undo command was written for | [decision 0093](0093-no-caps-for-now.md) |
| One rule for stored text, and a document built from it | [decision 0135](0135-write-backs-filed-under-the-craft-they-name.md), item 1 |
| The rubric's sentence counts and floor it amends | [decision 0147](0147-time-market-and-figures-kept-true.md) |
| The off-question part it amends, left to the lead | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md), item 6 and Consequences |
| The off-question count the part reads | [decision 0138](0138-answers-composed-from-the-asked-fields.md) |
| The follow-up rules as they stand | [learning.md](../contracts/learning.md), Follow-ups |
| Every decision, by group | [README.md](README.md) |

## Context

The review of 2026-11-23 confirmed four faults in this lane's area.

- **An undo that drops production tables.** The RUNBOOK's AI spend section said "To undo the data
  step: `alembic downgrade 0028_roles_and_contributions`". That was safe only while
  `0029_unlimited_ai_use` was the head. From today's head, `0092_readings_layers_categories`, the
  command walks back 50 revisions, each committed on its own (`transaction_per_migration`), and
  their downgrades drop tables that hold production data: map layer proposals, stage reviews, the
  contribution queue, OAuth clients and tokens, image contributions, structure proposals,
  open-data releases. Nothing in the code stopped it. The Roll back section's "run `alembic
  downgrade` from the release that added it" named no target at all.
- **A translation longer than its field.** Section titles, composed headings and component titles
  were put into the stream and the document as the model translated them, checked only against the
  translator's 1,000 characters. `section_started`, `section_heading` and a stored section cap a
  title at 120 characters, a component at 200. In Tamil or Malayalam an 80-character English heading
  can pass 120: a composed heading then failed `section_heading` after its section's research,
  composition and write-back were paid for, and the section ended empty as "stopped"; a long
  fallback title ended the whole answer; a long component title raised a validation error that is
  not an `AppError`, so every section stopped. Only the stored-only answer kept the English when a
  heading was too long.
- **A follow-up that repeats its explainer.** A follow-up's new section had no deepening, its
  stream's claim ledger started empty and its builders' craft-level stories started untaken. A fact
  the base shows in Process, filed under Chemistry too (decision 0143 files a claim under several
  fields), came back in a new Chemistry section; a region story, seasons strip, supply map or zoom
  story could be built a second time; a composed heading could repeat a base section's title.
- **A note longer than its event.** A section that found nothing says what it searched, quoting
  every live query. An Expert section with a nearly full share of 24 queries, each prefixed with the
  craft's name, passes the 2,000 characters `section_done` carries; the event then failed, and the
  section was reported as stopped and left out of the answer's verdict, so the gap queue never
  heard that an asked field went unanswered.

The lead's full answer-quality run 45161982883 (release da569eda, 24 asked, 23 answered, judge
0.80, rubric 0.754 against a 0.82 floor) showed two more.

- **One source ended an answer.** The blue pottery safe-handling answer ended "Something went
  wrong while answering": CORE's `_fetch_document` built a document whose `text_sha256` did not
  match its text. `build_document` hashed the cleaned text, but a cleaned text can begin or end
  with space (a NUL or control byte removed beside it, or the cut at `FETCH_TEXT_MAX_CHARS`
  landing on a space), and the model strips its strings, so it held another text than the one
  hashed. The validation error is not an `ExternalFailure`, so the research step's guard let it
  through and every section stopped. A lone surrogate in a reply would have failed the same way.
- **The rubric's cited part was all or nothing.** It was 1 only when no shown sentence was
  unresolved or off the question. 22 of the 23 answers had 1 to 10 off-question sentences, most
  of them 2 or 3 of 20 to 76, so almost every answer stopped at 0.8 and a floor of 0.82 could not
  hold whatever the answers did.

## Decision

### A downgrade in production undoes one revision unless its count is confirmed

1. **The guard reads the plan alembic will run.** `backend/migrations/env.py`, after configuring
   the context and before any step, asks `core/downgrade_guard.planned_downgrade` for the revisions
   the command would undo: the command's own plan for the database's current heads, read only for a
   command that names a destination, and counting only downgrade steps (an upgrade, a stamp,
   `current` or `check` undoes nothing and is never planned twice). `refuse_long_downgrade` then
   refuses, with alembic's `CommandError` (the CLI prints `FAILED:` and exits non-zero), any
   downgrade of more than `PRODUCTION_STEPS` (1) revision when `APP_ENV` is `production`, saying how
   many revisions it would undo, from which to which, and how to confirm.
2. **The override confirms a count, not a wish.** `CONFIRM_DOWNGRADE_STEPS` (the setting
   `confirm_downgrade_steps`) lets a downgrade through only when it equals the number of revisions
   the downgrade would undo. A yes-or-no switch was rejected: left in the box's environment once, it
   would let every later downgrade through unseen, while a count confirms one downgrade of one
   length and refuses a mistaken target of any other.
3. **Outside production anything goes.** CI's database job runs `alembic downgrade base` with
   `APP_ENV` `test`, and a laptop is `development`; neither is guarded. An offline (`--sql`) run
   only prints SQL and is not guarded.
4. **No document says to undo a data step with a downgrade.** The AI spend section puts each value
   back where it now lives (the AI budget screen's daily allowances, a route's `maxOutputTokens`),
   with the values the data step cleared; Roll back says `alembic downgrade -1` from the release that
   added the migration while it is the head, and how a longer one is confirmed. No other
   `alembic downgrade` instruction is left in `docs/`.

### A translated title never outgrows its limit

5. **The English stays when the translation is too long.** `answer_translation.translate_segments`
   takes `longest` and leaves out any translation longer than it, so the caller keeps the original:
   section titles (`AnswerLayout.translated_titles`) and composed headings
   (`section_headings.headed_specs`) at `HEADING_MAX_CHARS` (120), a component's title at
   `TITLE_COLUMN_CHARS` (200); a translation left out is not cached. Asking the model again for a
   shorter translation was rejected because it adds a call for every long title; cutting the
   translation was rejected because it can cut a word or a meaning. The stored-only answer already
   kept the English this way.

### A follow-up repeats nothing its explainer shows

6. **The ledger and the builders start from the base.** Before any section starts, a follow-up's
   stream notes every block of the base's sections in its claim ledger
   (`ExplainerStream.shown_before`, `ClaimLedger.note_shown`): their sentences and claims, so a
   sentence whose claims are all shown or that restates a shown one is left out; the materials,
   molecules, generated explainers, what-ifs and concept nodes they show; their pictures, picture
   strips included; and their craft-level stories. Each base section's English title is claimed for
   that section, so a composed heading cannot take it. The answer's builders note the base's kinds
   (`BlockBuilders.note_shown(AnswerLayout.shown_kinds)`), so a craft-level story the base shows is
   not built again. Every section of a follow-up, new or deepened, is then held to what the whole
   explainer shows, as a later section of a first answer is held to the sections before it
   (decisions 0080 and 0090).
7. **A new section is not filtered before it is built.** Giving a new section a deepening that
   drops shown claims before its blocks are built was rejected: a section left with no blocks
   researches once more with fresh live queries, so a follow-up that only repeated its explainer
   would cost more calls than today. With the ledger, such a section's blocks are left out as they
   are sent, it ends `EMPTY` as already covered with no further research, and a follow-up that adds
   nothing stores no version.
8. **A craft-level story is once per explainer** (amends decision 0143, item 9). A deepened section
   no longer adds a region story of another river: a region story is one of the craft-level stories
   an answer shows once, and a follow-up's version is read as one explainer. Map layers, reaction
   players, molecules and material cards still count as repeats only when everything they show is
   shown already.
9. **The base lede is not noted.** A follow-up's version carries the follow-up's lede, not the
   base's (`version_merge.merged_version`), so only the base's sections are noted.

### An empty section's note fits `section_done`

10. **It lists what fits and counts the rest.** `research_summary.searched_note` lists the queries,
    in order, while the note fits `SEARCHED_MAX_CHARS` (2,000), then adds "; and N more"; when not
    one fits it only counts them. The limit now lives in `research/research_summary.py` beside the
    note it bounds, and `research/explainer.py` imports it for `section_done` and a stored section.
    `not_enough_evidence_message`, whose event has no limit, still lists every query.

### A source that cannot be built is skipped

11. **A document is hashed as it is stored.** `sources/adapter.build_document`, which every
    adapter and the open-access reader use, strips the cleaned text and the cut, so the text it
    hashes is the text the model holds; `research/storable.storable_text` also drops lone
    surrogates, which neither UTF-8 nor Postgres can carry. CORE checks its full text after
    cleaning, so a full text of control bytes alone gives way to the abstract.
12. **A document that still cannot be built is a failure of its source.** `build_document` turns
    the model's refusal into an `ExternalFailure` naming the item and the problem, which the
    research step's guard records as a `FETCH` failure (logged, shown in what the section
    searched) and skips; the open-access copy is built under the same guard, and an abstract that
    cannot be joined to a full text leaves the full text alone. No other adapter had a different
    pattern: each builds through `build_document`.

### The rubric's cited part is a share

13. **everyCited is the share of shown sentences that are resolved and on the question**: the
    shown sentences less those without a listed source and those resting on a passage about
    another craft or a place abroad, over the shown sentences, and 0 when none is shown. An
    explainer lists every source it cites, so an unresolved sentence is one with no citation and
    cannot also be off the question; the two counts never overlap. Under this rule run
    45161982883's rubric mean is 0.920 (0.754 as run; the 23 answers recomputed from the report's
    measures, each old score reproduced first). The floor stays 0.82 until the lead re-bases it
    on the next run.

## Consequences

- No migration. A new setting, `CONFIRM_DOWNGRADE_STEPS`, is unset everywhere; it is set on the
  command line for one confirmed downgrade and never kept in the box's environment.
- Model calls and tokens per answer are unchanged or fewer: a long translation is dropped, not
  asked for again; a follow-up builds no craft-level story its base shows; a note is shorter.
- A follow-up that only repeats its explainer now adds no section and stores no version, where it
  used to add a section of repeats.
- The same change corrected, from the review's docs findings, the contribution worker's 4 gate
  runs, the release's six fail-stop seed steps (`sync_dataset_registry` and `refresh_shared_terms`
  among them), the retrieval ranking depth (60), Deep's reference reserve (15 of 48), the web's
  hourly public cache, the simulation draft limit (40,000), two retired names in the catalogue and
  the OAuth discovery routes outside `/api`. No register entry was added.
- A source failure that once ended an answer now costs one document; the section reads the next.
- The rubric mean rises with the share (0.920 on run 45161982883), so the floor recorded in
  `backend/app/data/eval/floors.json` is the lead's to re-base after the next run, as the register's
  rubric floor entry says.

## How this record is kept true

It is not edited after acceptance except to mark a row superseded: a later choice is a new record
that names this one, and the table above links the two both ways. It records the choices as taken
on 2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/test_downgrade_guard.py`,
`backend/tests/db/test_downgrade_guard_db.py` (a two-step downgrade refused on a real database),
`backend/tests/answering/test_translated_titles_fit.py`,
`backend/tests/answering/test_follow_up_flow.py`, `backend/tests/answering/test_heading_once.py`,
`backend/tests/alerts/test_follow_up_layout.py`, `backend/tests/ledger/test_ledger_shown_before.py`,
`backend/tests/research/test_searched_note.py`, `backend/tests/sources/test_unbuildable_documents.py`,
`backend/tests/research/test_coverage_eval.py` and `backend/tests/answering/test_off_question.py`.
