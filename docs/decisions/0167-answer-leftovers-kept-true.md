# 0167. A stopped answer is marked, a quote in an Indian script is read in English, a term keeps its local name, and a page curates its signs of imitation

An answer whose stream stops before it finishes is marked stopped instead of left empty; the
composer reads a failing sentence's quotes in an Indian script through one bounded English
rendering; a Hindi answer keeps its quiz on its terms' Hindi names, and a name in an Indian script
is marked only as a whole word; a glossary term carries the casing its texts write it in; a dossier lists its signs
of imitation; every scholarly adapter names a paper's journal; the planner reads a closed DOI from
the publisher that holds it and searches the colourant oxides when a question asks what gives a
glaze its colour; and a Professor places a process stage answers found into its craft's process from the review
queue.

Date: 2026-11-23. Status: accepted (the lead's answer-leftovers lane brief of 2026-11-23, round 7's
debt-clearing programme). It amends [decision 0039](0039-pictures-and-terms-wired.md) and
[decision 0089](0089-expert-depth-caps-and-answer-routes.md) (term spans in a translation),
[decision 0066](0066-local-measures-and-market-gi.md) (signs of imitation),
[decision 0120](0120-grounded-sentences.md) (a seat kept for its difference),
[decision 0138](0138-answers-composed-from-the-asked-fields.md) (one fact once across sections),
[decision 0139](0139-sources-and-providers-reach-outside-services-once.md) (quote renderings and
publisher full text), [decision 0143](0143-lessons-exports-and-follow-ups-kept-true.md) (the journal
a paper is in), [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) (the answer
record) and [decision 0151](0151-a-release-the-live-side-can-read.md) (a review kind the live web does
not know). The contracts are `docs/contracts/research.md` (the composer, the planner, the answering
service), `docs/contracts/explainer.md` (term spans, the supply map, the market block),
`docs/contracts/curation.md` (Market and GI, the glossary), `docs/contracts/craft-page.md` and
`docs/contracts/review-queue.md` (the `STAGES` kind).

| For | Read |
|---|---|
| Term spans kept in a translation | [decision 0039](0039-pictures-and-terms-wired.md) and [decision 0089](0089-expert-depth-caps-and-answer-routes.md) |
| The imitation word list | [decision 0066](0066-local-measures-and-market-gi.md) |
| A seat kept for its difference | [decision 0120](0120-grounded-sentences.md) |
| One fact once across sections | [decision 0138](0138-answers-composed-from-the-asked-fields.md) |
| Quote renderings and publisher full text, built and not yet asked | [decision 0139](0139-sources-and-providers-reach-outside-services-once.md) |
| The journal a source stores | [decision 0143](0143-lessons-exports-and-follow-ups-kept-true.md) |
| The answer row and its request id | [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) |
| What the live web ignores | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| The answer regression this lane kept the cost line of | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Twelve entries of `docs/TECH_DEBT.md` were left after round 7's lanes, and the lead found a new
fault on production: nine `Answer` rows with no payload and no sections, every one a production
check whose stream closed after about 11 seconds (answer 943e22ff, request 861d96b4542bebc7824ab8b5).
The row is begun before research and written at the finish; a stream the client closes cancels
the answer between the two. Several entries needed a choice the register did not make: whether a
stopped row is deleted or kept, where a curated imitation list is stored, how a quote's language is
known when no evidence item records one, which local name a translated sentence may carry, and how
a glossary term's sentence-case name is found when no dossier states it.

## Decision

1. **A stopped answer is marked, not deleted.** `Answer.stoppedAt` (migration 0090) is set for the
   request's rows that have no `latencyMs` when anything stops the answer after it began: a
   cancelled stream, a failed research, a lost version (`answer_stops.stopped_unless_finished`
   around `answering._answer`, `SqlAnswerStore.stop(request_id)`); `finish` clears it. We chose
   marking over deleting: a deleted row would take its usage rows, kept pieces' and write-backs'
   answer links and its saved items with it, and the cost the nightly upkeep settles would lose its
   row. A stopped row has no explainer, so the history already leaves it out; the open-work demand
   and the piece rebuild's asks do not count it. The migration marks the rows of more than an hour
   ago that never finished.
