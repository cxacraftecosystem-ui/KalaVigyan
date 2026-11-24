# 0188. An unscored answer breaks the floors, research for any craft is filed by the craft it names, chapters behind one address stay apart, and a difference is named only when every pair names it

A whole answer-quality run holds its floors only when it scored every question it asked; a fact
that research for any craft writes back is filed by the same naming rules as a craft's; the
answer's source merge never joins two chapters, two journal entries or two authors' works because
they share an address; and the duplicate gate stores what facts differ on only when every
differing pair names that one subject.

Date: 2026-11-24. Status: accepted (the lead's review lane of 2026-11-24, answers, from the
whole-codebase review of that day, workflow wf_af6bcf74-937). It amends
[decision 0126](0126-measurement-that-grows.md), item 3 (when a whole answer run holds its floors),
[decision 0135](0135-write-backs-filed-under-the-craft-they-name.md), item 3 (research for no
craft), [decision 0080](0080-claim-ledger.md), item 8 (sources are works) and
[decision 0177](0177-differences-named-and-the-monograph-shell-measured.md), item 2 (the
difference a duplicate outcome stores). The contracts are `docs/contracts/answer-eval.md` (The
report, The floors), `docs/contracts/research.md` and `docs/contracts/knowledge-writes.md` (the
filing and the duplicate gate) and `docs/contracts/explainer.md` (Sources).

