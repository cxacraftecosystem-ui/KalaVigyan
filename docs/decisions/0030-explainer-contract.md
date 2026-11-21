# 0030. The explainer contract

The explainer contract turns an answer into sections of typed blocks under one envelope with a
version per kind, streamed as they are ready and stored as knowledge pieces for reuse. It fixes the
vocabulary, sentences and terms, the ladder, images, depth by role, artisan voices and the fixtures
phase A's lanes build to.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The lanes built to it | [0031](0031-understanding-and-depth.md), [0032](0032-sectioned-composition.md), [0033](0033-knowledge-pieces-and-reuse.md), [0034](0034-images-and-terms.md), [0035](0035-listen-and-voice-switched-off.md), [0036](0036-asking-screen.md) and [0037](0037-explainer-ui.md) |
| The review that fixed it | [0038 Phase A review fixes](0038-phase-a-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

`docs/plans/answer-experience.md` (owner-approved 2026-11-17, section 8 final) turns an answer
into an explainer: sections of typed blocks, streamed as they are ready, stored as knowledge
pieces for reuse, with depth by role. Phase A is built by parallel lanes (0031 understanding and
depth, 0032 sectioned composition, 0033 stored pieces and reuse, 0034 images and terms, 0035
Listen and voice switched off, 0036 the asking UI, 0037 the explainer UI, 0038 review fixes). The
practice skills ask for the interface they share to be agreed and built first, pinned on both
sides by tests against hand-written fixtures. The plan names the pieces but leaves their shapes,
several rules and some readings open.

## Decision

1. **Home.** The models live in `backend/app/research/` because the answer stream validates
   every frame and `research` is the layer `stream.py` lives in: `explainer.py` (document,
   events, kind registry), `blocks.py` (envelope and the phase A kinds), `blocks_place.py`,
   `blocks_matter.py`, `blocks_people.py` (later kinds by subject), `terms.py`, `media_refs.py`,
   `subject_keys.py`, `knowledge_pieces.py` and `depth.py`, each under 400 lines. `stream.py`
   imports the explainer events, so the cited-sentence shapes it owned (`SourceRef`, `Citation`,
   `AnswerSentence`) moved to `research/citations.py` to avoid a cycle; `stream` re-exports them
   so their other importers are untouched. The first-citation walk `cited_source_ids` moved there
   from `schemas/science.py` (its three importers switched), since blocks need it and `research`
   may not import `schemas`. `absent` (the "leave out when null" test) joined `research/base`.
2. **Vocabulary.** `BLOCK_KINDS`, `EXPLAINER_DEPTHS` and `DISCIPLINES` are tuples in
   `models/enums.py`, ready to become the stored piece's database enums, with literal types in
   `research/vocabulary.py`. Block kinds keep the plan's lower-case names. `FACT_LEVELS` (every
   level but `HYPOTHESIS`) is one constant there. A section's discipline and a piece's facet share
   one vocabulary: the owner's fields of 2026-11-17 plus `OVERVIEW` and `PROCESS`.
3. **One envelope, a version per kind, built kinds guarded.** Every block is `{id, kind, version,
   reuse, ...}`; all 21 kinds of plan 2.1 are models now, with their fields, so later phases fill
   them without changing the envelope. `BUILT_BLOCK_KINDS` (`prose`, `process_ladder`, `images`)
   is a guard that fails closed: the `block` event, the stored explainer, a stored piece and the
   client parser refuse any other kind, so nothing reaches a reader before its renderer exists.
   A block refuses itself when it cites nothing (images by the claims they illustrate, map layers
   by their datasets).
4. **Sentences and terms.** Block sentences are today's `AnswerSentence` plus `terms`. A term
   span is the marked text and its key, found in the sentence, not character offsets, because
   Python counts code points and the browser UTF-16 units. Prose, ladder and term sentences state
   facts only; hypotheses stay open questions.
5. **Ladder.** `research` cannot import `schemas.science`, so the ladder has its own small stage
   shape holding the stored stage, material and reaction ids (the Process tab keeps the full
   science view). A condition shows the source's own words (`stated`), which must occur in one
   of its citation quotes; normalised values stay with the science engine.
