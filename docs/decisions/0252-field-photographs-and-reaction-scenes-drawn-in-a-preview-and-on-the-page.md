# 0252. Field photographs and reaction scenes drawn in a preview and on the page, and the rules that name what to fix

A field photograph placed by its label is drawn in a preview's pictures and seen by its drawing
checks: the renderer reads it through its pass from the site, never from the media bucket it cannot
open. `list_field_photos` shows each photograph as a thumbnail with its address, and a generated
page's masthead photograph sits in a figure that names its label, where the drawing checks look. A
reaction step's species is drawn in the material its facts state or by the mark of a colourless
substance (`clear`, `gas`, `ion`), never as an empty outline: the preview names each one drawn with
no colour, and its drawing checks refuse the page until none is left.
Rule 24 counts a field's cited sentences wherever the page draws them, so a page whose sections are
written in full passes; rule 25 names the figure, the unit and the sentence it repeats, and rule 26
the fact that reads as a gap and the tool that fixes it.

Date: 2026-11-28. Status: accepted (the lead's lane brief `ux-1126/page-media`, after the
Opus agent's Sanganeri Hand Block Printing build over MCP filed what it could not do). It amends
[decision 0195](0195-a-preview-drawn-seen-and-checked-before-it-is-proposed.md) (the pass opens a
third route), [decision 0228](0228-players-molecules-and-timelines-that-play-and-a-reaction-s-species-drawn-from-the-kit.md)
(a species with no recorded colour is no longer drawn as a dashed outline on a published page) and
[decision 0233](0233-room-for-a-whole-page-its-reading-tools-and-the-site-s-own-gaps.md) (a portal
photograph placed by its label is now seen and drawn) and [decision 0248](0248-what-the-fresh-agent-could-not-fix-on-sanganeri.md)
(the tool named for each failed rule now names the figure, the sentence and the fact). No migration. The contracts are
`docs/contracts/open-work.md` (Drawn as a reader sees it), `docs/contracts/page-layout.md` (Field
photographs), `docs/contracts/component-specs-general.md` (The figure kit) and
`docs/contracts/component-specs-science.md` (the composed reaction player) and `docs/contracts/open-work.md` (the checklist report: rules 23 to 26), with the
contributor skill, the component guide, the interactives skill and the page checklist (rule 27).

| For | Read |
|---|---|
| The renderer and its pass | [decision 0195](0195-a-preview-drawn-seen-and-checked-before-it-is-proposed.md), [open-work.md](../contracts/open-work.md) |
| The field photographs a page may show | [decision 0112](0112-reviewed-field-photographs.md), [decision 0233](0233-room-for-a-whole-page-its-reading-tools-and-the-site-s-own-gaps.md) |
| A reaction's species from the kit | [decision 0228](0228-players-molecules-and-timelines-that-play-and-a-reaction-s-species-drawn-from-the-kit.md), [component-specs-general.md](../contracts/component-specs-general.md) |
| The page checklist | `backend/app/data/contributor/references/page-checklist.md` |

## Context

1. **The field photographs (verified).** The agent placed 15 of Sanganeri's 31 portal photographs
   (HERO, OPENER, PLATE) and every one failed in the preview; it filed the gap with
   `preview drawing.blocked: ["kalavigyan-media-626159998512.s3.ap-south-1.amazonaws.com"]` and "the
   masthead picture is not drawn" (read with `admin_reports site_gaps`). Three causes, each checked:
   - A plate's picture is `/api/field-voices/images/<id>`, which answers `302` to a presigned link in
     the media bucket (checked on production with `curl -I`: `Location:
     https://kalavigyan-media-626159998512.s3.ap-south-1.amazonaws.com/...`). A reader's browser
     follows it (the site's CSP names the bucket in `img-src`), so the published page draws it. The
     renderer's guard (`renderer/guard.RequestGuard`) passes only the site and, for images,
     `upload.wikimedia.org`, and its resolver maps every other host to nothing, so the redirected
     request was blocked. The CSP, the picture's label and the presigned link were sound.
   - A generated page's masthead is drawn by `KitMasthead` through `MastheadPlateView`, whose figure
     carried no `data-component`, while the drawing checks find the masthead picture by
     `[data-component="<label>"]`. Every generated page with a photograph at its masthead failed rule
     28 with "the masthead picture is not drawn", whatever the picture's host.
   - `list_field_photos` returned no address and no picture, so the agent could not see a photograph
     before captioning it.
2. **The empty scenes (verified).** The live Sanganeri document (version 116) holds three reaction
   players whose steps carry kit scenes of `species` parts. Every part with no `material` is drawn by
   the kit as a paper bead with a dashed edge (`SpeciesArt`, the contract's "a dashed outline when no
   colour is recorded"): at rest the alizarin player shows two, the iron-tannate player two and the
   indigo player one (oxygen in the air). The "empty dashed squares" are the lane's `clear` swatch,
   the kit's mark for a colourless species: the composer fills every lane species whose colour the
   craft's specimen records do not give with `clear` (`compose_reaction._side`), and Sanganeri has no
   specimen record, so alizarin (CID 6293) and harda's tannic acid, which Kutch Ajrakh draws in
   `--dye-madder` and `--dye-harda`, read as colourless. It is not the blocked host (a scene loads no
   file) and not a missing scene (the spec model refuses a player without one); Kutch Ajrakh's four
   players draw their own scenes and colour every coloured species. The kit had no way to draw a
   colourless species (oxygen, alum, water) except that same empty outline.
3. **Rule 24 and the chapters (verified).** On the live Sanganeri document (version 119) the why
   chapter's prose draws 2 GEOLOGY and 2 CLIMATE sentences and PROCESS 3 of its 27 published sentences
   (checked against `get_page` with `sections`). The drawing does not cap a field; it places a
   field's sentences in two other places: `monograph_generated_why_here.place_why_here` moves up to 8
   of the why chapter's sentences (2 a reading) into the ground figure, after
   `monograph_generated_structure.told_sentences` has kept at most 3 in the prose, and a sentence whose
   facts the structure shows is told by the process ladder, the stage player and the other blocks.
   GEOLOGY's 6 sentences are 2 in the prose, 3 in why_here and 1 in a fact grid; PROCESS's are 3 in
   the prose and the rest in the stage player and the 67-sentence ladder; CLIMATE's 2, 1 and 4 in a
   what-if. Rule 24 counted only top-level `p` units outside a component, so it failed whatever the
   agent wrote. Kutch Ajrakh tells most fields inside its figures too (PROCESS: 2 sentences in the
   prose, 40 in the stage player), so a prose-only count would fail it as well.
4. **Rules 25 and 26 (verified).** Rule 25 said "`<unit>` repeats a sentence of the page" and no tool
   says which figure holds a unit: nine units of the round-1 figures repeated prose and the agent
   could not find them. Rule 26 said "'...' admits a gap" for fact `3ec568cd` ("carried no
   information"), drawn as `fact-health-3ec568cd542f`, naming neither the fact nor a fix.

## Decision

1. **The renderer reads a field photograph through its pass.** The site's proxy sends a request for
   `/api/field-voices/images/{id}` that carries the render pass to `GET
   /api/knowledge/pages/drawn-field-photos/{id}` (`apiProxy.upstreamPath`, beside the own-picture
   route), which streams the photograph's shown copy, its crop where a reviewer cropped it, only while
   the pass's preview names it and the site still shows it (`page_preview_pictures.pass_field_photo`,
   `field_photo_scope.served_photo`, which now gives the copy's type). The renderer keeps to the site:
   no host is added to its guard. A reader's request is unchanged.
2. **The masthead names its label.** `MastheadPlateView` draws the masthead photograph's figure with
   `data-component` set to the picture's label (`MastheadPlate.label`), so the drawing checks find it,
   check it loaded and measure it in the first screen.
3. **The agent sees each photograph.** `list_field_photos` gives each photograph its `pictureUrl` on
   the site and returns it as a 320 px thumbnail captioned with its label, read from its shown copy
   (`services/field_photo_thumbnails`, four reads at a time), 12 a page by default and 24 at most;
   its message says how many it could not show. The visibility rules stay as they were: only a
   photograph the site shows (an Admin's decision, the Master Admin switch) is listed, read or
   served.
4. **A species has a colour or a mark.** A kit `species` part takes `material` or `mark` (`clear`,
   `gas`, `ion`, the lane's marks), never both. The kit draws a mark as a drawn substance (a clear
   bead with a glint, three small rings for a gas, a ringed bead for an ion), on the web and on paper;
   a part with neither keeps the dashed outline, now marked `data-kit-uncoloured`. The composer marks
   oxygen, hydrogen, nitrogen and carbon dioxide `gas`, water `clear` and a charged formula or a name
   saying ion `ion`, in the scene and the lane alike (`compose_scene.species_mark`).
5. **The preview names it and refuses it.** Rule 27 names, for each step, the species drawn with no
   colour, the two fields that colour one and `edit_draft`, and a lane that marks `clear` a species
   its scene colours, with the swatch to give (`research/page_report_species`). The drawing checks
   fail a component that holds a species drawn with no colour (any step, shown or not), so rule 28
   fails and `propose_page` refuses the page until it is filled: no reader sees an empty outline on a
   page published after this release.
6. **A field is told wherever the page draws it.** `ReadPage.told_by_field()` counts each field's
   distinct cited sentences in its prose, in its figures (a cited unit inside a component that ends
   as a sentence, a `related_crafts` component's left out) and in its `answer_block` structure blocks;
   rule 24, the second half of rule 23 and the report's `fields` read it. The drawing keeps its prose
   short where a figure tells the rest, as rule 25 asks; the rule now agrees with it.
7. **Rules 25 and 26 name what to fix.** Rule 25 names the units told twice, or the figure, its unit
   and the sentence it repeats (`<unit> in <label> repeats <unit>: '<text>'`). Rule 26 names a fact
   that reads as a gap by its unit and id with the fix, `propose_facts` for a fact stating what its
   source does find and an Admin's `stage_reviews` retraction (kind `FACTS`, action `retract`), and
   the page's own unit with `edit_draft`; `RULE_FIXES` says the same. `propose_source` is not named:
   it adds a quote and keeps the statement. No tool is added; the list stays at 26.

## Consequences

- A field photograph placed by its label draws in the preview's pictures and passes rule 2 and rule
  28 as a masthead; a hidden one is never served to the renderer, listed or drawn. Tests:
  `backend/tests/layouts/test_field_photo_seen.py` (thumbnails, addresses, the pass both ways),
  `backend/tests/db/test_field_photo_plates_db.py` (the pass reads a placed photograph until a
  reviewer hides it), `backend/tests/db/test_field_photo_reviews_db.py` and
  `test_field_photo_decisions_db.py` (the served copy's type), `frontend/e2e/preview-render-pass-unit.spec.ts`
  (the proxy's two routes), `frontend/e2e/monograph-generated-unit.spec.ts` (the masthead found and,
  unlabelled, not found).
- A species is drawn in its colour or its mark, and one with neither is named and refused. Tests:
  `backend/tests/research/test_kit_species.py`, `backend/tests/compose/test_compose_scene.py`,
  `backend/tests/exports/test_export_species.py`, `backend/tests/research/test_page_report_species.py`
  (named, passed filled, the lane, Kutch Ajrakh's players untouched), `frontend/e2e/kit-species-unit.spec.ts`
  (drawn, and the drawing checks both ways).
- The published Sanganeri page keeps its empty outlines and its typographic masthead until a page
  agent fills its species and places a photograph and proposes the page again (the lane's report
  says how).
- Monograph parity draws Kutch Ajrakh as before: its masthead is a component home, and its players
  draw no kit species.
- A page whose sections are written in full passes rule 24, and a field told once is still thin.
  Tests: `backend/tests/research/test_page_report_told.py` (rules 23 to 26 both ways),
  `backend/tests/layouts/test_generated_why_here.py` (a field held by the ground figure, dense and
  thin, on the real assembly), `backend/tests/research/test_page_report.py`.

## What is left

- `SWATCH_MARKS` in `research/component_specs_science_players.py` (and `frontend/lib/componentSpecsSciencePlayers.ts`)
  repeats the three marks `art_kit.SPECIES_MARKS` now holds; the players' spec file was another lane's
  during this round, so the lane's marks should import the kit's once it is free.
- A compound's own drawing (its skeletal structure from its PubChem record) in a species' place is a
  new feature, not taken here.
- The `kalavigyan-craft-pages` skill's "Where each change goes" table is the lead's to extend (in the
  lane's report).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-28; what the code does today is in the contracts named above and in the tests listed under
Consequences.