| For | Read |
|---|---|
| The floors that alert, and the whole run they are compared on | [decision 0126](0126-measurement-that-grows.md) |
| The rubric floor a run with failed answers could pass | [decision 0184](0184-a-measured-rubric-floor-the-recorded-clip-one-open-acl-and-a-named-refusal.md) |
| The naming rules a write-back is filed by | [decision 0135](0135-write-backs-filed-under-the-craft-they-name.md), [decision 0136](0136-write-backs-filed-by-their-source.md) |
| The shared concepts a craft's search reads through the concept graph | [decision 0179](0179-transcript-windows-a-chunk-kind-linked-shared-concepts-and-one-paid-clip.md) |
| Sources counted as works | [decision 0080](0080-claim-ledger.md) |
| The subject a differing pair names | [decision 0177](0177-differences-named-and-the-monograph-shell-measured.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **Failed answers left the means and passed the floors.** A question whose answer failed, timed
  out at `ASK_TIMEOUT_SECONDS` (600 s), kept no explainer or was not scored by the judge has no
  rubric score or no judge's share, and `eval_report` takes each mean over the questions that have
  one. `floors_applied` asks only that the run asked every question and was not stopped by the cap.
  So a run of 24 in which 10 answers failed and the other 14 averaged rubric 0.93 and judge 0.81
  was reported at its floors (0.88 and 0.76): `belowFloor` false, the issue `Answers fell below
  their floor` closed and the stored run `floorsHeld` true. Only a run in which every answer failed
  broke a floor, through its missing mean.
- **Research for any craft filed every fact on shared concepts.** `craft_filing` returned no craft
  before any naming rule ran when no craft was researched, so a sentence naming one catalogued
  craft ("In Bagru the rekh block ...") went onto the shared concept of its facet's type and name.
  Since decision 0179 a craft's stored search reads the shared concepts the concept graph links to
  it; about 15 production shared concepts are linked so (category glossary terms such as the
  Textiles `rekh`, linked to Kutch Ajrakh, Bagru and Sanganeri). That claim was then offered to a
  linked craft's answer as a stored `CLAIM` candidate, which `off_question.screened_request` does
  not label as another craft's, as it does `EVIDENCE`.
- **One address held three chapters.** The Cane-Bamboo-Craft dossier cites three chapters of one
  FAO book at `https://www.fao.org/3/y2783e/y2783e.pdf`, all `BOOK_CHAPTER`, 2002, no DOI: S04 by
  C. Renuka (15 citing facts), S39 by Walter Liese (15) and S40 by Terry C.H. Sunderland and John
  Dransfield (5). `SourceMerge` joined any two records on an address unless two DOIs differed, so
  an answer citing S39 and S40 listed every quote under the first chapter's title and author.
  Supplementary GI Journal 1 holds the applications of Agates of Cambay, Konark Stone Carving,
  Machilipatnam Kalamkari and Orissa Pattachitra at one address, and GI Journal 54 those of
  Firozabad Glass and Kanpur Saddlery, so a comparison answer named one craft's application for
  another's quote. A record was also compared with the first work holding its first matching key
  only, so refusing that work would have kept a second record of the same chapter apart from it.
- **One subject was written onto every differing pair.** The duplicate gate kept the first named
  `about` of its DIFFERS pairs, and `mark_sources_differ` and `settle_sources_differ` write that
  one subject onto the candidate and every held fact it differs from. A candidate that differs from
  fact A on the resist paste's ingredients and from fact B on the dyeing time showed B as "Sources
  differ on: Resist paste, ingredients".

## Decision

1. **An unscored question breaks a whole run's floors.** `coverage_eval.unscored_questions(report)`
   lists the ids of the questions with no rubric score or no judge's share, and
   `floors_hold(report, checks)` holds only when no floor is broken and that list is empty. The
   printed line carries it as `unscored`, `belowFloor` is `floorsApplied and not floors_hold`, and
   `eval_run_store.answers_record` stores `floorsHeld` by the same rule. The means stay the means of
   the scored questions, so a run's numbers still compare with earlier runs'. Scoring a failed
   answer 0 in the means was the alternative; it changes what every stored mean measures, and one
   failure in 24 at 0.93 still leaves 0.89, above the 0.88 floor. A partial or stopped run is still
   never compared, and the exit status is unchanged.
2. **Research for any craft is filed by the same naming rules.** With no craft researched,
   `craft_filing` reads the sentence, its passing quotes, their passages and the cited sources'
   titles in that order, and the first level that names something decides: one catalogued craft
   takes the fact (`CraftFiling(slug)`), several refuse it (`SKIP_SEVERAL_CATALOGUED`, now worded
   "names {crafts}, so no one craft's page can hold it", true with or without a craft researched),
   and a place outside India or another culture's practice as where it is practised refuses it
   (`SKIP_ABROAD`). What names neither stays on the shared concepts: a held fact needs the craft it
   is suggested for, and there is no family to share. Screening stored `CLAIM` candidates of linked
   shared concepts in `off_question.screened_request` was the other route; it reaches only rows
   already written and would need a second naming pass at answer time.
3. **An address alone joins only what nothing says apart.** `SourceMerge` compares a record with
   every work that already holds one of its keys, in key order, and joins the first that is the
   same work. A DOI key still joins (unless two DOIs differ). An address or title key never joins
   two records that both state authors and share no surname either way round
   (`research/evidence.shares_an_author`, the rule a supplied source's identity check already used,
   now its one home), and an address key never joins two book chapters or two GI journal entries
   (`PART_KINDS`) whose title keys differ. So the three FAO chapters stay three works, a second
   record of Liese's chapter still joins it, and each GI application keeps its own title.
4. **A duplicate outcome names a subject only when every pair names it.** `_compared` keeps `about`
   when all its DIFFERS pairs name the same subject, and none when they name different subjects or
   one names none. Storing each pair's subject (a held-id-to-subject map on `CandidateCheck`, read
   by `candidate_writes` and `sources_differ`) was the fuller alternative; it needs a migration and
   a release the live side can read, so naming nothing rather than the wrong thing comes first.

## Consequences

- The next whole answer-quality run in which any answer fails, times out or goes unjudged fails
  and keeps the issue open, and its `unscored` names the questions to look at.
- An answer or craft page that cites several chapters or GI applications behind one address lists
  each: Cane-Bamboo-Craft's three FAO chapters, the four applications of Supplementary GI Journal 1,
  the two of GI Journal 54, and the Mahabalipuram application beside the Stone family's record of
  all of GI Journal 99. Two records of one page titled differently as chapters, one by the book's
  title and one by the chapter's (the FAO lacquerware case study at `x5859e04.htm`), are two
  entries where they were one.
- Rows written before this record stay as they are. Any-craft write-backs already on linked shared
  concepts are found by the filing report (`python -m app.scripts.write_back_filing`), which now
  says where today's rule would file each; a `CandidateCheck` with several related facts may still
  hold the first pair's subject, and `Claim.differsOn` keeps what it wrote. Both need a production
  read, which this record leaves to the lead.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/answering/test_answer_floors.py`, `backend/tests/write_back/test_write_back_names.py`,
`backend/tests/write_back/test_write_back_plan.py`, `backend/tests/ledger/test_source_merge.py` and
`backend/tests/knowledge_writes/test_candidate_gates.py`.