6. **Images.** An image names the claims it illustrates, which another block of its section must
   cite. `MediaRef` is inline only under an open licence (the existing allow-list) and with its
   author; everything else is a credited link card whose thumbnail is loaded from the source site
   and which opens the source page (owner O2). `credit` carries a site's own credit line (the
   V&A's copyright notice).
7. **Stream.** Six events join `STREAM_EVENTS`: the five the plan names and `section_state`,
   because plan section 1.4 shows each section's working state (researching, writing, checking)
   changing after it starts. `section_done` ends a section `READY` or `EMPTY` with what was
   searched (plan 2.1). `understood` replaces `match` and never blocks: the best candidate
   proceeds and the rest are offered; no craft is "Any craft". Trail keys reuse the evidence ids,
   with `source:` and `piece:` prefixes for stored knowledge. `open_question` and `reaction` stay
   until `open_questions` (phase D) and `reaction_player` (phase B) are built, so phase A loses
   neither. The 60 s heartbeat is unchanged.
8. **Depth.** Basic and Detailed run as `HYBRID`, Expert as `DEEP`; `VERIFIED` stays internal as
   the stored-only answer that still works when spend is refused. Mapping Basic to `VERIFIED`
   was rejected: `VERIFIED` shows only reviewed and verified claims and never researches, so a
   student's default answer would be nearly empty today and would never grow the knowledge base,
   against PLAN section 0 and plan 2.4's "stored first, light". Basic stays light through its 3-4
   sections and 2 experts. Every known role may choose every depth (plan: "anyone can switch"),
   Master Admin is the only uncapped role and is never degraded (owner O3), and past the degrade
   mark Expert becomes Detailed for everyone else. The defaults, ranges and caps are data in
   `research/depth.py`; the cap amounts are AI budget settings that lane 0031 adds.
9. **Stored pieces.** A piece holds a block as built (no reuse mark), sorted claim and source
   ids derived from it, and a content hash over its JSON without placement fields (`id`, `reuse`),
   so the same content placed in two explainers hashes the same. Reuse rewrites only `id` and
   `reuse`. Topic keys are `<namespace>:<subjects>` with a fixed namespace list and subjects
   slugged, deduplicated and sorted, so `alum and alizarin` and `alizarin and alum` meet. The
   reuse rule is the plan's (craft, facet, topic, depth at least, every claim visible) plus not
   stale and not superseded; block kind is not part of it, so a facet's ladder and prose are both
   reusable. A retraction, a hide, a level change or a text change stales the pieces resting on
   the claim. The embedding is a table column, not part of the model.
10. **Terms.** A term summary may come from stored cited claims first (`STORED`), then Wikipedia,
    then a web search, as plan 2.8 orders the last two: what the knowledge base already holds,
    cited, is preferred to a fresh model summary (PLAN section 0).
11. **Artisan voices.** Quotes name the artisan with credentials and place, and an address where
    the answer needs it (owner O4 and the owner's request of 2026-11-17); a phone number, email
    address or identity number anywhere in the block refuses it.
12. **Client.** `frontend/lib/explainerContract.ts` types every kind name and builds runtime shapes
    for the built kinds only, with the existing shape kit, so a kind the server does not send yet
    is refused rather than drawn; `explainerStream.ts` parses the stream's events. Their
    vocabularies are pinned to the backend tuples by `e2e/backend-vocabulary-unit.spec.ts`, and
    Frontend checks now run when those backend files change.
13. **Fixtures.** Written by hand from the seed claims, the seeded sources and the science
    golden's ids, so every citation resolves to a seeded claim source and the tests check it
    through `claim_seed.seed_id`. The two pictures are real: a CC BY-SA 4.0 Commons photograph
    taken in Kutch (metadata read from the Commons API) and the V&A's own thumbnail of the
    Ajrakh process sample, a seeded source, as a link card.

## Consequences

- No service, route, table or screen exists yet; each lane builds against these models and must
  make its output reproduce the fixtures.
- Lane 0031 lets every role ask at every depth, which today's `ASK_DEEP` capability (Researcher
  and above) does not; lane 0033 adds the `KnowledgePiece` table and its enums; lane 0034 the
  `Term` and `MediaRef` tables and the image hosts in the CSP. These are in the debt register.
- A badly formed block fails loudly where it is produced, never on a reader's screen.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
