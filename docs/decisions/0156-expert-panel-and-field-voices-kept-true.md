# 0156. The expert panel takes a failing view again, differs across linked concepts and reuses only the seats it seats, and field voices reach the craft page, their pictures and every run

A failing expert take is asked for once more while the wait allows, two claims on concepts one
glossary term links are one subject, a reused panel keeps only the seats the new answer seats,
the artisan seat writes back what it would quote and still reads only public transcripts, field
voices are drawn on generated craft pages, field photographs illustrate the claims they show and
never while held, the sync's order check spans runs, a section that lost a withdrawn quote says
so, and Sources differ opens after its paragraph and names what the sources differ on.

Date: 2026-11-23. Status: accepted (the lead's debt brief of 2026-11-22, expert panel and field
voices lane). It amends [decision 0046](0046-expert-panel.md) (points 5 and 6),
[decision 0099](0099-wider-expert-panel.md) (the artisan seat),
[decision 0091](0091-field-voices-kalavigyan-side.md) (point 12, field images as illustration
candidates) and [decision 0141](0141-design-system-and-answer-screens-without-debt.md) (the
Sources differ leftover). The contracts are `docs/contracts/explainer.md` (the expert panel as
built, `expert_view`, the sentence and the section), `docs/contracts/field-voices.md` and
`docs/contracts/frontend.md`.

