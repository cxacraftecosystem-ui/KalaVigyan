# 0182. A section's pictures illustrate only what it shows and never end an answer, the citation numeral's touch area stays on the page, and the production checks read only our own frames

The claim ledger hears only of blocks the stream can send, so a block left out for a source the
answer cannot send lends its section no claim and says nothing; the one picture rule is applied
where a section's pictures meet its final blocks, never by refusing the document; the citation
numeral's 44px touch area grows from the numeral's end toward its word, so it never reaches past
the phone margin; the sideways-scroll audit names positioned pseudo-elements; the page-sentence
check reads an expert difference both views state as drawn once; and the console checks count
only messages from our own frames.

Date: 2026-11-24. Status: accepted (the lead's brief for lane F, production defects, from E2E
production run 45230284106 on release aa85ff4c, 2026-11-23). It amends
[decision 0080](0080-claim-ledger.md) (what the ledger records) and
[decision 0175](0175-production-checks-read-what-the-page-shows.md) (the page-sentence check and
the sideways audit it named). The contracts are `docs/contracts/explainer.md` (sections; the
claim ledger's pictures); the operator's side is `docs/RUNBOOK.md` (E2E production).

| For | Read |
|---|---|
| The ledger whose record this narrows | [decision 0080](0080-claim-ledger.md) |
| The checks and the sideways audit this amends | [decision 0175](0175-production-checks-read-what-the-page-shows.md) |
| Concept pictures, the builder's own images blocks | [decision 0087](0087-generated-explainers-per-concept.md) |
| An expert difference told once | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| What a reused section places and rebuilds | [decision 0090](0090-reused-and-curated-sections-enriched.md) |
| The E2E production run | [decision 0029](0029-e2e-production-run.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Run 45230284106 failed 11 of 38 checks on three faults and one misreading.

- **An Expert answer lost at its last step.** Indigo's Expert answer (request
  60d3408595bea7eeca974a02) streamed 94 cited sentences over 245 s, then failed in
  `explainer_document` with "section s1 shows images only for claims it cites". The stream's ids
  fit a reused first section: placed pieces s1.b1 to s1.b6, rebuilt blocks from s1.b7 (its
  reaction player and zoom story), with s1.b3, s1.b5 and s1.b6 never streamed. The code gives the
  path, and the new answer test walks it. A reused piece's direct source (the compound record of a material card, a
  molecule or a zoom level, a reaction's formula source, a component's sources) is not among the
  claim sources the reuse lookup carries (`piece_store.reusable` reads claim sources only), so
  `ExplainerStream.blocks` left such a block out for citing a source not sent. It did so after the
  claim ledger had admitted the block: its claims were recorded as the section's, its sentences as
  said. The builders work from the section's blocks as placed, before the ledger, and the
  generated explainer's builder returns concept pictures for the section's claims about each
  concept it does not explain; the ledger let such a picture through for a withdrawn card's claim,
  and the document built from the blocks the page showed refused it, throwing away the paid answer.
- **A misread pair.** The same run reported "2 streamed sentences are not on the page:
  pbad3cb7ef9e2.4, pbad3cb7ef9e2.5". They were not withdrawn: they are the mirror of a difference
  two expert views state (s2.b4 and s2.b5, texts swapped), which the panel draws once (decision
  0165), and the check matched a sentence's text only within its own block.
- **Answers scrolled sideways on phones**, 5 to 6 px at 390 and 3 px at 360, on the English and
  history answers and the saved essay, not in Hindi or at 834. The audit decision 0175 added named
  nothing, because it measured elements only. `.kv-cite::after`, the numeral's touch area, is
  `inset-inline: -12px` with `min-width: 44px` on a coarse pointer; round a one-digit numeral
  (about 9 px) the minimum wins, the end inset is dropped and the area reaches about 23 px past
  the numeral. A numeral ending a line in the 16px phone margin then carries the page up to 7 px.
  Monograph pages revert the class in their authored shell, so they never showed it.
- **Turnstile's frame failed Sign up.** Since decision 0175's hotfix allowed the challenge frame,
  it loads, and its own console noise (`%c%d font-size:0;color:transparent NaN`) and its own
  policy's refusals ("Connecting to 'data:,' violates ... connect-src 'self'
  https://hagen.challenges.cloudflare.com ...") reached the screens check, which counted every
  frame's errors.

## Decision

