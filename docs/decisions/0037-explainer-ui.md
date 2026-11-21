# 0037. The explainer view

The explainer view reads the stream through one reader and one reducer, and shows what was
understood, the research trail, sections with their state, and Listen with the text highlighted.
Citations, evidence badges, terms, the ladder and pictures follow the explainer contract.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0030 The explainer contract](0030-explainer-contract.md) |
| The review that fixed it | [0038 Phase A review fixes](0038-phase-a-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

`docs/plans/answer-experience.md` (owner-approved, section 8 final) turns the chat-style answer
into an explainer: the reader sees what was understood (1.2), a research trail (1.3), sections
that build one at a time with their state and a section bar (1.4), and Listen with the text
highlighted as it reads (1.5, 2.5); prose carries citation chips and tappable terms (2.8), the
process ladder fills step by step, and pictures sit inline with their credit or as credited link
cards (2.7, O2). Decision 0030 fixed the stream events and block shapes, 0034 the term route and
the picture rules, 0036 the asking screen and its controls. The boards are the "Explainer" and
"Learn" pages of the design project. Today's answer view drew `section` and `sentence` events.

## Decision

1. **One stream reader, one reducer.** `lib/explainerStream.streamExplainer` reads `/answers/stream`
   and parses every frame with the contract's shapes; a frame off the contract is logged and
   dropped (`explainerEventOf`), as 0036 did for `understood`, so one bad block never ends an
   answer. The retired `match`, `section` and `sentence` are skipped. `lib/explainerState.reduceExplainer`
   is the only reducer: sections ordered by `order` whatever order they start in, a block kept
   once and only while its section is working, a trail key that only moves forward and keeps the
   place it was first found, and the settled phases (`empty`, `failed`) unchanged by late events.
   The old reducer, `AnswerView`, `AnswerPayload` (with its `mode`) and `CraftMatch` are gone, and
   the specs and the production E2E read the explainer events (the record now counts frames that
   broke the contract as a problem).
2. **What is shown.** A section with blocks, or `EMPTY` with what it searched, is drawn; a working
   section only while the answer streams; a `READY` section with nothing to draw is hidden. A
   section's working state is a word with a spinner; the spinner stops under either reduced-motion
   switch and the word stays.
3. **The understood line changes through the existing controls.** "Answering for Kutch Ajrakh ·
   Expert · in English": each part the reader can change is a button that moves focus to that
   control under the question box (`focusAskOption`), so each choice keeps one control and the
   re-ask rule of 0036. The depth label is the config's.
4. **Citations.** One numbering per answer, in order of first citation walking the sections in
   reading order (prose sentences; a ladder stage's sentences, materials, conditions), which is the
   document's `sources` order; then open questions and reactions. `CitationContext` moved from
   `components/craft` to `components/answer` beside the chip, since the craft page and the
   explainer both read it.
5. **Evidence badges.** A sentence shows a Verified or Reviewed badge; Provisional, the level of
   most findings, is the chip's title and accessible name only, as the board marks only the
   stronger levels. Ladder stages show their level as the craft page's stages do.
6. **Terms.** Spans are matched as text (decision 0030 point 4): the first occurrence of each, in
   the text shown, never overlapping; showing the English original drops spans the original does
   not contain. A tap opens `TermSheet` (the one modal primitive, `FieldDialog`) on `GET
   /terms/{key}?language=`; a 404 closes it and removes that term's underline for the answer, as
   0034 asks (hide what cannot work). The summary's chips number the term's own sources and open
   the same source dialog. Ask about it asks "What is kut in Kutch Ajrakh?". A follow-up, the
   server's or Ask about it, keeps the answer's language, so an English template or follow-up
   does not switch a Hindi reader's Auto choice to English.
7. **The ladder fills with the scroll.** The guide's spine (decision of the walkthrough): one
   `useScroll` value over the stage list (`start 65%` to `end 65%`), smoothed by the read-along
   spring, drives the fill's `scaleY`; a stage's bubble fills once the fill reaches it
   (`ladderReach`). Under either reduced-motion switch the fill and every bubble are drawn full.
   Stage numbers are the stored ordinals; a stage's reactions link to the craft page's Process tab.
8. **Pictures.** An inline picture links its page, with author, licence (linked) and site under
   it; a link card shows the source site's thumbnail, title, site and credit and opens the page.
   Every picture is `next/image` unoptimised with `referrerPolicy="no-referrer"` (0034); one that
   fails to load is removed rather than drawn broken.
9. **The research trail.** While streaming: counts per group and the five latest entries with
   their stage; after `done`: the counts and Replay the trail, which plays every entry in arrival
   order with the house stagger (all at once under reduced motion).
10. **Listen.** The client's reading of Listen is the explainer contract's Listen section, written
    first by this lane and served by Listen's lane (0035) in the same batch: `/answers/config`
    lists `listen.languages`; `GET /answers/{answerId}/listen?language=` answers tracks per block
    with word timings as text found in order (no character offsets). `e2e/explainer-view-unit.spec.ts`
    checks `shared/listen.script.golden.json` against the client's checks and finds every word of
    the golden in the document's sentences. The Listen button is drawn only after `done` in a
    listed language, so nothing is offered that cannot work. A dock (the voice
    dock's place and z-index) plays the tracks in order with pause, speed and a progress bar; the
    sentence being read is tinted and the word marked, both static states. The audio element lives
    in its own component that owns its ref, so the Listen state stays plain data.
11. **Width.** The answer column widens from `max-w-3xl` to `max-w-4xl` for the ladder and the
    picture strip; prose stays at reading size.

## Consequences

- Until the sectioned composition lane (0032) streams sections and blocks, the page draws only
  the understood line, the trail, open questions, reactions and follow-ups, and the production E2E
  reports the old events as frames that broke the contract.
- Listen stays hidden wherever the config does not list the answer's language (no ElevenLabs key,
  a language it cannot speak).
- Save, Export, Share and Film mode on the board are not drawn: they belong to phases C and D.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
