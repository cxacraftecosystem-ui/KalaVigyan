---
name: kalavigyan-design
description: The KalaVigyan design system (Alum & Indigo, version 1.1, approved by the owner on 18 November 2026) - principles, non-negotiables, tokens by role, type and scripts, motion, the components and where they live, page templates, copy, accessibility, the acceptance every build meets and an index of traps. Load it before ANY user-interface, styling, CSS or Tailwind class, component, page, layout, chart, figure, map, picture, animation or reader-facing copy work in this repository, and before reviewing such a change, even a one-class fix. It replaces the retired portal skills (field-repo-frontend, gsap, motion), which describe the portal look (purple, Plus Jakarta Sans, glass, GSAP) and no longer apply here.
---

# KalaVigyan design system

Version 1.1, approved by the owner on 18 November 2026 (decision 0092). Direction A, **Alum &
Indigo**: alum-white paper, kut iron-black ink, one interactive indigo. Three grafts: from the
Specimen Cabinet the specimen label on every craft, the collection wall (every craft has a plate),
figure numbering and Cite this monograph; from Night Vat the full-bleed photographic first screen
and the vat moment as the one orchestrated animation. Every engineer and agent who touches a
screen, a class, a figure or reader-facing copy reads it first.

| For | Read |
|---|---|
| Why the system is this way | [decision 0092](../../../docs/decisions/0092-design-system.md), and SYSTEM.md section 9 |
| The pixel references | `docs/design/design-system.html` and `docs/design/master-board.html` |
| The code rules | `engineering-practices` (with `references/project-bindings.md`) and `frontend-practices` |
| A page's content rules | the page checklist, `backend/app/data/contributor/references/page-checklist.md` |

This file covers the common case. The full specification is in `references/`:

| File | What it holds | Read it when |
|---|---|---|
| `references/SYSTEM.md` | the whole system: every token in four themes, ramps, maps, type tables, scripts, right to left, every component's states, templates, migration counts, and section 9, the decisions | your task touches a section: read that section in full; read section 9 before overturning anything |
| `references/tokens.json` | the source of truth: values in light, dark, high-contrast light and dark, contrast classes, the generator's checks | you need a value, a ratio or a class |
| `references/tokens.css` | the generated CSS, also written to `frontend/app/tokens.css`, which `globals.css` imports | wiring or reading tokens |
| `references/tailwind.config.ts` | the generated config, which the generator also writes to `frontend/tailwind.config.ts`; it holds no migration alias (decision 0141) | you need to know whether a class exists |

The three outputs come from one generator that refuses a token set breaking a check:
`tools/design/` (inputs in `tools/design/system.json`, code beside it), run with
`backend\.venv\Scripts\python.exe tools\design_tokens.py`. It writes `references/tokens.json`,
`references/tokens.css`, `references/tailwind.config.ts`, `frontend/app/tokens.css` and
`frontend/tailwind.config.ts`;
`--check` fails when any of them differs from what the generator writes, and
`tools/tests/test_design_tokens.py` runs that check. Change `system.json` or the generator and
regenerate; never hand-edit a value in an output or type a colour in a component.

The pixel references live in `docs/design/`: `design-system.html` and `master-board.html` (open
them in a browser; their pictures are in `docs/design/img/`) and the authored landing mask
`docs/design/img/hero-dyed-mask.png` (`.webp` beside it). The approval's final screenshots are not
committed (80 MB); capture the boards with Playwright at the acceptance widths when a comparison
needs them.

Code rules: `engineering-practices` (with `references/project-bindings.md`) and
`frontend-practices`. Owner rule: no comments in any CSS, TS, TSX or Python a task writes.

**Retired in this repository:** the portal purple and the purple, field, gold, ministry, archive,
errand, steward, mango and evidence ramps; Plus Jakarta Sans and Inter; the flask BrandMark and its
logo tokens; GlassSurface, LiquidGlass, grad-mesh, grad-brand, text-gold-gradient,
text-gradient-violet, glass-card, glass-dark and ambient-light; the island nav look; GSAP; staggered
and spring entrances; the ochre and neem accents of version 1.0. Institution credit, where shown:
IIT Kharagpur and its Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform.

---

## 1. Principles

1. **One control per job.** A button repeating a link, two controls for one value, a margin note
   reopening the popover its sentence opens: each is a defect.
2. **Button rows follow the ActionGroup rule** (non-negotiables).
3. **Concise copy.** Sentence case, verbs on buttons, the finding in a chart title, no marketing
   adjectives, no exclamation marks, no instructions the layout already gives.
4. **Citations quiet but always present.** Every reader sentence carries one cluster of indigo
   numerals that opens the verbatim quote, its locator and its reliability.
5. **Never admit a gap.** A craft without a monograph shows its plate, its record and questions
   that start research. An empty list says what fills it and offers one way forward.
6. **Motion only to explain** a reaction or a process, with a still end state as the default style.
7. **Indigo means you can press it.** Madder is emphasis, disagreement or hazard; terracotta is
   place; turmeric only highlights; data borrows none of them.
8. **Names in their own scripts, at equal standing, only where a source states them and names
   this craft.** Never transliterate a name ourselves.
9. **Pictures are plates.** Caption first, credit after, standard Commons widths, no repeats on a
   page, no stock, shopping or AI imagery.
10. **Dense with every field** (owner, 2026-11-20). Every field a page's sources cover is on the
    page with cited quantities, mechanisms, names and dates; margin notes, fact grids, small
    multiples and tables carry detail beside the prose; every screen earns its height, never at
    the cost of the measure, the type scale or the citation rules (SYSTEM.md principle 10).

## 2. Non-negotiables

- **Indigo is the only interactive colour**: links, the primary button, citation numerals, the
  selected tab, chip and segment, a pressed stage, toggles on, focus rings. Nothing indigo that
  cannot be pressed: no indigo headings, kickers, margin numbers, icon circles, bands or series.
- **Madder is emphasis and Sources differ**, plus genuine chemical or safety hazards and
  destructive actions (field errors use `error`, the same pigment). Never decoration, never a
  chart series. Specimen `--dye-madder` is a depicted material, not this colour.
- **Data never borrows the identity colours.** Every ramp step, series and family hue sits 10 or
  more OKLab delta E (x100) from indigo, indigo-hover, madder, terracotta and turmeric in its theme;
  the generator enforces it. Never colour data with a semantic token.