| For | Read |
|---|---|
| The panel whose take and subject rules it amends | [decision 0046](0046-expert-panel.md) |
| The wider panel and the artisan seat it amends | [decision 0099](0099-wider-expert-panel.md) |
| The field voices it draws, links and orders | [decision 0091](0091-field-voices-kalavigyan-side.md) |
| The Sources differ drawing it finishes | [decision 0141](0141-design-system-and-answer-screens-without-debt.md) |
| The approved Kutch Ajrakh page it leaves alone | [decision 0100](0100-ajrakh-monograph-served-as-built.md) |
| A difference's subject from the judge's own answers, and on every answer sentence (amends item 10) | [decision 0177](0177-differences-named-and-the-monograph-shell-measured.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Twelve entries of `docs/TECH_DEBT.md` were still open in this area on 2026-11-22: a panel view
lost to one failing sentence, differences only between claims stored on one concept, reused panels
keeping the seats of the answer that stored them, the panel never seen on Claude Sonnet, the
artisan seat quoting only chunks a claim already cites and reading with the public ACLs, no
database test of the seat search, field voices served but not drawn, field images never beside a
sentence, a partly withdrawn section saying nothing, the sync's order check within one run, the
Sources differ readings drawn inside the sentence, and the voice call still mounting the retired
source dialog.

## Decision

1. **One retake of a failing take, whole.** A seat whose take has a failing sentence (the
   composer's validator or `prose_problems`, the latter named `PROSE_CHECK`) is asked once more
   for its whole take, with each failed sentence numbered, its problems and its text in an
   untrusted block as the composer's regenerate lists them (`composer/expert_takes.compose_retake`,
   `services/expert_seat_takes.retaken_takes`). The retake replaces the take and must pass whole;
   a replacement per sentence, as prose does, was refused because a take is one expert's short
   argument and a sentence left out could change it. All failing seats are asked at once, bounded
   to 20 s, and only while 40 s of the 90 s wait remain, so the difference pass keeps its time; a
   refused spend, a failed call, an empty take or a reply off the schema is not asked again.
2. **One subject is one concept or two concepts one glossary term links.** A difference is kept
   between claims on two concepts linked to one `Term` (`TermConcept`, the curated link the
   shared-science explorer reads), read once per section with two views or more
   (`services/expert_subjects`). A model's word that two claims concern one thing is still not
   evidence; an edge claim, which has no concept, is still refused.
3. **A reused panel seats the new answer's experts.** A reused section keeps only the views of the
   seats `panel_seats` gives its field for the new understanding and depth; the kept views lose the
   agreements and differences naming a dropped seat, with their claims, sources and hash taken
   again, and a view left with no difference that cites only what the section's other pieces show
   is dropped as the builder would (`research/piece_reuse.seated_pieces`,
   `reused_sections.ReuseBuilds.seated`). Reusing the set whole, or dropping the whole set, was
   refused: the first shows seats the reader's question did not seat, the second loses views that
   still hold.
4. **The panel's model route is tested, and the paid run reads its result.** A test runs the
   registered panel builder on the answer's builder compose model and checks every call is
   `COMPOSE` on `BUILDER_TUNING` (Claude Sonnet 5.5) with the answer's headroom principal. Seeing
   it on Claude Sonnet in production needs the paid questions run, so the production record of
   the Expert answer notes the panel's views and Experts differ pairs
   (`e2e/production/expertPanel.ts`) and the debt entry now names that run.
5. **The artisan seat writes back what it would quote, and reads only public transcripts.** For
   each quotable turn spoken by an artisan whose public quote chunk the seat's search finds and no
   citation of the recording quotes, the seat writes back one `QUOTED` claim of the craft through
   the research write-back's gates (no embedder, no judge, the way the term store writes), filed
   under the craft with its name as the concept: "An artisan who practises <craft> says:
   “<quote>”", the quote the turn's first whole sentences within 300 characters. The text names
   nobody, so no personal data enters a fact; the speaker is named only in the sentence the server
   writes from the recording. It writes only in the fields a field interview alone may support
   (`write_back_plan.FIELD_ONLY_DISCIPLINES`), only for a stored answer, and quotes the written
   claim only when it is visible (a claim held for review waits). The seat keeps the public
   reading ACLs (`PUBLIC`, `SIGNED_IN`) rather than the asker's: its sentence carries the quote in
   its text, and expert views are stored as pieces, reused for other askers and served through
   share links, so a `RESEARCHER` chunk quoted for one asker would reach readers without that
   access. KalaVigyan testimony stays with the section's `artisan_voice` block, which already
   quotes it. An artisan with no recorded name is quoted as "one account from an artisan", never
   as "None".
6. **Field voices on the craft page, never on the approved one.** A generated monograph draws "In
   the artisan's words" and "From the workshops" after its document, inside its frame, and a craft
   without a monograph above "Start the research"; each shows its first page (6 quotes, 12
   photographs) read on the server from the public list route, Show all continuing from the same
   list, and nothing when the craft has none. Kutch Ajrakh, the one authored shell page, reads no
   field voices: its parity run compares its whole text with the approved file, and adding a part
   there is the owner's call. Putting the part among the chapters was refused because it would
   change the stored document and its rail.
7. **Field photographs illustrate what they show, filtered when read.** Each applied image's
   `MediaRef` is linked (relevance `TEXT`) to the fact-level claims of its crafts that its caption
   and the labels of what it shows (not a person, session or workshop label) share two stems with,
   the craft name left out (`image_relevance.illustrated_claims`, the one stems rule). Every image
   is linked, held ones too, and `stored_pictures` leaves out any field image not shown now,
   because visibility changes without a new revision (a review, a stale stream, the switch); the
   craft page's pictures leave field images to the gallery. The `artisan_images` switch is
   unchanged.
8. **The order check spans runs.** Each view's last (`updatedAt`, `id`) is stored with its cursor,
   only when the cursor moves past a page with changes, cleared with it, and a run's first page is
   refused at or before it.
9. **A section cut short by a withdrawn interview says so.** A ready section that keeps other
   blocks carries `withdrawn`, the number of sentences, blocks and artisan quotes the field
   readback took out (left out of the JSON when 0), and the answer page says "A field interview
   this section quoted is no longer shown, so one passage was taken out." (or N passages). Only
   what a withdrawal removed counts: sentences closed to a public reader of a shared answer do
   not, so the note never blames an interview for them. Artisan quotes count because answers do
   not draw `artisan_voice`, so this note is the reader's only word of them.
10. **Sources differ opens after its paragraph and names its subject.** A flagged sentence carries
    `differsOn`, stored on the claim when the flag is set: from the dossier conflict's `about`
    (the first conflict of a claim wins), from an accepted structure proposal's conflict, and by
    `mark_sources_differ(..., about=)`, which never replaces a stored one. `ExplainerSentence`
    draws only the tag; each host draws `SentencesDiffer`, a `<details>` with both readings quoted
    and cited, after its paragraph, never inside a `<p>`; with no subject its summary is plain
    "Sources differ". `ClaimView` is another lane's file, so the sentence reads the claim's
    subject through a named seam (`DIFFERS_ON_FIELD`) that lane fills.
11. **The voice call draws no source dialog.** `SourceDialog` and its spec are deleted; citations
    open their own panel as everywhere else.

## Consequences

- Migration `0080_stream_stamps_differs_on` adds the four stamp columns and `Claim.differsOn`.
- Answers name what the sources differ on once `ClaimView` carries `differs_on`, and write-back
  flags once the duplicate judge names it; until then the summary reads "Sources differ"
  (`docs/TECH_DEBT.md`, Leftovers of the design-conformance lane).
- A section with a failing view may wait up to 20 s more for its panel, inside the same 90 s.
- Differences can appear between two crafts' claims on one glossary term when the seat search
  offers both.
- Field photographs can appear beside answer sentences once the portals' images arrive.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/experts/test_panel_retakes.py`, `backend/tests/experts/test_reused_seats.py`,
`backend/tests/db/test_expert_subjects_db.py`, `backend/tests/experts/test_artisan_turns.py`,
`backend/tests/db/test_expert_seats_db.py`, `backend/tests/field_voices/test_field_image_claims.py`,
`backend/tests/db/test_field_image_claims_db.py`, `backend/tests/field_voices/test_sync.py`,
`backend/tests/db/test_field_voice_stamps_db.py`, `backend/tests/field_voices/test_readback.py`,
`backend/tests/answering/test_grounded_blocks.py`, `backend/tests/curation/test_curation_claim_rules.py`,
`frontend/e2e/craft-field-voices-unit.spec.ts`, `frontend/e2e/sentence-differ-unit.spec.ts` and
`frontend/e2e/expert-panel-record-unit.spec.ts`.