2. **A failing sentence's quotes in an Indian script are rendered once per draft.** After the first
   draft and before any regenerate, the quotes of its failing sentences written in a script of an
   answer language other than English go to `quote_renderings.english_renderings` in one call of
   the `TRANSLATE` route's `ModelTranslator`, at most `RENDERED_QUOTES_MAX` (8) per draft. A quote's
   language is its script's when one answer language writes it (Gujarati, Tamil, Urdu), else the
   language its source id names (`wikipedia:hi:<page>`), else it is not rendered: we did not guess
   Hindi for every Devanagari quote, since the rendering's stance check reads the source language's
   negations and hedges. A sentence passing the checks on the rendering is kept, citing the verbatim
   quote; one that still fails goes on to the regenerate. The extra work is bounded: one
   `TRANSLATE` call (two with its translator's retry) per draft with such a failing quote, at most
   8 quotes of at most 300 characters, about 2,400 input tokens with the prompt and about 700 output
   tokens; an English answer on English sources makes none.
3. **A Hindi answer keeps its quiz on its terms' Hindi names.** This lane first kept a translated
   span by a term's stored local name through a glossary read of its own; the pictures lane
   ([decision 0166](0166-pictures-terms-and-stored-pieces-kept-true.md)) shipped the same rule on
   the answer's glossary (`Enrichment.term_names`: label, aliases and local names, a whole word in
   any script), so we dropped ours and hold that the quiz, built from the translated spans, keeps
   the questions whose terms have Hindi names. We chose occurrence over a language field on each
   local name: a name the translated sentence shows is in that sentence's language. The term
   marker reads a word of an Indic or Arabic script through its vowel signs and marks
   (`term_marking.WORD_CHARS`), so नील is not marked inside नीला. No model call or read is added.
4. **A glossary term carries the casing its texts write it in.** `Term.sentenceName` is the casing
   its meaning and its concepts' claims write it in most often away from a sentence's start
   (`research/sentence_names.sentence_name`), filled after every curated import for each term that
   has none; a term never written there keeps none. The supply map carries it as a link's
   `material`, and the web keeps a later name as carried ("Indigo and alum"). We chose reading the
   stored texts over a new dossier field, which every dossier would have to fill by hand.
5. **A dossier lists its signs of imitation.** `market.imitation` lists claim ids, each citing a GI
   journal, kept with the GI record (`CraftGiRecord.imitationClaimIds`, so `market.gi` is given);
   the market block shows them first, in their order, then what the word list finds, at most three.
   We chose the GI record's column over a table of its own: a sign of imitation is evidence the GI
   journal gives, so a dossier without a GI record has none to list.
6. **Every scholarly adapter names the journal.** Crossref, OpenAlex (a journal, conference or book
   series source only, never a repository), DOAJ, Springer Nature, Elsevier, CORE, Europe PMC and
   Semantic Scholar fill `container_title` (`sources/records.journal_of`), which retires
   `JOURNAL_AS_PUBLISHER_ADAPTERS`; each `publisher` is unchanged. `app.scripts.source_journals`
   reads the journal of each stored source with a DOI and none from Crossref, storing it only with
   `--write`.
7. **The planner reads a closed DOI from its publisher, and searches the colourant oxides.**
   `LiveSources.publisher` is the registry's `PublisherFullText`; a DOI the locator calls closed is
   read from the publisher holding its prefix. A question asking what gives a glaze, glass, enamel,
   pigment or pottery its colour adds one query per tier the model used, naming its hues and the
   oxides of cobalt, copper, iron, manganese and chromium, inside the mode's query limit, so it adds
   no model call.
8. **One fact is told once, one heading is shown once, and no sentence names our internals.** The
   lead's comparison of Opus and Sonnet on release 987e94c5 found three faults. In Ajrakh's indigo
   answer (a5af3bee) MATERIALS retold CHEMISTRY's leucoindigo sentence from the same passage:
   `restates` returned early for a pair of one claim group short of half its stems, so decision
   0138's three-tenths passage rule never ran; it now falls through. Two PROCESS expert seats whose
   takes the earlier sections had said in full were kept whole for their difference; a seat left
   with no take now goes, and its differences with it (amending decision 0120's keeping, at the
   lead's word). The GEOGRAPHY timeline's only entry retold its prose (the 2001 move to Ajrakhpur)
   and was spared to stand; a `timeline_map` left with nothing new now goes, while a `region_story`
   stays for the rivers and districts its map draws. Three
   sections carried one composed heading; a heading is now one section's per answer
   (`ExplainerStream.claim_heading`, folded), and a later section keeps its own title. In Bidri's
   answer (cf252138) an overview sentence said "The stored statements say ..."; a composed sentence
   naming our internals now fails the composer's check (`INTERNAL_WORDS`) and goes to the
   regenerate. Bidri's MATERIALS had no section because the understanding never listed it, not for
   want of facts (Bidriware holds 11 approved MATERIALS facts): its prompt now says what MATERIALS
   covers, about 15 input tokens per answer. We left the lede's claims out of the repeat rule:
   sections expand what the lede says in brief.
9. **No rule orders the seed's four unordered stages.** The seed holds no `PRECEDES` edge joining
   them to their crafts' ladders (its only one among them says Akola's mud soaking precedes paste
   preparation), so a rule reading such edges would place nothing; a test holds the seed's edges as
   they are, and the register names the sources that would place them.
