# 0069. Learning screens: follow-ups, saved answers, notes, lessons, exports, the map and compare

The learning screens draw follow-ups on top of the explainer being read, stored explainers in the
ask screen, saved answers and notes on `/saved`, professors' lessons, exports under the server's
file name, ask the map and a compare page. Cited text outside the explainer uses one reading frame.

Date: 2026-11-18. Status: accepted. Amended by 0067 (item 5: lesson files and the report PDF are
signed links) and by 0070 (item 3: notes are held per account; item 7: an unknown craft and a
comparison with nothing cited are told apart).

| For | Read |
|---|---|
| What amended it | [0070 Phase D review fixes](0070-phase-d-review-fixes.md): item 3, notes held per account, and item 7, an unknown craft told apart from a comparison with nothing cited |
| What amended it | [0067 Lesson packs, the explainer PDF and citation export](0067-lessons-and-exports.md): item 5, with lesson files and the report PDF as signed links |
| What amended it | [0141](0141-design-system-and-answer-screens-without-debt.md), items 6 to 8: Check yourself asks only when `done` offers a quiz, an empty added section leaves with its version, and a lesson's sections reorder |
| The contract it was built to | [0062 Phase D contract: learning blocks, versions, alerts, lessons, exports and the map](0062-phase-d-contract.md) |
| The contracts it names | [learning.md](../contracts/learning.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase D of `docs/plans/answer-experience.md` ("Learn and act", owner-approved, section 8 final)
fixes its routes in `docs/contracts/learning.md` (decision 0062) and builds them in lanes 0063 to
0067. This lane draws the screens around them and edits no backend file: follow-ups that extend
an explainer with a version switcher, Save and an in-app inbox of "This answer got better" notes,
the lesson builder, the explainer's PDF and citation exports, ask the map, and the compare entry
point. The boards are `Learn`, `Journeys`, `Explainer`, `Map` and `Nav` of the design project.
Rules that bind: every fact is cited to a source or a dataset row, roles come from the backend and
the client hides what a role cannot do, nothing widens a 390 px phone page, every animation has a
static end state under either reduced-motion switch, and no how-it-works copy reaches a screen.

## Decision

1. **A follow-up streams on top of the explainer the reader is looking at.** "Ask a follow-up",
   the "Ask next" suggestions and a term's "Ask about it" send `{question, depth: null, buildsOn
   {explainerId, version, facets: []}}` (`lib/explainerVersions.followUpRequest`) once the shown
   explainer is stored and is its latest version; before that they ask a new question as they
   did. The state keeps the base version's sections (`followingExplainer`, `basedOn`), the
   `builds_on` event must name that base (else the answer fails with "This explainer changed…"),
   a `section_started` for a base section reopens it, a deepening block goes after the section's
   own blocks and before its pictures (`withDeepeningBlock`), and `version` stores the new
   `VersionMark` (`ExplainerState.mark`). `explainerRef` names the shown explainer and version:
   the base while a follow-up runs or after it fails, the mark once stored, else a finished first
   answer's own id at version 1. `reduceAnswerEvent` wraps `reduceExplainer`, which is unchanged.
2. **Stored explainers open in the ask screen.** `/ask?explainer=<id>[&version=<n>]` loads
   `GET /api/explainers/{id}` or `.../versions/{n}` (`explainerStateOf`), which also marks it seen;
   a follow-up replaces the address with the explainer's own, so a reload shows the stored latest
   version instead of asking again. The version picker (the one searchable select, newest first,
   "Version 2 · latest") appears from two versions, says what the shown version changed
   ("Deepened Why the water matters · Added History") and offers "Read the latest"; a follow-up
   is offered only on the latest version, since the server refuses another (409).
3. **Saved answers and notes live on `/saved`.** Save is a button on the explainer (pressed state,
   constant name) over `PUT` and `DELETE /api/saved-explainers/{id}`; `/saved` lists the notes
   first, then the saved answers with their version and "Newer version" when the reader has not
   opened the latest. A note reads "This answer got better", the question linked to its
   explainer, the craft and its news ("3 new findings in Geography and water · 1 in History",
   `lib/savedView.newsText`), with "Update the answer" and, while unread, "Mark read". Update
   marks it read and opens `/ask?explainer=<id>&update=<facets>`, which loads the latest version
   and asks the version 1 question as a follow-up for those facets under the reader's own caps
   (the contract's Update); nothing is asked on anyone's behalf. One store (`useNotes`) feeds the
   page and the unread count on the Saved entry of the navigation (desktop strip, sheet and the
   phone island's badge), refreshed at most once a minute and on focus. The weekly email switch is
   on Settings and is drawn only while `GET /api/preferences/me` says `alertDigestOffered`.
4. **Lessons are a professor's screens.** `/lessons`, `/lessons/new` and `/lessons/{id}` carry a
   route guard on `canBuildLessons` (the backend's `BUILD_LESSONS`), the nav's Lessons entry
   follows it, and the explainer offers "Make a lesson" only to that role. The builder chooses the
   version's finished sections (all at first, at most 14, kept in the explainer's order), an
   optional title (the question when blank) and a quiz switch, and posts the contract's
   `LessonRequest` (`lessonRequest`); the pack page previews every slide in order (a section's
   cited bullets with their chips and its open picture with credit, each quiz question with its
   key marked, the reading list by the server's order with reliability and how often it is cited,
   and the sources), downloads the PPTX, PDF and HTML files and offers the citation menu.
5. **Exports take the server's file name.** The explainer's Export menu (Report as PDF; citations
   as APA, BibTeX, RIS and CSL-JSON) and the lesson files go through `lib/download.downloadApiFile`,
   which saves the body under the name in `Content-Disposition` (`filename*` first) and refuses a
   file that comes without one, so every name stays the server's (`services/naming.py`); a
   refusal shows the route's own sentence. Every role that may export sees Export
   (`canSaveExport`, the backend's `SAVE_EXPORT`).
6. **Ask the map reads the stored district.** Districts on `/map` are tappable with or without a
   layer (an open fill when none is chosen; the shapes load once with the page); a tap sets
   `?district=<lgd>`, outlines the district, tags it with the layer's reading or its name, and
   opens the district panel under the map: the crafts with a cited location there (linked, with
   their roles and the location's source and level), "Why the land suits them" with the stored
   blocks drawn by their renderers and the district's soil, climate, water and terrain values,
   the numbered sources, every dataset credited once and the boundary caption. Two or more crafts
   offer "Compare these crafts".
7. **Compare has a page and three doors.** `/compare?crafts=a&crafts=b` (two to four different
   crafts, `lib/comparePage`) picks crafts from the catalogue as removable chips and draws the
   comparison route's block with the phase D table renderer and its sources; a comparison with
   nothing cited says so. The explainer offers "Compare with <candidate>" (or all its crafts when
   it names several), and the district panel offers its crafts.
8. **One reading frame for cited text outside the explainer.** `components/answer/CitedReading`
   (the reading and citation contexts, the source dialog and the term sheet over sources numbered
   in their listed order, `citations.listedSourceNumbers`) and `ListedSources` serve the lesson
   pack, the district panel and the comparison; `RegionPlaceCard` exports `BasisLine` and
   `FacetBlock` for the district panel.
9. **Check yourself.** A finished explainer asks `GET /api/answers/{answerId}/quiz` once and, when
   a quiz comes back, offers it collapsed under the explainer, drawn by the phase D quiz renderer.

## Consequences

- `e2e/learning-screens-unit.spec.ts` and `e2e/lesson-map-screens-unit.spec.ts` drive the screens
  from the learning goldens: a follow-up rebuilding version 2 block for block from the version 1
  document, the stale-base refusal, the request, versions and their changes, the role gates,
  notes read and unread and the news line, saved answers and a newer version, file names and a
  refused file, the builder's defaults, the pack's slides, picture, quiz, reading list and files,
  the district's crafts, land story, values and credits, compare's rules and picker, the motion
  switches and the shrinkable tracks.
- `ExplainerState` gains `mark` and `basedOn`; `ExplainerView` takes optional `tools`, `versions`
  and `footer` slots; `AskRequest` takes `buildsOn`; the stream reads `builds_on` and `version`.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
