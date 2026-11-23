# 0138. An answer researches the fields it is asked first, tells one fact once across sections, and cites only passages about its craft

An answer hands its research budget to the fields the question asks and the craft holds few facts
in, caps the fields it was not asked, files a craft's GI record under policy, tells a fact once
however many claims carry it, routes every admission of a gap to the open questions, offers the
composer no passage about another craft or a place abroad, rewrites once what its write-back could
not keep, and reads each document once per answer.

Date: 2026-11-22. Status: accepted (the lead's debt-clearing brief of 2026-11-22, answer composition
lane, from the answer judge of run 44994632550 and the live Khurja test of answer
504968ea-49cc-469c-88f9-205a2ea90e8a). It amends [decision 0127](0127-coherent-answers.md) (the
restatement rule), [decision 0032](0032-sectioned-composition.md) (the even budget split and the
dropped block) and [decision 0010](0010-composer.md) (the composer's candidates). The contracts are
`docs/contracts/research.md` (the planner, the composer, the answering service),
`docs/contracts/explainer.md` (One claim, one rendering; No gap on the page; seasons) and
`docs/contracts/answer-eval.md` (the rubric).

| For | Read |
|---|---|
| The restatement rule it widens | [decision 0127](0127-coherent-answers.md) |
| The sectioned composition it re-budgets | [decision 0032](0032-sectioned-composition.md) |
| The composer whose candidates it fills | [decision 0010](0010-composer.md) |
| The naming rule it reuses | [decision 0135](0135-write-backs-filed-under-the-craft-they-name.md) |
| The evaluation that found the faults | [answer-eval.md](../contracts/answer-eval.md) |
| The asked fields are the ones the understanding's reply marks as asked | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The judge of run 44994632550 (13 DETAILED answers on production) scored 0.815 against a floor of
0.85. Its notes named the same faults again and again: one fact told twice across sections (the
1971 Gazetteer figures in the Bandhani GI answer, the 1625 miniature in the Bidri history answer,
harde, kut and alizarin in the Ajrakh dye-plants answer); answers padded with process and history
while asked fields stayed thin (no ecology in the Ajrakh water and climate answer, no physics in the
Jaipur glaze answer, the Bandhani GI record filed under economics); a sentence admitting it had no
rainfall, temperature or seasonal detail that the gap pattern missed. The live Khurja answer added
two more: four expert seats wrote an honest gap that grounding then dropped for adding a negation,
and the answer cited passages about Jaipur blue pottery and a Nigerian porcelain study. The
register also held the open parts of decisions 0010 and 0032: an even budget split, a section's
reads repeated by another section, a claimless sentence lost without a second try, a status line
counting only the first section, and schema limits that had become prompt lines.

## Decision

1. **One fact, once, across sections.** The ledger's restatement rule (`services/restatements`)
   keeps decision 0127's rules and adds two. A later sentence states the same fact when it states
   exactly the same numbers with the same units (`sentence_support.figure_units`) as an earlier one
   and half or more of its content stems, less its unit words, are shared ("about the same
   subject"); or when every passage it cites overlaps a passage of the same source the earlier one
   cites (one contains the other, or they share a run of six words) and three tenths of its stems
   are shared. The first stays. Different evidence no longer makes a sentence new when its figures
   and subject are the same; two steps that take the same time keep both, since their subjects
   differ.
2. **The budget goes where the question asks.** The understanding records the fields the question
   itself asks (`Understanding.asked`, before the depth's floor fills it with held fields). Before
   any plan call, each section is ranked: an asked field the craft holds fewer than three curated
   facts in (`stored_fields.FIELD_CLAIMS_MIN`) is thin and first, another asked field next, a field
   the question did not ask last (`services/section_fields.SectionFields`). The depth's budget is
   shared among the highest rank present and the rest start with none
   (`research_ledger.first_shares`); what a section leaves still reaches the later ones
   (`take_section`, decision 0123). Sections start in rank order; a thin field's first research is
   `fresh`, so live research runs even when weak coverage says its facets are covered; a field not
   asked writes at most half the depth's section sentences. We chose this over planning every
   section first, as the register proposed: the field counts are known before any plan, and a plan
   first would need either a second plan call per section or the planner's research split in two.
3. **The GI record is policy.** When an answer has both an economics and a policy section, the
   market block's GI record and signs of imitation are built in the policy section and its prices in
   the economics one (`market_builder.section_parts`, from `BuildAsk.answer_fields`); with one of
   them, that one shows all three. The once-per-answer seasons block is built by the climate section
   when the answer has one (`BuilderEntry.prefers`), and a climate section whose facts name no month
   shows its district's CHIRPS normals alone (a rain-only seasons block).
4. **A gap is an open question, from any author.** The gap pattern reads "no ... detail" (up to
   five listed words) and "statements, records, texts, passages, studies or findings do not say,
   name, give ..." (`research/gap_admissions`). A section or seat sentence that admits what its
   sources lack (`SOURCE_GAP`) may carry the negation of that admission and no other
   (`drafts.checked_block_sentence`); routed by `gap_routing`, it becomes an open question with its
   citation. Seats are told a gap is never part of their view. The lede, voice and terms keep the
   strict check: nothing routes their gaps.
5. **Passages about another craft or a place abroad are not offered.** The section's live and
   field passages are read with the write-back's naming rule (`write_back_names.CraftNames`): one
   that names no craft researched but names another catalogued craft or a place abroad is left out,
   or, in a comparison, labelled "about X, not the craft asked about: cite only to compare"
   (`services/off_question`). Stored claims are not screened; their filing is the write-back's. The
   evaluation counts shown sentences whose citation quotes are such passages
   (`AnswerMeasures.offQuestion`), and the rubric's everyCited part is 0 when any is.
6. **The composer sees what a claim rests on and what was asked.** A stored claim is offered with
   its citations' quotes as passages and its sources' titles and years in its label
   (`candidates.ClaimSupport`, from the claims the section already reads for its trail); the pack
   records every live searcher asked (`EvidencePack.searched`), which the research summary lists.
   Stored passages that are not field voices stay out of the candidates: a sentence citing one
   could not be kept, because the write-back keeps only read documents and field voices.
7. **A late failure is rewritten once.** A sentence dropped after its write-back while it cited
   evidence (its source not kept, its figure or name not in what was) is named to the composer once
   more, with the section's stored claims only, through the regenerate prompt
   (`ComposeRequest.refused`, `services/section_rewrite`); what passes joins the section's prose.
   Dropped sentences are logged by reason.
8. **One read per document per answer.** The answering service holds a `planner/reading.ReadCache`
   keyed by evidence id and passes it to every section's and seat's research; a second section
   awaits the first read instead of fetching again.
9. **Smaller fixes.** The status line sums the sections' counts while a step is current
   (`ExplainerStream.status`); the whole-answer reply is trimmed to six sections of eight sentences
   and five follow-ups (`drafts.AnswerForm`), and a translation longer than an item may be is
   refused and asked again.

## Consequences

- No migration. `Understanding.asked` is left out when empty, so stored understandings still read;
  an understanding without it treats every field as asked.
- An answer whose craft has no curated facts treats every asked field as thin: all research fresh,
  the budget split among them as before.
- More near-duplicates are held back. A rare pair of different facts with the same figures and much
  the same words loses its second sentence.
- An answer about one craft no longer cites a page about another, which may leave a thin field
  thinner; a page naming no craft and no place (a commercial kiln schedule) is still offered.
- A rewrite costs one more compose call in a section that lost a sentence to its write-back.
- The voice turn still passes no form to `parsed_answer`; its file is the voice lane's (the register
  keeps that part).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/ledger/test_near_duplicates.py`, `backend/tests/answering/test_asked_fields.py`,
`backend/tests/answering/test_off_question.py`, `backend/tests/answering/test_refused_rewrite.py`,
`backend/tests/answering/test_status_line.py`, `backend/tests/experts/test_seat_gaps.py`,
`backend/tests/research/test_gap_admissions.py`, `backend/tests/composer/test_candidates.py`,
`backend/tests/composer/test_answer_form.py`, `backend/tests/planner/test_read_cache.py`,
`backend/tests/planner/test_searchers_asked.py`, `backend/tests/place/test_seasons.py` and
`backend/tests/db/test_answer_plans_migration_db.py`.