1. **The ledger hears only of blocks the stream can send.** `ExplainerStream.blocks` checks a
   block's sources before admission (`_sendable`, with `SourceMerge.knows` for a source an earlier
   block made canonical); a block citing one the answer cannot send is left out first, with the
   same warning. Which blocks are sent is unchanged; what changes is that a withdrawn block never
   becomes the section's claims, said text, materials or pictures. We chose this over keeping the
   later check and undoing the ledger's record, which would need every ledger field to be
   reversible, and over building the builders' ask from sent blocks only, which would change what
   every builder is given.
2. **The picture rule is applied where the pictures meet the final blocks.**
   `research/section_pictures.pictures_of_cited` keeps each image's claims that the section's
   other blocks cite, leaves out an image left with none and an images block left with no image.
   `explainer_document` applies it to every section before validating (logging what it left out),
   so a picture can no longer end an answer; a section left with nothing is `EMPTY` as already
   covered, and an answer left with no ready section stores no document. `version_merge` applies it
   when a follow-up moved onto a newer version drops repeated blocks, and the field voices readback
   uses the same function in place of its own copy. `ExplainerSection` still refuses a section
   that breaks the rule, so a stored or served explainer always satisfies it. We chose trimming an
   image's claims over dropping any image with one uncited claim, as the readback did, because the
   contract says an image left illustrating no cited claim goes; an image that still illustrates a
   shown claim stays.
3. **The numeral's touch area grows toward its word.** `.kv-cite::after` is anchored at the
   numeral's inline end, 12 px past it on a coarse pointer (5 px with a fine one), and grows toward
   the inline start to its minimum of 44 px (24 px), over the word the cluster is glued to. It
   stays inside the 16px margin at 360 and 390 and in right to left text. We chose this over
   clipping the shell sideways, which would hide every real overflow from the check, and over
   centring the area, which still reaches 18 px past a one-digit numeral.
4. **The sideways audit names pseudo-elements.** When the page scrolls sideways, `auditPage` also
   measures every positioned `::before` and `::after` from its containing block's padding edge and
   names the ones past the screen beside the outermost boxes, so the next overflow of this kind
   names its element.
5. **An expert difference is read as drawn once.** The page-sentence check matches an expert
   view's sentence by its text anywhere in its section's views, so the mirror of a difference
   counts as shown where the pair is drawn.
6. **The console checks count our own frames only.** `production/pageConsole.PageConsole` records
   which frame loaded each script and document; a console error counts unless every frame that
   loaded the place it names is a frame of another origin (an `about:` or `data:` frame takes its
   parent's), and one with no place counts. Both the screens run and the release controls use it,
   in place of two copies of the same filter. We chose frames over a message's text, which would
   also hide our own policy's refusals quoting the same words, and over the place's origin alone,
   which would drop errors of a third-party script running in our page (Google's sign-in client,
   Turnstile's own loader). Our Content Security Policy is unchanged.

## Consequences

- No migration, and no model call or input token is added to an answer: the stream no longer
  translates a block it then leaves out, which saves one translation call per such block on an
  answer in another language.
- A reused card, molecule, zoom level, reaction player or component placement whose direct source
  the reuse lookup does not carry is still left out of every reused section, as before. Carrying
  those sources would show the cards again but add their sentences to the late lede's evidence and
  to translation, so under the owner's rule of 2026-11-23 (decision 0165) it waits for answers to be
  measured; the lead holds it.
- The streamed page and the stored document now agree on a section's pictures; a picture the
  assembly leaves out is logged, which should not happen once item 1 holds.
- An answer whose expert panel states a difference no longer fails the page-sentence check for
  the pair's mirror, and the Sign up screen no longer fails for Turnstile's frame.
- No register entry was added.

## How this record is kept true

It is not edited after acceptance except to mark a row superseded: a later choice is a new record
that names this one, and the table above links the two both ways. It records the choices as taken
on 2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/answering/test_withdrawn_pictures.py` (a reused card withdrawn for its record
source after the builder chose a picture from it, and the assembly keeping only cited pictures),
`backend/tests/ledger/test_stream_unknown_source.py`, `frontend/e2e/citation-cluster-unit.spec.ts`
(a numeral ending a line at 360 and 390 on a touch screen), `frontend/e2e/page-audit-unit.spec.ts`,
`frontend/e2e/production-page-sentences-unit.spec.ts` and `frontend/e2e/page-console-unit.spec.ts`
(a Turnstile frame's errors and our page's own).
