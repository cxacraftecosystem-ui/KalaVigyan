# 0248. What the fresh agent could not fix on Sanganeri: unit words drawn, tiles and bars at their size, borrowed figures held to the page's facts, toggles checked in their lab, prose kept, pictures given and read, and the tool named for each failed rule

A delivered component's unit named where its kind draws plain words (a stat tile's figure, a
disagreement's summary or reading) is drawn as that unit's words. Contributed stat tiles stand in the
flow at their own height in the authored tiles' scope, and a declared bar keeps a track of its own
beside a long reading. The drawing checks name a chart whose bars draw 0px wide and a part drawn
against the page outside its slot. A borrowed component is drawn on a page only when the page holds
every fact its units cite, a why-here figure only when it holds a sentence, and a toggle its lab
draws is checked inside the lab. A figure that shows a fact keeps the fact's sentence in its field's
prose until the field holds three. The acceptance run offers `give_pictures`, the guide says how an
open-licence picture reaches a draft, kin crafts draw their own named plates, the server reads a
failed drawing's pictures, and `preview_page`'s next step names the tool that fixes each failed rule.

Date: 2026-11-26. Status: accepted (the lead's lane brief `ux-1126/acceptance-gaps`, from the owner's
acceptance run of the same day). It amends
[decision 0193](0193-components-withdrawn-replaced-or-borrowed-and-pages-held-for-one-confirmation.md)
(a borrowed component citing facts the page does not hold was refused in a draft but still drawn on
the page), [decision 0234](0234-a-contributor-s-ai-builds-a-page-over-mcp-from-one-line-and-the-run-keeps-what-it-made.md)
(`give_pictures` was not offered to the run) and
[decision 0237](0237-a-preview-s-pictures-read-as-a-designer-by-the-agent-and-by-the-server-only-when-asked.md)
(the server's read was skipped whenever the drawing failed). The contracts are
`docs/contracts/open-work.md` (the server's read; the `give_picture` prompt) and the contributor
skill (pictures by `page_url`; a field's prose from a draft).

Amended by [decision 0249](0249-a-category-draws-its-crafts-shared-figures-a-craft-its-own-place-s-and-the-checks-wait-for-the-api.md): a category's page also holds its crafts' facts, and a craft's page draws a shared figure keyed to its own place.
Amended by [decision 0250](0250-a-contributor-s-ai-proposes-a-field-s-section-from-the-facts-its-page-holds.md): a field's prose is also written over MCP as a reviewed section proposal, which What is left asked for.
Amended by [decision 0252](0252-field-photographs-and-reaction-scenes-drawn-in-a-preview-and-on-the-page.md): rules 25 and 26 name the figure, the sentence it repeats, the fact that reads as a gap and the tool that fixes it.

| For | Read |
|---|---|
| The run | GitHub run 45833659342 (`agent-acceptance.yml`), its summary, transcript, preview and pictures |
| The rules the fixes serve | `backend/app/data/contributor/references/page-checklist.md`, rules 2, 9, 15, 23 to 26 and 28 |

## Context

A fresh agent deepened Sanganeri Hand Block Printing over MCP from one line: $14.84 of $25, 20
components, 8 previews, and it stopped with 10 rules failing, believing the rest needed tools it
lacked. Each claim was checked against the code and the run's files before it was fixed:

1. **Raw unit keys: real.** The delivery gate counts every string of a spec that looks like a unit
   id as a unit (`spec_unit_refs`), and the draft renames them all (`renamed_spec`), but a view
   resolves a unit only where its kind's model types a `UnitRef`. The agent's tiles gave `figure`
   and `small` as units (`u0001`, `u0002`), so the page drew `u5139u5140`; the disagreement cards'
   summaries drew `u5260` the same way. The paper export already printed every unit a spec names.
2. **Empty charts and flat tiles: real, two causes.** A contributed `stat_tiles` had no scope of its
   own (it fell to `mb`, where nothing styles tiles) and, placed beside the text, met the kit's
   `.bx-pt .ws-stats{position:absolute; inset:0}`, which overlays a map card: the slot drew at no
   height. A declared bar chart's row was `minmax(5rem,9rem) minmax(0,1fr) auto`, so a reading
   sentence wider than the row left the bar's track, and every bar, 0px wide: "draws no marks".
3. **Borrowed figures: real.** The draft refused the alizarin molecule and the indigo vat for citing
   facts Sanganeri does not hold, but the page assembly drew any linked shared component a place
   did not exclude. The page's own `why_here` held no note sentence, so it cited nothing (rules 9
   and 15).
4. **Toggles placed alone: the check, not the page.** The lab draws its toggles, but bare inside it,
   so the drawing checks found no `[data-component]` for them, and the render plan counted every
   component of a generated page as placed. A draft's layout already replaces the published one
   entirely; it can neither add nor drop a component.
5. **Prose: half real.** No tool writes a section, but a draft's facts are already drawn as
   sentences of their field's section; the agent did not know. The de-duplication drops a sentence
   whose facts a curated figure shows (never a contributor's figure), which can leave a field below
   three sentences.
6. **Pictures: real, in the harness and the guide.** The run disabled `give_pictures`, the only way a
   picture reaches a draft (by `page_url`, slot `MASTHEAD`, then the draft's `contribution_id`), and
   the contributor skill and the `search_sources` description said KalaVigyan's team places open
   pictures. Kin entries drew the family's plate ground with no name, a blank square.
7. **Pictures not seen: by design of the run.** The server returns the pictures as MCP image content
   (at most 1 MB decoded, `kept_images`); the run calls `preview_page` itself and keeps them as files
   (decision 0240). The server's read, asked for instead, was skipped on every preview because rule
   28 failed, so the agent never learnt what its page looked like.
8. **Stopping early: real.** `nextStep` said "fix each failed rule" without the tool for any of them.

## Decision

1. **Unit words drawn** (`research/spec_text_units.py`, used by `drawn_delivery`). Before a delivered
   spec's units are renamed, every string its kind's model types as plain words (not a `UnitRef` or
   any other pattern) that names one of the component's own units becomes that unit's words, and so
   does every string node of a held text; a `UnitRef` keeps its id so the page cites it. The preview,
   the published page and the review queue draw through `drawn_delivery`; the export prints the unit.
2. **Tiles and bars at their size.** `stat_tiles` takes scope `pt` (`monographScopes.ts`) and a
   contributed tile group stands in the flow (`documentPage.css`), one column in the margin; a
   declared bar row is `minmax(5rem,9rem) minmax(6rem,1fr) minmax(0,14rem)` with the reading
   wrapping. The drawing checks report `draws no marks: its N bars draw 0px wide`, and `a <tag> is
   drawn against the page outside its slot, so the slot does not hold its height` for an absolutely
   placed part whose containing block lies outside its slot.
3. **Borrowed figures held to the page's facts.** `subject_components` draws a borrowed (library or
   other craft's) component only when `held_claims` holds every fact its units cite, the test the
   draft already applied, so the published page and the preview follow one rule. A family's or a
   category's page tells its crafts' science: there a fact also counts as held when it is about a
   concept one of the page's own facts is about, the tie by which a category chooses its shared
   figures, so a shared figure on that science still draws and one on another craft's science does
   not (`held_rows`); a craft's page holds only its own facts. A `why_here` with
   no note sentence is not drawn (rule 15: a card with no sentence is not drawn). Rules 9 and 15 read
   a figure's units from its spec as well as from the layout, and its citations by their cite marks
   (`research/page_report_read.py`), so a borrowed figure drawn on facts the page holds cites them.
4. **Toggles checked in their lab.** The render plan does not count as placed a component another
   component's spec names (`nested_labels`): the lab's own check covers it.
5. **Prose kept and written from the draft.** `told_sentences` drops a sentence a figure shows only
   while its field keeps three sentences; below that, the first such sentences stay, in order. The
   contributor skill and rule 26 say that a draft's facts are its field's prose.
6. **Pictures given.** The acceptance run offers `give_pictures` (`tools/acceptance/request.py`, the
   only edit there: the gap needs the tool) and its limits say so. The contributor skill and the
   `give_picture` prompt's contract say an open picture is given by its `page_url`. A kin entry
   draws its craft's typographic plate, named, in the family's material.
7. **A failed drawing is read.** `drawing_skip` reads any drawing that made pictures, failed or not;
   only a drawing with no picture is skipped. The run's own handling of pictures is unchanged.
8. **The tool for each failed rule.** `preview_page`'s `nextStep` follows the review with "Every failed
   rule has its tool; keep fixing and previewing while one fails:" and, for each failed rule, the
   tool and what to send it (`api/mcp_rule_fixes.py`).

## Consequences

- A page that borrowed a shared figure on facts it does not hold loses that figure on its next
  build; its own figure on its own facts takes the place. A page whose ground no sentence reads loses
  its why-here map until a place sentence is written.
- A curated figure's sentence may now be told twice, in the figure and in a thin field's prose.
- The server's read costs at most $0.50 for each new set of pictures, now also when the drawing fails.
- Tests: `backend/tests/research/test_spec_text_units.py` (every kind fixture, a unit in each kind's
  words both ways), `backend/tests/layouts/test_generated_text_units.py` (the page and the paper),
  `test_generated_why_here.py`, `test_generated_structure.py`, `test_page_render.py`, `test_page_report.py`,
  `test_borrowed_and_held_pages_db.py`, `test_design_read.py`, `test_page_design_read.py`,
  `test_mcp_preview_critique.py`, `tools/tests/test_acceptance_loop.py`, and the web specs
  `parity-drawing-unit`, `monograph-homes-unit`, `monograph-kinds-general-unit` and `kin-crafts-unit`.

## What is left

- No tool writes or reorders a field's prose from facts the page already holds but lists; a reviewed
  section proposal needs a review path of its own.
- The hero names the craft in the H1 and on its decorative plate, as rule 3 asks; left as it is.
- Two tool descriptions still say the team places open pictures (`search_sources`) or name only a
  contribution for `edit_draft`'s pictures; their sentences go to the directory-listing lane.
