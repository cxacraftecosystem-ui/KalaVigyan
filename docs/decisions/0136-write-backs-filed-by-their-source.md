# 0136. A write-back is filed by what its source says around it, and what nothing names waits for a reviewer

Live research files a fact by reading, in order, its sentence, its quotes, the passage each quote
sits in and its sources' titles; holds what none of them names for a reviewer instead of dropping
it; keys and gates a family's science by its family; titles a candidate as the stored facts are
titled before the duplicate gate embeds it; and lists where every live-research fact would be
filed today without changing any.

Date: 2026-11-22. Status: accepted (the lead's round 7 brief, write-back-by-source lane, on the
owner's direction that good findings must not be refused because their own sentence does not
name the craft, and must be fixed durably, not patched). It amends
[decision 0135](0135-write-backs-filed-under-the-craft-they-name.md), items 3 and 5, and the
family-science consequence. The contracts are `docs/contracts/research.md` (The writer and the
coverage job), `docs/contracts/knowledge-writes.md` (The gates, in order; The research
write-back) and `docs/contracts/review-queue.md` (Decisions).

| For | Read |
|---|---|
| The filing rule it amends | [decision 0135](0135-write-backs-filed-under-the-craft-they-name.md) |
| The write-back rules 0135 amended | [decision 0124](0124-live-research-write-back.md) |
| The family science a craft's answers read | [decision 0122](0122-evidence-reach.md) |
| The titled stored facts the duplicate gate compares with | [decision 0129](0129-first-stage-retrieval.md) |
| How a fact's craft is chosen | [research.md](../contracts/research.md), The writer and the coverage job |
| Held write-backs, family keys and the filing report | [knowledge-writes.md](../contracts/knowledge-writes.md), The research write-back |
| Filing a fact under another craft | [review-queue.md](../contracts/review-queue.md), Decisions |
| A one-word alias that is an ordinary English word or shared by three crafts' names names no other craft (amends item 1) | [decision 0144](0144-stored-passages-as-evidence.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0135 filed a fact under a craft only when the sentence or its quote named the craft. On
the Khurja live test (answer 504968ea-49cc-469c-88f9-205a2ea90e8a) that kept the Khorezm,
Nigerian and kiln-schedule sentences off Khurja's page, but it had two costs the owner would not
accept. A good finding was refused because its own sentence did not name the craft: "the clay is
aged for two days", from a study of Khurja pottery, named neither Khurja nor its place, so it
was dropped. And a Khurja-specific chemistry sentence that did not say "Khurja" was filed as the
clay family's general science. A source's paragraph and title usually say what a sentence is
about when the sentence does not. Facts the rule could not place were discarded with only a log
line, family-science facts were keyed and compared as all shared knowledge, the duplicate gate
embedded candidates without the titles the stored facts carry since decision 0129, and the
places that refuse a fact were a hand-kept list nothing checked.

## Decision

1. **The filing reads the source around the quote.** `write_back_crafts.craft_filing(FilingTexts,
   *, field, names)` reads four levels in order: the sentence, its passing quotes, the passage each
   quote sits in within its cited document, then the cited documents' titles. The passage
   (`write_back_passages.passage_around`) is the paragraph holding the quote, split on blank lines;
   when the text has none or the paragraph is over `PASSAGE_MAX_CHARS` (1,200 characters, about
   two hundred words: a long paragraph, beyond which the context names what the sentence is not
   about), it is the quote's own sentences and their neighbours, one before and one after at a
   time, while the passage stays within the bound. At every level the precedence of decision 0135
   holds: two researched or compared crafts named refuse the sentence; the researched craft (or a
   compared one) named takes it; else exactly one other catalogued craft named takes it, and
   several refuse it; else a place abroad refuses it. Field-interview documents give their quotes,
   as before, but no passage or title, so a field voice places a fact only through its own words,
   and a sentence resting on field interviews alone stays with the craft researched.
2. **A place of India in the sentence's own words decides before its context.** When the text
   and quotes name no craft but a place of India (a state included), the sentence is about that
   place: it is held (item 3) before its passage or title is read, so a study's title cannot file
   "In Uttar Pradesh, kaolin is fired white" under the craft it studies. A place of India named
   only in the passage or the title holds the fact only when no level names a craft: a Khurja
   study's paragraph that mentions where its clay is dug does not take the fact off Khurja.