- **The Rann is salt flat**: `--map-salt`, stippled, dotted edge, italic label ("Great Rann of
  Kachchh", "Little Rann"). Never the water fill.
- **Citations are superscript clusters**: one per sentence, de-duplicated by source and sorted
  ("1,4,5"), glued to the last word, never breaking a line or changing line height. From 640px a
  non-modal popover; from 1200px it docks into the margin beside the sentence, where margin notes
  list the sources; below 640px a modal bottom sheet.
- **One control per job.** "All N" is a link when it navigates and a button with `aria-expanded`
  when it expands in place.
- **Every row of buttons is an `ActionGroup`**: one centred; two on one line, sharing the width
  below 640px; three or more stacked full width below 640px and pills from 640px; a destructive
  action last (`data-danger`) and set apart. Nobody hand-places buttons.
- **Copy rules** (section 9), and **no gap admissions** on any reader screen: never not built yet,
  coming soon, no data, not enough cited evidence, 0 results, not curated, nothing here yet.
- **Motion only to explain, complete at rest.** Every end state is the default style; motion is
  added only when neither reduced-motion switch is on, and under either switch the end state shows
  at once. The largest element never first-paints at opacity 0.
- **Native-script names only when sourced and reviewed** (section 5).
- **Pictures credited at standard Commons widths** 330, 500, 960, 1280, 1920 through
  `commonsThumb(fileUrl, width)`, caption first and credit after ("Photo: Author, licence, via
  Wikimedia Commons"), where the picture is shown, OG images included.
- **Complete at rest.** A page's structure is final at first paint, every state reads without
  hover, and a control that drives motion works and announces its result without it.

## 3. Colour tokens by role

Semantic colours ship as channel triplets `--c-<name>` (so `/alpha` works) with a hex alias
`--<name>`; use the Tailwind class. Classes per `frontend/tailwind.config.ts`.

**Surfaces, lines and ink**

| Token | Class | Use it for |
|---|---|---|
| ground | `bg-ground` | The page; the body of every page. Paper grain (3 to 4.5 per cent) on ground only, off in high contrast and print. |
| raised | `bg-raised` | What floats or can be pressed as a card: popovers, sheets, dialogs, specimen labels, inputs, interactive cards. Never a box around prose or a section. |
| sunk | `bg-sunk` | Wells: figure grounds, the How to read band, skeletons, disabled inputs, code wells, hover on a quiet control. |
| rule | `border-rule` | Hairlines, dividers, table row lines, gridlines. Never the only boundary of a control or swatch. |
| rule-strong | `border-rule-strong` | Edges of what you press: quiet buttons, chips, inputs, segmented groups, toggles off (3:1 on every surface). |
| ink-1 | `text-ink-1` | Reading text, headlines, dates (tabular lining), the current step, figure strokes, the chart baseline. |
| ink-2 | `text-ink-2` | Captions (italic), standfirsts, chart annotation, botanical names (italic), field labels, the 1px specimen frame. |
| ink-3 | `text-ink-3` | Credits, source lines, axis labels, kickers, timestamps, margin-note numbers, counts in chips. Never below 12px. |

**Interactive and accents**

| Token | Class | Use it for |
|---|---|---|
| indigo | `text-indigo`, `bg-indigo`, `border-indigo` | Only what can be pressed or is chosen (non-negotiables). Indigo fills: the primary button, the selected segment, a pressed stage, a switch that is on. |
| indigo-hover | `hover:text-indigo-hover`, `hover:bg-indigo-hover` | Indigo under the pointer and pressed. |
| indigo-wash | `bg-indigo-wash` | The selected fill: a pressed chip, the selected option. Never a section background or a focus indicator alone. |
| on-indigo | `text-indigo-on` | Label on an indigo fill; the thumb of a switch that is on. |
| madder | `text-madder`, `border-madder` | Sources differ marker and hatch, real hazards, destructive actions. |
| madder-wash | `bg-madder-wash` | Behind a hazard note or a destructive confirmation. |
| on-madder | `text-madder-on` | Label of a confirming destructive button (madder fill). |
| turmeric | `border-turmeric` | The 2px rule beside a demonstrated sentence. Nothing else: never text, a control or a state. |
| turmeric-wash | `bg-turmeric-wash` | Highlighter: the sentence a popover is open for, search matches, the sentences a selected source supports, flashed rows. |
| turmeric-text | `text-turmeric-text` | The word Inferred and its dotted underline. |
| terracotta | `text-terracotta` | Place: map pins, the outline and 45 degree hatch of the page's place, place glyphs, place headings 24px and up. Never 12 to 16px text in light. |

**Status.** `error`, `warning`, `info`, `success`, each with `-wash` (`text-error`,
`bg-error-wash`). Only inside a toast, inline message, banner or field error, always with an icon
and words. Info is slate, not indigo. Warning is for take care (expiring session, unsaved
changes, quota), never ordinary facts.

**Specimen, plate and photo tokens** (CSS variables only, do not theme)

- `--dye-cloth`, `-harda`, `-harda-dry`, `-lime`, `-lime-edge`, `-kut`, `-kesari`, `-mud`,
  `-mud-wet`, `-leuco`, `-vat-liquor`, `-indigo`, `-indigo-deep`, `-madder`, `-madder-bright`,
  `-pink`, `-pink-edge` and `--dip-1` to `--dip-4`: depicted materials. Always textured, framed
  (1px ink-2 outside a 2px raised mat) and named in a key; never a control, link, series or map
  class.
- `--plate-<material>` with `--plate-<material>-ink` for textile, metal, wood, fibre, clay,
  stone, paper, leather, paint, instr, toys and misc: a craft plate's ground, its seeded texture
  and the family swatch on shelf headers and the index. The kicker and name are knocked out of
  the texture (8px block of the ground).
- `--photo-ink-1`, `--photo-ink-2` over `--photo-scrim-start` (text at the inline start, tablet
  and desktop, mirrored in right to left) or `--photo-scrim-bottom` (phone). A failing crop
  strengthens its scrim; text is never weakened. The photo buttons and rings use
  `--photo-indigo`, `--photo-indigo-hover`, `--photo-paper-hover`, `--photo-quiet-fill`,
  `--photo-quiet-hover`, `--photo-quiet-edge` and `--photo-focus-ring`; scrims under dialogs are
  `--scrim` and the Lightbox `--scrim-deep`; a plate's hairline edge is `--plate-edge`. None of
  them theme.

**Data and chart tokens** (CSS variables only)

- Ramps for area fills only (choropleths, relief, legends), because they flip lightness in dark:
  `--rain-1…6`, `--density-1…6`, `--heat-1…6`, `--ph-1…5` (diverging, neutral class fixed at 6.5
  to 7.5), `--elevation-1…7` (always with contours or spot heights), `--earth-1…6` (soil and bare
  earth), `--cover-1…6` (tree cover and cropland). `--mineral-1…6` is categorical: mineral deposit
  classes as point symbols, each class also in its own shape, never an area fill. The physical
  layer shades relief with `--map-relief-shade` at `--map-hillshade-opacity` (off in high
  contrast); the steps and checks are in `references/tokens.json`.
- Series keep their hue in every theme and colour bars, lines and circles: `--series-rain`,
  `--series-heat`, `--series-count` (crafts counted: proportional circles and ranked bars).
  Anything else takes `--chart-series`; only the mark the title names takes `--chart-emph`.
- Families in fixed order: `--fam-textiles`, `-metal`, `-wood`, `-paper`, `-clay`, `-stone`,
  `-leather`, `-fibre`, then `--fam-other` (More crafts). Bars, stacks and legends may use all;
  maps, scatter plots and small multiples carry at most three. Every family mark has a 1px ink-1
  outline or sits in an ink-ringed marker. A family legend never sits beside plates.
- Chart neutrals: `--chart-axis-text`, `-axis-line`, `-grid`, `-series`, `-emph`, `-reference`
  (dashed 3 4), `-trend` (2.5px over a 6px ground halo), `-band` (18 per cent), `-annotation`,
  `-differ`.

**Map tokens** (CSS variables only): `--map-land`, `-land-foreign` (Natural Earth, under the Survey
of India outline), `-water` (never indigo, never a ramp step), `-coast`, `-water-label`, `-river`,
`-salt`, `-salt-hatch`, `-border-intl`, `-border-state`, `-border-district` (zoomed in only),
`-label`, `-label-minor`, `-label-halo`, `-selection` with `-selection-halo`, `-hover`,
`-marker`, `-marker-ring`, `-place`, `-nodata`, `-hillshade-opacity`.

**Hatch grammar**: one meaning per pattern, and every legend explains the hatches it shows.

| Meaning | Pattern |
|---|---|
| Salt flat (the Rann) | stipple, `--map-salt-hatch` on `--map-salt`, dotted edge |
| The place a page is about | 45 degree lines in terracotta, solid terracotta edge, never a fill |
| Sources differ (span between two readings) | 135 degree lines in madder |
| No reading in the dataset | 45 and 135 cross-hatch in rule-strong |
| Earth in a section drawing | horizontal dashed strata in ink-3 on sunk |

`[var(--x)]` arbitrary values are allowed only in `components/charts`, `components/map`,
`components/cloth` and `components/crafts`; everywhere else a token has a class.

## 4. Space, shape, depth and layout

- **Spacing** `--space-1…10` = 4, 8, 12, 16, 24, 32, 48, 64, 96, 128px; `--space-section` (64px
  phone to 96px desktop, `py-section`); paragraphs 1.05em apart.
- **Controls** are rem tokens and grow with Larger text: `h-control` 46px (48 touch),
  `h-control-sm` 40px (44 touch), `h-input` 48px, chips 34px (44 touch), search 60px, segments
  40px (44 touch), code boxes 46x56 (52x64 from 640px), toggle 48x28, `min-h-target` 44px, appbar
  64px, chapter rail 46px.
- **Radii**: `rounded-plate` 2 (photographs, plates, swatches, specimen labels, figures),
  `rounded-control` 4 (buttons, inputs, code boxes, segments, search), `rounded-card` 6
  (popovers, quote cards, toasts, dialogs, menus), `rounded-sheet` 14 (phone sheet top corners),
  `rounded-pill` (chips, toggle tracks, rows of three or more buttons from 640px), `rounded-full`
  (avatars, icon buttons). Sections have no radius.
- **Borders**: hair 1px rule separates; control 1px rule-strong bounds what you press; 1px ink-1
  tops sections and figures; 2px ink-1 for selection and high contrast; 2px ink-1 on the leading
  edge for the current step; 2px madder on the inline start of a disagreement; 2px dashed ink-2
  for a hypothesis.
- **Shadows**, three only: `shadow-pop` (popovers, menus, toasts, dialogs), `shadow-label` (a
  specimen label lying on a photograph), `shadow-sheet` (the phone sheet). High contrast replaces
  each with a 2px ink outline.
- **Layers**: `z-sticky` 20 (chapter rail), `z-appbar` 30, `z-popover` 70, `z-scrim` 80, `z-sheet`
  85, `z-dialog` 90, `z-toast` 110, `z-skip` 120. Never invent a z-index.
- **Breakpoints** in px, no others: below 640 phone (citation sheet, sideways shelves); `sm` 640
  (popover, pill rows, two-up); `md` 768 (tablet column, appbar nav, legend in the map frame); `lg`
  1024 (masthead label over the photograph, two-column heads, six-column shelves); `rail` 1200
  (the spread); `xl` 1280 (64px margins); `2xl` 1536.
- **Margins** 16px below 640, 24 to 767, 40 to 1199, 48 to 1279, 64 from 1280, never less than the
  safe-area inset. Content up to 1280px (`max-w-content`); photographs and figures may bleed.
- **Measure** 66ch (`max-w-measure`), never wider than 75ch.
- **The spread from 1200px**: `160px minmax(0, 680px) 240px`, 40px gaps. Left rail: light chapter
  numeral, dates, provenance. Right margin: numbered source titles, evidence labels, small
  plates. From 768 to 1199px a monograph is one centred 66ch column; margin notes fold into the
  popover. No right rail on a tablet.

## 5. Type and scripts

| Role | Face | Class | Size tokens | For |
|---|---|---|---|---|
| Headline and display | Newsreader 300 to 600 with italics, optical size follows the size | `font-headline` | `text-hero`, `text-title`, `text-h1`, `text-h2`, `text-stat`, `text-numeral` | the landing headline, craft names in a masthead, page titles, chapter titles, stats, rail numerals; display sizes keep growing to 1920px |
| Reading text | Newsreader at text sizes, old-style proportional figures, Noto Serif per script | `font-reading` (`font-serif`) | `text-lede`, `text-body`, `text-body-sm`, `text-quote`, `text-figcaption`, `text-h3` | prose, ledes, quotes, captions (italic), h3, names on plates |
| UI | IBM Plex Sans 400, 500, 600, italic 400 | `font-ui` (`font-sans`) | `text-caption`, `text-label`, `text-ui`, `text-ui-lg`, `text-h4` | everything you operate or scan: buttons, nav, tabs, labels, meta, inputs, toasts, kickers, h4 |
| Mono for codes | IBM Plex Mono 400, 500, lining tabular | `font-code` | the size of its context | the six-box sign-in code, API keys, PubChem CIDs, slugs |

`font-display` no longer exists (decision 0141): display lines are `font-headline`. Each size
class carries its line height, tracking and weight; do not restate them. It does not carry the
family: inside reading text a UI size (`text-caption`, `text-label`,
`text-ui`, `text-ui-lg`, `text-h4`) needs `font-ui`, and inside UI text a reading or headline size
needs `font-reading` or `font-headline`.

| Token | 360 / 1440 / 1920 px | Use |
|---|---|---|
| `text-caption` | 12 | credits, source lines, axes, map labels, kickers, tags; the floor |
| `text-label` | 13 | field labels, chip text, provenance, fact labels, margin notes |
| `text-ui` | 14 | buttons, nav, tabs, list meta, popover body |
| `text-ui-lg` | 16 | inputs (stops iOS zoom), toasts, dialog body |
| `text-h4` | 16, weight 600 | small figure titles, card names on tool pages |
| `text-figcaption` | 15 / 16 / 16 | picture captions in italic |
| `text-quote`, `text-body-sm` | 16 / 17 / 17 | verbatim quotes (italic); dense prose, stage text, keys |
| `text-body` | 17 / 19 / 19 | monograph and answer prose, 66ch |
| `text-lede` | 20 / 23 / 23 | opening paragraph, standfirsts |
| `text-h3` | 21 / 26 / 26 | sub-sections, shelf names, figure titles, stage names |
| `text-h2` | 28 / 44.6 / 52 | chapter titles |
| `text-h1` | 36 / 66.5 / 80 | page titles that are sentences: questions, "The atlas", long craft names |
| `text-title` | 44 / 88.3 / 108 | a craft name in a masthead |
| `text-hero` | 54 / 109.4 / 134 | the landing headline, one per site |
| `text-numeral` | from 1200px: 80 / 88 | light chapter numerals in the left rail; below 1200 the "Chapter 3" kicker |
| `text-stat` | 36 / 55.4 / 64 | a headline number, its unit in label beneath |

- **Floor**: nothing below 12px, SVG text included, except citation numerals at
  `max(0.6875rem, 0.62em)`; subscripts `max(0.7em, 0.75rem)`; formulas 17px or more; body text
  16px or more on a phone. **Larger text** is exactly 1.125x every token at every width.
- **Figures**: reading `oldstyle-nums proportional-nums`; headlines and UI lining proportional;
  tables, charts, axes, counts, dates and codes `lining-nums tabular-nums`. Chemistry uses true
  subscripts in the surrounding face.
- **Case**: sentence case everywhere. Only kickers and the GI tag are uppercase (`.kicker`: UI 12,
  600, tracking 0.08em, ink-3, `"case"` feature, never indigo).
- **Italic**: transliterated local terms (saaj, kut, gach), botanical names (ink-2), verbatim
  quotes, photo captions. English names are never italic.
- **Weight**: `b` and `strong` render 600 with `font-synthesis: none`; Plex has no 700.
- **Equations**: a side never breaks; a line breaks only before the arrow; else the equation
  scales down with container units, 24px to 17px.
- **Wordmark**: SVG outlines, KalaVigyan in Newsreader 600 and कलाविज्ञान in Noto Serif Devanagari
  500 at x1.08, split by a 1px rule; the mark is the eight-pointed ajrakh star cut as a block, one
  colour (the four-dye version only at 64px and up).

**Scripts**

- Every non-Latin string carries `lang` (BCP 47, with a script subtag where a language has two:
  `ks-Arab`, `ks-Deva`, `sd-Arab`, `sd-Deva`, `mni-Mtei`, `mni-Beng`) and `data-script` (ISO
  15924: `Deva`, `Beng`, `Gujr`, `Guru`, `Orya`, `Taml`, `Mlym`, `Telu`, `Knda`, `Aran`, `Arab`,
  `Mtei`, `Olck`). The selector sets the face, `--script-scale`, `--script-leading` and
  `--script-display-leading`; add `.ui` for the Noto Sans face in controls. Select by script,
  never by language.
- Arabic-script strings carry `dir="rtl"`; a native name inside an English line is in `<bdi>`.
  Urdu and Kashmiri are Nastaliq (`Aran`, leading 2.2 prose, 1.7 display, never inside a 44px chip
  or button); Sindhi is Naskh (`Arab`).
- Never uppercase or letter-space Indic or Arabic-script text. Indian names never break inside a
  word (`word-break: keep-all; overflow-wrap: normal`).
- **Equal standing** applies to titles (masthead, specimen label, page title, wordmark): both names
  at one size (own script at the token times `--script-scale`), stacked with a hairline. A
  masthead takes `text-title` when the Latin name has 18 characters or fewer, else `text-h1`; at
  most three lines a name; if a word still overflows, both names shrink together with container
  units, never one alone. Plates and the names wall are labels: one display name, and the strip
  always carries the English catalogue line in the same place.
- **Which names may appear**: `nativeName: { text, lang, script, sourceId, sourceKind: "dossier" |
  "wikidata", reviewed }`. Render nothing without `sourceId` and `reviewed`. A Wikidata label only
  in the language of the craft's home state, and only when the item is the craft itself; a
  place-carrying name whose item is the technique in general is held back (SYSTEM.md 2.10 lists
  them). The Wikidata CC0 credit appears once under the wall and in the label's provenance line.
- **Loading**: self-hosted through `next/font/local` with `unicode-range` and `preload: false`; a
  page loads a script's reading face only when it has prose in it; the atlas and names view use
  build-time subsets of 24 KB or less per script, 160 KB for all. The wordmark is outlines.
- **Right to left** follows the content language: an Urdu answer mirrors its article (rail,
  prose, margin notes, figure order); the appbar and chapter rail keep the interface direction.
  Logical properties only (`ms`, `me`, `ps`, `pe`, `start`, `end`, `border-s`, `text-start`).
  Western digits for citation numerals, figure numbers, dates and data. Popovers keep the source's
  language and direction.

## 6. Motion

Durations: press 120ms, state 200ms, panel 320ms, dip 600ms, hold 500ms, oxidise 1500ms, vat
2600ms, vat-delay 800ms (`duration-press`, `duration-state`, `duration-panel`, `duration-dip`,
`duration-oxidise`; `--dur-*`). Easings: `ease-out` for entrances, `ease-in-out` for chemical
changes, `ease-linear` for scroll-linked progress, `ease-toggle` (the only overshoot) on a switch
thumb.

| Motion | What it explains | Trigger | Reduced-motion end state |
|---|---|---|---|
| dip | cloth going into a bath: a band fills from the bottom (clip-path) | choosing a stage on the living cloth | the band shown filled |
| oxidise | leuco green turning indigo in air from the top edge down | stage 8, the vat's last phase | the blue end state with the green as a still frame beside it |
| press | a citation numeral or the Saved mark settling from 1.02 to 1 | pressing it | the state changes at once |
| vat | dip, hold lifted and green, oxidise: the one orchestrated animation | landing: once per visit and Play again; VatFigure: Dip again | the finished blue cloth and the three captioned phases as stills |

- **The vat on the landing** tints only the authored dyed-region mask of the photograph (green
  rises with a 3 per cent meniscus, blue returns from the top with a 12 per cent ragged edge),
  driven by one transition of a registered `@property --vat`. Resist whites, kut black and madder
  never change. It plays 800ms after the photograph is in view, once per visit (`sessionStorage`
  key `kv-vat-played`, read and written in try/catch). The photograph is never at opacity 0 and
  the tint layer is off the LCP path (the 960 hero preloaded with `fetchpriority="high"`). The
  label's steps are non-pressable progress with one quiet Play again text button and an
  `aria-live` status naming each phase. The answer's VatFigure plays it on the drawn cloth from
  Dip again, steps `--dip-1…4` and offers Start again after the fourth dip. The authored mask
  reaches the tint as `--vat-mask: url(…)` on the `vat-tint` layer, intersected with the two
  moving edges. Under either reduced-motion switch, `useVatMoment().play` steps one still phase
  per press (in the vat, lifted, in the air, rest) and announces it; autoplay shows the rest
  state.
- **Reduced motion has two switches**: `prefers-reduced-motion` and
  `html[data-reduced-motion="true"]`, read before anything moves. The end state is the default
  style; motion is added only under a variant that checks both; under either, `animation` and
  `transition` are `none`, so nothing snaps back to a start state.
- **In code**: framer-motion 14 (which is Motion; never add the `motion` package) owns declarative
  motion. `app/motion.css` owns the named CSS motions (`motion-press`, `motion-dip`,
  `motion-oxidise`, the `motion-enter` and `motion-rise` entrances, `motion-pulse`), the vat's
  registered properties and phases (`vat-tint` under `data-vat-phase`) and the reduced-motion switch
  for both settings. Play a named motion with `useNamedMotion()` and `motionClass(name)`, run the
  vat with `useVatMoment()`, and ask `useMotionAllowed()` (all in `components/motion/`); framer
  code reads the switches with `useAppReducedMotion()` (`components/guide/useAppReducedMotion.ts`),
  never framer's `useReducedMotion()`, which sees only the OS. Gate the motion, never the markup:
  server and first client render move nothing. GSAP is gone (decision 0094); add none. The
  retired look's `guideMotion.ts` factories (springs, stagger, rise, slide) are deleted (decision
  0141); scroll to an anchor with `scrollToAnchor()` (`components/motion/`), which reads both
  switches. The thread motion is retired (SYSTEM.md section 9).
- **Never**: Ken Burns drift, word-by-word or letter headline reveals, staggered rise-in of cards,
  parallax, scroll-linked decoration, a first paint at opacity 0 for the largest element, overshoot
  anywhere but a switch thumb, two animation systems on one property, smooth scrolling under a
  reduced-motion switch.

## 7. Components and where they live

Paths are under `frontend/components/`. Existing files keep their behaviour, ARIA and tests and
change only their classes; "new" names the file to create, in that place and nowhere else. Every
state and prop is in SYSTEM.md section 3.

**Controls**

| Component | File | Rule |
|---|---|---|
| Button, IconButton | `ui/button.tsx`, `ui/IconButton.tsx` | `primary`, `quiet`, `danger`, `text`; `md`, `sm`. One primary per view and none on a reading page. Busy shows spinner plus a verb over the resting label, width unchanged. Danger is a madder outline; a confirming destructive button is a madder fill. On a photograph, primary is a paper button with indigo text and quiet is outlined in photo ink over a 40 per cent dark fill. `outline`, `secondary`, `ghost`, `provider` map to quiet. |
| ActionGroup | `ui/ActionGroup.tsx`, `ui/actionGroupLayout.ts` | Every button row; `align`, `fill`, `inline`; `data-danger` child last. |
| TextLink | `ui/TextLink.tsx` | Prose: indigo, 1px underline at 3px offset, 2px on hover. Standalone ("All 97"): UI 14 500. Link to navigate, button to expand or act. Replaces `field-link`. |
| Field, Input, Textarea | `FormControls.tsx`, `forms/*` | Label above (UI 13 500 ink-2, sentence case); raised fill, rule-strong edge, 16px text; error is a 2px madder edge plus message with icon, `aria-invalid`, `aria-describedby`; required is the word in the hint. |
| SearchBox | `SearchInput.tsx` | 60px, ink edge, lede-size Newsreader input, 44px Clear; `/` focuses it unless typing elsewhere; counts in `role="status"`. |
| OtpCodeInput | `ui/OtpCodeInput.tsx`, `TwoStepCodeEntry.tsx`, `TwoStepChallengeForm.tsx` | Six boxes in `font-code`, lining tabular; the field ring on focus. |
| Toggle | `ui/Toggle.tsx` | Pill track; off sunk with rule-strong edge; on indigo with on-indigo thumb; mirrors in right to left. |
| SegmentedChoice | `ui/SegmentedChoice.tsx` | Two to four options; selected is the indigo fill. More options become a select. |
| SearchableSelect, Dropdown, LanguagePicker | `ui/SearchableSelect.tsx`, `ui/Dropdown.tsx`, `LanguagePicker.tsx` | Raised card panel; search past eight options; keyboard highlight sunk with a 2px indigo inline-start bar; selected indigo on indigo-wash with a check; languages in their own script with the English beside. |
| Chip | `ui/Chip.tsx` | Pill, rule-strong edge, UI 13; pressed is indigo-wash, indigo edge, indigo-hover text. Never the only way to an action. |
| Tabs | `ui/Tabs.tsx` | Only for views of one object on signed-in tool pages. Monographs have no tabs. |

**Citations, evidence, provenance**

| Component | File | Rule |
|---|---|---|
| CitationCluster (`Cite`) | `editorial/CitationCluster.tsx`, drawn by `answer/CitationChip.tsx` and `CitationChips` | Indigo UI numerals, no border, pill or icon; hit area 24px (44 on touch) inside its own line; name "Sources 1 and 2" with the short titles as its description (`aria-describedby` on a hidden element); `aria-haspopup="dialog"`, `aria-expanded`, and `aria-controls` while open. Open: ink-1 and the sentence in turmeric-wash. |
| SourcePopover and SourceSheet | `editorial/SourcePanel.tsx` in `ui/AnchoredPopover.tsx` or `ui/Sheet.tsx` | Non-modal 380px popover from 640px, docked in the margin from 1200px; modal bottom sheet with focus trap below 640px. Every quote verbatim in italic, locator, A to D reliability mark with words, "Open the source". Focus returns to the numeral. |
| MarginNotes, Spread | `editorial/MarginNotes.tsx` | From 1200px: numbered short titles and year, UI 13 ink-3 (numbers ink-3, not buttons); top-aligned to the first citing sentence, pushed down with 8px gaps, never repeated in a chapter. |
| EvidenceMark, SourcesDiffer | `editorial/EvidenceMark.tsx` (`EvidenceTag`, `InferredText`, `HypothesisText`, `SourcesDifferNote`) | The page states its norm once; a mark appears only where a sentence differs. Inferred: dotted turmeric-text underline and the word. Hypothesis: dashed ink-2 rule and the word. Sources differ: a `<details>` after the paragraph, madder summary, both readings quoted and cited. |
| ProvenanceStrip | `craft/Provenance.tsx` (new) | "Drawn from N sources", the A/B/C/D strip (`role="img"` with a spoken summary), the monograph link, the curation date. Never pipeline counts. |

**Crafts, collection, pictures**

| Component | File | Rule |
|---|---|---|
| SpecimenLabel, NameStack, Masthead | `editorial/SpecimenLabel.tsx`, `editorial/NameStack.tsx`, `editorial/Masthead.tsx` | On every craft: raised, double ink frame; kicker row; name (h1 in a masthead, a paragraph on the landing, h2 as a chapter label); native name only when sourced; one cited sentence; GI line; place; provenance; credit when on a photograph. Label shadow only `onPhoto`. No catalogue number. |
| Plate | `editorial/Plate.tsx` (it replaced `MediaFigure`, now gone) | Photograph at 2px radius cropped from its focal box; caption first, credit after; opens the Lightbox. |
| Lightbox | `ui/Lightbox.tsx` | Modal on a 92 per cent dark scrim, largest standard width, zoom, caption and credit; focus returns to the plate. |
| TypographicPlate, CollectionPlate | `editorial/TypographicPlate.tsx` (the plate and its ground); `crafts/CollectionPlate.tsx` wraps it with the strip and link | Every craft: material ground and seeded texture, sub-family kicker (none for catch-all rows), the display name, a raised strip with the English name, state, then Monograph and GI tags. |
| PhotoCard | `crafts/PhotoCard.tsx` | Leads a shelf for a craft with a licensed photograph. |
| CollectionShelf | `crafts/CollectionShelf.tsx` | Plate-ground swatch, family, counts, "All N"; sideways scroll-snap row below 640px, 2 / 4 / 6 columns from 640 / 768 / 1024; lead alternates sides. |
| NamesWall | `crafts/NamesWall.tsx` | Sourced own-script names by home state, English always visible beneath in UI 13 ink-3. |
| AtlasIndex | `crafts/AtlasIndex.tsx` | Families, places, ideas; three columns from 1200px; rows are links. |
| FactGrid | `editorial/FactGrid.tsx` | At a glance as a `<dl>`, 1 / 2 / 4 columns, ink top rule; on an uncurated craft, "What the craft list records", uncited. |
| RecordStrip | `craft/InTheRecord.tsx` (new) | "In the record": date in ink-1 tabular, cited sentence, optional plate. |
| StageList | `craft/StageList.tsx` (new) | Numbered stages, local term in italic with the English name, prose starting with its verb, materials with botanical names; five shown, then "Show all 11 stages" (`aria-expanded`). |
| DatedRail | `craft/DatedRail.tsx` (new) | Dates in the left rail from 1200px, inline above the paragraph below. |
| ChapterRail | `editorial/ChapterRail.tsx` (it replaced `craft/CraftTabs.tsx`, retired with the tabbed craft screen in round 6) | Sticks once the appbar scrolls away; scroll-spy with `aria-current="location"` and an indigo underline; deep-linkable anchors (`?tab=science` maps to `#chem`); `scroll-margin-top: calc(var(--rail-h) + 1rem)`. |
| CiteThis | `craft/CiteThis.tsx` | Text or BibTeX (`@misc`), the lower-case versioned URL, one Copy citation button; the text ends with the access date. |

**Figures, data, maps, chemistry**

| Component | File | Rule |
|---|---|---|
| Figure | `ui/Figure.tsx` | Kicker "Fig. 3" ("Table 1"), numbered through the page; charts title their finding, diagrams and maps describe; source line under; the table behind "All N values"; one tab stop, arrow keys between marks. |
| Chart kit | `charts/*` (new): Axis, Bars, Line, TrendLine, RefLine, DirectLabel, Band, Tooltip, DataTable | The chart grammar: axes in UI 12 tabular, direct labels for one or two series, a legend for three or more, one y-axis, uncertainty as band or whisker, `data-fit` text. |
| MapLegend, RankedList | `map/*` (today `map/ChoroplethLegend.tsx`), `map/RankedList.tsx` | Stepped legend with labelled breaks in the unit, salt, water, place and no-reading swatches; under the map on a phone, over open sea from 768px. The ranked list beside every map: top ten, then "All N". |
| Formula, Swatch | `chem/Formula.tsx`, `chem/Swatch.tsx` (new; today `answer/ChemEquation.tsx`) | True subscripts at 12px or more, the equation rule; swatches framed with the weave texture. |
| LivingCloth | `cloth/*` (new, one SVG engine) | One deterministic ajrakh drawing in its eleven states; stage buttons are a `role="toolbar"` with roving tabindex, each `aria-pressed`. |
| VatFigure | `answer/VatFigure.tsx` | Three frames with the current frame's ink rule, Dip again, live status, the balanced equation with its atom count. |

**Shell and status**

| Component | File | Rule |
|---|---|---|
| Appbar, BrandMark | `DynamicIslandNav.tsx`, `BrandMark.tsx` | SVG wordmark at parity; nav UI 14 ink-2, current ink-1 with an indigo underline; 44px account button; below 768px a Menu button opening a sheet. On a photograph: photo ink, translucent rule, photo focus ring, switching to page ink after 64px of ground. |
| HowToRead | `landing/HowToRead.tsx` | The sunk band: a demonstrated sentence with its turmeric rule, keys a to d and their quote cards. |
| InstitutionFooter | `landing/Footer.tsx` | One line, UI 12 ink-3 under a hairline. |
| Toast | `ui/Toast.tsx` | Raised, pop shadow, status icon tile, three at most; info and success leave after 5s, warnings 8s, errors stay; error is `role="alert"`. |
| Dialog | `dialogs/*` | Title in h3 reading; ActionGroup actions; destructive last, madder, named for what it does; initial focus on the least destructive; Escape cancels. |
| EmptyState | `EmptyState.tsx`, `DeadEnd.tsx` | Hairlines, what the place is for, one way forward; a craft's state shows its plate; no generic icons. |
| Skeleton | `ui/Skeleton.tsx` | Sunk blocks in the content's shape, slow pulse that stops under reduced motion, `aria-busy` container. Never "Loading" alone. |

## 8. Page templates

Every page has one h1. Full detail in SYSTEM.md section 4; the master board is the reference.

- **Landing**: full-bleed licensed photograph of the flagship cloth with its mask and start scrim,
  appbar in photo ink, kicker, hero h1 ("The science in India's crafts, *sourced to the
  sentence.*"), standfirst, ActionGroup of two (Request access primary, Sign in quiet), audience
  line, the landing SpecimenLabel with the vat steps and Play again. Then the living-cloth ribbon,
  One cloth, four chemistries (h2; Blue, Black, Red, White as h3), How to read a page (h2), the
  crafts map with its ranked list and legend, the institution footer. On a phone the photograph,
  headline and label fill the first screen.
- **Crafts atlas**: h1 "The atlas" with the count from the catalogue endpoint, the SearchBox with
  Try chips and concept results, the Index (h2), the collection (h2) with Plates / Names, one
  CollectionShelf per family. Catch-all rows are never plates; they come through "All N".
- **Monograph (craft page)**: masthead SpecimenLabel (name as h1) over a 16:7.4 photograph from
  its focal box (4:3 photograph first and the label on paper below 1024px), the lede, the chapter
  rail, then chapters (h2) on one continuous page: At a glance, How it is made, The chemistry, Why
  Kachchh (or the craft's place), Sources, then Cite this monograph. Borrowed category science is
  labelled "From the Textiles family monograph".
- **Craft without a monograph**: the typographic plate at the masthead ratio, the masthead label
  (kicker "Craft · family · sub-family", provenance "From the KalaVigyan craft list"), "What the
  craft list records" as a FactGrid, and an EmptyState (h2 "Start the research on {craft}") with
  the plate and three questions as an ActionGroup. No chapter rail and no Cite this.
- **Category hub**: family h1 on its plate ground, the family's cited science chapters, its
  sub-families as shelves, its monographs first.
- **Map**: India scale with the Survey of India caption; one variable at a time with its ramp and
  legend; paper-disc markers; at most three families coloured; ranked list beside; a table of
  every value.
- **Answer essay**: provenance rail, the question as h1 at `text-h1`, a three-sentence cited lede,
  ActionGroup of two quiet buttons (Save, Cite this answer), the signature figure as Fig. 1, then
  numbered h2 sections in the spread with margin notes and plates. Arabic-script answers mirror
  their region.
- **Signed-in tool pages** (saved, lessons, settings, keys, admin): ground and raised only, no
  photography, h1 in the headline face, Fields, Tabs only for one object's views, tables with
  tabular figures and rule row lines, ActionGroup for every row, empty states with one way forward.

## 9. Copy

- Sentence case; title case only in proper names. Buttons are verbs: Request access, Sign in,
  Save, Cite this answer, Show all 97, Dip again, Play again, Copy citation.
- Counts come from the catalogue endpoint, never typed.
- Provenance names sources and dates: "Drawn from 20 sources · curated 17 Nov 2026"; never pipeline
  words (stored findings, claims table, records, research trail).
- Chart titles state the finding; diagrams and maps describe ("Blue", "Kachchh and Barmer").
- Stage prose starts with its verb. Errors say what happened and what to do, a sentence each.
- Never on a reader screen: not built yet, coming soon, no data, not enough cited evidence, 0
  results, not curated, yet to be, nothing here yet, beta, AI-generated.
- A stand-in picture says what it shows; a picture from elsewhere is never captioned as the craft's
  place.

## 10. Accessibility

- Contrast by class (SYSTEM.md 2.3): text 4.5:1, large text and graphics 3:1, high contrast 7:1
  for text; control edges rule-strong, never rule; photo text passes the scrim check.
- Focus: a 2px indigo outline at 3px offset on every focusable element (3px in high contrast),
  never removed and never only a colour change; fields keep a 2px ring at 2px offset; segments,
  tabs and stage buttons inset theirs; on a photograph a 2px photo-ink-1 outline over a dark inner
  ring.
- Targets 44px on touch for every control, chips and the account button included.
- Figures: title, description, table; one tab stop, arrow keys, Home and End, tooltips on focus
  closed by Escape; maps reach districts through the ranked list or table.
- Status is never colour alone: evidence states, toasts and errors carry a word and an icon; the
  current step has `aria-current="step"` as well as its rule.
- Search and live research announce short counts or stage names in `role="status"`.
- `lang` and `data-script` on every non-English string; no `aria-label` on generic spans (use
  visually hidden text: the GI tag says "GI registered").
- Themes: `data-theme`, `data-high-contrast`, `data-larger-text` and `data-reduced-motion` are set
  on `<html>` by the boot script before paint (`lib/preferences.ts`). `prefers-contrast: more`
  applies high contrast unless the reader chose Standard. Forced colours: plates, swatches,
  figures and maps set `forced-color-adjust: none` with 1px borders; the primary button, the
  selected segment and a switch that is on use `Highlight` and `HighlightText`; numerals use
  `LinkText`.
- Print: Newsreader on white, margin notes as numbered footnotes, sources at the end, no appbar or
  rail.

## 11. Migrating a file

Decide by job, not by name: a purple class on something you can press becomes indigo; on a
surface, border or decoration it becomes a neutral or disappears (a hairline instead of a box).
The migration is finished (decision 0141): every retired ramp, every neutral, type and radius
alias and the shadcn colour names are gone from the config, and `frontend/tailwind.migration.ts`
with them. Any of those classes compiles to nothing, so write the token class:

- `ink-900`, `ink-700` and `ink-500` are `ink-1`, `ink-2` and `ink-3`; `line-200` is `rule`;
  `surface-50` is `sunk`; `text-xs` and `text-sm` are `text-caption` and `text-ui`;
  `rounded-sm` and `rounded-md` are `rounded-control` and `rounded-card`; `font-bold` is
  `font-semibold`; `font-display` on a display line is `font-headline`.
- `primary` and `ring` are `indigo`, `border` is `rule`, `input` is `rule-strong`, `background`
  is `ground`, `foreground` is `ink-1`, `card` and `popover` are `raised`, `muted` is `sunk`,
  `destructive` is `madder`, and each `-foreground` is the ink that sits on it (`text-indigo-on`,
  `text-madder-on`, `text-ink-1`, `text-ink-3`).
- A purple badge, stage number or reached step is not pressable: badges and stage numbers are
  `bg-ink-1 text-ground` or `bg-sunk text-ink-1`, a reached step the 2px ink-1 leading rule. A
  highlight is `bg-turmeric-wash text-ink-1`; text on an indigo fill is `text-indigo-on`.
- `bg-white`, `fill-white` and `stroke-white` stay #FFF in every theme (the sandbox canvas);
  `text-white` never sits on a photograph or a scrim (use photo ink).
- Stock palettes (`text-indigo-600`, `bg-blue-50`, `text-amber-700`) compile to nothing; status is
  the status tokens.

`e2e/design-guard-unit.spec.ts` keeps all of this from growing. Per file, against
`e2e/design-guard-baseline.json`, it counts and blocks any rise in: retired ramp and stock
palette classes and `black` (`retired`); hex colours outside `app/tokens.css` and the sign-in
brand marks (`hex`); `rgb()`, `hsl()`, `oklch()` and other colour literals (`literal`); every
alias above, the shadcn colour names, `bg-card`, `text-white` and `font-mono` (`alias`); physical
left and right utilities and, in CSS, physical properties (`physical`); media queries,
`min-[…]:`/`max-[…]:` variants and
`matchMedia` widths off the breakpoint list (`media`); and `[var(--…)]` or `-(--…)` values outside
`components/charts`, `map`, `cloth` and `crafts` (`arbitraryVar`). It parses arbitrary, important
and responsive forms and `@apply`. A new file starts at zero. After migrating, record the lower
counts on GitHub: dispatch the **Design guard** workflow (`.github/workflows/design-guard.yml`,
which runs the guard with `DESIGN_GUARD_SHRINK=1`) on the branch and commit the baseline it
uploads. While touching a file, also: `.panel` and `bg-card` around prose go
(interactive cards keep `bg-raised border border-rule rounded-card`), `.eyebrow` becomes `.kicker`,
`.field-button*` becomes Button, `.field-input` becomes Input, physical left and right become
logical, arbitrary sizes become named tokens, and `dark:` overrides of a token are deleted (tokens
theme themselves). The full table with counts is SYSTEM.md section 6.

## 12. Acceptance for every build task

- Board-versus-implementation screenshots at 360, 390, 834, 1194, 1440 and 1920, light and dark,
  plus high contrast and Larger text at 360, against `docs/design/master-board.html` and
  `docs/design/design-system.html` (SYSTEM.md section 8). Capture through Playwright on CI (the E2E
  production run, decision 0076); nothing heavy runs on the laptop.
- No sideways page scroll at any width, Larger text on (phone shelves scroll inside themselves).
- The design guard passes (section 11): no new retired or stock class, hex, colour literal,
  alias, physical utility, off-list media query or misplaced `var()` value; no `font-display` on a
  display line.
- `tools\design_tokens.py --check` passes: no output of the generator was edited by hand.
- Nothing below 12px except citation numerals, SVG text included; every size 1.125x under Larger
  text.
- Reduced motion: every named motion shows its end state and every control still works.
- The landing: a screenshot of each vat phase (rest, in the vat, lifted, in the air) at 1440 and
  390 shows only the dyed ground green, and the scrim check passes under every text line in every
  phase.
- The contrast gate by class and the generator's checks pass in all four themes.
- Pictures: standard Commons widths only, every picture credited, no repeat on a page, crops from
  focal boxes, no shopping imagery.
- Native-script names only with a recorded, reviewed source that names the craft.
- Existing unit specs still pass; a spec that pinned the old look is updated to the system, never
  deleted to make a run green. The hygiene check (`tools/hygiene_check.py`) passes.

## 13. Trap index

- **`text-indigo-600` or any stock palette or retired class** compiles to nothing, silently; only
  the guard catches it. It is `text-indigo`, and the status tokens for status.
- **An unknown class compiles to nothing.** Tailwind reports no error; check the class exists in
  `frontend/tailwind.config.ts` before you rely on it.
- **`text-on-indigo` does not exist**: on-fill ink is `text-indigo-on` and `text-madder-on`.
- **`text-white` does not theme**: on a photograph or scrim use photo ink; on an indigo fill write
  `text-indigo-on`.
- **An old alias class** (`text-ink-900`, `text-sm`, `rounded-md`, `bg-primary`, `bg-purple-700`)
  compiles to nothing since decision 0141 deleted the aliases. Migrate by job (section 11).
- **A UI size inside reading text renders in Newsreader**: size classes carry no family; add
  `font-ui`.
- **`font-display` and `font-bold` compile to nothing.** Display lines are `font-headline`; bold
  is `font-semibold`.
- **A size class sets weight.** `text-h2` is 480 and `text-h4` 600; an extra `font-semibold`
  overrides the token. Plex has no 700.
- **A ramp step on a bar or line** inverts in dark; bars and lines take a series token.
- **The Rann drawn as water**, or the page's district as a solid terracotta fill: salt is
  stippled land; place is outline and 45 degree hatch.
- **Terracotta body text** fails contrast in light (4.0:1); it is large-text only.
- **Turmeric as a state** or an indigo-wash focus: the current step is the indigo fill
  (pressable) or the 2px ink-1 leading rule (not pressable); focus is the indigo outline.
- **Indigo on a heading, kicker, margin number or icon circle** reads as a link.
- **Status colours outside status components**, or info confused with indigo: info is slate.
- **A margin note made into a button**: the sentence's numeral already opens the source.
- **A popover or sheet opened inside a dialog, sheet or Lightbox** that portals to the body opens
  under it. `AnchoredPopover` hosts itself in the nearest modal layer and `Sheet` takes `stacked`
  (the citation cluster sets it) to sit above a dialog; reuse them, never a raw portal.
- **`outline-none` or `outline-hidden` on a control** removes the focus ring: the global ring is in
  the base layer (`app/primitives.css`), so any utility beats it. Only a modal panel that takes
  focus itself drops it; component insets (segments, tabs) are in the components layer.
- **A source shown without its attribution and licence**: the source panel prints both
  (`entryRights`); a new source view does the same (DATA_SOURCES.md).
- **A citation cluster repeating a source number**, or two clusters in one sentence: the release
  gate fails it; de-duplicate and sort.
- **Sources differ inside a `<p>`**: `<details>` is invalid there; it follows the paragraph.
- **`dark:` overrides of themed tokens**: `dark:` compiles to `[data-theme="dark"]`, and tokens
  already theme; such overrides fight high contrast. `class="dark"` on a container does nothing.
- **High contrast in one block only**: light, dark, HC light and HC dark are all generated; add a
  token in the generator, never by hand in one theme. The OS contrast setting follows the app's
  theme: with `data-theme="dark"` it gives HC dark, whatever the OS colour scheme.
- **`suppressHydrationWarning` on `<html>`** is deliberate (the boot script writes attributes);
  keep it and the boot script.
- **framer's `useReducedMotion()`** misses the Settings switch; use `useAppReducedMotion()`.
- **Element existence tied to reduced motion** is a hydration mismatch; gate the motion.
- **Inline framer transitions and springs** escape the tokens and the switches; durations and
  easings come from the motion tokens.
- **Opacity 0 first paint** of a headline or the largest picture fails the release gate.
- **`next/image` for Commons pictures** requests widths Commons does not cache; use `<img srcset
  sizes>` through `commonsThumb`.
- **A centre crop** cuts faces and cloth; crops come from the picture's focal box, and a crop that
  would upscale is a cached derivative.
- **The same picture twice on a page** fails the release gate.
- **Uppercase, letter-spacing or a line break inside an Indic or Arabic-script name.**
- **Nastaliq inside a chip or button**: controls use Noto Sans Arabic.
- **A Wikidata label for the technique in general** shown as the craft's own name (bandhani for
  Kutch Bandhani): held back.
- **A transliteration we made**: never; English alone until a source states the name.
- **SVG labels shrinking with the drawing**: figure SVGs carry `data-fit` and size labels with
  `--k`; a label that would crowd is dropped, never shrunk.
- **Shadows on buttons or sections, blur, gradients, glass**: three shadows exist, blur does not
  compile, the rest is retired.
- **A box around prose**: sections are hairlines and space; raised is for what floats or presses.
- **A media query in rem or at an unlisted width**: breakpoints are px so Larger text never shifts
  a layout, and the guard rejects other widths.
- **`left`, `right`, `ml-`, `pl-`, `text-left`, `border-l`** in a component: logical properties
  only, or right to left breaks.
- **A primary button on a reading page**: an answer's Save and Cite this answer are both quiet.
- **Hand-placed button rows**: ActionGroup, destructive last.
- **Tabs on a monograph**: one continuous page with the chapter rail.
- **Gap copy in an empty state**: say what fills it and offer one way forward.
- **Pipeline words or typed counts** on reader screens: counts come from the catalogue endpoint.
- **A second animation library or GSAP**: framer-motion and token keyframes only.
- **Writing outside the files a task owns** while other lanes run: shared changes reach their
  components through tokens and the shared primitives above.

Found by the Kutch Ajrakh critics (2026-11-19; the full list is
`.claude/skills/kalavigyan-craft-pages/references/page-checklist.md`):

- **The reader's raw question as a headline** or in a citation: edit it into a short display
  line, with the full wording behind "Show the full question".
- **The best photograph below the first screen**: the masthead picture belongs in the first
  viewport.
- **Two mastheads**, or a label card repeating the masthead's GI date and place.
- **Two counts that disagree** ("7 chapters" over a rail of 12): one term, one true count.
- **A signature sentence retold in every section**: hero once, a figure link elsewhere.
- **Two photographs of the same scene** (same room, artisan, photographer): replace one or crop it
  to a clearly different subject.
- **A progress state at rest** ("Writing section 7 of 7", "Drawing · 58%"): pages rest finished;
  a replay is opt-in.
- **A toast in the document flow** draws far down the page; toasts are fixed to the viewport.
- **A translucent sticky bar**, or two sticky bars stacked: opaque, one at a time.
- **Dead zones**: a lone picture in a wide row, a framed box larger than its content, a lead over
  an empty field. Pair the picture, size the box, fill the row.
- **A credit a screen away from its figure**: it sits under the figure.
- **A card with a title and no sentence**: it is not drawn.
- **A media chapter that retells the text**: it is a gallery.

## How this skill is kept true

| What | Kept true by |
|---|---|
| Every value and class it names | `tools/design_tokens.py --check`, run by `tools/tests/test_design_tokens.py`, against the generated `references/tokens.json`, `tokens.css` and `tailwind.config.ts` |
| No file gains a retired class, alias, hex literal or physical utility | the design guard, `frontend/e2e/design-guard-unit.spec.ts` with `design-guard-baseline.json`, in Frontend checks and Design guard |
| Each screen matches its board at 360, 834 and 1440 px in light and dark | the capture and Monograph parity runs (`capture.yml`, `monograph-parity.yml`) against a preview |
| Where each component lives | `frontend/components/`; on 2026-11-21 each "new" file was checked against the tree, and those since built lost the word |
| Agents find it by its `name` and `description` | the frontmatter above |

Re-read it when the owner approves a change to the system, a component is built or moved, or a
section of SYSTEM.md changes.
