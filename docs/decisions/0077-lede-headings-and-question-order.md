# 0077. Every answer opens with a lede, its sections carry headings shaped by the question

Every answer opens with a lede, composed and streamed first outside the sections, and its sections
carry headings written for the question, in the question's order. Follow-ups come from what the
answer left open, and signature figures are declared but not built.

Date: 2026-11-18. Status: accepted. Amended by 0143 (a lesson pack's title slide opens with the
lede).

| For | Read |
|---|---|
| What amended part of it | [0140 Voice and Listen hold their state in the bucket, bill what they hear and read the lede first](0140-voice-and-listen-kept-true.md): Listen, film and the quiz read the lede |
| What amended it later | [0143](0143-lessons-exports-and-follow-ups-kept-true.md): a lesson pack's title slide opens with the lede |
| What built on it | [0086 The four signature figures are built, as lede figures only, behind a setting](0086-signature-figures-built.md): item 6's signature figures |
| Every decision, by group | [README.md](README.md) |

## Context

The answers audit of 18 Nov (E2E run 44260797709) found that an answer has no headline and no
direct answer: "Which mordant fixes the red in Kutch Ajrakh block printing?" opened with scouring,
and alum and myrobalan arrived in the second section, almost by the way. Every answer used the
same facet titles ("How it is made", "The chemistry", "Materials"), the full process came first
whatever was asked, and the four known answers (English, Hindi, Water, Indigo) offered the same
three templated follow-ups, including "What is the chemistry or physics behind Kutch Ajrakh?"
right after a chemistry answer. All four were answered from stored pieces, so nothing in the
answer was written for its question. Build plan task 3-02 asks for a cited lede composed and
streamed first, narrative headings, sections in the order the question needs, follow-ups from what
the answer left open, and the shapes of four signature figures for task 3-04.

## Decision

1. **The lede is the explainer's opening block, outside the sections.** `LedeBlock`
   (`research/blocks_lede.py`) is `{id "lede", kind "lede", version 1, reuse null, headline,
   sentences (2-3), figure}`. The headline is the question as asked; the sentences are composed
   for this question and held to every prose rule (the composer's quote, figure and overlap checks,
   then `section_blocks.prose_problems`: a stored claim cited, a fact, every figure and named place
   in a cited claim or quote). A sentence that fails is dropped; fewer than two left is no lede. It
   is never stored as a piece and never reused. `Explainer.lede` is optional, so every explainer
   stored before it still reads; `explainer_blocks` yields it first, so `sources` lists its
   sources first. Its kind is not one of `BLOCK_KINDS` and it never sits in a section.
2. **Composed first, streamed first.** The lede runs as its own task from the start of the answer
   (`services/answer_lede.py`), on the craft's stored claims ranked for the question (16 at most)
   and the claims of every reused section (8 per section for its heading). It is one more call to
   the COMPOSE route (`ModelComposer.lede`, `LEDE_SYSTEM_PROMPT`), with the composer's one
   regeneration. Until it settles, `ExplainerStream.blocks` holds every block, so the `lede` event
   always comes before the first `block`; reused sections wait for it because it also heads them,
   while the sections without a stored piece are started and research alongside it
   (`reused_sections.stream_reused_beside`). The 30 s wait (`LEDE_WAIT_SECONDS`) bounds the whole
   opening: rendering the question in English, the stored read, the call and the lede's
   translation. Only an answer whose opening found no stored finding (`Opening.deferred`) composes
   its lede later, once its sections are checked, from the claims they cite, leaving out any
   sentence a section already states word for word (so the kept answer, which admits the lede
   first, keeps every section sentence the reader saw), and sends it before `follow_ups`. A lede
   that fails, times out or is refused leaves the sections to open the answer; it is never tried
   a second time.
3. **Headings are written for the question and checked.** A section's COMPOSE reply now carries a
   `heading`; the lede call writes the headings of reused sections. The composer strips quotation
   marks around a heading and drops one that is empty, over 120 characters, carries a number, a
   link or personal data, or is a field's label (`sections.is_facet_label`: the discipline titles
   and fields in any case). The server then drops one that names a place, month or season its section does not
   state, or shares no content word with its section's sentences, claims and quotes. A section
   without an accepted heading keeps its fallback, which names the craft and is never a label
   ("The chemistry behind Kutch Ajrakh", `sections.FALLBACK_HEADINGS`). The stored-only answer of
   a spent budget makes no call: a concept group whose name is a field's label (History, Process,
   Design) takes its field's fallback heading (`stored_explainer.stored_heading`). `section_started` carries
   the fallback; the new `section_heading {sectionId, title, original?}` replaces it before the
   section's first block. Facet labels stay only as the field named on the composer's Section
   line. A follow-up's deepened sections keep their titles (the version rules require it).
4. **Sections follow the question.** The understanding still chooses which fields; the depth's
   maximum keeps the fields the question asks about first and fills the rest in the
   understanding's order, so a Basic answer to "which mordant" never loses its chemistry;
   `sections.question_order` then puts the fields the question asks about first
   (`research/question_cues.py`: English and Hindi cue words, the craft's own name left out), the
   rest in the understanding's order, and the full process last unless the question asks how the
   craft is made. "Which mordant fixes the red" leads with chemistry and ends with the process.
5. **Follow-ups come from what the answer left open.** The lede call and each section call write
   questions the sources leave open; `follow_ups.left_open` takes those first, then one question
   for each field the question touched that the answer did not show, never the question itself
   as asked or as rendered in English for the calls (`Opening.asked`), five at most. The templated stored follow-ups now serve only the stored-only answer of a spent
   budget.
6. **Signature figures are declared, not built.** `research/blocks_signature.py` fixes the fields
   of `indigo_vat`, `mordant_bath`, `lost_wax` and `firing` (phase `SIGNATURE`): every value a
   figure shows is stated by its own cited sentence, a dip count by its words. They join
   `BLOCK_KINDS` (migration `0025_signature_block_kinds` widens the piece table's check) but not
   `BUILT_BLOCK_KINDS`, so every reader refuses them until task 3-04 builds them; the lede's
   `figure` holds one when built. `chosen_signature` picks the figure from the answer's glossary
   terms in order, never a model.

## Consequences

- One more COMPOSE call per answer, never two: the late lede is tried only when no stored
  finding fed an early one. A reused-only answer now makes one call where it made none. A Hindi
  answer also translates the lede and the accepted headings.
- An answer that reuses some sections and researches others no longer waits for the lede before
  researching: the researched sections' `section_started` now come first, then the `lede`, then
  the reused sections, with the sections' events interleaved as among researched sections.
- `shared/explainer.lede.golden.json` and `explainer.lede.golden.sse` fix the new shapes;
  `answer-stream.research.golden.sse` and `answer-stream.not-enough.golden.sse` now carry the
  fallback heading. The phase A document golden is unchanged: it is an explainer stored before the
  lede, and the learning fixtures build on it.
- The PDF report opens with the lede's sentences (`export_pdfs.explainer_pdf`), so the report and
  the citations export, which number the lede's sources first, list the same sources. Listen, film
  and quiz read sections only. Task 3-03 draws it (`LedeBlock.tsx`); `explainerSourceNumbers` takes
  it to number its sources first. Until 3-03 ships, the server holds blocks for a lede the page
  does not draw, so 3-02 is released together with 3-03.
- The claim ledger of task 3-01 merges the lede's sources like any block's but does not record its
  claims, so a section may still state in full what the lede summarises.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