3. **What nothing names waits for a reviewer.** Only after every level does the family rule apply:
   chemistry, physics or materials naming nothing goes to the family's science. Anything else
   that names no craft (`HELD_UNNAMED`), or a place of India but no craft of it
   (`HELD_OTHER_PLACE`), is held: a `ClaimWriteBack` under the craft researched, its suggestion,
   with `heldBecause`. It passes the same gates and is written `DRAFT` whatever the review switch,
   with a `ReviewEvent` by `live_research_held` whose note names the reason and the suggestion.
   `DRAFT` is the existing hidden, waiting state: retrieval and readers never see it
   (`HIDDEN_CLAIM_STATUSES`), the review queue lists it because it has `CandidateCheck` rows, and
   the duplicate gate counts it as held. No table, column or migration was needed. A held
   sentence keeps no claim on the answer and refreshes no page; its gate vector is kept for the
   duplicate gate, which retrieval never reads for a `DRAFT` fact. A held sentence that another
   sentence of the same answer files is one filed fact.
4. **A reviewer's one decision files it.** Approving a fact in the review queue with `craft`
   moves it to that craft's concept of the same type and name and approves it in one decision
   (`review_queue_refile.refile_fact`); approving without `craft` files it under the suggestion;
   rejecting drops it. The route refreshes the pages the fact leaves as well as those it reaches.
   The same decision re-files a fact filed before decision 0135.
5. **Family science is its family's.** `ClaimWriteBack.categorySlug` carries the family's
   category. The dedupe key's owner is `category:<slug>`, so the same general sentence found for
   two families is one fact per family, and its duplicate, novelty and closed-fact checks read
   that category's facts (`candidate_store.owner_subject`, a `FactSubject` of kind `category`),
   not every shared fact. Write-backs for a craft and for no craft keep their keys.
6. **Candidates are embedded with the stored facts' titles.** `Candidate.title` (owner, concept,
   field, `candidate_store.subject_title` over `retrieval/text.context_title`) is embedded with the
   statement (`candidate_gates.candidate_text`): a write-back by its craft or category, its facet's
   concept and its field; a fact proposal by its subject, which is also its concept, and its field.
   Structure proposals run only the gates that read no vector, so they carry none. A titled
   paraphrase of a stored fact reaches the vector-twin floor (0.97) again.
7. **The places abroad cannot silently miss a country.** `data/places_abroad.natural_earth.json`
   vendors the sovereign names of Natural Earth's admin-0 sovereignty layer (version 5.1.2, public
   domain); a test holds each to a country of `places_abroad.json` or to its new `leftOut` map,
   where every name left out says why (Mali, Tonga and the rest of 0135's list). Somaliland,
   Northern Cyprus, the Democratic Republic of the Congo and the long forms Natural Earth uses were
   added.
8. **A read-only filing report.** `python -m app.scripts.write_back_filing [--answer <id>]
   [--since <date>]` re-runs today's filing on each live-research fact's statement, quotes, stored
   passage and source titles, for the craft its answer researched, and prints where each is
   against where it would be, and which facts have no gate checks. It writes nothing.

## Consequences

- More facts are filed under the craft researched: a sentence a Khurja study's title or paragraph
  places goes to Khurja, and its chemistry goes to Khurja rather than to the family. A general
  handbook's chemistry still goes to the family, and its process sentences wait for a reviewer.
- A sentence whose paragraph names two compared crafts is now refused where 0135 sent it to the
  family: the passage says it is about both.
- Reviewers gain work: every write-back that names nothing waits in the queue as a `DRAFT`
  researched fact. The review page shows it as any waiting fact of the suggested craft; it does not
  yet show the hold's reason or offer another craft, which the API takes (`docs/TECH_DEBT.md`).
- A held write-back found again later by a sentence that does name the craft is re-found under the
  same key and stays `DRAFT` until a reviewer decides it.
- No migration and no stored fact changes: the 19 Khurja facts and the older write-backs stay as
  they are until a reviewer acts on what the filing report lists.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/write_back/test_write_back_context.py`, `test_write_back_names.py`,
`test_write_back_passages.py`, `test_write_back_filing.py`, `test_candidate_titles.py` and
`test_write_back_filing_report.py`, `backend/tests/review_queue/test_review_queue_routes.py`, and
`backend/tests/db/test_held_write_backs_db.py`, `test_write_back_filing_report_db.py` and
`test_review_queue_refile_db.py`.
