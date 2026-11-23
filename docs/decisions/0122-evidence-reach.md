# 0122. Evidence the knowledge base holds reaches the answers that need it

A craft's answers now read its family's science and the knowledge of the crafts merged into it, a
concept is named only by whole words, every expert seat reads the kinds of source its work rests on
and fills its share with them, no search ranks passages it then throws away, and a reader's
question closes only when facts that answer it arrive.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21, on the audit of the answer pipeline: "yes,
run all five lanes"). The contracts are `docs/contracts/retrieval.md` (The search, Expert seats),
`docs/contracts/answer-eval.md` (Seats by field) and `docs/contracts/open-work.md` (step 6 of the
nightly gap check). It amends the acceptance rule of [decision 0113](0113-questions-become-work.md),
item 3.

| For | Read |
|---|---|
| How a craft's scope, the rankings and the seats search | [retrieval.md](../contracts/retrieval.md) |
| The source kinds each seat reads | [answer-eval.md](../contracts/answer-eval.md), Seats by field |
| When a reader's question closes | [open-work.md](../contracts/open-work.md), the nightly gap check |
| The expert panel and its reading order | [0046](0046-expert-panel.md) and [0099](0099-wider-expert-panel.md) |
| A craft's scope also reads the shared concepts its glossary terms or concept edges link to it | [decision 0179](0179-transcript-windows-a-chunk-kind-linked-shared-concepts-and-one-paid-clip.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Four read-only reviewers audited the answer pipeline on 2026-11-21 and the lead verified six faults
in the code, each one evidence the knowledge base already held that an answer never used, or work a
search did and threw away.

- **Family science never reached a craft.** A craft's scope read its own concepts and the shared
  concepts of its sub-category. A category dossier writes its concepts with neither a craft nor a
  sub-category, so the 2,029 facts of the nine category dossiers (Textiles 236, Metal 249, Mud 240,
  Natural fibre 243, Paper 242, Wood 236, Stone 216, Miscellaneous 204, Leather 163) were outside
  every craft's search, although the craft page shows exactly these facts as its family science.
  "Why does Bagru use alum?" could not cite the textile mordant chemistry the Bagru page shows. A
  craft merged into another kept its concepts under its own id, so its knowledge left the surviving
  craft's answers too.
- **The experts dropped facts by source kind after the cap.** Each seat searched 12 hits and then
  kept only facts citing a kind it lists. `OTHER` and `BOOK_CHAPTER` were listed by no seat, and
  `WEB_PAGE` by four. Of 4,210 curated craft facts, 844 cite only `OTHER` or `BOOK_CHAPTER` sources,
  and 1,481 could be read by no seat at all, by field and kind together. The Chemist lost 970 of the
  1,486 facts in its fields, the Historian 519 of 1,119. A dropped slot was never refilled.
- **The seat queries were padded.** Each seat searched its question with the craft name, its label
  and its field titles ("Historian History Overview"). The fields already filter; the padding pulled
  every seat's vector toward one generic point and added common words to the full-text query.
- **A concept name matched inside other words.** The entity ranking used `strpos`, so "leading"
  named Lead, "chemicals" Mica, "thousand" Sand, "formation" Mati, "carnelian" Neli, "pattachitra"
  Atta and "channapatna" Patna, and a longer false match outranked a true one.
- **Passage rankings ran for nothing.** In `HYBRID` and `DEEP` a search ran up to four passage
  rankings. The facet coverage, the seats and the gap check read only the claims. The facet coverage
  also searched its facets one after another.
- **Reader questions closed without an answer.** A gap counted as answered when each of its fields
  had 2 hits: for an English question any hit sharing one word ("use", the craft's name), for a
  question in another script any vector hit at all, and a fact with no field counted for every
  field. "Why does Ajrakh use camel dung?" closed the next night on two facts containing "Ajrakh".

## Decision

1. **A craft's scope reads its family science and its merged crafts** (`hybrid.craft_scope`,
   `CraftScope.category_id` and `merged_ids`). The family is found by the link the page already
   uses: the craft's sub-category's category, and the claims `CuratedCategoryClaim` marks for it;
   their subjects are the family's concepts. The shared concepts named as the category is (where
   the category's contributed facts are written) count too. Merged crafts are followed through
   `Craft.mergedIntoId` for up to 5 hops. No schema changes and no concepts move. Only the stored
   search builds this wider scope; the page stamp, the review queue, the candidate gates and
   `knowledge_view` keep the narrow one, so no page, stamp or queue changes.
2. **Names match as whole words.** The entity ranking keeps `strpos` as a cheap first test and then
   requires the name, its regular-expression characters escaped, to have no letter, digit or
   underscore right before it or right after it, an English plural ending `s` or `es` aside
   (`(?<!\w)name(?:e?s)?(?!\w)`). Multi-word names, glosses and native names match as before; the
   plural keeps "blocks" naming Block.
