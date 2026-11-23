# 0164. Every cited sentence of Kutch Ajrakh is a text unit, 73 of its components draw natively, and its content names its chapters

A text unit writes an apostrophe and a straight quote as entities, as the approved page does, so
the last 16 cited sentences held outside units became units; the stage player and both structure
diagrams draw natively; the answer's own sentences stay held text; the content carries the approved
page's chapter names, which the React rail and menu show; and what still keeps the authored shell
is recorded with what it waits on.

Date: 2026-11-23. Status: accepted (the lead's debt brief of 2026-11-22, monograph shell lane). It
amends [decision 0106](0106-one-monograph-template-for-every-page.md) (the native views on the
authored page, and where an authored page's chapter names live). The contracts are
`docs/contracts/monograph-document.md` and `docs/contracts/monograph-renderer.md`.

| For | Read |
|---|---|
| The template, the authored shell and the native views it amends | [decision 0106](0106-one-monograph-template-for-every-page.md) |
| The structured content and its byte-for-byte build | [decision 0105](0105-ajrakh-page-as-structured-content.md) |
| The approved page, served as built | [decision 0100](0100-ajrakh-monograph-served-as-built.md) |
| The ground figure captured from the React page | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| The document, its content and its units | [monograph-document.md](../contracts/monograph-document.md) |
| The renderer, the page plan and the native views | [monograph-renderer.md](../contracts/monograph-renderer.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **Sixteen cited sentences sat outside text units.** The approved page writes their apostrophe as
  `&#x27;` (the parts the original build drew through React's server render), while `render_nodes`
  wrote `'`, so a unit would have changed the approved page's bytes: the stage player's stage 11
  "Why", four timeline card lines, the shared-science atlas's three sentences, two Suran card lines,
  the climate map's side line and five in the shell. The stage player could not draw natively
  because stage 11's "Why" had no unit to name: its spec carried `why: null`, so the view dropped
  the line.
- **The React rail named the chapters its own way.** The plan names a chapter from its kicker or
  heading. On Kutch Ajrakh nine of the thirteen rail names and four of the chapter menu's names
  differed from the approved page's ("At a glance" for "The cloth", "How it is made" where the rail
  says "Making", "Answer" where the menu says "The answer"). The parity run compares `#kv-main`, so it never read the rail.
- **The register asked to retire the authored shell.** Besides components the shell holds
  hand-made markup per chapter (the masthead and its counts, the answer's table of contents, margin
  notes with fixed entries, the sources chapter's groups, each chapter's wrappers), which
  `MonographDocumentPage` does not draw, and a Vercel preview reads the production API's stored
  document, so no preview can show a branch's document.

## Decision

1. **A unit writes `&`, `<`, `>`, `"` and `'` as entities**, the apostrophe as `&#x27;`
   (`render_nodes` with `html.escape`'s quoting, `renderNodes` with `escapeMarkup`), the spelling
   React's server render and the approved page use. No unit held a straight quote before, so no page
   byte moved. The 16 sentences became 15 units, `u1114` to `u1128` (the black passage's opening
   paragraph holds two), in the layout where the page reads them; the specs name them; each unit's
   field is its cited fact's field, as 226 of the 239 units resting on facts of one field already
   were, and its `claimIds` its own cited facts, sorted. Rebuilding the approved page with plain
   apostrophes was the alternative; it would have changed the served bytes decision 0105 holds.
2. **The stage player and the two structure diagrams draw natively** (73 of 80): each draws the
   approved markup element for element (`monograph-native-unit.spec.ts`), and the smoke at 360, 834
   and 1440 in both schemes reads the page line for line as the approved page and finds each view
   within 2 per cent of its fragment's pixels.
3. **The answer's own sentences stay held text.** The language panels and the generator show the
   answer's sentences, cited by the answer's own sentence ids (`rm:`). Making them units was the
   alternative; the load publishes every unit with a field into its section, so the page's sections
   would repeat the answer's sentences, in English and in Hindi and Urdu. A structure's PubChem
   record citation cites a record, not a sentence, and stays in its spec.
4. **The content names an authored page's chapters.** `MonographContent.chapters` holds one
   `{key, title, rail}` per chapter of the layout, once and in its order (refused otherwise), left
   out when absent: `title` the name the chapter menu and section give it, `rail` the rail's
   shorter name. Kutch Ajrakh's are its approved rail's and menu's, tested against the template the
   static build draws them from. The plan takes `title` before the derived name and the rail shows
   `rail`; a page in another language derives its names from its own headings, since the names are
   the English page's. The `PageLayout` record was the alternative; it is the generated pages'
   record, and an authored page's layout is its content.
5. **What keeps the shell is recorded, not built.** The six page tools' views draw their own
   markup and legacy scope for the React shell, so inside the authored shell they would nest a
   second scope and differ from the approved markup; the ground figure waits on its map drawing its
   neighbours and pins in its first drawing (the place builders' `components/map`); the plate crops
   cannot become focal boxes while the native proof compares the approved `.ph.tall` markup, and
   stored editions keep `crop`; and the chapters' hand-made wrappers need either a port into
   structure the document carries or the owner's leave to let a React drawing become the approved
   reference, as the ground figure's capture did. The register says each.

## Consequences

- The register entries "Cited passages held outside text units" and "What the document does not
  carry yet" are cleared; the latter's source groups and masthead counts are parts of what the React
  shell must draw, so they join "Kutch Ajrakh's React page draws the authored shell". "Fragments are
  a bridge", "A plate's crop is a class or a focal box", that entry and "The authored shell keeps the
  app's CSS out by name" are rewritten to what remains and what each waits on.
- After the deploy, `python -m app.scripts.load_monograph` on the box stores the new document (its
  units, native views and chapter names) and publishes the new units' sentences into their sections;
  the React page shows the approved rail and menu names from then. Until then production's stored
  document has no chapter names and the rail keeps its derived names, which a preview shows too.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/research/test_monograph_page.py`, `backend/tests/research/test_monograph_authored.py`,
`backend/tests/research/test_science_spec_files.py`, `backend/tests/research/test_component_specs_tools.py`,
`frontend/e2e/monograph-render-unit.spec.ts`, `frontend/e2e/monograph-units-unit.spec.ts`,
`frontend/e2e/monograph-rail-unit.spec.ts`, `frontend/e2e/monograph-native-unit.spec.ts` and
`frontend/e2e/monograph-native.smoke.spec.ts`.