10. **A Professor places a process stage answers found.** The write-back makes a `PROCESS_STAGE`
   concept for a stage an answer names (`claim_writer.concept_id_for`), but no answer writes a
   `Process` or `ProcessStage` row ([decision 0038](0038-phase-a-review-fixes.md)), and the cited-order
   route the register named could place none. A `STAGES` review-queue item now lists such a concept
   once a shown fact is about it and its craft has a live process with stages that is not curated;
   a Professor places it first or after a stage of that process, which writes a `ProcessStage` named
   as the concept and moves the later stages down by one, or rejects it with a reason, both kept in
   `StageReview` (migration 0090). We chose a table of decisions over a status on `Concept`: the
   concept is shared by facts, terms and edges the decision does not touch, and a rejected stage must
   stay out of the queue without being removed. A curated process is never offered: the curated
   import rewrites its stages from the dossier
   ([decision 0142](0142-curated-crafts-read-only-curated-rows.md)), so a curated craft's stage goes
   through its dossier. No model call is added.

## Consequences

- Migration 0090 adds `Answer.stoppedAt`, `Term.sentenceName` and
  `CraftGiRecord.imitationClaimIds`, and marks the old stopped rows; the lead links it after the
  other lanes' migrations.
- The voice turn is trimmed to one section of three sentences and no follow-ups by
  `voice/compose.VOICE_FORM`, and the zoom story reads the answer's one read of the craft's matter.
- `fill_sentence_names` runs over every term without a name, seeded ones included, at each curated
  import; the seed itself fills none.
- The composer hands its renderings on with its answer (`ComposedAnswer.renderings`, never in a
  dumped payload), and the write-back's quote measures read them (`services/write_back_plan`), so a
  sentence kept by its rendering is written back `QUOTED` with its verbatim quote, and no second
  `TRANSLATE` call is made.
- Migration 0090 also creates `StageReview`. A release ships the backend first, so for some minutes
  the live web reads a review page that names `STAGES` before its own build knows the kind. As the
  production build ignores an unknown field (decision 0151), it now skips a review kind it does not
  know: `shape.knownOnly` drops from the page's `kinds` and `items` a kind, or a structure item's
  kind, outside the build's vocabulary, and the page renders the rest; the unit specs and the
  development server still refuse it, so the drift is caught. Either deploy order is safe.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/answering/test_stopped_answers.py`, `backend/tests/db/test_stopped_answers_db.py`,
`backend/tests/composer/test_quote_renderings_compose.py`,
`backend/tests/terms/test_local_name_marks.py`, `backend/tests/research/test_sentence_names.py`,
`backend/tests/db/test_term_sentence_names_db.py`, `backend/tests/place/test_supply_sentence_names.py`,
`backend/tests/answering/test_market_imitation.py`, `backend/tests/curation/test_imitation_checks.py`,
`backend/tests/sources/test_scholarly_journals.py`, `backend/tests/sources/test_source_journal_reads.py`,
`backend/tests/db/test_source_journals_db.py`, `backend/tests/planner/test_publisher_reads.py`,
`backend/tests/planner/test_colourant_search.py`, `backend/tests/science/test_seed_stage_order.py`,
`backend/tests/voice/test_voice_compose.py`, `backend/tests/journey/test_zoom_story.py`,
`backend/tests/ledger/test_ajrakh_retold.py`, `backend/tests/write_back/test_rendered_quotes.py`, `backend/tests/ledger/test_ledger_rules.py`,
`backend/tests/answering/test_heading_once.py`, `backend/tests/composer/test_internal_words.py`,
`backend/tests/planner/test_understanding_fields.py`, `backend/tests/review_queue/test_stage_place.py`,
`backend/tests/db/test_stage_review_db.py` and the unit specs `frontend/e2e/sentence-once-unit.spec.ts`,
`frontend/e2e/sentence-once-figures-unit.spec.ts`, `frontend/e2e/review-stages-unit.spec.ts` and
`frontend/e2e/review-unknown-kinds-unit.spec.ts`.
