# 0039. Pictures and terms in the answer stream

Pictures and term spans reach the answer stream: terms are marked in English once per answer's
glossary, pieces keep the marked blocks, and a translation keeps the spans its text still shows.
Pictures follow a section's blocks, wait at most 8 seconds, never stop a section and are never
stored as pieces.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| Every decision, by group | [README.md](README.md) |

## Context

Step 7 of `docs/plans/answer-experience.md` section 2.3 enriches each checked section with
pictures and term spans. Lane 0034 built the image sources, `SectionImages`, the glossary and
`TermMarker`; lane 0032 built the sectioned flow; neither called the other, so no `images` block
was streamed and no sentence carried a span (debt "Pictures and term spans have no caller in the
stream yet", "Step 7 has a place but no call", "Reused sections bring no pictures or follow-ups").
Decision 0038 kept `https:` out of every page's `img-src` until pictures were streamed.

## Decision

1. **Terms are marked in English, once per answer's glossary.** `services/section_enrichment.
   EnrichmentTools.for_answer(craft)` reads the craft's glossary once per answer
   (`term_glossary.glossary_entries` of the resolved craft, its own names left out) into one
   `TermMarker`. `answer_sections._built` marks every sentence of a section's `prose` and
   `process_ladder` blocks (`Enrichment.marked`: a payload round trip validated like any block),
   before translation. An answer for any craft has no craft id, so it reads no glossary and marks
   nothing. A glossary that cannot be read is logged and the answer goes on unmarked.
2. **Pieces keep the marked blocks.** `SectionOutcome.built` holds the marked English blocks and
   `pieces.keep` stores them as they are; a reused piece keeps the spans it was stored with, since
   placing a piece changes only its id and reuse mark (decision 0033).
3. **A translated sentence keeps the spans its text still shows.** The contract says spans mark
   the shown text and says nothing of how a translation gets them. `answer_translation` keeps a
   span of the English sentence only where its text occurs in the translation and its first
   occurrence overlaps no span kept before it (`research/terms.spans_still_shown`); nothing is
   marked anew. A name the translation keeps (`alizarin` in a Hindi sentence) stays tappable; one
   it renders in another script loses its underline (debt). Without the rule a translated marked
   block fails the span check and its section stops.
4. **Pictures follow the section's blocks.** Once a section's final attempt is chosen, its search
   starts as a task (`PictureSearches.start`) with the claims its blocks cite in order of first
   citation, the craft's name and the next block id, and runs while the blocks are translated and
   sent; the `images` block goes out after them, before the open questions and `section_done`.
   Reused sections search the same way from their placed blocks' claims, all of them at once before
   the first reused section streams, so pictures delay the open sections by one wait at most.
5. **Pictures never stop a section, and wait at most 8 seconds.** Each image service gets 6 s for
   its searches (`section_images.IMAGE_SEARCH_SECONDS`); a slower one is left out and the others
   still count. The whole step (claim texts, searches, choosing, storing) gets 8 s
   (`section_enrichment.PICTURES_WAIT_SECONDS`). A failing service, no relevant picture, a timeout
   or any failure of the step is logged and the section is sent without an `images` block, still
   `READY`; a section that stops cancels its search. A section spends tens of seconds on model
   calls, Commons and Openverse answer in about a second and SearXNG in a few, so 6 s covers a
   search and its retry with the craft name alone, and 8 s leaves room to store what was chosen.
6. **Pictures are shown, never stored as pieces.** The `images` block joins the section's shown
   blocks and the stored explainer but not `SectionOutcome.built`, so pieces stay `prose` and
   `process_ladder` (decisions 0030, 0033); the pictures are `MediaRef` rows as before.
7. **An answer made only of reused sections offers the stored follow-ups.** `stored_follow_ups`
   with the headings of the reused pieces' claims (`knowledge_view.section_heading` of each
   claim's concept type), translated like any follow-ups. An answer with a researched section
   keeps the composer's.
8. **Every page loads https pictures.** A page's CSP is fixed when its document loads and Next's
   client-side navigation keeps that document, so an `/ask`-only policy would hide every web
   picture from a reader who reaches `/ask` from the navigation, the landing page or a craft page.
   Making those links full page loads would slow every move to Ask. So the one site-wide policy's
   `img-src` is `'self' data: <media bucket> https:`, as decision 0034 first set it: a picture
   cannot run script, `script-src` and `connect-src` are unchanged, plain http and `*` stay
   refused, and every picture loads with `referrerPolicy="no-referrer"`.
   `e2e/picture-rules-unit.spec.ts` resolves `/`, `/ask`, `/settings`, a craft page and `/map`
   with Next's own path matcher and finds the same policy on each.
9. **The research golden shows both.** The answering flow's golden
   (`shared/answer-stream.research.golden.sse`) is produced with a fake glossary (`alum`,
   `alizarin`, `cotton`) and two fake picture sources, so it carries spans and an `images` block
   with an inline picture and a link card; the backend writes it byte for byte and
   `e2e/answer-stream-golden-unit.spec.ts` reduces it. `e2e/explainer-drawing-unit.spec.ts`
   renders `ImageStrip`, `ExplainerSentence` and the whole `ExplainerView` from the reduced golden
   on the server and finds both pictures, their credits and no-referrer links, and the term
   buttons. The client needed no change.

## Consequences

- A section can stay open up to 8 s longer when pictures are slow; a reused-only answer up to 8 s.
- Every page may load https pictures; only the explainer draws them, each with no referrer.
- The nightly piece rebuild answers through the same pipeline, so rebuilt pieces carry spans and
  its sections also search pictures nobody sees (debt).
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
