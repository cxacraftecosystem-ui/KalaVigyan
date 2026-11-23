# 0179. A transcript window is a chunk kind, a craft reads the shared concepts the graph links to it, and the paid checks make one Gemini clip when asked

A field transcript's speaker-labelled windows are written `PUBLIC` and told apart from its quotes
by a chunk kind, not by an ACL; a craft's stored search reads the shared concepts that its glossary
terms or the concept edges link to it; and the paid checks gain a Gemini video step, made only
when a run names it, with each check a choice of the run.

Date: 2026-11-23. Status: accepted (the lead's evening brief of 2026-11-23, lane C, access and
media checks; the owner approved one paid Gemini clip on 2026-11-23). It amends
[decision 0097](0097-public-reading-everywhere-but-asking.md) (the transcripts' `SIGNED_IN` ACL),
[decision 0122](0122-evidence-reach.md) (what a craft's scope reads) and
[decision 0154](0154-ai-media-and-film-scores-kept-true.md) (the paid checks). The contracts are
`docs/contracts/field-voices.md` (Chunks and their ACL), `docs/contracts/retrieval.md` (the
craft's scope, `chunkKinds`), `docs/contracts/research.md` (Stored-knowledge retrieval) and
`docs/contracts/media.md` (Models, queues and limits).

| For | Read |
|---|---|
| The public transcripts whose ACL this retires | [decision 0097](0097-public-reading-everywhere-but-asking.md) |
| The craft scope it widens | [decision 0122](0122-evidence-reach.md) |
| Research for any craft, filed on shared concepts | [decision 0031](0031-understanding-and-depth.md) |
| Filing one fact under a craft in the review queue | [decision 0136](0136-write-backs-filed-by-their-source.md) |
| The shared-science explorer whose term graph links the concepts | [decision 0064](0064-quiz-compare-and-shared-science.md) |
| The paid checks it extends | [decision 0154](0154-ai-media-and-film-scores-kept-true.md) |
| Why a label is dropped only a release later | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| What is left | `docs/TECH_DEBT.md`: The `SIGNED_IN` chunk ACL is read by everyone; Gemini video not yet seen live |
| Every decision, by group | [README.md](README.md) |

## Context

- **The `SIGNED_IN` ACL did a second and a third job.** Since decision 0097 every reader reads
  `PUBLIC` and `SIGNED_IN`, so the label no longer means signed in. It still marked a transcript's
  windows apart from its one-sentence quotes: the quote recheck after an edit
  (`field_voices_store.recheck_quoted_claims`) and the passage shown around a quoted citation
  (`citation_contexts`) read `PUBLIC` chunks only, so neither met a window. And the searches that
  pass no reader's ACLs, among them the answer's stored pack, the lede and the evaluation, read
  `PUBLIC` only, so they read quotes and not windows. Writing windows `PUBLIC` without another mark
  would let the recheck keep a quote only a window holds, show a window as a citation's context,
  join a quote passage with the window after it, and put up to 1,500-character windows into every
  answer's stored pack, which the owner's rule of 2026-11-23 forbids while answers are measured
  (decision 0165).
- **The windows' locators cannot tell them apart.** A window of one segment and a quote of that
  segment carry the same locator (`0:06–0:33`, or `paragraph 1` untimed), so the locator is no
  rule.
- **A label is dropped a release later** (decision 0151): the release before this one still writes
  `SIGNED_IN`, and may serve the migrated database for minutes.
- **Any-craft facts reached no craft.** Research for any craft files its facts on shared concepts
  (no craft, no sub-category). A craft's scope read its own concepts, its sub-category's, its
  family science and its merged crafts', never a shared concept, so those facts reached only
  questions for any craft. Reading every shared concept in every craft's answer would mix crafts.
- **No video had been made.** The video adapter follows Gemini's documented shapes; the owner
  approved one paid clip with `gemini-omni-1.2-flash` on 2026-11-23, and the paid checks had no
  step for it and no way to make one check alone.

## Decision

1. **A chunk has a kind.** `Chunk.kind` is `PASSAGE` (a source's text, a field quote, a kept quote)
   or `WINDOW` (a field transcript's speaker-labelled window), a string with a check, not an enum,
   so a later kind needs no label ceremony. Migration `0097_chunk_kinds` adds it with the default
   `PASSAGE`, marks every `SIGNED_IN` chunk `WINDOW`, and adds a `BEFORE INSERT` trigger that marks a
   `SIGNED_IN` chunk the release before writes the same way (field transcripts are always deleted
   and inserted again, never updated, so an insert trigger is enough).
2. **Windows are written `PUBLIC`.** `field_voices_records` writes each window `PUBLIC` with kind
   `WINDOW` (`SourceChunk.kind`, kept by `indexing.replace_planned_chunks`). The recheck reads
   `PASSAGE` chunks only; the citation contexts read `PASSAGE` chunks within the open ACLs; two
   neighbouring passages join for a quote only when their ACL and kind agree.
3. **A search names the kinds it reads.** `KnowledgeQuery.chunk_kinds` defaults to `PASSAGE`, so the
   stored pack, the lede, the facet coverage and the evaluation read what they read before; the
   artisan seat (`FIELD_READING_KINDS`) and the voice turn ask for both kinds, as they read
   `SIGNED_IN` before. `statements.chunk_conditions` takes the kinds beside the ACLs.
4. **One open set.** `SIGNED_IN_CHUNK_ACLS` is removed. `OPEN_CHUNK_ACLS` is what every reader reads
   (`chunk_acls_for`) and what a loader that names no reader reads: `PUBLIC`, and `SIGNED_IN` until
   the windows written with it are folded into `PUBLIC`. A loader naming no reader (the knowledge
   API, curation terms, reader facts) now reads a citation linked to a window, as an anonymous
   reader already did; `READER_TIERS` is `PUBLIC` then `RESEARCHER`. The migration that sets every
   `SIGNED_IN` chunk to `PUBLIC` and drops the label waits for this release to be live
   (`docs/TECH_DEBT.md`).
5. **A craft reads the shared concepts linked to it.** `hybrid.craft_scope` adds
   `CraftScope.linked_ids`, from `retrieval/shared_links.linked_shared_concepts(session, craft_ids)`
   over the craft and the crafts merged into it: a shared concept (no craft, no sub-category,
   `OPEN`) is linked when a glossary term that names it (`TermConcept`) is a term of the craft
   (`TermCraft`), the graph the shared-science explorer draws, or when a concept edge joins it to
   one of the craft's own concepts. The links are stored rows, written by the glossary seed, the
   curation import and approved structure proposals; nothing infers one with a model. A reviewer
   who wants one shared fact read by a craft files it under the craft in the review queue
   (decision 0136). A family's science (a concept a `CuratedCategoryClaim` fact is about, or one
   named as a category) is never linked, so another family's facts stay out of a craft's answers;
   an unlinked shared concept stays with searches for any craft. Only the stored search's scope
   reads the links: the page stamp, the review queue, the candidate gates and `knowledge_view` read
   as before.
6. **No new spend.** The linked claims are ranked inside each search's `limit` like the rest, so a
   section's evidence and its prompt stay the same size; no call is added.
7. **The paid checks choose their checks.** `paid_checks --checks` takes groups (`narration`,
   `music`, `image`, `speech`, `agent`, `video`; every one but `video` by default,
   `paid_check_runs.CHECK_GROUPS`), and the workflow has a boolean input for each, `video` off.
8. **One clip, recorded whole.** The `gemini_video` step (`scripts/paid_check_video.py`) asks
   `GeminiMediaWire` for one clip of the first `VIDEO` route's model with the job's requested
   output (16:9, 720p, `8s`), estimated from the catalogue at US$0.07 a second for 8 s (US$0.56)
   and counted against the run's cap. It polls every 5 s for up to 15 minutes, always deletes the
   interaction, and keeps the start, the first open poll, the finished interaction, the `DELETE`
   reply and the clip, with the clip's exact duration and size, whether it came silent, how long
   it took and whether `media/output.checked_output` would store it. It asks text-to-video only:
   the documented image-to-video shape names no first frame (an `image` block before the text,
   with `generation_config.video_config.task` `image_to_video` shown only as a fallback, and the
   examples wrap `input` two ways), and a wrong input would spend the one approved clip.
9. **Scripts may import `media`.** The step reads the media pipeline's MP4 reader, requested output
   and storage check, so `LAYER_IMPORTS` lets `scripts`, an entry point like `api`, import `media`.

## Consequences

- Migration `0097_chunk_kinds` shares its parent with the other lanes' migrations of this round; the
  lead links the chain.
- Until the label migration, `SIGNED_IN` rows and the insert trigger stay; the trigger is dropped
  in that migration.
- Answers read the same passages as before; a craft's answers may now rank a linked shared fact
  above one of their own, within the same limit.
- The step runs from the code on the box, so the clip can be made only after this release ships.
  Its recorded finished interaction may hold the clip's base64; the fixture committed from it is
  cut to a small MP4, as the image's was.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/db/test_chunk_kinds_db.py`,
`backend/tests/db/test_field_voices_db.py`, `backend/tests/db/test_field_voices_withdrawal_db.py`,
`backend/tests/field_voices/test_records.py`, `backend/tests/answering/test_citation_contexts.py`,
`backend/tests/retrieval/test_quote_passages.py`, `backend/tests/retrieval/test_statements.py`,
`backend/tests/db/test_linked_shared_concepts_db.py`, `backend/tests/test_paid_video_check.py` and
`tools/tests/test_layers.py`.
