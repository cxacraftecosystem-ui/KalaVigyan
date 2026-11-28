# 0254. A preview refuses what the confirm refuses, a layout names only what exists, and a duplicate is a component that shows the same thing

`preview_page` and `propose_page` (and a confirmed hold, which runs `propose_page`) run one set of
part checks on the same part: a part the confirm would refuse is refused by the preview with the
same reason and the tool that fixes it. A layout placing a label that nothing holds is refused with
the labels named, so a component its own bundle failed to make is never written into the page's
layout, and a published layout that already names one draws the page without it while the preview
names it. The library's duplicate check compares what two components show, their dataset's cells or
their facts, never their place or their words. The references mark every label drawn only on Kutch
Ajrakh's authored page, and a test holds each label they name to the library or to that mark.

Date: 2026-11-28. Status: accepted (the lead's lane brief `ux-1126/proposal-parity`, from the
held Sanganeri proposal `830b8acd-c928-4bd3-bd1b-086753291b24` confirmed that day, and the
coordinator's item from the climate agent's re-proposal). It amends
[decision 0193](0193-components-withdrawn-replaced-or-borrowed-and-pages-held-for-one-confirmation.md)
(a layout over components the bundle failed to make, and the confirm's own checks run before any
part writes) and [decision 0195](0195-a-preview-drawn-seen-and-checked-before-it-is-proposed.md)
(what the preview checks before proposing). No migration. The contracts are
`docs/contracts/open-work.md` (the component proposal's close match, Pages delivered whole, Previews
before submitting), `docs/contracts/page-layout.md` (how a document is ordered) and
`docs/contracts/knowledge-writes.md` (Section proposals), with the cookbook, the component guide and
the contributor skill.

| For | Read |
|---|---|
| The preview and its checklist report | [decision 0195](0195-a-preview-drawn-seen-and-checked-before-it-is-proposed.md), [decision 0110](0110-contributor-supplied-sources.md) |
| A page held for one confirmation, borrowed components | [decision 0193](0193-components-withdrawn-replaced-or-borrowed-and-pages-held-for-one-confirmation.md), [decision 0248](0248-what-the-fresh-agent-could-not-fix-on-sanganeri.md) |
| The library search and the two ways on | [decision 0101](0101-knowledge-architecture-for-every-craft.md), item 16 |
| A section's checks and its judge | [decision 0250](0250-a-contributor-s-ai-proposes-a-field-s-section-from-the-facts-its-page-holds.md) |
| A translation's preview, which already shares its checks | [decision 0117](0117-pages-in-other-languages.md) |

## Context

On 2026-11-28 an Opus agent built Sanganeri's climate figures over MCP. Its last `preview_page`
passed and refused no part; the person confirmed the hold and 1 of its 9 parts was accepted. Each
cause was read in the code and checked against production (`get_page` and `list_components`) and the
agent's saved component files before anything changed:

