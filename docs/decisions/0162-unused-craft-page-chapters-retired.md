# 0162. The craft page's chapters keep only what a page draws, and an approved structure writes its shared rows at once

The pieces of the version 3 craft page that were never built are retired rather than built, and so
are the parts no page draws: a reader's answer pieces joining the chapters, the archive of earlier
versions, the concept pictures and job steps 2 and 3. The web stops parsing the chapters, since no
screen draws them; the chapters stay as the structure a curated craft's monograph document takes.
An approved glossary term or reaction writes its shared glossary entry or science row at approval.

Date: 2026-11-23. Status: accepted (the owner, 2026-11-23: "retire the unused v3 craft page
chapters"; the lead's monograph follow-up brief). It amends
[decision 0098](0098-craft-page-chapters-build.md) (items 6, 8, 13 and 14 and its list of what was
not built) and [decision 0096](0096-reader-question-pieces-join-their-craft-page.md) (the merge of a
reader's pieces into the chapters), and [decision 0108](0108-structure-proposals-become-curated-facts.md)
(what approval writes). The contracts are `docs/contracts/craft-page.md` and
`docs/contracts/knowledge-writes.md`.

| For | Read |
|---|---|
| The chapters' build it amends | [decision 0098](0098-craft-page-chapters-build.md) |
| The reader's pieces it stops joining | [decision 0096](0096-reader-question-pieces-join-their-craft-page.md) |
| A release the live side can read, which orders the payload's changes | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| The AI media still joining the chapters | [decision 0154](0154-ai-media-and-film-scores-kept-true.md) |
| What approval of a structure proposal writes, which item 5 amends | [decision 0108](0108-structure-proposals-become-curated-facts.md) |
| The page's chapters, parts and job | [craft-page.md](../contracts/craft-page.md) |
| The archive table and `fromQuestion` dropped in the release after this one | [decision 0168](0168-a-table-under-a-said-sentence-and-python-within-budget.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0098 left a list of chapter pieces not built: `what_if`, `concept_graph`, `zoom_story`,
`supply_map` and `measure`, reaction players cut per mechanism, concept pictures, the rest of
decision 0096's merge with its question screen, job steps 2 to 5, and archived versions read through
the live field-voice filters. Since then every craft's page became a monograph document: Kutch
Ajrakh's authored one, a generated one for each curated craft, and the record page for the rest.
No screen draws `GET /api/crafts/{slug}/page`'s chapters; the web parsed and checked them only.

The brief named `chapter_records`, `chapter_chem` and `craft_chapters_job` as paths no page reads.
They are read: `services/document_components_store.subject_structure` builds every curated craft's
generated document from the page's chapters (`document_components.document_structure` takes their
key facts, places, communities, disagreements, open questions and drawn blocks such as the ladder,
the reaction player, the molecules and the region story), `place_ground` reads `chapter_records`'
place points, and job step 1 keeps the conformers and Wikidata points those blocks draw. Deleting
them would empty every generated document.

## Decision

1. **Retired rather than built.** The five chapter pieces, a What if builder, players cut per
   mechanism and concept pictures (job step 3, and the always-empty `ChapterRows.concept_pictures`)
   are not built. Their figure titles leave `research/craft_chapters.FIGURE_TITLES`, `concept_graph`
   leaves the kin kinds, and the four that only a reader's piece could bring leave
   `document_components.DRAWN_BLOCK_KINDS`. Job step 2 (a generated explainer per concept) is not
   built; an explainer an answer stores in a concept's slot still joins `chem`. `whatif` stays a
   chapter key, because the monograph layouts' authored pages hold a What if chapter.
2. **A reader's pieces no longer join the chapters.** `services/craft_page_answer_assets.py` and its
   loader go, and with them decision 0096's merge and its question screen. A generated document
   skipped every item with an origin, so no page ever drew them; what an answer builds reaches a
   page as a registered component of the library. AI media keep joining (decision 0154), since the
   AI media entry of the debt register places them on the monograph.
3. **No archive.** `services/craft_page_archive.py`, `?version=N` and the archive write at a rebuild
   go: an edition (`/crafts/<slug>/v<N>`) is the monograph document of that version, which the web
   already reads. Decision 0151 forbids a migration the release before cannot read, and that
   release still writes and reads `CraftPageArchive`, so the table and its model stay until the
   release after this one drops them.
4. **The web reads the page's head and lists, not its chapters.** `lib/craftChapters.ts`,
   `craftChapterReads.ts`, `craftContributed.ts` and `craftOrigins.ts` go; the page shape drops
   `chapters` before parsing (`UNREAD_CHAPTERS`), so it reads a page with or without them, and keeps
   the masthead plate and the source groups (`craftPageContract`); the answer block's own kinds live
   with its spec (`answerBlockSpec.PAGE_BLOCK_KINDS`). The backend keeps sending `chapters`, valid as
   before, so the web of the release before still reads the page while the backend ships first.
   `ItemOrigin.fromQuestion` stays in the payload, always null, for the same reason.
5. **An approved structure proposal writes its shared rows at once** (amending decision 0108's
   consequences). A glossary term writes the shared `Term` the import would write for it (keyed by the
   term's slug, `curation_records.label_key`), its `TermCraft` and `TermConcept` links, the entry's
   `termKey` and the term's stored English summary (`write_curated_term_summaries` for that key); a
   reaction on a stage writes its `Reaction` row through the import's own `curation_structure.reaction_row`
   under the page's stage, a `ReactionCitation` per quote of its fact, and the entry's `reactionId`
   (`services/structure_proposals_rows.py`). Waiting for the next export and import was the
   alternative; until then the shared glossary and the science players did not know the approved item.
   Every row is inserted only when missing, so the next import of the exported dossier writes the same
   rows under the same ids.

## Consequences

- The register entries "Craft page chapters not built yet (decision 0098)" and "The decision 0096
  merge is the minimal novelty rule" are cleared. A new entry asks the release after this one to drop
  `CraftPageArchive` and `fromQuestion`.
- `GET /api/crafts/{slug}/page` ignores `version`; the route's tests and the snapshot's DB test
  hold that no page is archived.
- Each source's `supports` count is held by a backend test over the chapters' shown sentences, since
  the web no longer reads them.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/curation/test_craft_page_route.py`, `backend/tests/curation/test_craft_page.py`,
`backend/tests/db/test_craft_page_snapshots_db.py`, `backend/tests/db/test_structure_writes_db.py`,
`frontend/e2e/craft-page-unit.spec.ts` and `frontend/e2e/monograph-blocks-unit.spec.ts`.