3. **Each seat reads the kinds its work rests on, and filters before the cap.** Every new kind is
   added after a seat's earlier kinds, so its live reading order (decision 0046) is unchanged.
   `KnowledgeQuery.sourceKinds` keeps only claims citing a visible source of those kinds inside
   every ranking, so a seat's 12 hits are all facts it may use. The seat still checks its kinds
   against the citations the reader may read.
   - `BOOK_CHAPTER` goes to every seat that reads books or papers: a chapter in an edited volume or
     proceedings (the FAO's rattan species profiles, the ethnoarchaeology of Khambhat beads, the
     NIAS study of the Bidri patina) is the same scholarship as the book or paper it sits in. The GI
     and policy expert and the artisan's voice read neither, and do not get it.
   - `WEB_PAGE` goes to the seats whose fields institutional pages describe: design schools' and
     craft bodies' process pages (D'source, Khamir, Global InCH) for the Chemist, Physicist,
     Materials scientist and Technologist; district and forest pages for the Geologist and
     Botanist; museum and heritage pages for the Historian; scheme and trade pages for the
     Economist and the GI and policy expert. The Anthropologist, Design historian, Conservator and
     artisan's voice already read them. The Hydrologist, Soil scientist, Climatologist, Ecologist and
     Toxicologist do not: their evidence is measured data and hazard records.
   - `OTHER` holds museum object records (the V&A's accession records), magazine and newspaper
     reports (Down To Earth, The Hindu, Mongabay) and court judgments. It goes to the Historian,
     Design historian and Conservator (dated, described objects), the Materials scientist (what a
     catalogued piece is made of), the Technologist (trade bodies' and technical magazines' process
     notes), the Anthropologist and Economist (reportage of communities, prices and livelihoods), the
     Hydrologist and Ecologist (environmental reporting and pollution judgments) and the GI and
     policy expert (registrations and judgments as reported).
   - `GI_JOURNAL` also goes to the Chemist, Physicist and Materials scientist: the registered method
     of production is the formal record of a craft's process, and 1,032 curated facts quote it.

   Every kind is now read by at least one seat. The curated craft facts no seat can read, by field
   and kind together, fall from 1,481 to 385; the Chemist keeps all but 345 of its 1,486, the
   Historian all but 86 of its 1,119.
4. **A seat searches its question and its craft only.** `seat_query` words the search with the
   answer's English question and the craft name; the fields and the kinds are filters.
5. **A search can skip its passages.** `KnowledgeQuery.passages` (default true) false runs no passage
   ranking. The facet coverage and the seats set it. The facet coverage searches its facets at once;
   one `StoredKnowledgeSearch` lets searches sharing its session take turns, so a caller on one
   session (the coverage enrichment script) stays safe.
6. **A reader's question closes only on facts that answer it.** The nightly check counts, per field,
   the craft's facts (family science and merged crafts included) filed under that field, never an
   unfielded one, that match the question. An English question matches by its rare words: its
   terms less the craft's name and common words, of which a fact's text-search vector must hold 2,
   or the only one. A question in another script, or with no rare word left, matches by meaning: a
   cosine similarity of at least 0.6 to the question's vector, the floor at which the craft finder
   already takes a question to mean a stored text by meaning alone (same embedder, same query and
   document templates). The check counts directly and runs no search, so it ranks no passages.

## Consequences

- An answer about a craft can cite its family's chemistry, physics and materials with the family's
  own sources, as its page does; a merged craft's facts stay in the survivor's answers. The golden
  question `farrukhabad-family-mordants` asks an uncurated block-printing craft what only the
  textile family's mordant facts answer; it is scored against the live database, where the
  category dossiers are imported.
- Questions that used to name a stray concept inside a longer word lose that false entity rank;
  retrieval's recall and reciprocal-rank floors (`backend/tests/db/test_retrieval_eval.py`) still
  hold.
- Seats speak from many more of the facts in their fields, and the 12 hits a seat asks for are no
  longer wasted on kinds it would drop.
- A planned question costs fewer queries: no passage ranking for the coverage or the seats, and the
  facet searches run together.
- Gaps close later and only for cause: a question needs facts that name its own subject.
- Not changed here: the stored-only fallback answer (`answer_store.stored_claims`) reads
  `knowledge_view.claims_for`, whose scope is still the narrow one.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/db/test_evidence_reach_db.py`, `backend/tests/db/test_entity_names_db.py`,
`backend/tests/db/test_gap_acceptance_db.py`, `backend/tests/retrieval/test_statements.py`,
`backend/tests/retrieval/test_seat_fields.py`, `backend/tests/retrieval/test_search_turns.py`,
`backend/tests/planner/test_facet_coverage.py` and `backend/tests/research/test_open_work_gaps.py`.
