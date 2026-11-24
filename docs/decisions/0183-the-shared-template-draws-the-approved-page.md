# 0183. The shared template draws the approved page's masthead, contents, margin notes, sub-rail and source groups for every generated page

A craft page built through the MCP tools, or generated from a craft's sections, is drawn by the
shared template in the approved Kutch Ajrakh page's form: the masthead with the label on the
photograph, its tools and the page's own sources counted apart from the kin crafts', the table of
contents, margin notes beside each paragraph from 1200px, the sub-rail of a chapter's sections and
the sources chapter's five groups with the kin crafts' sources apart, every word, count and source
the craft's own.

Date: 2026-11-24. Status: accepted (the lead's evening brief of 2026-11-24, lane G, shared
template; the owner asked "how else someone supposed to create same looking page using the mcp for
some other craft?"). It amends [decision 0177](0177-differences-named-and-the-monograph-shell-measured.md),
item 5 (what is left of the authored shell), and [decision 0106](0106-one-monograph-template-for-every-page.md),
item 3 (the one renderer). The contracts are `docs/contracts/monograph-renderer.md` (The page),
`docs/contracts/monograph-document.md` (The generated document) and `docs/contracts/open-work.md`
(the page report's rule 5).

| For | Read |
|---|---|
| One renderer for every page | [decision 0106](0106-one-monograph-template-for-every-page.md) |
| What holds Kutch Ajrakh's authored shell, measured | [decision 0177](0177-differences-named-and-the-monograph-shell-measured.md) |
| The approved page, served as built | [decision 0100](0100-ajrakh-monograph-served-as-built.md) |
| A generated page's kin crafts | [decision 0180](0180-places-abroad-yearly-series-picture-levels-figures-and-kin-crafts.md) |
| The design system the kit's look belongs to | [decision 0092](0092-design-system.md) |
| How the web draws a document | [monograph-renderer.md](../contracts/monograph-renderer.md) |
| A popover docked in a run's margin seen whole past its passage's foot (amends item 4) | [decision 0187](0187-listen-asked-when-pressed-and-a-docked-popover-seen-whole.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **A generated page did not look like the approved one.** Kutch Ajrakh is drawn from its authored
  shell; every other page is drawn by `MonographDocumentPage`, whose masthead was the app's
  editorial `Masthead` (a specimen label over a 16:7.4 photograph), with no table of contents, no
  margin notes beside its prose (only the lede had them), no sub-rail and one list of sources
  grouped by reliability. Decision 0177 measured the five parts the shell draws and the template
  does not.
- **The masthead's count disagreed with the sources chapter.** The masthead counted the sources
  units cite; the sources chapter listed every source of the document, a figure's included. On the
  stored documents read on 2026-11-24, Bagru Hand Block Print said "Drawn from 41 sources" over a
  list of 47, Machilipatnam Kalamkari 27 over 37.
- **A stored document cannot say which group a source belongs to.** A generated document's sources
  keep their number, title, publisher, year, grade and address, not the stored source's kind, and
  the approved page's groups (Government records, Scholarship, Museums and references, Community
  and press, Compound records) follow the kind of each source and, for museums, its publisher.
- **A Vercel preview reads production's stored documents**, so a part drawn only from a new field
  shows on a preview only after the release rebuilds the stored copies.

## Decision

1. **The generated masthead is the approved page's.** `KitMasthead` draws `header.kv-open` with the
   kicker over the name as the page's one `h1`, "The monograph" over the cited lede, the tools
   (Listen when the page has an `audio_player`, Cite this monograph to the page's citation) and the
   counts, beside the photograph as `figure.plate.kv-open-photo` with the label card on it and its
   caption and credit under it; without a photograph the card lies on the family's typographic
   plate. Keeping the editorial `Masthead` was the alternative; it is the design system's own
   component, but the owner asked for pages that look like the approved one, which the kit's
   stylesheet already draws at every width. The approved page's Save button is not drawn: in the
   kit it changes its label and saves nothing.
2. **The counts are the page's own sources and, apart, the kin crafts'.** `sourceSplit` takes every
   source the sources chapter lists and sets apart those only a `related_crafts` component's
   sentences cite; the masthead, its "N more for the kin crafts" link, the sources chapter and the
   page report's rule 5 read the same split (`lib/monographSources.ts` on the web,
   `research/page_report_sources.py` for the report, the same hand-derived cases testing both).
   Counting the cited units only, as before, was the alternative; it is what made the two counts
   disagree.
3. **A source carries its stored kind; the web groups.** `CitedSource.kind` (optional, left out when
   absent) is written by the generated builder from the stored source, and the web's `kindGroup`
   draws the five groups. A `source_list` component carrying the groups in its spec, as the
   register suggested for Kutch Ajrakh, was the alternative; every generated page would gain a
   component to place, number and keep in step with its sources, and a grouping would be stored in
   every document where it is a way of drawing them. A document without kinds (one stored before
   this change, or an authored one) keeps the reliability groups. The schema version stays 1: the
   field is optional and additive, as `chapters` and a unit's `lang` were, and a version 2 would
   store Kutch Ajrakh's document again for nothing it draws.
4. **Margin notes stand beside each paragraph.** A passage's column is cut into runs, an `h3`
   opening one and a paragraph or list closing it, each its own spread with the sources its
   sentences cite first in the chapter, as the approved page's static `li[data-g]` notes are drawn.
   Anchoring one long spread's notes to their sentences with the kit's script was the alternative;
   the script anchors by the sentences' `data-src`, which a generated sentence does not carry, and
   writing it would change every generated document for a layout the spreads already give.
5. **A chapter of two or more sections draws the sub-rail.** Each section heading carries an id and
   the chapter's head is followed by `nav.subrail` "In this chapter"; it draws no colour swatch,
   because the document gives a section no colour. The colour key is not drawn for the same reason:
   a colour taken from a component's drawing would be a colour the page invents for the key.
6. **The table of contents follows the masthead**, in the reading column, one row per numbered
   chapter with its number and name; the approved page's Fig. 1 beside it stays a component the
   opening places, so a page without one draws no empty column.
7. **The page report's rule 5 stays judged**, its evidence now the counts the masthead draws, so a
   contributor reads them in `preview_page` before proposing.

## Consequences

- Every generated page, and every page `preview_page` shows, draws the masthead, the table of
  contents, the margin notes and the sub-rail from its stored document at once, so a preview shows
  them on production's stored documents before the release. The five groups show once the
  release's builder stores the copies again (the page code's fingerprint in the stamp asks for it);
  until then a page keeps the reliability groups. The kin crafts' count and list show on pages that
  carry the kin crafts component of decision 0180, after its release.
- Kutch Ajrakh's page is unchanged: its route draws the shell, its content carries no kind, and the
  approved files are not edited. The register entry "Kutch Ajrakh's React page draws the authored
  shell" is rewritten to what its own document still lacks before its route can move to the shared
  template.
- `DocumentMasthead`, its lede spread and the app's `.kv-doc-open`, `.kv-prov`, `.kv-rel-strip` and
  `.kv-rel-count` rules are gone; `citedSources` is replaced by `sourceSplit`; the three copies of a
  spec's string walker are one, `research/spec_strings.py`; `pictureSources` moved from the
  client module `components/editorial/Plate.tsx` to `lib/pictureSources.ts`, so a server component
  (the masthead) can work out a photograph's widths.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`frontend/e2e/monograph-template-unit.spec.ts`, `frontend/e2e/monograph-template.smoke.spec.ts`,
`frontend/e2e/monograph-generated-unit.spec.ts`, `frontend/e2e/monograph-doc-groups-unit.spec.ts`
and `backend/tests/research/test_page_report_sources.py`.