1. **The preview skipped the component proposal's own checks.** `page_preview._component` ran the
   bundle's checks (keyed to the page, a borrowed link) and the delivery checks, while the confirm's
   `component_proposals.propose_component` also checks the task, every label in
   `considered_labels` and `extends` (`_check_labels`, `NOT_IN_LIBRARY`), a label kept or waiting,
   the replaced component, the craft, the subjects and the library search. Six of the hold's seven
   components named `shared/climate/kachchh-annual-temperature-chart` in `proposal.considered_labels`
   (the field, read from the agent's saved components), and that label is not in the library, so the
   confirm refused all six; the seventh was refused by the library search, which the preview never
   ran. The layout part checked only its base version and borrowed labels in the preview; the section
   part ran the right checks with other words.
2. **A layout was written over components refused in the same bundle.** `propose_layout` checks the
   base version and nothing names a label's existence, so version 4 of Sanganeri's layout was written
   at once. It has 25 entries, and 8 name components that do not exist: the seven
   `shared/climate/jaipur-*` labels and `sanganeri-hand-block-printing/history/dated-record-on-the-map`
   (refused as a duplicate in round 1 and kept in the layout since). The page draws without them:
   `page_layout.arranged_layout` orders only what the document holds and ignores any other entry, and
   the web client reads the stored layout only to size and crop what the document holds.
3. **The cookbook named a component outside the library.** The chart entry's Kutch Ajrakh line
   (`ajrakh-why-kachchh/1`) names the temperature chart beside the rainfall chart. It is Fig. 16 of
   Kutch Ajrakh's authored page and has a component home there, but `load_monograph` registers an
   authored component only when a unit within it cites a stored fact, and its four units (u0713 to
   u0716) cite none, so it was never registered. The coordinator's guess that the duplicate check kept
   it out is not so: the check never ran on it. Of the 80 labels the references name, all Kutch
   Ajrakh's, 40 are registered this way and 40 are drawn on Ajrakh's page alone, unmarked.
4. **The duplicate check matched place, not content.** `match_reasons` counted any library component
   of the same kind keyed to the same concept, compound or place as a close match, and also titles
   sharing half their words. The climate agent's district map was refused as a copy of
   `sanganeri-hand-block-printing/geography/sanganer-water-and-courts-map` (both keyed to `lgd:102`)
   though one draws the rainfall layer and the other the river and the court cases; to pass, the
   agent keyed four of its six Jaipur figures to the craft alone and reworded their titles.

## Decision

1. **One set of part checks.** `services/page_part_checks.PART_CHECKS` holds one check a part kind
   (fact, structure, component, layout, picture, withdrawal, section), each the confirm's own checks
   that refuse a part before anything is written: a fact's page and task; a structure item's page,
   owner, target and task (`structure_proposals.fitting_structure`); a component's page, borrowed
   link and every check of `component_proposals.checked_proposal`, the part of `propose_component`
   before it stores, the library search among them; a layout's version, the labels it places and its
   borrowed labels (`page_layout_checks.layout_problem`); a picture's page and, given, its gift or,
   new, its upload slot (`upload_links.checked_slot`, the part of `start_upload` before it writes);
   a withdrawal's who, its reason and an Admin's request already waiting
   (`component_withdrawals.withdrawal_problem`); a section's page and facts
   (`section_proposals.checked_section`). `propose_page` runs `PART_CHECKS[part]` before each part's
   writer, and `preview_page` runs it before drawing the part, so both report the same refusal. The
   writers keep calling the same functions, so no check has a second copy. The preview's own
   refusals that the confirm writes as records use the confirm's words: a structure item's stated
   check (`structure_proposals.stated_refusal`) and a section's four checks
   (`section_proposals.refusal_message`). A translation keeps its own shared checks (decision 0117).
2. **What only the confirm checks.** The checks that need a model call: a fact's later gates
   (NOVELTY and the judges) and a section's FAITHFUL judge. The checks that need a live read of every
   source, which `preview_page` never does: the QUOTES and SOURCE gates of a fact and of a structure
   item; `read_source` with `quotes` runs the same reader and matcher before proposing. And what only
   the moment of writing knows: an hour's limit spent, a label taken by a concurrent proposal, and a
   fact the same bundle proposes that a picture's slot or a component registered at once needs shown.
3. **A layout names only what exists.** A layout part is refused, in the preview and at confirm,
   when it places a component label that no registered component, no live component proposal, no
   component of the same bundle that passed (shown in the preview, accepted at confirm) and nothing
   the page draws now holds; a picture's label is left to the pictures. The refusal names the labels
   and the tools that make them (`edit_draft`, `propose_page`, `list_components`). Refusing the layout
   and not the whole bundle keeps the bundle's good parts, so a person's confirmation is never
   wasted on parts that passed. With no layout in the bundle, the preview reports the published
   layout's missing labels as a `LISTED` layout part naming them and the fix; the page draws without
   them, as it already did.
4. **What counts as showing the same thing.** What a component shows is its data, the dataset it
   draws from (`spec.dataset.code`) and the cells of it it draws (each point's, place's or row's
   `cell`; its column is the variable and its unit), and the facts its units cite (a registered
   piece's `claimIds`). Two components of one kind show the same thing when both draw from one
   dataset and share 80 % of the cells they draw or more (both drawing none counts as sharing them),
   or, when either draws from none, when 80 % or more of their facts are shared, shared over all
   (`research/component_showing.same_showing`, `CLOSE_CELL_OVERLAP` and `CLOSE_FACT_OVERLAP`). So a
   rainfall chart and a temperature chart of one district, two datasets, both pass; a rainfall chart
   and its trend drawn from another column of one dataset both pass; a chart restating a registered
   one's facts in other words is refused, and so is one drawing the same cells. A place, concept or
   compound both are keyed to is never a match on its own, and a delivered proposal's words are not
   compared. A proposal without a spec shows nothing yet, so its words are still compared as before,
   and the same label is always a match. The library search adds every registered piece of the kind
   that cites one of the proposal's facts or draws from its dataset
   (`component_library.showing_components`), and the review queue's closest components give the same
   reasons. A threshold of 80 % keeps a figure that reuses one caption fact of many apart from a
   copy, and a restatement, which cites every fact its original cites, is always caught.
5. **The references mark what lies outside the library.** The cookbook marks each of the 40 labels
   drawn only on Ajrakh's page "page only" where it names it, says in Reading an entry that such a
   label is never named in `considered_labels`, `extends` or a layout, and says in Placing a component
   what a layout may place. The component guide and the contributor skill say the same in their own
   words. `backend/tests/mcp/test_reference_labels.py` reads the library from the repository's seed,
   Kutch Ajrakh's `content.json` and its dossier, by the rule `load_monograph` registers with
   (`monograph_load.component_units` and `cited_refs`, now shared), and the authored pages' component
   homes (`document_components_homes.authored_homes`), and fails a reference naming a label in neither,
   or one drawn only by an authored page without the mark. The storyboard example in the interactives
   skill names a label for a new component, which no reference test reads.

## Consequences

- An agent sees at preview every refusal its confirm would give, the model-call and live-read checks
  aside, so a held page carries no part that its own preview passed and its confirm refuses for a
  check the preview could run. Tests: `backend/tests/db/test_page_part_parity_db.py` (every part kind
  of `PART_CHECKS` refused alike by both when its check refuses, built from the registry the confirm
  runs; a label outside the library refused alike and a registered one passing both; a restatement
  refused alike and a component of other facts passing both; a layout over a refused component
  refused and never written, one over what exists written; a published layout naming a missing label
  drawn without it and named by the preview, and one naming only what exists adding nothing) and
  `backend/tests/research/test_page_part_checks.py` (every part kind of the contract but the
  translation has a check; a layout naming a missing component arranges the page without it).
- Sanganeri's published layout v4 keeps drawing the page without its 8 missing labels. Its next
  preview without a layout names them as a listed layout part; a new layout naming them is refused
  until those components are registered, wait for review or are made in the same bundle. Nothing in
  production was written by this lane.
- The duplicate check no longer pushes an agent to key a figure away from its district or to
  reword it: tests `backend/tests/research/test_component_showing.py`,
  `backend/tests/research/test_component_proposals.py` (a delivered proposal matched by what it
  shows, not by its words or place; the old "keyed to the same compound" case now passes, the
  owner's rejected behaviour changed in the test) and the parity test above.
- The preview runs the library search and the label checks, so a preview of a bundle with many
  components reads the library once more per component.
- Left open: the fact and structure source gates run at confirm only; running them in the preview
  would read every cited source on every preview. A component registered only in production cannot
  be named by the references, since the test reads the library from the repository's seed.
