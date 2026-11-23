# 0120. Every sentence says no more than the quotes it cites

An answer sentence is now held to its quotes by what they assert, not only by the words they
share: a negation, a number word, a unit and a hedge must stand as the quotes give them, every
source a sentence cites must itself speak to it, a live sentence must quote the places and months
it names, and links and personal data are screened out. A failing sentence is dropped alone,
disagreements survive the repeat rule and are flagged on the sentences that cite them, and the
lede ships only with its answer, written from the answer's own hybrid search.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21: "is there any other fault in our existing
RAG pipeline?", then "yes, run all five lanes"; this is the grounding lane of round 7). The
contracts are `docs/contracts/research.md` (Composer, the answer's sections, Translation) and
`docs/contracts/explainer.md` (the claim ledger, the expert panel, the lede).

| For | Read |
|---|---|
| The sentence checks and the translation checks | [research.md](../contracts/research.md), Composer and Translation |
| The ledger, the expert panel and the lede | [explainer.md](../contracts/explainer.md) |
| Where components stand beside the prose | [answer-components.md](../contracts/answer-components.md) |
| The quote overlap this builds on | [0013](0013-review-fixes-quotes-licences-scope.md) |
| An expert difference whose two readings the page already said is not shown again | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| A seat whose take was all said goes with its differences | [decision 0167](0167-answer-leftovers-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Four read-only reviewers audited the answer pipeline, and the lead verified eight faults in the
code. Support was counted in shared four-letter stems (`quote_overlap` at one half), so "alum is
not used" passed on a quote saying it is used, "three times" on "twice", 30 °F on 30 °C and "the red
comes from iron" on "the red may come from iron". The overlap pooled every verified quote, so a
second source quoted about a Sunday market passed as support for a sentence about the indigo vat.
The month, season and district guard read the cited claims' texts, and a claim written back by
this answer has the sentence itself as its text, so the guard could never fire for a live
sentence. Sentences were never screened for links or phone numbers. One claimless sentence refused
its whole prose block and sent the section to fresh research. Disagreements were dropped whenever
one reading had been said in prose, and a seat restating its section took its differences with it.
The lede could ship two background sentences after its answer sentence failed, and its evidence
came from a word-density rank with no order and no limit.

## Decision

1. **Stance checks** (`research/sentence_support.py`). Against the verified spans, the composer now
   refuses `NEGATION_CHANGED`, `NUMBER_WORD`, `UNIT_CHANGED` and `DROPPED_HEDGE`. The negation set is
   `gate_thrift.NEGATION`; the sentence's count must lie between the most any one span holds and
   what all hold together, so two sources stating one negated fact, and one sentence joining two
   negated quotes, both pass. A number word is held by the same word, a word of the same value
   ("two" by "twice") or that value in digits. A unit is compared only where the spans give the
   same number a unit, from the units of `translation.protected_tokens`. Hedges reuse the hedge
   module, which moved from `curation/` to `research/` because the composer may not import
   curation; `doubt_words` counts may, might and could, which the curation rules leave out of
   quotes, because "the red may come from iron" is doubt, and treats a capital May as the month.
2. **Each source on its own** (`UNRELATED_SPAN`). When a sentence cites two or more sources, each
   one's verified spans must share at least two content stems or figures with the sentence (all of
   them when a span holds fewer). One shared word is the size of a coincidence: a place or a
   material named in passing ("Bhuj", "indigo") lets an unrelated quote through, while two
   independent shared items is the least that shows the quote speaks to the sentence. The pooled
   one-half overlap still holds the sentence to its quotes jointly; a single source is judged by it
   alone, as before.
3. **Live names quote their sources.** `KeptSentence` carries the verified spans of a composed
   sentence and the ids of the claims this answer wrote for it. The names guard leaves out the text
   of those written claims, so a live sentence's months, seasons and districts must stand in its
   quotes. A claim the sentence cites from the store still states what its text states.
4. **The screen.** Links (a scheme, `www.`, a bare shop domain), tags, Markdown links and personal
   data are violations of the sentence itself. Comparison signs and reaction arrows are not markup.
5. **Dropped alone.** `section_sentences` drops, each alone, a sentence with no visible stored
   claim, not a fact, with an unheld figure or an unstated name; the prose block is built from the
   rest and refused only when nothing remains. `prose_block` stays a strict guard for the callers
   that hand it stored claims.
6. **Disagreements survive.** The ledger skips a pair of seats only when that same pair of claims
   was already shown as a difference, and keeps a seat whose take was all shown while it carries a
   difference. The panel judges differences over every view that passed and seats a restating view
   only for a kept difference. Every section prompt asks for both readings where sources differ.
   `ExplainerSentence.sourcesDiffer` is set from the cited claims and drawn as the madder Sources
   differ tag after the sentence.
7. **The lede keeps its answer.** The lede schema asks the model to mark the answer sentence; it
   leads the lede. When it fails its checks, is unmarked, or a section already said it, no lede is
   sent, whatever the other sentences say.
8. **The lede's evidence is the answer's search.** The early lede reads the answer's
   `KnowledgeRetriever` (the hybrid search with rarity weighting, vectors and entity names) for the
   question in English, at most 24 claims in its order, and reads their citations through the store.
9. **Translations keep stance.** `translation_problems` refuses a translation that drops the English
   original's negation or hedge, against a list of negation and hedge words and endings for each
   answer language (`research/stance_markers.py`). Only a missing one is refused: idioms such as
   Hindi "until ... नहीं" add a negation the original does not hold.

## Consequences

- Composed sentences fail more often at first; the one regenerate call carries the new kinds as its
  problems and the source rules ask for negations, hedges, number words and units as quoted.
- A section loses one bad sentence instead of its whole prose and its components, so fewer sections
  fall to fresh research.
- `knowledge_view.ClaimView` does not yet carry `Claim.sourcesDiffer`; the flag is read by the
  attribute name `sources_differ` and stays absent until the access lane adds it.
- `knowledge_view.claims_for` is no longer used by the lede; the stored-only answer and the other
  pages still use it.
- A language's word list is maintained by hand. A correct translation using a negation or hedge form
  the list lacks is refused, sent back once with the problem named, and the answer keeps its
  English; adding the form to the list is the fix.
- A written claim keeps one quote per document (write-back), so a name or figure that only a second
  span of the same document carried is not in its stored quotes; the sentence's spans now carry it
  for the names guard.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/research/test_grounded_sentences.py`, `test_translation_stance.py`,
`backend/tests/composer/test_grounded_compose.py`, `test_lede_compose.py`,
`backend/tests/answering/test_grounded_blocks.py`, `test_lede_answer.py`, `test_sections.py`,
`backend/tests/ledger/test_ledger_rules.py`, `test_ledger_kinds.py`,
`backend/tests/experts/test_expert_views.py` and `frontend/e2e/sentence-differ-unit.spec.ts`.
