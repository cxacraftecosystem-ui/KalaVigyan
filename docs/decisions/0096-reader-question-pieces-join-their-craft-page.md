# 0096. Every piece built for a reader's question joins its craft's page, whoever asked

Every piece built for a reader's question joins its craft's page whoever asked, placed by chapter,
one per slot, with its provenance shown and its asker never. AI media join too, and withdrawal and
staleness follow the sources.

Date: 2026-11-18. Status: accepted. Extends decision 0095 (craft page schema version 3); amends
decision 0033 (stored pieces served only to answers) and the media contract's sharing rule for
assets made from a craft's claims.

| For | Read |
|---|---|
| What it amends | [0033 Stored knowledge pieces and reuse](0033-knowledge-pieces-and-reuse.md): stored pieces served only to answers |
| What it builds on | [0095 The craft page becomes a monograph in chapters, public to read, built without a question](0095-craft-page-chapters.md): craft page schema version 3 |
| Every decision, by group | [README.md](README.md) |

## Context

The owner wrote on 2026-11-18: "all the assets and information that is built for each and every
question should be added to their respective craft, no matter who looks it up." Decision 0095
builds the chapters of a craft's page from stored rows by fixed rules, so a page showed what an
answer wrote back as claims but none of the blocks an answer built from them: an Expert answer's
reaction player, material cards, timeline, what-if lab, generated explainer, expert seats or the AI
illustrations made for it stayed in that one reader's answer. Answers keep their blocks as
knowledge pieces (decision 0033), and pieces already carry their craft, facet, topic, claims and
staleness, but nothing linked a cross-craft piece (a region story, a generated explainer) or an
any-craft answer's pieces to a craft, an answer piece whose answer was deleted looked curated, and
an AI asset's object key names the user who asked for it.

## Decision

1. **One module decides, at build time.** The whole merge is one async function of
   `services/craft_page_answer_assets.py`, called by the chapter builder before the ledger; it
   writes nothing. A piece belongs to a craft when its `craftId` is the craft; when it is
   cross-craft and its answer was about the craft; and, for an answer about no craft, when a claim
   it cites is about one of the craft's own concepts and every claim it cites is on the page. No
   link table is kept, so pieces kept before this decision join at once and nothing can drift.
2. **Readers' or curated, without a new column.** A piece with an answer id is a reader's; one
   without is curated only when every claim it cites is curated, so a reader's piece whose answer
   was deleted (the id set null) is never shown as curation. Decision 0090's supersession rule
   still reads the answer id alone; aligning it is recorded as debt.
3. **Placed by chapter, one per slot, then the ledger.** A piece goes to its kind's chapter, else
   its facet's (`DISCIPLINE_CHAPTERS`). Items of a kind are reduced to one per page slot (per
   mechanism, CID, material, concept, input, facet and topic, or once per page): kinds the page
   rebuilds from rows on every build keep the page's own; otherwise the higher evidence floor wins,
   so a curated piece is never displaced by an answer piece of lower evidence, then the item showing
   more distinct claims, then the newer. The claim ledger (decision 0080) then drops repeats across
   the whole page as it does within an answer.
4. **Provenance shows, the asker never does.** Each item carries `origin`: curated, earlier
   research or readers, model-built or AI media, and for a reader's piece "From a reader's
   question, <Month YYYY>", with the question beneath only when a fixed screen passes it
   (`research/question_screen`: English, at most 160 characters, no first- or second-person word,
   no personal-data pattern, address, handle, URL or six-digit run); else "From a reader's
   question" alone. The question is read through the piece's answer at build time and never copied;
   no user id, answer id, role, depth or reading style is read for the page.
5. **AI media join too.** An AI image or video made from a craft's claims joins its page while its
   claims stay visible: the media worker copies it to a craft-neutral key with no requester id and
   marks it `CRAFT_SHARED`, except that an asset depicting a named cluster keeps the two professors'
   sign-off. It is drawn labelled "AI illustration" or "AI video" on a mat, never as a plate, the
   masthead or an OG image. A public route redirects to the neutral copy.
6. **Withdrawal follows the sources, and so does staleness.** A piece or asset whose claims are
   retracted, hidden or stale, or that is superseded or hidden, leaves at the page's next build; an
   archived version is read back through the same filters.
7. **Incremental.** The craft's pieces, their marks and the assets are terms of the page stamp, so
   keeping a piece changes that craft's ETag at its next read, with no job, no model call and no
   other page rebuilt.
8. **Moderation.** A Professor or above (`HIDE_GENERATED`) can hide any piece or AI asset on a page;
   a hidden piece is also never reused by an answer.

## Consequences

- Two build units: the merge module with its tests (which piece belongs, slots, provenance, the
  question screen; it edits no other file), and the CHAPTERS build of decision 0095, which calls it
  and adds the payload fields, the stamp terms, `MediaAsset.pageKey` with the AI media copy and
  route, the film score route, the hide routes and the goldens' reader-question inputs.
- A reader's Expert answer now enriches the public page for everyone. An answer piece built on a
  shallow question of equal evidence but more claims can replace a curated piece of the same slot;
  the curated claims stay in All evidence.
- Spending on an answer now benefits every reader of the craft; nothing new is spent by the page.
- Media sharing by a first professor (`SHARE_MEDIA`) is no longer needed for an asset to appear on
  its craft's page; the two-professor rule for named clusters is unchanged, and the owner may lift
  it.
- An any-craft answer whose pieces cite claims of two crafts with no common page attaches nothing;
  its claims still reach each page through the write-back.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
