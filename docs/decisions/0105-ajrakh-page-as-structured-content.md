# 0105. The Ajrakh page as structured content, rebuilt by a static build

The approved Kutch Ajrakh page became structured content (text units without HTML, fields,
registered components and citations against the dossier) and a template rebuilt by a static build,
at parity by construction. Its later sections record its load into the database and every citation
resolved.

Date: 2026-11-19. Status: accepted (owner: "port the rest of the things of the Ajrakh page into
structured content, and do a static build as well").

| For | Read |
|---|---|
| What it builds on | [0101 One knowledge architecture for every craft: facts, sections, components, monographs](0101-knowledge-architecture-for-every-craft.md): build step 2's first half, the Ajrakh page as structured content |
| What built on it | [0106 One monograph template for every page, reached through fragments](0106-one-monograph-template-for-every-page.md): the structured content it renders |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0101, step 2 asks for the approved Kutch Ajrakh page to become sections, registered
components and a layout, rebuilt by a template renderer with no change a reader can see (item 14).
The page was a 3 MB hand-built file whose sentences did not point at stored facts.

## Decision

1. **Content, template and a build.** `backend/app/data/monographs/Kutch-Ajrakh/` holds:
   - `content.json` (`research/monograph_page.MonographContent`, schema 1): the page's 68 sources,
     its 348 citations with their quotes and locators, each citation's stored dossier facts, its
     embedded data (molecules, region layers, listening and quiz data, film subtitles), 1,086 text
     units, 79 registered components and the layout;
   - `template.html`: the approved page with a `<kv-slot unit="…">` or `<kv-slot data="…">` where
     each text unit and data block was.

   `python -m app.scripts.build_monograph` writes `frontend/public/monographs/kutch-ajrakh/index.html`
   from them; `--check` reports a served page that differs from its build.
2. **Parity by construction.** The port was accepted only because the build reproduces the
   approved page byte for byte, so text, screenshots and interactions are unchanged.
   `tests/research/test_monograph_page.py` holds that for every build.
3. **Text units carry no HTML.** A unit is the text of a paragraph, heading, caption, list item or
   table cell, as text and a fixed set of marks:
   - sentence (with its `data-src`, `data-sid` or `data-pair`);
   - citation (its key and sources; the button, numbers and labels are rebuilt from the source
     table);
   - italic (plain, local term, botanical name), bold, subscript, superscript, highlight;
   - link (in-page or outbound), figure reference, and a named style span.

   Text whose markup falls outside that set stays in the template. 11,742 of the about 20,200
   words in the chapters are units. The rest is text inside drawings and widgets: SVG labels,
   grade badges, buttons.
4. **Fields.** Each unit's field comes from its cited dossier facts where it has them (226 units),
   otherwise from its chapter. Two agents reviewed the 403 units in chapters that mix fields
   (231 changes kept after the check). 108 units are page apparatus (reading tools, the source
   list) and carry no field.
5. **The component registry.** 79 components (figures, players, maps, charts, molecules, plates,
   film, reading tools), each with a label, an anchor that matches exactly one element of the
   page, a kind, a title, a description written for a model, fields and subjects. Their views
   stay in the template; 953 text units sit inside them and are marked `within` in the layout.
6. **Citations against the dossier.** 251 of the 348 citations map to stored dossier facts by
   their quotes (115 of its 135 facts). 97 citations and 48 of the 68 sources are not in the
   dossier yet.

## Loaded into the database (2026-11-19)

- `python -m app.scripts.load_monograph` (`services/monograph_load.py`) writes the content into
  the database and can be run again at any time: a field whose sentences have not changed is left
  alone, and a changed field gets a new version while the old one is superseded.
- **Sections.** One published `ArticleSection` per field. It holds the cited sentences of that
  field's paragraphs, list items, quotes, captions and table cells, in page order, each with the
  database facts its citations map to. A sentence must cite a stored fact (`SectionSentence`), so
  a cited sentence whose facts are not stored yet waits; the load reports how many.
- **Components.** Each component whose text cites stored facts is registered in `KnowledgePiece`:
  its label, kind, title, description and fields, the facts and sources it rests on, and a payload
  naming the monograph, its anchor and its units. A `shared/` label is filed under no craft. Its
  subjects are linked: crafts by slug, compounds by PubChem id, places by key. Concept subjects
  wait until concepts have keys; the load reports them.
- **Component kinds.** `models/component_kinds.COMPONENT_KINDS` names the 37 monograph component
  kinds that are not answer block kinds. Migration `0034_component_kinds` lets `KnowledgePiece`
  hold them, and `list_components` filters by any piece kind.

## Every citation resolved (2026-11-19)

- **Facts across dossiers.** A citation's facts are named in `citationClaims` either by the
  monograph's own dossier id (`C001`) or across dossiers as `craft:<Slug>:<id>` or
  `category:<Slug>:<id>`. 77 of the 98 citations without an Ajrakh fact were already stored in
  other dossiers: 49 in the textile category's, the rest in the kin crafts' (Bagru, Madhubani, Dabu,
  Sanganeri, Machilipatnam Kalamkari, Bagh, Kutch Bandhani, Channapatna).
- **Whose section.** A sentence joins the craft's own sections only when at least one of its facts
  is the craft's or its category's; a sentence resting only on another craft's facts (the kin
  chapter) stays with that craft. A component may rest on any stored fact.
- **New facts.** Eight citations became Ajrakh facts in dossier version 3 (C153 to C160), with
  three new sources (Aino et al. 2018, Tiedemann and Yang 1995, Bag et al. 2013); the verifier
  passed all 284 quotes and the checker found nothing.
- **Left as they are.** Five citations quote compound records by name or formula (dithionite,
  indigo, indican, Tyrian purple, tannic acid): their quotes are under the dossier's 25 characters
  and the facts they support are PubChem's compound data. Three kin citations belong to Bagh,
  Pedana and Bagru's dossiers, and two molecule citations carry no quote.

## What follows

- Add the facts and sources the dossier lacks (97 citations, 48 sources) through the curation
  gates, then load again so every cited sentence and component is in the database.
- Move each component's view from the template into a component spec, so other crafts reuse it.
- Render other crafts with the same template once their content exists (decision 0101, step 6).

## How this record is kept true

Its sections of 2026-11-19, Loaded into the database and Every citation resolved, record what
followed the build. Beyond that it is not edited except to mark it superseded: a later choice is a
new record that names this one, and the table above links the two both ways. It records the choice
as taken on 2026-11-19; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
