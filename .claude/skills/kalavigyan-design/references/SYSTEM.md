# KalaVigyan design system

Version 1.1, 18 November 2026. Owner decision of 18 November 2026: the system is Direction A, **Alum & Indigo**, with three grafts. From the Specimen Cabinet: the specimen label on every craft, the collection wall (every craft has a plate, its name in its own script when sourced), figure numbering and Cite this monograph. From Night Vat: the full-bleed photographic first screen and the vat moment as the one orchestrated animation. Version 1.1 applies both critiques of version 1.0 (creative and engineering); section 9 records every decision, including where a critique was not followed and why.

Read this file before any frontend task. The companions are the reference:

- `tokens.json`: every token with light, dark, high-contrast light and high-contrast dark values, classes and the generator's checks (contrast, reserved-colour distance, ramp floors, texture visibility, specimen frames). It is the source of truth; this file explains it.
- `tokens.css` and `tailwind.config.ts`: written by the same generator, ready to drop in. `tools/design_tokens.py` (with `tools/design/colour.py` and `cvd.py`) writes all three and refuses to pass a token set that breaks a check. Edit the generator, never the outputs.
- `design-system.html`: every token and component rendered in every state. Its Theme, Contrast, Text and Motion switches show each state; map and family colours also appear side by side in all four themes.
- `master-board.html`: the pixel reference for six screens: the landing, the crafts atlas, the Kutch Ajrakh monograph, an answer, a craft without a monograph (Kasuti Embroidery, with its name at equal standing) and an answer in Urdu, right to left.
- `img/hero-dyed-mask.png`: the authored dyed-region mask that ships with the landing photograph (section 2.12).

**Retired for this repository:** the portal purple and every purple, field, gold, ministry, archive, errand, steward, mango and evidence ramp; Plus Jakarta Sans; the flask BrandMark and its logo tokens; glass, mesh and gradient-text utilities (GlassSurface, LiquidGlass, grad-mesh, grad-brand, text-gold-gradient, text-gradient-violet, glass-card, glass-dark, ambient-light); GSAP; the ochre and neem accent colours of version 1.0; and the repository's `field-repo-frontend` and `gsap` skills, which no longer describe this product. Institution credit, where one is shown: IIT Kharagpur and its Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform.

---

## 1. Principles

1. **One control per job.** Each task has one way to do it on a screen. A button that repeats a link, two controls for one value, or a margin note that reopens the popover its sentence already opens is a defect.
2. **Button rows follow the ActionGroup rule.** One action is centred. Two sit on one line and share the width on a phone. Three or more stack full width on a phone and become pills from 640px. A destructive action goes last and is set apart. Every row of buttons is wrapped in `ActionGroup`; nobody hand-places buttons.
3. **Concise copy.** Sentence case. Verbs on buttons. The finding in a chart title. No marketing adjectives, no exclamation marks, no instructions the layout already gives, no pipeline words (stored findings, claims table, records) on reader screens.
4. **Citations quiet but always present.** Every reader sentence carries one cluster of indigo numerals that opens the verbatim quote, its locator and its reliability. The cluster never breaks a line or changes line height.
5. **Never admit a gap.** No reader screen says not built yet, coming soon, no data, not enough evidence, or 0 results. A craft without a monograph shows its plate, its record and questions that start research. An empty list says what fills it and offers one way forward.
6. **Motion only to explain.** Movement shows a reaction or a process. Nothing drifts, staggers, parallaxes, decorates or follows the scroll, and every motion has a still end state authored as the default style.
7. **Indigo means you can press it.** Indigo is the only interactive colour. Madder means emphasis, a disagreement between sources, or a real hazard. Terracotta means place. Turmeric only highlights. Data never borrows any of them: every ramp step, series colour and family hue sits 10 or more delta E from indigo, indigo-hover, madder, terracotta and turmeric in its theme, and the generator enforces it.
8. **Names in their own scripts, at equal standing, only where a source states them and names this craft.** Until then the plate and title carry the English name alone. Never transliterate a name ourselves.
9. **Pictures are plates.** Caption first, credit after, standard Commons thumbnail widths, no repeats on a page, no stock, shopping or AI imagery, no price tags or sale tables.
10. **Dense with every field** (owner, 2026-11-20). A reading page carries every field its sources cover (the 16 of `research/sections.DISCIPLINE_FIELDS`), each with cited quantities, mechanisms, names and dates, and every screen earns its height: margin notes, fact grids, small multiples, tables and figures hold detail beside the prose instead of below it. No empty band, no spacer beyond the spacing scale, no card that repeats a sentence already on screen. Density never breaks the measure (66ch), the type scale, the citation rules or the floor of 12px; a field with no source stays off the page and becomes a research question (principle 5).

The owner rule against code comments still holds: none of the CSS, TSX or Python a task writes carries comments.

---

## 2. Tokens

### 2.1 How tokens ship

Semantic colours are RGB channel triplets in `--c-<name>`, so Tailwind's alpha modifier keeps working, with a hex alias `--<name>: rgb(var(--c-<name>))` for raw CSS and SVG. Data, map, specimen and plate tokens are hex in `--<name>`. The boot script already sets `data-theme`, `data-high-contrast`, `data-larger-text` and `data-reduced-motion` on `<html>` before paint; tokens hang off those attributes. Copy `tokens.css` into `globals.css` as generated; never hand-type a hex in a component.

```css
:root { color-scheme: light; --text-zoom: 1; --c-ground: 244 245 241; --c-indigo: 36 59 156; --ground: rgb(var(--c-ground)); }
:root[data-theme="dark"] { color-scheme: dark; --c-ground: 14 18 28; --c-indigo: 169 188 243; }
@media (prefers-contrast: more) { :root:not([data-high-contrast="false"]) { --c-ground: 255 255 255; --c-indigo: 23 40 129; } }
:root[data-high-contrast="true"] { --c-ground: 255 255 255; --c-indigo: 23 40 129; }
:root[data-theme="dark"][data-high-contrast="true"] { --c-ground: 0 0 0; --c-indigo: 201 213 251; }
:root[data-larger-text="true"] { font-size: 112.5%; --text-zoom: 1.125; }
[data-script="Gujr"] { font-family: var(--font-gujr-reading); --script-scale: 1.08; --script-leading: 1.75; --script-display-leading: 1.25; }
```

- **OS contrast setting.** `prefers-contrast: more` applies the high-contrast tokens unless the reader has chosen Standard in the app, which writes `data-high-contrast="false"`.
- **Forced colours (Windows).** Specimen swatches, plates, figures and maps set `forced-color-adjust: none` and keep explicit 1px borders; the primary button, the selected segment and a switch that is on use `Highlight` and `HighlightText`; citation numerals use `LinkText`.
- **Scoped themes.** `tokens.css` also emits `.tscope-light`, `.tscope-dark`, `.tscope-hcl` and `.tscope-hcd`, which redefine every token on a subtree. They exist for the design-system page and for screenshot tests that compare themes side by side; product code never uses them.

### 2.2 Tailwind

The repository runs Tailwind 4.3.5 with `@config`. `tailwind.config.ts` in this folder is complete; use it as written. Its rules:

- Semantic colours live in `theme.colors`, not `theme.extend.colors`, so the stock palettes (indigo-50…950, purple, amber, red and the rest) stop compiling and a near-miss like `text-indigo-600` fails the build instead of looking almost right. `transparent`, `current` and `inherit` are kept.
- Screens: `sm` 640, `md` 768, `lg` 1024, `rail` 1200, `xl` 1280, `2xl` 1536. No other breakpoint exists.
- `fontSize` maps every type token to `text-caption` … `text-stat`, each carrying its line height, tracking and weight. `fontFamily` has `headline`, `reading` (and `serif`), `ui` (and `sans`), `code`, and `display` as a migration alias of `ui`.
- `font-headline` needs no plugin: Newsreader's optical size follows the size (`font-optical-sizing: auto` in the base layer), so the family key is enough and no variation setting is forced. Opsz 72 is never forced below 40px.
- `borderRadius`: `plate` 2, `control` 4, `card` 6, `sheet` 14, `pill`, `full`. `boxShadow`: `pop`, `label`, `sheet`, `none`. `transitionDuration` and `transitionTimingFunction` map the motion tokens. `backdropBlur` is empty: blur utilities stop compiling.
- Data, map, specimen and plate tokens stay CSS variables only. Chart, map, cloth and plate modules use them through props or `[var(--x)]` arbitrary values; the guard allows `var(--` arbitrary values in `components/charts`, `components/map`, `components/cloth` and `components/crafts`, and nowhere else.
- Migration aliases (`legacyInk`, `legacyColors`, `legacyFontSize`, `legacyRadius`, `bold` → 600, `shadow-sm` → none, `ease-spring` → out) keep today's classes compiling to the new tokens, so nothing silently disappears. The guard spec blocks new uses of every alias; each alias is deleted when its count reaches zero (section 6).
- Base layer: `b, strong { font-weight: 600 }`, `font-synthesis: none` (Plex ships 400 to 600, so nothing renders faux bold), the base border colour `rgb(var(--c-rule))`, the placeholder colour `rgb(var(--c-ink-3))`.

### 2.3 Contrast classes

Every colour token has a class, and the gate checks it by class:

- **text**: 4.5:1 or better on ground, raised and sunk in its theme, 7:1 or better in high contrast. Usable at any size.
- **large-text**: 3:1 or better everywhere; only for text 24px regular or 18.66px semibold and up, and for graphics. Terracotta is the one large-text token: never 12–16px terracotta text in light.
- **graphic**: non-text marks that identify a control, a state or a data value: 3:1 or better against the surface they sit on, recorded per surface (ground, sunk, land, water, salt).
- **onFill**: text or icons on a fill (`on-indigo`, `on-madder`): 4.5:1 or better against that fill, 7:1 in high contrast. Not checked against ground.
- **fill**: a background; the text set on it is checked instead (`onText` in tokens.json lists the pairs).
- **surface**: page, panel and map grounds.
- **decorative**: no requirement, and never the only boundary of a control or the only carrier of meaning (rule, gridlines, turmeric, district lines).
- **specimen**: a depicted material; does not theme; always textured and framed (1px ink-2, then a 2px raised mat); never a control.

### 2.4 Semantic colour

Ratios are the lowest against ground, raised and sunk in that theme (on-indigo against indigo and indigo-hover; on-madder against madder).

| Token | Tailwind | Class | Light | Dark | HC light | HC dark | Use |
|---|---|---|---|---|---|---|---|
| `--c-ground` | `ground` | surface | `#F4F5F1` 1.0 | `#0E121C` 1.0 | `#FFFFFF` 1.0 | `#000000` 1.0 | Alum paper. The page. Body background of every page. Paper grain sits on it only. |
| `--c-raised` | `raised` | surface | `#FBFBF9` 1.0 | `#161B28` 1.0 | `#FFFFFF` 1.0 | `#0E121C` 1.0 | Paper laid on paper. Popovers, sheets, dialogs, specimen labels, inputs, interactive cards, the mat inside a specimen frame. Never a box around prose. |
| `--c-sunk` | `sunk` | surface | `#E8EAE4` 1.0 | `#0A0D15` 1.0 | `#EEF0EA` 1.0 | `#05070C` 1.0 | A shallow well in the paper. Figure grounds, the how-to-read band, skeletons, disabled inputs, code wells. |
| `--c-rule` | `rule` | decorative | `#D2D6CE` 1.2 | `#2A3142` 1.3 | `#8A9088` 2.9 | `#7F889C` 5.3 | Hairline. Dividers between rows and sections, gridlines. Never the only boundary of a control or a swatch. |
| `--c-rule-strong` | `rule-strong` | graphic | `#767C74` 3.5 | `#7A849A` 4.6 | `#3D433C` 8.8 | `#C4CBD8` 11.5 | Control and specimen edge. Borders of quiet buttons, chips, inputs, segmented choices and toggles off. 3:1 or better on every surface. |
| `--c-ink-1` | `ink-1` | text | `#1C1815` 14.5 | `#ECEAE3` 14.3 | `#000000` 18.3 | `#FFFFFF` 18.7 | Kut iron-black. Headlines, body text, figure strokes, the chart baseline and trend line, dates, the current step of a process. |
| `--c-ink-2` | `ink-2` | text | `#3A3430` 10.1 | `#CBC8C0` 10.3 | `#1C1815` 15.4 | `#F1EFE9` 16.3 | Second ink. Captions in italic, standfirsts, chart annotation, botanical names in italic, list meta that is still read, and the 1px frame of every specimen swatch. |
| `--c-ink-3` | `ink-3` | text | `#59534E` 6.2 | `#A5A198` 6.7 | `#2E2925` 12.5 | `#D9D6CE` 12.9 | Third ink. Credits, source lines, axis labels, kickers, timestamps, margin-note numbers. Never below 12px. |
| `--c-indigo` | `indigo` | text | `#243B9C` 7.9 | `#A9BCF3` 9.2 | `#172881` 11.0 | `#C9D5FB` 12.8 | The only interactive colour. Links, the primary button, citation numerals, the selected tab, chip and segment, a pressed stage, toggles on, focus rings. Nothing that cannot be pressed. Chroma 0.15 or more, so no dyed specimen (chroma 0.06 or less) reads as a control. |
| `--c-indigo-hover` | `indigo-hover` | text | `#162779` 10.8 | `#CBD7FA` 12.0 | `#0C1761` 13.9 | `#E2E9FD` 15.4 | Indigo under the pointer. Hover and pressed state of indigo text and the primary button. |
| `--c-indigo-wash` | `indigo-wash` | fill | `#DFE6F6` 1.0 | `#1E2849` 1.2 | `#D3DCF4` 1.2 | `#24305A` 1.5 | Selected fill. Background of a pressed chip and the selected option in a list. Never a section background, never a focus indicator on its own. |
| `--c-on-indigo` | `on-indigo` | onFill | `#FBFBF9` 9.3 | `#0E121C` 10.0 | `#FFFFFF` 12.7 | `#000000` 14.4 | Ink on indigo. Label of the primary button, the selected segment and a pressed stage; the thumb of a switch that is on. |
| `--c-madder` | `madder` | text | `#9E2E27` 6.0 | `#EF8E80` 7.2 | `#7A1D18` 9.1 | `#FFAFA3` 10.6 | Emphasis, disagreement and real hazard. The Sources differ marker and its 135 degree hatch, genuine chemical or safety hazards, destructive actions. Never decoration, never a chart series. |
| `--c-madder-wash` | `madder-wash` | fill | `#F4DFDB` 1.1 | `#3B2124` 1.2 | `#F4DAD5` 1.1 | `#45242A` 1.4 | Madder ground. Behind a hazard note or a destructive confirmation. Text on it is madder or ink-1. |
| `--c-on-madder` | `on-madder` | onFill | `#FBFBF9` 7.0 | `#0E121C` 7.9 | `#FFFFFF` 10.4 | `#000000` 11.9 | Ink on madder. Label of a confirming destructive button (madder fill). |
| `--c-turmeric` | `turmeric` | decorative | `#E6AE2A` 1.7 | `#F0C152` 10.2 | `#E6AE2A` 1.8 | `#FFD166` 13.0 | Highlight only. The 2px rule beside a demonstrated sentence. Never text, never a control, never a state indicator. |
| `--c-turmeric-wash` | `turmeric-wash` | fill | `#F8E6A8` 1.0 | `#4A3A12` 1.6 | `#F8E09A` 1.1 | `#5A4614` 2.1 | Highlighter. The sentence a citation popover is open for, search matches, the sentences a selected source supports. Ink-1 reads on it. |
| `--c-turmeric-text` | `turmeric-text` | text | `#7A5300` 5.7 | `#F0C152` 10.2 | `#5A3D00` 8.7 | `#FFD166` 13.0 | Turmeric when it must be text. The word Inferred and its dotted underline. |
| `--c-terracotta` | `terracotta` | large-text | `#B05A36` 4.0 | `#E0916C` 6.9 | `#7D3519` 7.6 | `#F5AE8C` 10.1 | Place. Map pins, the outline and 45 degree hatch of the place a page is about, place glyphs, large place headings (24px and up). Not for small text in light. |
| `--c-error` | `error` | text | `#9E2E27` 6.0 | `#EF8E80` 7.2 | `#7A1D18` 9.1 | `#FFAFA3` 10.6 | Something went wrong. Field errors and failed actions. Same pigment as madder; always with an icon and words. |
| `--c-error-wash` | `error-wash` | fill | `#F4DFDB` 1.1 | `#3B2124` 1.2 | `#F4DAD5` 1.1 | `#45242A` 1.4 | Error ground. Error toast and inline error banner. |
| `--c-warning` | `warning` | text | `#8A4A12` 5.6 | `#F0A868` 8.6 | `#6A3608` 8.5 | `#FFC08A` 11.7 | Take care. Expiring sessions, unsaved changes, quota near its limit. Never for ordinary stage facts. |
| `--c-warning-wash` | `warning-wash` | fill | `#F6E4D2` 1.0 | `#3D2A17` 1.3 | `#F4DCC4` 1.1 | `#4A3016` 1.5 | Warning ground. Warning toast and banner. |
| `--c-info` | `info` | text | `#2F5266` 6.9 | `#84A5B0` 6.5 | `#1F3D4F` 9.9 | `#A1BCCA` 9.4 | Neutral news. Info toasts and notices. Slate, 10 or more delta E from indigo in every theme, so it never reads as a link. |
| `--c-info-wash` | `info-wash` | fill | `#DDE7EC` 1.0 | `#16252F` 1.1 | `#D2E1E8` 1.2 | `#1A2C38` 1.3 | Info ground. Info toast and banner. |
| `--c-success` | `success` | text | `#2E6A41` 5.3 | `#8CC79A` 8.8 | `#1F4F2E` 8.2 | `#AEE0BA` 12.6 | Done. Saved, copied, access granted. |
| `--c-success-wash` | `success-wash` | fill | `#DCEADF` 1.0 | `#16281C` 1.1 | `#D0E6D5` 1.1 | `#173020` 1.3 | Success ground. Success toast and banner. |

**When to use what.**
- Ground under everything; the 3 to 4.5 per cent paper grain only on ground, off in high contrast and print. Raised for anything that floats or that you can press as a card. Sunk for wells: figure grounds, the how-to-read band, skeletons, disabled fields. A section is never boxed in raised.
- Ink-1 for reading, headlines, dates (in tabular lining figures) and the current step of a process; ink-2 for captions, standfirsts and botanical names (in italic); ink-3 for credits, axes, margin-note numbers and meta (never below 12px).
- Indigo only for links, the primary button, citation numerals, the selected tab, chip and segment, a pressed stage, toggles on and focus rings. Indigo fills mark what you can press or have chosen: the primary button, the selected segment, a pressed stage, a switch that is on. Nothing indigo that cannot be pressed: no indigo headings, margin numbers, icons in circles, section bands or chart series.
- Madder only for the Sources differ marker and its hatch, genuine chemical or safety hazards, destructive actions, and field errors (as `error`). A confirming destructive button is a madder fill with `on-madder` text.
- Turmeric as a 2px rule beside a demonstrated sentence, nothing else. Turmeric-wash highlights the sentence a popover is open for, search matches and the sentences a selected source supports. Turmeric-text is the word Inferred and its dotted underline. Turmeric is never a state indicator.
- Terracotta marks place: map pins, the outline and 45° hatch of the page's own district, place glyphs.
- Status colours appear only inside status components (toast, inline message, banner, field error), always with an icon and words. Info is slate and sits 10 or more delta E from indigo in every theme, so it never reads as a link.

**The current step of a process** has two looks and no others. A stage you can press (the living cloth's stage buttons) follows SegmentedChoice: indigo fill, on-indigo text, `aria-pressed`. A step you cannot press (the landing label's vat steps, the answer's three frames, the stage the reader jumped to) carries a 2px ink-1 rule on its leading edge (top of a horizontal step, inline start of a vertical one) with its label at weight 600, and `aria-current="step"`.

### 2.5 Specimen colours

Depicted materials. They do not change with the theme. Each is a material record in `tools/design/materials.json`: the craft's material by its dossier id, the facts that state or show its colour, the colour and what the swatch shows. The generator turns every record into its token, records the nearest reserved colour and the frame ratios, and refuses a record within 3 delta E of a reserved colour in any theme, a blue as saturated as the interactive indigo (chroma 0.15 or more), or a swatch whose edge does not read; it also writes the names a spec may depict (`backend/app/research/depicted_materials.py`, `frontend/lib/depictedMaterials.ts`). Kutch Ajrakh's dyes were the first records; any craft's material with a record can be drawn. The interactive indigo is chroma 0.15 or more and every dyed blue is chroma 0.06 or less, so a dye never reads as a control; dye-madder is alizarin crimson, deeper and bluer than the semantic madder. The nearest semantic colour is recorded per theme.

| Token | Hex | Nearest semantic (light) | Shows |
|---|---|---|---|
| `--dye-cloth` | `#F4F2EA` | 22.6 from turmeric | Scoured cotton after saaj. |
| `--dye-harda` | `#DFC974` | 7.3 from turmeric | Myrobalan (harda) yellow after kasanu. |
| `--dye-harda-dry` | `#E7D48D` | 10.7 from turmeric | Harda yellow, sun-dried. |
| `--dye-lime` | `#F7F5EE` | 23.4 from turmeric | Lime and gum resist outline. |
| `--dye-lime-edge` | `#CFCBBE` | 14.5 from turmeric | Edge of a lime outline on cloth. |
| `--dye-kut` | `#2A1C17` | 17.6 from indigo-hover | Kut iron-black on tannin: chocolate-black. |
| `--dye-kesari` | `#E8894A` | 10.0 from turmeric | Kesari rang, the fugitive saffron tint in the alum paste. |
| `--dye-mud` | `#97785A` | 7.9 from terracotta | Gach clay resist. |
| `--dye-mud-wet` | `#7D6249` | 9.1 from terracotta | Gach clay, wet from washing. |
| `--dye-leuco` | `#6F9A3E` | 18.6 from turmeric | Cloth lifted green from the vat. |
| `--dye-vat-liquor` | `#A3A14A` | 11.2 from turmeric | Yellow-green vat liquor with dissolved leucoindigo. |
| `--dye-indigo` | `#253045` | 10.0 from indigo-hover | Indigo-dyed cotton after oxidation: a dull slate navy, chroma 0.04, never the interactive indigo. |
| `--dye-indigo-deep` | `#121A2B` | 14.6 from indigo-hover | Indigo after the second round (minakari). |
| `--dye-madder` | `#7E032C` | 10.1 from madder | Madder red where alum was printed: alizarin crimson, deeper and bluer than the semantic madder. |
| `--dye-madder-bright` | `#C03D69` | 10.6 from terracotta | Madder after the second round: a lighter crimson. |
| `--dye-pink` | `#EED6CC` | 16.9 from turmeric | The pinkish tinge madder leaves on whites that no lime protected. |
| `--dye-pink-edge` | `#C98F86` | 14.6 from turmeric | Edge of the pink tinge. |
| `--dip-1` | `#5D7698` | 17.7 from terracotta | One dip, oxidised. |
| `--dip-2` | `#475C7A` | 12.7 from indigo | Two dips. |
| `--dip-3` | `#354660` | 11.2 from indigo | Three dips. |
| `--dip-4` | `#253045` | 10.0 from indigo-hover | Four dips, the darkest blue. |
| `--dye-bidri-white` | `#D6D5CE` | 16.7 from turmeric | Bidriware: the alloy sanded zinc-white. |
| `--dye-bidri-black` | `#232326` | 14.9 from indigo-hover | Bidriware: the matt black patina of the fort-earth bath. |
| `--dye-bidri-silver` | `#BFC2C6` | 15.9 from turmeric | Bidriware: the silver inlay. |
| `--dye-quartz-white` | `#F1EFE7` | 21.9 from turmeric | Blue Pottery of Jaipur: the white quartz body. |
| `--dye-cobalt` | `#385E95` | 10.3 from indigo | Blue Pottery of Jaipur: cobalt oxide fired deep blue, chroma 0.10. |
| `--dye-copper-turquoise` | `#429595` | 20.5 from terracotta | Blue Pottery of Jaipur: copper oxide fired turquoise. |
| `--dye-field-soil` | `#3B342E` | 15.4 from indigo-hover | Bastar Dhokra: the black field soil of the core. |
| `--dye-sem-green` | `#5F7B3B` | 15.2 from terracotta | Bastar Dhokra: the core rubbed green with sem leaves. |
| `--dye-river-soil` | `#8E5E4A` | 6.3 from terracotta | Bastar Dhokra: the red riverside soil. |
| `--photo-ink-1` | `#FBFAF6` | – | Headline ink over a scrimmed photograph. |
| `--photo-ink-2` | `#E6E3DA` | – | Standfirst ink over a scrimmed photograph. |

- **Frame.** Every swatch sits in a 1px ink-2 frame with a 2px raised mat inside it. Its edge then reads at 3:1 or better against the mat (dark swatches) or the frame (light and mid swatches) in all four themes; tokens.json records both ratios per swatch. The swatch carries the weave texture.
- **Exception, with safeguards.** A dye is a real material, so a few specimens sit closer than 10 delta E to a reserved colour in some theme: harda 7.3 from turmeric, gach clay 7.9 and dhokra's riverside soil 6.3 from terracotta, dye-madder 4.4 from the high-contrast madder. Safeguards: a specimen is always framed, textured and named in a key; it never fills a control, a link, a chart series or a map class; the reserved colours never fill an area larger than a control.
- **On a photograph.** Text uses `--photo-ink-1` and `--photo-ink-2` over a scrim keyed to the text block: `--photo-scrim-start` (a horizontal gradient under text at the inline start, desktop and tablet, mirrored in right-to-left) and `--photo-scrim-bottom` (phone, text stacked at the bottom). The primary button on a photograph is a paper button with indigo text; the quiet one is outlined in photo ink over a 40 per cent dark fill. These do not theme.
- **Scrim check (acceptance).** For every art-directed crop, the build hides the text, screenshots the photograph through its scrim and samples the pixels under each text line's own boxes. The 95th-percentile luminance must leave photo-ink-1 at 4.5:1 or better for every line, in every vat phase (rest, in the vat, lifted green, in the air). On the landing photograph today the worst line is 5.96:1 (kicker, 390px); headlines are 8.0:1 or better. A failing crop strengthens its scrim; text is never weakened.
- **Appbar on a photograph.** Photo ink and a translucent rule while the photograph is under it; once 64px of page ground has scrolled under the bar it switches to page ink in one 200ms state change.

### 2.6 Plate grounds

The material ground of a craft's typographic plate. Each ground pairs with an ink at 5:1 or better in every theme. Dark grounds stay warm and material (cotton, brass, wood, clay), not generic slate.

| Token | Material | Texture (tile, opacity) | Light ground / ink | Dark | HC light | HC dark |
|---|---|---|---|---|---|---|
| `--plate-textile` | Textiles | twill: regular diagonal twill (7px, 12%) | `#E8E4D6` / `#1C1815` (13.86, tex ΔE 7.3) | `#373226` / `#F4EEE4` (11.05, tex ΔE 8.8) | `#EFEBDD` / `#000000` (17.6, tex ΔE 8.6) | `#2D291C` / `#FFFFFF` (14.53, tex ΔE 10.1) |
| `--plate-metal` | Metal | hammer: seeded hammer dents: 26 open arcs, radius 2 to 6px, random rotation (112px, 16%) | `#D5BD84` / `#1C1815` (9.61, tex ΔE 8.5) | `#4D4122` / `#F4EEDD` (8.65, tex ΔE 10.1) | `#DCC48C` / `#000000` (12.32, tex ΔE 10.0) | `#433617` / `#FFFFFF` (11.81, tex ΔE 11.8) |
| `--plate-wood` | Wood | grain: seeded wood grain: 9 wavy lines of varying spacing and 2 knots (240px, 15%) | `#B08A5F` / `#1C1815` (5.58, tex ΔE 6.1) | `#45301C` / `#F4EEE4` (10.75, tex ΔE 10.3) | `#BC9668` / `#000000` (7.7, tex ΔE 7.7) | `#3B2612` / `#FFFFFF` (14.27, tex ΔE 12.2) |
| `--plate-fibre` | Natural fibre and grass | weave: basket weave, over two under two (14px, 16%) | `#DCCD92` / `#1C1815` (11.08, tex ΔE 9.1) | `#454024` / `#F3EFDF` (9.06, tex ΔE 10.3) | `#E3D59C` / `#000000` (14.26, tex ΔE 10.6) | `#3B3619` / `#FFFFFF` (12.16, tex ΔE 12.0) |
| `--plate-clay` | Clay | plaster: seeded trowel arcs: 14 shallow curves (128px, 15%) | `#9C553A` / `#FBF7EF` (5.21, tex ΔE 6.9) | `#4F2A1D` / `#F6ECE6` (10.74, tex ΔE 10.2) | `#84432B` / `#FFFFFF` (7.45, tex ΔE 8.4) | `#442013` / `#FFFFFF` (14.37, tex ΔE 11.7) |
| `--plate-stone` | Stone | speckle: seeded mineral speckle: 70 dots, radius 0.5 to 1.6px, clustered (120px, 20%) | `#C6CAC6` / `#1C1815` (10.64, tex ΔE 11.2) | `#33393E` / `#EEF0F2` (10.24, tex ΔE 13.7) | `#D0D4D0` / `#000000` (14.01, tex ΔE 13.2) | `#292E34` / `#FFFFFF` (13.68, tex ΔE 16.0) |
| `--plate-paper` | Paper | laid: laid lines with chain lines, as in handmade paper (26px, 12%) | `#EEEAE0` / `#1C1815` (14.68, tex ΔE 7.6) | `#3F3D36` / `#F1EFE8` (9.45, tex ΔE 7.9) | `#F4F1E8` / `#000000` (18.59, tex ΔE 8.8) | `#35332C` / `#FFFFFF` (12.64, tex ΔE 9.2) |
| `--plate-leather` | Leather | pebble: seeded pebble grain: 22 small ellipses (96px, 15%) | `#673A2A` / `#FBF7EF` (8.87, tex ΔE 9.2) | `#371F19` / `#F6ECE3` (13.13, tex ΔE 11.7) | `#592C1D` / `#FFFFFF` (11.65, tex ΔE 10.7) | `#2D1610` / `#FFFFFF` (17.02, tex ΔE 13.3) |
| `--plate-paint` | Painting | brush: seeded brush strokes: 7 tapered curves (180px, 13%) | `#EAE2CF` / `#1C1815` (13.67, tex ΔE 8.0) | `#41392F` / `#F3EFE7` (9.89, tex ΔE 8.9) | `#F0E9D8` / `#000000` (17.35, tex ΔE 9.2) | `#362F25` / `#FFFFFF` (13.21, tex ΔE 10.3) |
| `--plate-instr` | Musical instruments | grain: seeded wood grain: 9 wavy lines of varying spacing and 2 knots (240px, 15%) | `#C9A274` / `#1C1815` (7.48, tex ΔE 7.2) | `#4E381F` / `#F5EEE3` (9.54, tex ΔE 9.7) | `#D2AC7E` / `#000000` (9.94, tex ΔE 8.8) | `#432E14` / `#FFFFFF` (12.81, tex ΔE 11.3) |
| `--plate-toys` | Toys and figurines | plaster: seeded trowel arcs: 14 shallow curves (128px, 15%) | `#D2AC63` / `#1C1815` (8.25, tex ΔE 7.4) | `#524225` / `#F6F0E1` (8.53, tex ΔE 9.4) | `#D8B46D` / `#000000` (10.67, tex ΔE 9.0) | `#48381A` / `#FFFFFF` (11.31, tex ΔE 10.8) |
| `--plate-misc` | More crafts | brush: seeded brush strokes: 7 tapered curves (180px, 13%) | `#E2D9C6` / `#1C1815` (12.57, tex ΔE 7.8) | `#3C372F` / `#F2EEE6` (10.2, tex ΔE 9.1) | `#E8E0CE` / `#000000` (15.98, tex ΔE 9.0) | `#322D25` / `#FFFFFF` (13.66, tex ΔE 10.4) |

- **Textures.** Irregular materials (hammered metal, stone, wood, plaster, pebble, brush) are seeded random patterns on a large tile, so no grid shows; woven and laid materials keep their regular structure. The pattern is drawn in `color-mix(in srgb, ink <opacity>, transparent)`; where it falls it changes the ground by 3 or more delta E in every theme (recorded as `textureDeltaE`).
- **Knockout.** The kicker and the name sit on a block of the plate ground with 8px padding (`box-shadow: 0 0 0 8px var(--gb)`, cloned per line), so no texture runs through text.
- Wood and leather, adjacent on the wall, are 26 delta E apart in light. Painting, musical instruments and toys take their own grounds inside the More crafts family; everything else in it takes `misc`.
- Shelf headers and the index use the plate ground as the family swatch, never a categorical data colour, and a family legend never sits beside plates.

### 2.7 Data colour and charts

**The reserved floor.** Every ramp step, series colour and family hue sits 10 or more OKLab delta E ×100 from indigo, indigo-hover, madder, terracotta and turmeric in its own theme. Every ramp's first step sits 10 or more from ground, sunk, land, neighbouring land and water; the pH neutral class and the highest elevation class too. Adjacent steps are 8 or more apart (5 for the hypsometric elevation tints). The generator prints a violation and refuses to ship otherwise; tokens.json records the worst value per ramp and theme.

**Ramps.** Sequential ramps flip lightness in dark (low values near the ground, high values bright) but keep their hues tied to the value, so rain is yellow-green for little and teal for much in every theme, and temperature is blush for cool and plum for hot. pH is diverging and its neutral class always contains 7.0. Earth runs khaki to chocolate and cover spring green to forest green, so soil and vegetation never read as rain or place. Mineral is categorical: six classes drawn as point symbols, each in its own shape with a 1px ink-1 edge, never an area fill.

| Ramp | Kind | Light steps | Dark steps | Worst reserved ΔE (L/D/HCL/HCD) | First step vs land (L/D/HCL/HCD) | Use and breaks |
|---|---|---|---|---|---|---|
| `--rain-1…6` | sequential | #E8E281 #ACCE78 #71B679 #389B7A #007C76 #005C68 | #434600 #4B6425 #4F824C #579F77 #68BBA3 #85D6CF | 10.6 / 10.6 / 10.6 / 10.3 | 11.2 / 13.8 / 11.2 / 14.0 | Annual or seasonal rainfall, rain anomalies above zero, groundwater recharge on maps. Bars and lines take --series-rain, not a ramp step. Classes from the data (Jenks or quantiles) unless the variable has agreed thresholds; label each break in mm. |
| `--density-1…6` | sequential | #ADA57E #948963 #79704F #65563B #4E3E29 #372818 | #4C3201 #604D2A #7B6E4F #9D9275 #C2BA9C #ECE6C2 | 10.2 / 10.5 / 10.5 / 10.7 | 21.0 / 10.7 / 21.6 / 11.2 | Crafts per state or district on choropleths. Proportional circles and ranked bars of the same count take --series-count. Counts: natural breaks; proportional circles scale by area, never radius. |
| `--heat-1…6` | sequential | #FFB3AD #E58D95 #C56A84 #A04C74 #7A3163 #531A4F | #5B161D #802E41 #A34A6B #C36999 #DF8CC8 #F9B2F6 | 10.7 / 10.6 / 10.6 / 10.8 | 12.6 / 11.6 / 11.7 / 12.6 | Mean, maximum and minimum temperature on maps, firing temperature bands. Temperature lines take --series-heat. Whole degrees Celsius; firing bands by the kiln stage named in the source. |
| `--ph-1…5` | diverging | #8B3B74 #C182A5 #B0A389 #76AF77 #2F743D | #E093CF #A46B91 #575343 #5E9660 #88CF8A | 11.5 / 11.0 / 11.1 / 10.3 | 46.5 / 47.9 / 51.8 / 55.0 | Soil pH, water pH. The middle class is fixed at 6.5 to 7.5 whatever the data range; never re-centre on the mean. The neutral class is 10 or more delta E from land, so a neutral district never looks unshaded. Agronomic classes: below 5.5, 5.5 to 6.5, 6.5 to 7.5, 7.5 to 8.5, above 8.5. |
| `--elevation-1…7` | hypsometric | #99C68B #D2D6A1 #ECDCC1 #D5B89D #C29C80 #A28572 #A79EC4 | #2C4526 #4C512D #675D39 #806B4A #957B61 #A28A77 #9BA6B1 | 10.6 / 10.2 / 10.5 / 12.2 | 16.7 / 10.4 / 18.3 / 12.0 | Relief tints on locator and region maps. Always paired with labelled contours or spot heights. Metres: below 100, 100 to 300, 300 to 600, 600 to 1,000, 1,000 to 2,000, 2,000 to 4,000, above 4,000. |
| `--earth-1…6` | sequential | #AEAE82 #9F8D69 #7D766E #6F5847 #5F3B27 #4B1F09 | #59311E #704C36 #856851 #978673 #C1BAA5 #EBE2B5 | 10.7 / 10.9 / 11.1 / 13.5 | 19.0 / 11.0 / 20.7 / 10.6 | Soil organic carbon, clay, sand, cation exchange capacity, bare ground and forest loss on maps. Bars and lines take --chart-series, not a ramp step. Classes from the data (quantiles) in the dataset's unit. |
| `--cover-1…6` | sequential | #B4D181 #92B661 #6A9C50 #458242 #266739 #164B2E | #124C28 #2D6634 #4A823E #6C9D45 #93B660 #D2DEB2 | 10.7 / 10.6 / 10.7 / 10.6 | 14.2 / 12.5 / 14.0 / 15.7 | Tree cover, cropland and other vegetation shares on maps. Bars and lines take --chart-series. Classes from the data (quantiles) in per cent of the district's area. |
| `--mineral-1…6` | categorical | #546577 #884F91 #DA8A9C #1C8D7A #99C163 #2A92BB | #8EA1B4 #C184CB #F9B5C3 #54B9A5 #A9DD83 #00A4C0 | 11.1 / 10.7 / 13.8 / 10.8 | 42.6 / 40.7 / 49.9 / 49.8 | Mineral deposits by class on the map's mineral layer: point symbols with a 1px ink-1 edge, never area fills. Classes, in order, by the deposit's first-listed commodity in the USGS Mineral Resources Data System: iron; manganese, chromium and alloy metals; aluminium; copper, lead, zinc and precious metals; titanium, zirconium and rare earths; industrial minerals. |

**Series colours.** A bar or line never takes a ramp step, because ramps flip in dark. Each variable has a series token that keeps its hue in every theme, at 3:1 or better on ground and sunk (and on land for counts):

| Token | Class | Light | Dark | HC light | HC dark | Use |
|---|---|---|---|---|---|---|
| `--series-rain` | graphic | `#00736F` 5.21:1, ΔE 19.3 | `#59B0A8` 7.31:1, ΔE 14.8 | `#005C5A` 7.84:1, ΔE 17.6 | `#73C9BF` 10.84:1, ΔE 13.8 | Rainfall bars and lines, in the rain ramp's teal in every theme. |
| `--series-heat` | graphic | `#803668` 7.25:1, ΔE 11.1 | `#CC79A9` 6.13:1, ΔE 11.1 | `#783166` 8.64:1, ΔE 11.4 | `#E195C5` 9.31:1, ΔE 10.7 | Temperature lines and dots, in the heat ramp's rose-plum in every theme. |
| `--series-count` | graphic | `#6F6246` 5.46:1, ΔE 11.4 | `#918567` 5.13:1, ΔE 13.7 | `#43361B` 11.78:1, ΔE 11.6 | `#A99D83` 7.84:1, ΔE 13.1 | Counts of crafts: proportional circles and the ranked bars beside them, in the density ramp's umber. |

Anything else takes `--chart-series`; only the mark the title names takes `--chart-emph`. On the landing, the proportional circles and the ranked bars both show crafts per state, so both wear `--series-count`, and Uttar Pradesh, the state the title names, is `--chart-emph` on both.

**Craft families (categorical).** Eight hues in a fixed order, validated for protanopia and deuteranopia; painting, instruments and the rest fold into More crafts. Bars, stacks and legends may use all eight. Maps, scatter plots and small multiples carry at most three families at once; fold the rest into More crafts or facet. Every family mark carries a 1px ink-1 outline (bars, swatches) or sits in an ink-ringed marker whose disc takes the family colour, so no family relies on its own contrast on any surface.

| Order | Family | Token | Light | Dark | HC light | HC dark |
|---|---|---|---|---|---|---|
| 1 | Textiles | `--fam-textiles` | `#B3487E` | `#CE6196` | `#9F366C` | `#E47FAD` |
| 2 | Metal | `--fam-metal` | `#A1942F` | `#989018` | `#8F8214` | `#B0A941` |
| 3 | Wood | `--fam-wood` | `#664610` | `#805B2C` | `#473418` | `#9C703A` |
| 4 | Paper | `--fam-paper` | `#569CD4` | `#5399D1` | `#3786C3` | `#69AFE8` |
| 5 | Clay | `--fam-clay` | `#E75E70` | `#D75063` | `#C94358` | `#ED6576` |
| 6 | Stone | `--fam-stone` | `#00A0B4` | `#0092A4` | `#00839A` | `#25AEC5` |
| 7 | Leather | `--fam-leather` | `#69344A` | `#894667` | `#4A1F32` | `#A66082` |
| 8 | Natural fibre and grass | `--fam-fibre` | `#529E41` | `#55A144` | `#408C2D` | `#6EBB5D` |
| – | More crafts | `--fam-other` | `#8A8F88` | `#7E8496` | `#5E645C` | `#A9B0C0` |

Validation (OKLab delta E x100, protan and deutan simulated with Machado 2009 at severity 1.0, adjacent pairs. Target 8, floor 6; normal vision floor 15. Every family hue sits 10 or more from the reserved colours.) light: worst adjacent CVD ΔE 12.2, normal ΔE 24.4, nearest reserved ΔE 11.6; dark: worst adjacent CVD ΔE 12.0, normal ΔE 16.1, nearest reserved ΔE 13.9; hcLight: worst adjacent CVD ΔE 12.0, normal ΔE 24.3, nearest reserved ΔE 11.0; hcDark: worst adjacent CVD ΔE 12.0, normal ΔE 16.0, nearest reserved ΔE 13.5.

**Chart neutrals.**

| Token | Class | Light | Dark | HC light | HC dark | Use |
|---|---|---|---|---|---|---|
| `--chart-axis-text` | text | `#59534E` 6.92:1 | `#A5A198` 7.27:1 | `#2E2925` 14.38:1 | `#D9D6CE` 14.46:1 | Axis tick labels and units (UI 12, tabular lining). |
| `--chart-axis-line` | graphic | `#1C1815` 16.1:1 | `#ECEAE3` 15.55:1 | `#000000` 21.0:1 | `#FFFFFF` 21.0:1 | Baseline and the zero line. |
| `--chart-grid` | decorative | `#DDE0D9` 1.22:1 | `#232A39` 1.3:1 | `#B6BBB3` 1.95:1 | `#4A5266` 2.69:1 | Gridlines, 1px, behind the data. Never the only way to read a value. |
| `--chart-series` | graphic | `#5E6670` 5.31:1 | `#97A0B2` 7.12:1 | `#3E454E` 9.69:1 | `#C2C9D6` 12.62:1 | The default series colour: one neutral series when the variable has no series token of its own. |
| `--chart-emph` | graphic | `#1C1815` 16.1:1 | `#ECEAE3` 15.55:1 | `#000000` 21.0:1 | `#FFFFFF` 21.0:1 | The one mark the title names (the record year, the flagship craft). Nothing else. |
| `--chart-reference` | graphic | `#3A3430` 11.19:1 | `#CBC8C0` 11.2:1 | `#1C1815` 17.63:1 | `#F1EFE9` 18.26:1 | Mean or threshold lines, dashed 3 4. |
| `--chart-trend` | graphic | `#1C1815` 16.1:1 | `#ECEAE3` 15.55:1 | `#000000` 21.0:1 | `#FFFFFF` 21.0:1 | Fitted trend lines, 2.5px, with a 6px ground halo under them. |
| `--chart-band` | decorative | `#59534E` 6.92:1 | `#A5A198` 7.27:1 | `#2E2925` 14.38:1 | `#D9D6CE` 14.46:1 | Uncertainty bands and whiskers. Use at 18 per cent over the series. |
| `--chart-annotation` | text | `#3A3430` 11.19:1 | `#CBC8C0` 11.2:1 | `#1C1815` 17.63:1 | `#F1EFE9` 18.26:1 | Direct labels and annotation text. |
| `--chart-differ` | graphic | `#9E2E27` 6.67:1 | `#EF8E80` 7.89:1 | `#7A1D18` 10.41:1 | `#FFAFA3` 11.91:1 | A value the sources disagree on: the madder 135 degree hatch over the span between the two readings. |

**Chart grammar.**
- Charts title their finding ("Rain over Kachchh has risen about 71 mm a decade since 1981"); diagrams and maps take a descriptive title ("Blue", "Kachchh and Barmer"). The dek gives the method and the test in words; the source line sits under the figure.
- Axes in UI 12 with lining tabular figures in `--chart-axis-text`; gridlines in `--chart-grid`; the baseline in ink. Direct labels at line ends for one or two series, a legend for three or more. One y-axis per chart. Uncertainty as a band or whisker, never a lone number.
- A disagreement between sources is the madder 135° hatch across the span between the two readings.
- **SVG text never shrinks.** Figure SVGs carry `data-fit`; a ResizeObserver sets `--k` to viewBox width over rendered width, and every label is `calc(var(--text-caption) * var(--k))`, so labels render at the token size (and grow with Larger text) at any width. Labels that would crowd a small drawing are dropped at that width, never shrunk.
- **Keyboard.** One tab stop per figure. Arrow keys move between marks (roving tabindex), Home and End jump to the ends, the tooltip follows focus and Escape closes it; the focused mark takes a 2px ink-1 outline over a 2px ground halo. Every chart also has its table behind "All N values", which is the full keyboard and screen-reader path. Maps make districts reachable through their ranked list or table, not by tabbing through hundreds of shapes.

**Hatch grammar.** Five patterns, one meaning each; no two meanings share a pattern, and every legend explains the hatches it shows.

| Meaning | Pattern | Angle | Spacing | Mark | Colour on ground | Edge |
|---|---|---|---|---|---|---|
| Salt flat (the Rann) | stipple | – | 4px | dots, radius 0.55px, jittered by 0.8px | map-salt-hatch on map-salt | 0.75px dotted map-salt-hatch, 1 2 |
| The place a page is about | lines | 45 | 5px | stroke 1.4px | terracotta on transparent | 1.25px solid terracotta |
| Sources differ: the span between two readings | lines | 135 | 4px | stroke 1.4px | madder on transparent | 1px solid madder |
| No reading in the dataset | cross-hatch | 45 and 135 | 6px | stroke 0.8px | rule-strong on map-land | none |
| Earth in a section drawing (Figs. 2 and 7, the vat in the answer) | strata | 0 | 8px | horizontal dashes 6 4, stroke 0.8px | ink-3 at 35 per cent on sunk | 1.2px solid ink-1 on the surface line |

### 2.8 Maps

Paper cartography with three distinct fills: land, water (10 or more delta E from land in every theme) and salt flat (brighter than land, always stippled, with a dotted edge and an italic label). Neighbouring land comes from Natural Earth and is drawn under the India outline, which follows the Survey of India depiction and carries its one-line caption.

| Token | Class | Light | Dark | HC light | HC dark | Use |
|---|---|---|---|---|---|---|
| `--map-land` | surface | `#E4E7DF` | `#262C3A` | `#E3E5DE` | `#1E2433` | Indian land. |
| `--map-land-foreign` | surface | `#EEEFEA` | `#181D29` | `#F4F5F1` | `#10141D` | Neighbouring land, quieter than India. Natural Earth land under the Survey of India outline. |
| `--map-water` | surface | `#B4C8D0` ΔE 10.7 from land | `#0A141D` ΔE 10.8 from land | `#A7BFC9` ΔE 13.3 from land | `#03090F` ΔE 12.8 from land | Sea, lakes and reservoirs. Cool grey, 10 or more delta E from land in every theme, never indigo, never a ramp step. |
| `--map-coast` | graphic | `#646A62` 4.44:1 on land, 3.2:1 on water | `#8790A3` 4.35:1 on land, 5.79:1 on water | `#3D433C` 8.0:1 on land, 5.29:1 on water | `#B4BCCC` 8.12:1 on land, 10.48:1 on water | Coastline and the outer edge of land, 0.75px. 3:1 or better against land and water. |
| `--map-water-label` | text | `#2F4652` 5.72:1 on water | `#93ACB9` 7.82:1 on water | `#1C3240` 6.92:1 on water | `#C2D6E0` 13.32:1 on water | Italic labels on water, 4.5:1 or better on water. |
| `--map-river` | graphic | `#566F7C` 4.24:1 on land | `#7896A7` 4.47:1 on land | `#3E5A68` 5.76:1 on land | `#9CBDCD` 7.8:1 on land | Rivers, 0.75 to 1.25px by order. Slate, never indigo; 3:1 or better on land. |
| `--map-salt` | surface | `#FBFAF6` ΔE 6.2 from land, ΔE 16.7 from water | `#4A4740` ΔE 11.2 from land, ΔE 21.5 from water | `#FFFFFF` ΔE 8.2 from land, ΔE 21.2 from water | `#4F4D47` ΔE 16.3 from land, ΔE 28.7 from water | Salt flat (the Great and Little Rann). Land, not water: brighter than land and always stippled. |
| `--map-salt-hatch` | graphic | `#7D827B` 3.76:1 on salt | `#B1B6BF` 4.55:1 on salt | `#5E645C` 6.08:1 on salt | `#D2D7E0` 5.85:1 on salt | The stipple and dotted edge that mark a salt flat, 3:1 or better on the salt. |
| `--map-border-intl` | graphic | `#3A3430` 9.8:1 on land | `#CBC8C0` 8.35:1 on land | `#1C1815` 13.88:1 on land | `#F1EFE9` 13.47:1 on land | India external boundary as depicted by Survey of India, 1px. |
| `--map-border-state` | graphic | `#747A72` 3.52:1 on land | `#8A93A6` 4.53:1 on land | `#4E544C` 6.13:1 on land | `#A9B2C4` 7.27:1 on land | State and union-territory lines, 0.75px, 3:1 or better on land. |
| `--map-border-district` | decorative | `#B9BEB5` 1.51:1 on land | `#3E4558` 1.46:1 on land | `#8A9088` 2.57:1 on land | `#6E778B` 3.45:1 on land | District lines, 0.5px, only when zoomed in; never the only boundary of a selection. |
| `--map-label` | text | `#1C1815` (ink-1) | `#ECEAE3` (ink-1) | `#000000` (ink-1) | `#FFFFFF` (ink-1) | Place labels, UI 12 to 14, with the halo. |
| `--map-label-minor` | text | `#59534E` (ink-3) | `#A5A198` (ink-3) | `#2E2925` (ink-3) | `#D9D6CE` (ink-3) | Minor place labels. |
| `--map-label-halo` | surface | `#F4F5F1` (ground) | `#0E121C` (ground) | `#FFFFFF` (ground) | `#000000` (ground) | 3px halo behind labels (paint-order: stroke). |
| `--map-selection` | graphic | `#1C1815` (ink-1) | `#ECEAE3` (ink-1) | `#000000` (ink-1) | `#FFFFFF` (ink-1) | Selected district or marker: 2px outline over a 4px halo. Outside every ramp. |
| `--map-selection-halo` | surface | `#F4F5F1` (ground) | `#0E121C` (ground) | `#FFFFFF` (ground) | `#000000` (ground) | Halo under the selection outline. |
| `--map-hover` | graphic | `#3A3430` (ink-2) | `#CBC8C0` (ink-2) | `#1C1815` (ink-2) | `#F1EFE9` (ink-2) | Hovered district: 1.25px outline. |
| `--map-marker` | surface | `#FBFBF9` (raised) | `#161B28` (raised) | `#FFFFFF` (raised) | `#0E121C` (raised) | Point markers: a paper disc. A family marker fills the disc with its family colour; the ring stays ink. |
| `--map-marker-ring` | graphic | `#1C1815` (ink-1) 14.1:1 on land | `#ECEAE3` (ink-1) 11.6:1 on land | `#000000` (ink-1) 16.53:1 on land | `#FFFFFF` (ink-1) 15.49:1 on land | Point marker ring, 1.5px. It carries the 3:1 edge, so any fill reads on any land. |
| `--map-place` | large-text | `#B05A36` (terracotta) | `#E0916C` (terracotta) | `#7D3519` (terracotta) | `#F5AE8C` (terracotta) | The place a page is about: terracotta outline and the 45 degree hatch, never a solid fill. |
| `--map-nodata` | graphic | `#767C74` (rule-strong) | `#7A849A` (rule-strong) | `#3D433C` (rule-strong) | `#C4CBD8` (rule-strong) | Cross-hatch for a district with no reading in the dataset. |
| `--map-hillshade-opacity` | decorative | .06 | .09 | 0 | 0 | Relief shading: ink-1 at 6 per cent multiplied over land (9 per cent in dark). Never terracotta, which means place. Off in high contrast. |

- **The Rann.** The Great and Little Rann of Kachchh are salt flat, drawn from the Natural Earth playa polygons in `--map-salt` with the stipple and dotted edge, labelled in italic "Great Rann of Kachchh" and "Little Rann" (or "Great Rann" at India scale). Never the water fill; a seasonal flooding layer may tint them only when that layer is named.
- **Place.** The district a page is about is a terracotta outline with the 45° hatch, never a solid fill. Another district the text discusses (Barmer in Fig. 9) takes the selection style: an ink outline over a ground halo.
- **Markers.** Paper discs with a 1.5px ink ring; a family marker fills its disc with the family colour. Proportional circles use `--series-count` at 85 per cent with a 1px ground edge, area to scale.
- **Legends** sit under the map on a phone; from 768px they sit in the map frame over open sea (the Arabian Sea on an India map, the Gulf of Kachchh on a regional one), never over land or islands, or beside the map in its text column as on the landing. The legend explains circles, the place hatch, the salt stipple and water.
- **Labels never collide.** A label that would overlap another label, a marker or a coast moves along its leader or drops to the ranked list beside the map; minor labels drop first below 768px. Water labels are italic in `--map-water-label`.
- Relief shading is ink-1 at 6 per cent multiplied over land (9 per cent in dark), never terracotta; off in high contrast. No scale bar unless the map is drawn to a stated projection and scale; locators carry none. No third-party tiles.

### 2.9 Type

Families, all OFL and self-hosted through `next/font/local`:

- `--font-headline`: Newsreader, opsz 6–72, the system uses weights 300 to 600 (the axis runs 200 to 800; load only 300 to 600) with italics. Hero, title, h1, h2, numerals, stats. A separate token from `font-display`, which stays on the UI face.
- `--font-reading` (also `font-serif`): Newsreader at text optical sizes. Prose, ledes, quotes, captions, h3, names on plates. Old-style proportional figures. Its stack names each Indian script's Noto Serif after Newsreader, so a mixed line falls back by glyph and each face downloads only when its unicode-range is used.
- `--font-ui` (also `font-sans`, and `font-display` during migration): IBM Plex Sans 400, 500, 600, italic 400. Everything you operate or scan, and h4.
- `--font-code`: IBM Plex Mono 400 and 500. The six-box sign-in code, API keys, PubChem CIDs, slugs. Lining tabular figures; never old-style serif figures.

Optical size follows the size everywhere (`font-optical-sizing: auto`): Newsreader gives opsz 72 to every size from 72px up and follows the size below, so a 28px h2 on a phone never gets display hairlines.

Every size is a rem token. Reading sizes are fluid from 360 to 1440px and stop there; display sizes (h2, h1, title, hero, stat) keep growing to 1920px, so a projector gets a 134px hero and a 108px title. The fluid part of every clamp is multiplied by `--text-zoom`, so Larger text is exactly 1.125 times the standard size at every width (the table's columns are computed from the clamps, not estimated). On a phone the hero (54px) outranks a craft title (44px).

| Token | Family | 360 | 834 | 1440 | 1920 | Larger text (360 / 1440 / 1920) | Line height | Tracking | Weight | Use |
|---|---|---|---|---|---|---|---|---|---|---|
| `--text-caption` | ui | 12 | 12 | 12 | 12 | 13.5 / 13.5 / 13.5 | 1.333 | 0em | 400 | Credits, source lines, axis labels, map labels, kickers, tags. The floor for any text. |
| `--text-label` | ui | 13 | 13 | 13 | 13 | 14.6 / 14.6 / 14.6 | 1.385 | 0em | 500 | Field labels, chip text, provenance lines, fact labels, margin notes. |
| `--text-ui` | ui | 14 | 14 | 14 | 14 | 15.8 / 15.8 / 15.8 | 1.429 | 0em | 500 | Buttons, nav, tabs, list meta, popover body. |
| `--text-ui-lg` | ui | 16 | 16 | 16 | 16 | 18 / 18 / 18 | 1.5 | 0em | 400 | Inputs (16px stops iOS focus zoom), toasts, dialog body. |
| `--text-h4` | ui | 16 | 16 | 16 | 16 | 18 / 18 / 18 | 1.35 | 0em | 600 | Small figure titles, card names on tool pages, demo heads. The interface voice at weight 600, so it never matches body text. |
| `--text-figcaption` | reading | 15 | 15.4 | 16 | 16 | 16.9 / 18 / 18 | 1.45 | 0em | 400 | Picture captions in italic, what to look at. |
| `--text-quote` | reading | 16 | 16.4 | 17 | 17 | 18 / 19.1 / 19.1 | 1.48 | 0em | 400 | Verbatim quotes in popovers and quote cards, italic. |
| `--text-body-sm` | reading | 16 | 16.4 | 17 | 17 | 18 / 19.1 / 19.1 | 1.62 | 0em | 400 | Dense prose: stage text, fact values, figure keys, result sentences. |
| `--text-body` | reading | 17 | 17.9 | 19 | 19 | 19.1 / 21.4 / 21.4 | 1.63 | 0em | 400 | Monograph and answer prose. Measure 66ch. |
| `--text-lede` | reading | 20 | 21.3 | 23 | 23 | 22.5 / 25.9 / 25.9 | 1.45 | 0em | 400 | The opening paragraph of a monograph or answer; standfirsts. |
| `--text-h3` | reading | 21 | 23.2 | 26 | 26 | 23.6 / 29.2 / 29.2 | 1.2 | -0.01em | 500 | Sub-sections, family shelf names, figure titles, stage names. |
| `--text-h2` | headline | 28 | 35.3 | 44.6 | 52 | 31.5 / 50.2 / 58.5 | 1.08 | -0.016em | 480 | Chapter titles. |
| `--text-h1` | headline | 36 | 49.4 | 66.5 | 80 | 40.5 / 74.8 / 90 | 1.03 | -0.022em | 470 | Page titles that are sentences: questions, the atlas title, a long craft name stepped down from title. |
| `--text-title` | headline | 44 | 63.4 | 88.3 | 108 | 49.5 / 99.3 / 121.5 | 1.0 | -0.024em | 480 | The craft name in a masthead, set at equal size with its own-script name when one is sourced. |
| `--text-hero` | headline | 54 | 78.3 | 109.4 | 134 | 60.8 / 123.1 / 150.8 | 0.98 | -0.026em | 460 | The landing headline over the photograph. One per site. |
| `--text-numeral` | headline | – | – | 80 | 88 | – / 90 / 99 | 0.86 | -0.03em | 300 | Light chapter numerals in the left rail, from 1200px only. Below 1200px the chapter number is the chapter-no kicker ("Chapter 3" with its 40px rule). |
| `--text-stat` | headline | 36 | 44.5 | 55.4 | 64 | 40.5 / 62.3 / 72 | 1.0 | -0.02em | 480 | A headline number with its unit in label beneath. |

- **h4** is the interface voice (IBM Plex Sans 600 at 16px), so it never matches body text by weight alone.
- **Numerals** appear only from 1200px, in the left rail. Below 1200px the chapter number is the chapter-no kicker ("Chapter 3" with its 40px rule).
- **Captions** have their own token, `--text-figcaption` (Newsreader italic, 15 to 16px). Margin notes use `--text-label`.
- **The floor.** Nothing renders below 12px except citation numerals, which sit at `max(0.6875rem, 0.62em)`. Subscripts are `max(0.7em, 0.75rem)`, and a formula is set at 17px or more; smaller labels spell the species out.

**Figures.** Reading text: `oldstyle-nums proportional-nums`. Headlines and UI: lining proportional. Tables, charts, axes, counts, dates and codes: `lining-nums tabular-nums`. Chemistry: true subscripts in the face of the surrounding text.

**Equations.** A side of an equation never breaks inside itself. The line may break only before the arrow, with the products starting a new line arrow first; if a side still does not fit, the whole equation scales down with container units (from 24px to 17px), never wraps a formula.

**Case and italics.** Only kickers and the GI tag are uppercase (UI 12, 600, tracking 0.08em, `font-feature-settings: "case"`); never letter-space or uppercase an Indic or Arabic-script string. Field labels are sentence case. Italic marks transliterated local terms (saaj, kut, gach), botanical names (in ink-2), verbatim quotes and photo captions. English names are never italic.

**Wordmark.** KalaVigyan in Newsreader 600 and कलाविज्ञान in Noto Serif Devanagari 500 at ×1.08, separated by a 1px rule, shipped as SVG outlines so an English page loads no Devanagari font. The mark is the eight-pointed ajrakh star cut as a block: deep notches (inner radius 0.56 of the outer) and long points, so it reads as a star, not a cog, at 16 to 24px; a hexagon in negative space; one colour; the four-dye version only at 64px and up.

### 2.10 Scripts and languages

| `data-script` | Script | Languages (BCP 47) | Reading face | UI face | Size factor | Leading | Display leading | Direction |
|---|---|---|---|---|---|---|---|---|
| `Deva` | Devanagari | hi, mr, ne, sa, kok, mai, doi, bho, brx, ks-Deva, sd-Deva | Noto Serif Devanagari | Noto Sans Devanagari | ×1.08 | 1.75 | 1.25 | ltr |
| `Beng` | Bengali-Assamese | bn, as, mni-Beng | Noto Serif Bengali | Noto Sans Bengali | ×1.08 | 1.75 | 1.25 | ltr |
| `Gujr` | Gujarati | gu | Noto Serif Gujarati | Noto Sans Gujarati | ×1.08 | 1.75 | 1.25 | ltr |
| `Guru` | Gurmukhi | pa | Noto Serif Gurmukhi | Noto Sans Gurmukhi | ×1.08 | 1.75 | 1.25 | ltr |
| `Orya` | Odia | or | Noto Serif Oriya | Noto Sans Oriya | ×1.08 | 1.75 | 1.3 | ltr |
| `Taml` | Tamil | ta | Noto Serif Tamil | Noto Sans Tamil | ×1.0 | 1.8 | 1.3 | ltr |
| `Mlym` | Malayalam | ml | Noto Serif Malayalam | Noto Sans Malayalam | ×1.0 | 1.8 | 1.35 | ltr |
| `Telu` | Telugu | te | Noto Serif Telugu | Noto Sans Telugu | ×1.0 | 1.8 | 1.35 | ltr |
| `Knda` | Kannada | kn | Noto Serif Kannada | Noto Sans Kannada | ×1.0 | 1.8 | 1.35 | ltr |
| `Aran` | Urdu and Kashmiri, Nastaliq | ur, ks-Arab | Noto Nastaliq Urdu | Noto Sans Arabic | ×1.0 | 2.2 | 1.7 | rtl · Nastaliq needs 2.2 leading in prose and 1.7 in display, and never sits inside a 44px chip or button; controls use Noto Sans Arabic. |
| `Arab` | Sindhi, Naskh | sd-Arab | Noto Naskh Arabic | Noto Sans Arabic | ×1.0 | 1.9 | 1.45 | rtl · Sindhi is set in Naskh, its print convention, not Nastaliq. |
| `Mtei` | Meetei Mayek | mni-Mtei | Noto Sans Meetei Mayek | Noto Sans Meetei Mayek | ×1.05 | 1.7 | 1.25 | ltr · No Noto Serif exists for this script; the sans serves reading and UI. |
| `Olck` | Ol Chiki | sat-Olck | Noto Sans Ol Chiki | Noto Sans Ol Chiki | ×1.0 | 1.7 | 1.25 | ltr · No Noto Serif exists for this script; the sans serves reading and UI. |

- **Select by script, not language.** Every non-Latin string carries `data-script` with its ISO 15924 code and a BCP 47 `lang`, with a script subtag where a language is written in two scripts (`ks-Arab`, `ks-Deva`, `sd-Arab`, `sd-Deva`, `mni-Mtei`, `mni-Beng`). The `[data-script]` selector sets the face and `--script-scale`, `--script-leading` and `--script-display-leading`; UI text in a script adds `.ui` for the Noto Sans face. The wikidata pipeline already fetches mni, sat, kok, mai, doi, bho and brx labels; they route through this table.
- **Fallbacks.** No Noto Serif exists for Meetei Mayek or Ol Chiki; Noto Sans Meetei Mayek and Noto Sans Ol Chiki serve reading and UI. Urdu and Kashmiri in Arabic script are Nastaliq; Sindhi is Naskh, its print convention.
- **Equal standing.** Two names at equal standing share one size: the Latin name at the size token, the own-script name at that token times `--script-scale`, on its own display leading, stacked with a hairline in a label or masthead. A masthead takes the title size when the Latin name has 18 characters or fewer, else h1; at most three lines a name; the label is at most 560px or 46 per cent of the masthead. If a word in either name would still be wider than the label, both names shrink together with container units (title to 17cqi, h1 to 12cqi of the label), never one alone and never by breaking a word. Indian names never break inside a word (`word-break: keep-all; overflow-wrap: normal`).
- **Plates are labels, not titles.** A collection plate and the names wall show one display name (the own-script name when sourced, else English) and the strip under it always carries the English catalogue line in the same place. Equal standing applies to titles (masthead, label, page title, wordmark), not to these labels.
- **Which names may appear.** A name in its own script appears only where a source states it and it names this craft: a dossier claim, or a Wikidata label in the language of the craft's home state whose item is the craft itself. When the craft's name carries a place (Kutch, Lucknow, Miraj) and the item is the technique, object or instrument in general, the label is held back. Held back today: Kutch Bandhani (બાંધણી, bandhani in general), Lucknow Chikan Craft (चिकनकारी, chikan work in general), Lucknow Zardozi, Kaudi Quilt Craft (quilt), Kundan Meenakari (kundan only), Kathputlis of Rajasthan (puppet art), Maddalam of Palakkad, Miraj Tanpura, Majuli Mask of Assam (the mask art of Assam), Assam Bihu Dhol and Assam Majuli Manuscript Painting (a history of the art). Kutch Ajrakh has no sourced Gujarati name, so it is set in English alone.
- **Data contract.** `nativeName: { text, lang, script, sourceId, sourceKind: "dossier" | "wikidata", reviewed: boolean }`. Render nothing without `sourceId` and `reviewed`. The Wikidata CC0 credit appears once under the collection wall and names wall, and in the provenance line of the craft's own specimen label ("Kannada name: Wikidata, CC0").
- **Loading.** Each face is self-hosted with its `unicode-range` and `preload: false`. A page with prose in a script loads that script's reading face, subset to the page. The atlas wall and names view load one build-time subset per script holding only the glyphs of the catalogue's sourced names: 24 KB or less per script, 160 KB or less for all scripts together (the boards use Google's `text=` subsetting to the same effect). The wordmark is SVG outlines.
- **Bidirectional text.** A native name inside an English line is wrapped in `<bdi>` (or `unicode-bidi: isolate`). Every Arabic-script string carries `dir="rtl"`.

### 2.11 Right to left

- **Scope.** Mirroring follows the content language. An Urdu answer inside the English app mirrors the answer region (provenance rail, prose, margin notes, figure order) with `dir="rtl"` on its article; the appbar and chapter rail stay in the interface language's direction. When the interface language itself is Urdu, the whole page mirrors.
- **Logical properties only.** Components use `margin-inline-*`, `padding-inline-*`, `inset-inline-*`, `border-inline-*`, `text-align: start/end` and Tailwind's `ms/me/ps/pe/start/end/border-s/border-e/text-start/text-end`. A lint rule rejects `left/right` utilities and physical properties in components (122 uses in 51 files today, section 6).
- **Digits.** Urdu answers use Western Arabic digits (0–9) for citation numerals, figure numbers, dates and data, so they match the sources and the figures; prose numbers follow the same rule.
- **Citations** follow the sentence end, which in Urdu is on the left; the popover keeps the source's own language and direction, because quotes are verbatim.
- **Type.** Nastaliq prose at leading 2.2 and display at 1.7; never inside a 44px chip or button (controls use Noto Sans Arabic); no letter-spacing, no uppercase.
- The master board's sixth screen is the reference at 390 and 1440px.

### 2.12 Space, controls, radii, borders, focus, shadows

- **Spacing:** `--space-1` to `--space-10` = 4, 8, 12, 16, 24, 32, 48, 64, 96, 128px (rem). `--space-section` is 64px on a phone to 96px on a desktop. Paragraphs are 1.05em apart.
- **Controls** are rem tokens, so they grow with Larger text: `--control-h` 2.875rem (46px), `--control-h-touch` 3rem (48px), `--control-h-sm` 2.5rem (40px), `--control-h-sm-touch` 2.75rem (44px), `--input-h` 3rem (48px), `--chip-h` 2.125rem (34px), `--chip-h-touch` 2.75rem (44px), `--search-h` 3.75rem (60px), `--segment-h` 2.5rem (40px), `--segment-h-touch` 2.75rem (44px), `--code-w` 2.875rem (46px), `--code-h` 3.5rem (56px), `--code-w-lg` 3.25rem (52px), `--code-h-lg` 4rem (64px), `--toggle-w` 3rem (48px), `--toggle-h` 1.75rem (28px), `--target` 2.75rem (44px), `--appbar-h` 4rem (64px), `--rail-h` 2.875rem (46px).
- **Radii:** plate 2px (photographs, plates, swatches, specimen labels, figures); control 4px (buttons, inputs, code boxes, segmented choices, search); card 6px (popovers, quote cards, toasts, dialogs, menus); sheet 14px (top corners of the phone sheet only); pill (chips, toggle tracks, rows of three or more buttons from 640px).
- **Borders:** hair `1px rule` separates; control `1px rule-strong` bounds what you press; ink `1px ink-1` tops sections and figures; emphasis `2px ink-1` for selection and high contrast; current `2px ink-1` on the leading edge for the current step; differ `2px madder` on the inline start of a disagreement; hypothesis `2px dashed ink-2`; specimen `1px ink-2` outside a 2px raised mat.
- **Focus.** A 2px indigo outline at 3px offset on every focusable element (3px wide in high contrast); never removed, never only a colour change. Inputs, select triggers and the six code boxes keep a 2px indigo outline at 2px offset as well as the indigo edge; no halo is relied on. The keyboard-highlighted option in a listbox has a 2px indigo bar on its inline start plus the sunk fill. On a photograph, focus is a 2px photo-ink-1 outline at 2px offset over a 2px rgba(8,10,16,.8) inner ring, so it reads on light and dark parts of the picture. Segments, tabs and stage buttons inset their outline by 3 to 4px so it stays visible inside the group.
- **Shadows:** three. `--shadow-pop` for popovers, menus, toasts and dialogs; `--shadow-label` for a specimen label lying on a photograph only (a label on paper casts none); `--shadow-sheet` for the phone sheet. Nothing else casts a shadow. High contrast replaces each with a 2px ink outline (tokens.json lists hcLight and hcDark values), and since raised equals ground there, floating surfaces rely on that outline.

### 2.13 Motion

Durations: press 120ms, state 200ms, panel 320ms, dip 600ms, hold 500ms, oxidise 1500ms, vat 2600ms (dip + hold + oxidise), vat-delay 800ms. Easings: out `cubic-bezier(0.16, 1, 0.3, 1)` for entrances; inOut `cubic-bezier(0.65, 0, 0.35, 1)` for chemical changes; linear for scroll-linked; the overshoot `cubic-bezier(0.34, 1.56, 0.64, 1)` only on a switch thumb.

| Motion | What it does | Duration, easing | Trigger | Reduced-motion end state |
|---|---|---|---|---|
| dip | A colour band fills from the bottom with clip-path, as cloth goes into a bath. | dip (600ms), inOut | Choosing a stage on the living cloth. | The band is shown filled; no movement. |
| oxidise | Leuco green turns indigo from the top edge down, the colour of the cloth in air, with a soft ragged edge. | oxidise (1500ms), inOut | Stage 8 opening; the last phase of the vat. | The blue end state, with the green state shown beside it as a still frame. |
| press | A citation numeral or the Saved mark settles from scale 1.02 to 1. | press (120ms), out | Pressing a numeral, saving. | No scale; the state changes at once. |
| vat | The single orchestrated animation: dip (600ms), hold lifted and green (500ms), oxidise from the top down (1500ms), 2600ms in all. On the landing it starts vat-delay (800ms) after the photograph is shown and tints only the authored dyed-region mask of the photograph: the green rises with a soft meniscus edge, and the blue returns from the top with a ragged edge. Resist whites, kut black and madder never change. In the answer's VatFigure it plays on the drawn cloth from Dip again. | vat (2600ms), inOut | Landing: first view, once per visit (sessionStorage key kv-vat-played), and the Play again control in the specimen label. VatFigure: Dip again. | The finished blue cloth and the three captioned phases as still frames; Play again and Dip again step the state and announce it without movement. |

- **The vat moment, on the landing.** The landing photograph is cloth edge to edge (no skin, no background) and ships with an authored dyed-region mask (`img/hero-dyed-mask.png`, alpha, same aspect as the photograph): white where indigo took, clear over the lime-resist whites, the kut blacks and any madder. The leuco-green layer (`--dye-leuco`, `mix-blend-mode: color`) is masked by the intersection of that mask and a moving gradient: in the vat, the green rises from the bottom with a 3 per cent meniscus edge (600ms); lifted, it holds (500ms); in the air, it withdraws from the top with a 12 per cent ragged edge (1500ms), so the blue returns from the top down. The gradient position is a registered custom property (`@property --vat`), so one CSS transition drives it. Resist whites, black and madder never change colour.
- **Steps and replay.** The specimen label's three steps are non-pressable progress (`aria-current="step"`, the ink rule); one quiet Play again text button replays the moment, so a professor can show it again in class, and an `aria-live` status names each phase. It plays by itself once per visit (`sessionStorage` key `kv-vat-played`, read and written in try/catch), 800ms after the photograph is in view; the photograph is never at opacity 0 and the tint layer is not on the LCP path (the 960 hero is preloaded with `fetchpriority="high"`).
- **Acceptance.** A screenshot of each phase (rest, in the vat, lifted, in the air) at 1440 and 390 shows only the dyed ground green, and the scrim check passes in each phase.
- **The VatFigure** (in the answer) plays the same choreography on the drawn cloth from Dip again, steps dips 1 to 4 into `--dip-1…4`, says each phase in its status line and, after the fourth dip, offers Start again. The monograph's Fig. 2 (Blue) is a static cutaway, not a player.
- **Reduced motion.** Both switches count: `prefers-reduced-motion` and `html[data-reduced-motion="true"]`, read synchronously before anything moves. Every end state is the default style; motion is added only under a variant that checks both switches, and under either switch `animation` and `transition` are `none`, so nothing snaps back to a start state. Controls that drive motion still work and announce their result.
- **Never:** Ken Burns drift on photographs, word-by-word or letter headline reveals, staggered rise-in of cards, parallax, scroll-linked decoration, a first paint at opacity 0 for the largest element, overshoot on anything but a switch thumb, two animation systems on one property. Framer Motion owns declarative motion; GSAP leaves the codebase; CSS keyframes are generated from these tokens, and one module owns each named motion.

### 2.14 Layers, breakpoints, grid

- **z-index:** base 0, raised 1, sticky 20 (chapter rail), appbar 30, popover 70, scrim 80, sheet 85, dialog 90, toast 110, skip-link 120.
- **Breakpoints** (px, so Larger text never shifts a layout), and no others: below 640 phone (citation sheet, sideways shelves); sm 640 (popover replaces the sheet, pill rows, two-up grids); md 768 (tablet column, appbar nav replaces Menu, map legend inside the frame); lg 1024 (masthead label overlaps the photograph, two-column heads, six-column shelves); rail 1200 (the spread); xl 1280 (64px margins); 2xl 1536. A guard rejects media queries at any other width. Design and test widths: 360 and 390 phone, 834 and 1194 tablet, 1440 desktop, 1920 projector.
- **Margins:** 16px below 640, 24 to 767, 40 to 1199, 48 to 1279, 64 from 1280, never less than the safe-area inset. Gutters 16, 20, 24px; 4 columns on a phone, 8 on a tablet, 12 on a desktop. Content up to 1280px; at 1920 content stays 1280 while photographs and figures may go full bleed.
- **Reading measure:** 66ch (about 640px at body size), never wider than 75ch.
- **The spread, from 1200px:** `160px minmax(0, 680px) 240px` with 40px column gaps, `justify-content: space-between`. At 1200 the content box is 1104px: rail 160, gap, main 624, gap, margin 240. Left rail: the light chapter numeral, dates, provenance. Right margin: numbered source titles, evidence labels, small plates.
- **Tablet (768 to 1199px):** a monograph is the single 66ch column centred, with the chapter rail on top; margin notes fold into the citation popover. There is no right rail on a tablet.
- **Margin notes** top-align with the first sentence in their chapter that cites them, push down on collision with 8px between notes, and never repeat within a chapter.

### 2.15 Pictures

- **Widths.** Wikimedia Commons thumbnails only at the standard widths **330, 500, 960, 1280 and 1920**. Pictures use plain `<img srcset sizes>` through `commonsThumb(fileUrl, width)`, which snaps any request to the next standard width; `next/image` is not used for Commons pictures, because its `deviceSizes` would request other widths. srcsets: hero 960/1280/1920; masthead 500/960/1280/1920; plate 330/500/960; margin 330/500. sizes: hero `100vw`; masthead `(min-width: 1280px) 1280px, 100vw`; lead plate `(min-width: 1024px) 33vw, 72vw`; plate `(min-width: 1024px) 16vw, (min-width: 640px) 25vw, 72vw`; margin `240px`. The acceptance spec asserts every Commons URL width.
- **Ratios.** Hero 21:9 desktop with an art-directed 4:5 phone crop; masthead 16:7.4 desktop and 4:3 tablet and phone; textile detail 4:5; process and people 3:2; swatches 1:1.
- **Focal boxes.** Each picture record carries a focal box per ratio (`{ratio: [x, y, w, h]}` in fractions of the original), drawn by the curator so faces and the object stay in frame. Crops come from the box (`object-view-box` on the boards), never a centre crop: the Kutch Ajrakh masthead's 4:3 crop holds the cloth, not the floor.
- **Derivatives.** Where a crop would upscale (a 4:5 phone crop from a 21:9 hero gives about 660 source pixels across), the crop is made once from the Commons original and cached in the media bucket with its credit, at the standard widths. Hero originals are cached the same way, so a 1440 screen at 2x is not upscaled from the 1920 thumbnail.
- **Captions.** Caption first, in `--text-figcaption` (Newsreader italic) ink-2, saying what to look at; then the credit in UI 12 ink-3 under a hairline: "Photo: Author, licence, via Wikimedia Commons". A cited caption carries its numerals. On a full-bleed photograph the credit sits in the specimen label.
- Every picture carries its credit and licence where it is shown, including OG images. A picture never repeats within a page. No stock, shopping, social or AI imagery: no price tags, sale tables or shop displays. A craft with no licensed photograph gets its typographic plate. No scale bar on a photograph unless a museum record states the object's size.
- A stand-in picture says what it shows (the Great Rann, not Ajrakhpur; a Jaipur block, not an ajrakh block), and a picture from elsewhere (the 1877 Allahabad indigo works) is never captioned as if it were the craft's place.
- **Flagship photography.** For flagship mastheads, pursue consent-gated field photography from IIT's documentation portal; the Commons pictures on the boards are the floor, not the goal.

---

## 3. Components

Names are the React components the build uses. Existing files in `frontend/components/ui` keep their behaviour and contracts (keyboard handling, ARIA, tests) and change only their classes. Heights are the control tokens of 2.12.

| Component | File | Props | States and rules |
|---|---|---|---|
| Button | `ui/button.tsx` | `variant: primary \| quiet \| danger \| text`, `size: md \| sm`, `busy`, `disabled` | Rest, hover, focus (2px indigo outline, offset 3px), pressed, busy (spinner plus a verb, "Sending", stacked over the resting label so the width never changes), disabled (sunk, ink-3). `--control-h`, `--control-h-touch`; sm `--control-h-sm`, `--control-h-sm-touch`. One primary per view, and none on a reading page (an answer's Save and Cite this answer are both quiet). Danger is a madder outline; a confirming destructive button is a madder fill with on-madder text. `outline`, `secondary`, `ghost` and `provider` map to quiet; `default` to primary. |
| ActionGroup | `ui/ActionGroup.tsx` | `align`, `fill`, `inline` | 1 centred; 2 on one line, equal width below 640px; 3+ stacked full width below 640px and pills from 640px; `data-danger` child last. Never hand-place a row. |
| TextLink | `ui/TextLink.tsx` | `href`, `standalone`, `as: a \| button` | Prose: indigo, 1px underline offset 3px, 2px on hover, visited stays indigo. Standalone ("All 97"): UI 14 500. A link when it navigates ("All 97", "Show all 33 states"); a button with `aria-expanded` when it expands in place ("Show all 11 stages", "Show all 23"); a button when it acts (Play again). Replaces `field-link`. |
| Field, Input, Textarea | `FormControls.tsx`, `forms/*` | `label`, `hint`, `error`, `required`, `disabled` | Label above in sentence case (UI 13 500 ink-2). `--input-h`, UI 16 so phones do not zoom, raised fill, rule-strong edge. Focus: indigo edge plus the 2px indigo outline at 2px offset. Error: 2px madder edge, message with icon in madder, `aria-invalid`, `aria-describedby`. Disabled: sunk, ink-3. Required is the word "required" in the hint. |
| SearchBox | `SearchInput.tsx`, atlas and header search | `value`, `onChange`, `placeholder`, `shortcut` | `--search-h`, ink edge, Newsreader lede-size input, 44px clear button "Clear the search". The `/` shortcut focuses it unless focus is already in an input, textarea, select or contenteditable. Results announce a short count in `role="status"`, never the result body. |
| OtpCodeInput | `ui/OtpCodeInput.tsx`, `TwoStepCodeEntry.tsx`, `TwoStepChallengeForm.tsx` | unchanged | Six boxes in `font-code` (IBM Plex Mono 500), lining tabular, `--code-w`×`--code-h` (`--code-w-lg`×`--code-h-lg` from 640px), flexing down at 360px with Larger text. Focus: the field ring. Error: 2px madder edges, message, the existing shake (none under reduced motion). Disabled: sunk. Replaces `font-display` on the boxes. |
| Toggle | `ui/Toggle.tsx` | unchanged | Track `--toggle-w`×`--toggle-h` pill. Off: sunk fill, rule-strong edge, ink-3 thumb. On: indigo track, on-indigo thumb. Busy: spinner thumb plus status text. Disabled: 55 per cent and a reason in the description. Mirrors in right-to-left. |
| SegmentedChoice | `ui/SegmentedChoice.tsx` | unchanged | Raised group, rule-strong edge, `--segment-h`. Selected segment indigo fill with on-indigo text. Two to four options; more becomes a select. |
| SearchableSelect, Dropdown, ComboBox, LanguagePicker | `ui/SearchableSelect.tsx`, `ui/Dropdown.tsx` | unchanged | Trigger like an Input with a chevron; open trigger takes the field ring. Panel: raised, card radius, pop shadow; a search field once there are more than eight options; group headers as kickers; keyboard highlight sunk with a 2px indigo inline-start bar; selected option indigo text on indigo-wash with a check; footer with the count ("13 languages · type to filter"). Each language is listed in its own script with the English name beside it. Empty result: "No language matches 'xyz'". |
| Chip | `ui/Chip.tsx` | `pressed`, `count` | `--chip-h` pill (`--chip-h-touch`), rule-strong edge, UI 13. Pressed: indigo-wash, indigo edge, indigo-hover text. Counts in tabular ink-3. Chips filter or suggest; never the only way to an action. |
| CitationCluster | `answer/CitationChip.tsx` becomes `Cite` | `claimIds`, `numbers` | One cluster per sentence, de-duplicated by source and sorted ("1,4,5"), glued to the last word with a no-break wrapper. Indigo UI numerals, no border, pill or icon. Hit area 24px wide (44px on touch) and kept inside its own line, so clusters never steal a tap from the line above; inline targets meet WCAG 2.5.8 by its inline exception. Accessible name "Sources 1 and 2" (or "Source 3"), titles in `aria-description`; `aria-haspopup="dialog"`, `aria-controls`, `aria-expanded`. Pressed: the press motion. Open: ink-1 and the sentence in turmeric-wash. |
| SourcePopover and SourceSheet | `ui/AnchoredPopover.tsx` plus the source dialog | `sources`, `quotes` | From 640px a non-modal dialog, 380px, raised, card radius, pop shadow; from 1200px it docks into the margin beside the sentence, still non-modal. Focus moves into it; Escape and Close return focus to the numeral. Below 640px a modal bottom sheet with scrim, grab bar and focus trap. Content: "N sources for this sentence", each source numbered with short title, byline and year, "From the Textiles family monograph" when borrowed, every verbatim quote in Newsreader italic, the locator, an A to D reliability mark (A filled, B half, C and D ring) with its words, "Open the source", and "Quotes are verbatim". |
| MarginNotes | `editorial/MarginNotes.tsx` | `sources`, `anchors` | From 1200px: numbered short titles with year in UI 13 ink-3 (numbers in ink-3, not indigo: the sentence's numeral opens the source). Each note top-aligns with the first sentence in its chapter that cites it, pushes down on collision with 8px gaps, never repeats in a chapter. Hidden below 1200px. |
| EvidenceMark and SourcesDiffer | `answer/EvidenceBadge.tsx` | `level: verified \| provisional \| inferred \| hypothesis`, `conflict` | The page states its norm once ("Drawn from 20 sources · A 9 · B 7 · C 4 · curated 17 Nov 2026"); a mark appears only where a sentence differs. Provisional: no inline mark, a ring-dot label in the margin and popover. Inferred: dotted turmeric-text underline plus "Inferred". Hypothesis: dashed ink-2 inline-start rule plus "Hypothesis". Sources differ: a `<details>` after the paragraph (never inside a `<p>`), madder summary with the double-rule glyph naming the disagreement, body with both readings quoted and cited, madder inline-start rule. Only for conflicts the dossier records. |
| ProvenanceStrip | new, `craft/Provenance.tsx` | `sources`, `counts`, `curatedAt`, `monograph` | "Drawn from N sources", the A/B/C/D reliability strip (`role="img"` with a spoken summary), the monograph link, the curation date. Stacked in the left rail from 1200px, inline above the title below. Never pipeline counts. |
| SpecimenLabel | `editorial/SpecimenLabel.tsx` | `variant: landing \| masthead \| chapter`, `kicker`, `name`, `nativeName`, `sentence`, `gi`, `place`, `credit`, `provenance`, `steps`, `onPhoto`, `headingLevel` | On every craft. Raised card with the double ink frame (1px ink, 5px raised, 1px ink). Kicker row (series, family · sub-family; stacked below 640px). Name at title size in a masthead (h1 above 18 characters, rules in 2.10), h3 size on the landing, h2 size as a chapter label. Native name at equal standing only when sourced. One cited sentence, the GI line with its citation and seal, the place, provenance, and the photo credit when it lies on a photograph. The landing variant carries the vat `steps` and Play again. Heading level: h1 in a masthead, a paragraph on the landing (the hero headline is the h1), h2 as a chapter label. No catalogue number. Label shadow only `onPhoto`. |
| Plate | `editorial/Plate.tsx` (it replaced `answer/MediaFigure.tsx`) | `src`, `widths`, `ratio`, `focal`, `caption`, `credit`, `alt` | Photograph with 2px radius, crop from its focal box, caption first, credit after. Opens in the Lightbox. |
| Lightbox | `ui/Lightbox.tsx` | `picture` | Modal dialog on a 92 per cent dark scrim; the largest standard width; pinch and wheel zoom; caption and credit under the picture; Escape and Close return focus to the plate. |
| Figure | `ui/Figure.tsx` | `number`, `title`, `dek`, `source`, `table`, `kind: chart \| diagram \| map` | Kicker "Fig. 3" (tables: "Table 1"), numbered in order through a page; charts title their finding, diagrams and maps describe; the source line under it; the table behind "All N values"; one tab stop, arrow keys between marks. Text references it as (Fig. 3). |
| CollectionPlate | `crafts/CollectionPlate.tsx` | `craft` | Every craft, curated or not. Material ground and seeded texture; kicker of the sub-family (none for catch-all sub-families such as "More textiles"); the display name (own script when sourced and reviewed, container-sized, keep-all; else the English name in Newsreader 480), knocked out of the texture; a raised strip with the English name always in the same place, then the state, then Monograph and GI tags on their own line (GI with visually hidden "registered"). Link to the craft. |
| PhotoCard | `crafts/PhotoCard.tsx` | `craft`, `picture` | For crafts with a licensed photograph: photo, kicker, name, state · N sources, tags, credit. Leads a shelf. |
| CollectionShelf | `crafts/CollectionShelf.tsx` | `family`, `count`, `subfamilies`, `lead`, `plates` | Header: plate-ground swatch, family name, count, sub-family counts, "All N" link. Below 640px a sideways row with scroll-snap (plates at 72 per cent width, the next one peeking); 2 columns from 640, 4 from 768, 6 from 1024. A shelf of 50 crafts or more is big: its lead spans 2×2 and it shows 8 plates; smaller shelves lead 2×1 and show 4. The lead alternates sides shelf by shelf. Each shelf shows named and English-name plates, so the common case is visible. |
| NamesWall | `crafts/NamesWall.tsx` | `crafts` | The second view of the collection, behind a SegmentedChoice (Plates, Names): every sourced own-script name, grouped by home state, the English name always visible under it in UI 13 ink-3 (not on hover). Links to the craft. |
| AtlasIndex | `crafts/AtlasIndex.tsx` | `families`, `places`, `ideas` | Three columns from 1200px (families with plate swatch, sub-families and count; places by count; ideas named in the monographs), one below 768px. Rows are links. |
| RankedList | `map/RankedList.tsx` | `rows`, `series` | Beside every map: name, a bar in the map's series colour (the title's mark in chart-emph), the value in tabular figures; the top ten, then "All N" as a link. |
| FactGrid | `editorial/FactGrid.tsx` | `facts` | At a glance as a `<dl>`, one cluster per fact, 1 / 2 / 4 columns, ink top rule, never repeating the label's GI line. On an uncurated craft, the facts the craft list holds, uncited, under "What the craft list records". |
| RecordStrip | new, `craft/InTheRecord.tsx` | `entries` | "In the record": each entry a date in ink-1 tabular figures, its cited sentence, then an optional plate with its caption first and credit after. 1 / 2 / 5 columns. |
| StageList | new, `craft/StageList.tsx` | `stages` | Numbered stages with the stage tile, the local term in italic and the English name, prose that starts with its verb (the heading already names the stage), "Cloth after", materials with botanical names in ink-2 italic, and Sources differ where recorded. The first five show; "Show all 11 stages" is a button with `aria-expanded`. The stage the reader jumped to takes the current rule. |
| DatedRail | new, `craft/DatedRail.tsx` | `beats` | A date (ink-1, tabular) in the left rail from 1200px, inline above its paragraph below; each beat a spread with its margin notes. |
| HowToRead | `landing/HowToRead.tsx` | `sentence`, `sources` | The sunk band: a demonstrated sentence with its 2px turmeric rule, keys a to d (numerals, the quote, the locator, reliability A to D), and the quote cards they point to. |
| ChapterRail | `craft/*`, replaces craft tabs | `chapters` | Sticks to the top once the appbar has scrolled away; horizontal, scrollable with an edge fade on a phone; the chapter in view (scroll-spy) has `aria-current="location"` and an indigo underline; deep-linkable anchors (`?tab=science` maps to `#chem`); every chapter has `scroll-margin-top: calc(var(--rail-h) + 1rem)`, which grows with Larger text. Monographs are one continuous page; no tabs. |
| Tabs | `ui/Tabs.tsx` | `items`, `value` | Only for views of one object on signed-in tool pages (Settings). `role="tablist"`, roving tabindex, arrow keys, indigo underline. |
| Toast | `ui/Toast.tsx` | unchanged | Raised card with pop shadow; tone tile in the status wash with its icon; title in UI 14 600; three at most; info and success leave after 5s, warnings after 8s, errors stay until dismissed; pause on hover and focus; error uses `role="alert"`. Remove `font-display` and the spring overshoot. |
| Dialog | `dialogs/*` | `title`, `body`, `actions` | Raised, card radius, scrim; title in h3 reading; ActionGroup actions; destructive last, madder, named for what it does ("Delete lesson"); initial focus on the least destructive action; focus trapped; Escape cancels. |
| EmptyState | `EmptyState.tsx`, `DeadEnd.tsx` | `plate`, `title`, `body`, `action` | Hairlines above and below, what the place is for, and one way forward. A state about one craft shows that craft's plate; other states carry no glyph (no generic icons). Never "Not enough cited evidence yet", "Coming soon", "No data", "0 results". |
| Skeleton | `ui/Skeleton.tsx` | `shape: masthead \| lede \| plateGrid \| chart` | Sunk blocks in the shape of the content; a slow opacity pulse that stops under reduced motion; the container is `aria-busy`. Never the word Loading on its own. |
| MapLegend | `map/*` | `ramp`, `breaks`, `extras` | Stepped bar with labelled breaks in the unit; salt flat, water, place and no-reading swatches; proportional-circle key; at most three family swatches. Placement in 2.8. |
| Chart kit | new, `charts/*` | `Axis`, `Bars`, `Line`, `TrendLine`, `RefLine`, `DirectLabel`, `Band`, `Tooltip`, `DataTable` | Implements the chart grammar in 2.7, including `data-fit` text and the keyboard model. Trend lines carry a 6px ground halo. |
| Formula and Swatch | new, `chem/Formula.tsx`, `chem/Swatch.tsx` | `formula`, `specimen` | True subscripts at 12px or more; the equation rule of 2.9; swatches use specimen tokens with the weave texture, the ink-2 frame and the raised mat. |
| LivingCloth | new, `cloth/*` (one SVG engine) | `stage`, `width`, `borders` | One deterministic drawing of an ajrakh in any of its eleven states; feeds the landing ribbon, Fig. 1, stage tiles and the vat figure. Stage buttons under it are a `role="toolbar"` with roving tabindex (arrows, Home, End), each `aria-pressed`, the pressed one indigo; choosing one dips its band and jumps to its stage. |
| VatFigure | `answer/VatFigure.tsx` | `dips` | The three-frame filmstrip (In the vat, Lifted, In the air) with the current frame's ink rule, Dip again (Start again after dip 4), the live status line, the balanced equation with its atom count. |
| CiteThis | `craft/CiteThis.tsx` | `kind: monograph \| answer`, `version`, `url`, `accessed` | "Cite this monograph": a segmented Text / BibTeX choice, the citation, the permanent versioned URL (`https://kalavigyan.vercel.app/crafts/kutch-ajrakh/v1`, slug in lower case), one Copy citation button. The text form ends "…Accessed 18 November 2026." with the date of copying. BibTeX is `@misc` with `title`, `author = {{KalaVigyan}}`, `organization` and `publisher` (IIT Kharagpur, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform), `version`, `date`, `year`, `url`, `urldate`, and `howpublished = {\url{…}}` plus an Accessed note for plain BibTeX styles. |
| Appbar, BrandMark | `DynamicIslandNav.tsx`, `BrandMark.tsx` | — | Wordmark at parity (SVG), nav in UI 14 ink-2, current page ink-1 with indigo underline, account button (44px) with a rule-strong ring. Below 768px the nav folds into a Menu button (`aria-expanded`, `aria-controls`) that opens a sheet with the nav and account; the public landing shows only the wordmark and the craft count, because its two actions sit in the hero. On a photograph the bar takes photo ink, a translucent rule and the photo focus ring. |
| InstitutionFooter | `landing/Footer.tsx` | — | One line in UI 12 ink-3 under a hairline: "KalaVigyan, from IIT Kharagpur and its Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform." plus the citation promise. |

---

## 4. Page templates

Heading levels are given per template; every page has one h1.

**Landing (public).** First screen: the full-bleed licensed photograph of the flagship cloth (cloth edge to edge, with its dyed-region mask), the start scrim, the appbar in photo ink, kicker, hero headline (h1: "The science in India's crafts, *sourced to the sentence.*"), standfirst, ActionGroup of two (Request access primary, Sign in quiet), audience line, and the specimen label (landing variant) with the cited vat sentence, its three steps and Play again. The vat moment plays once. Then the living-cloth ribbon (h2-less band with a kicker), One cloth, four chemistries (h2; Blue, Black, Red and White as h3, White comparing lime-protected white with the pink tinge madder leaves on open cloth), How to read a page (h2, keys a to d), the crafts map (h2) with the ranked list and legend in its column, and the institution footer. On a phone the photograph, headline and label fill the first screen.

**Crafts atlas.** Title (h1 at `--text-h1`, "The atlas") and count, the search box with Try chips and concept results (h3 per concept, the matched cited sentence, co-occurring ideas, "Show all N" as an expanding button), the Index (h2; families, places and ideas as h3), then the collection (h2) with its Plates / Names choice: one CollectionShelf per family (h3), every shelf showing named and English-name plates and "All N". Catch-all rows ("Other leather goods") never appear as plates; they reach the reader through "All N".

**Public monograph (craft page).** Masthead: the specimen label (masthead variant, the name as h1) overlapping a 16:7.4 photograph cropped from its focal box, with its cited caption and credit; on a phone and tablet the 4:3 photograph comes first and the label follows on paper with no shadow. The lede in the reading column with the margin. The chapter rail. Chapters (h2) in one continuous page: 1 At a glance (FactGrid and In the record), 2 How it is made (Fig. 1 the living cloth with its stage toolbar, the StageList, "Show all 11 stages"), 3 The chemistry (Fig. 2 Blue, a static cutaway, with the leucoindigo equation and atom count; Fig. 3 Red; Fig. 4 Black), 4 Why Kachchh (full-bleed chapter photograph of the Great Rann under a chapter label, the DatedRail, Fig. 5 rainfall, Fig. 6 temperature, Table 1, Figs. 7–9), 5 Sources (grouped, each with reliability and "Supports N sentences here", selectable to light its sentences), then Cite this monograph. A craft page may cite its category dossier's science; those sources are listed under "For the chemistry, from the Textiles family monograph" and labelled so in the popover.

**Craft without a monograph (438 of 461 crafts today).** The typographic plate at the masthead ratio in place of the photograph (16:7.4 desktop, 4:3 below 1024px), showing the own-script name when sourced; the specimen label (masthead variant, kicker "Craft · family · sub-family", the name as h1 at equal standing with its own-script name when sourced, the GI line from the craft list, the state, and the provenance "From the KalaVigyan craft list" plus the name's source); "What the craft list records" as a FactGrid (family, sub-family, home state, practised in); and an EmptyState (h2 "Start the research on {craft}") with the craft's plate and three questions as an ActionGroup that start cited research. No chapter rail, no Cite this until a monograph exists. Never "Not enough cited evidence yet". The master board's fifth screen is the reference at every width, light and dark.

**Category hub.** Family title (h1) with its plate ground, the family's science chapters (h2) from its category dossier (cited), its sub-families as shelves, and its monographs first.

**Map.** Paper cartography at India scale with the Survey of India caption; one variable at a time with its ramp and legend; craft markers as paper discs; at most three families coloured; the ranked list beside the map; a table view of every value.

**Answer essay.** Provenance rail, the question as h1 at `--text-h1`, a three-sentence cited direct answer as the lede, ActionGroup of two quiet buttons (Save, Cite this answer), the signature figure (for indigo, the VatFigure as Fig. 1), then numbered sections (h2) in the spread with margin notes and margin plates. Provenance names sources and dates, never pipeline counts. An answer in an Arabic-script language mirrors its region (2.11).

**Signed-in tool pages** (saved, lessons, settings, API keys, admin). Ground and raised only, no photography, h1 in the headline face, forms in Fields, Tabs only where one object has several views, tables with tabular figures and `rule` row lines, ActionGroup for every row, empty states with one way forward.

---

## 5. Accessibility

- Contrast by class (2.3). Text 4.5:1, large text and graphics 3:1, high contrast 7:1 for text. Control edges use rule-strong, never rule. Text on a photograph passes the scrim check (2.5).
- Focus per 2.12: visible on every focusable element, on fields, options and photographs alike; never only a colour change.
- Targets: 44px on touch for every control, including chips and the account button; citation numerals 44px wide on touch inside their own line.
- Citations: short accessible name with titles in the description; popover focus moves to the dialog and returns to the numeral; the phone sheet is modal with a focus trap.
- Figures: title, description, table; one tab stop and arrow keys between marks; tooltips open on focus and close on Escape. Maps have a ranked list or table.
- Chapter rail: `aria-current="location"`, scroll-spy, scroll margins that grow with Larger text.
- Status is never colour alone: every evidence state, toast and error has a word and, where it fits, an icon. The current step of a process has `aria-current="step"` as well as its rule.
- Search and live research announce short counts or stage names in `role="status"`, never whole result bodies.
- Every animated control works under reduced motion and announces its result.
- `lang` and `data-script` on every non-English string, `dir="rtl"` for Arabic-script strings, `<bdi>` for a native name inside an English line.
- Body text never below 16px on a phone; nothing below 12px except citation numerals; every size grows by exactly an eighth under Larger text.
- No `aria-label` on generic spans; use visually hidden text (the GI tag says "GI registered").
- Windows forced colours and `prefers-contrast: more` per 2.1.
- Print: Newsreader on white, margin notes as numbered footnotes, plates in greyscale-safe tones, the source list at the end, no appbar or rail.

---

## 6. Migration from today's classes

Decide by job, not by name: a purple class on something you can press becomes indigo; a purple class on a surface, border or decoration becomes a neutral. Counts are from `frontend/{app,components,lib}` on 18 November 2026 (uses, then files). **Aliasing policy:** every neutral, type, radius and status key listed below is aliased to its new token in `tailwind.config.ts` (`legacy…` objects), so nothing silently stops generating when `ink`, `error` and `success` change shape under Tailwind 4.3.5; the guard spec, keyed per file so parallel tasks do not collide on one baseline, blocks every new use of an alias, and each alias is deleted when its count reaches zero. Retired brand ramps (purple, field, gold, ministry, archive, errand, steward, mango, evidence) are not aliased: they fail the build once the files that use them are migrated, and the guard blocks them meanwhile.

**Implementation note (decision 0092, point 6, amended 18 November 2026).** The retired ramps are aliased after all, in `frontend/tailwind.migration.ts`, so no unmigrated screen loses its buttons or its map; the aliases guess by lightness, `bg-purple-200` is the turmeric highlighter and `text-white` compiles to on-indigo (near-black in dark). The skill's section 11 lists every alias, where its guess is wrong and what the guard counts. The generator, the boards and the landing mask are in the repository: `tools/design/`, `docs/design/` and `docs/design/img/hero-dyed-mask.png`.

| Today | Uses | Interactive use becomes | Surface or decorative use becomes |
|---|---|---|---|
| `text-purple-700`, `text-purple-800`, `text-purple-600` | 98, 15, 1 | `text-indigo` (links, current nav item, selected option, citation numerals); hover `text-indigo-hover` | `text-ink-2` or `text-ink-3` (kickers, labels, eyebrows, badge text) |
| `dark:text-purple-300`, `dark:text-purple-200`, `text-purple-100`, `dark:text-purple-950` | 62, 23, 9, 3 | delete: indigo themes itself | delete; text on indigo fills is `text-indigo-on`; text on photographs is photo ink |
| `bg-purple-700`, `hover:bg-purple-800` | 35, 7 | `bg-indigo` / `hover:bg-indigo-hover` (primary button, selected segment, toggle on) | not allowed: an indigo fill that cannot be pressed is removed |
| `bg-purple-50`, `bg-purple-100`, `bg-purple-200` | 64, 11, 2 | selected or pressed: `bg-indigo-wash`; hover on a quiet control: `hover:bg-sunk` | bands, panels, header chips: `bg-sunk`, or nothing (hairline instead of a box) |
| alpha purples (`bg-purple-700/10`, `bg-purple-500/15`, `bg-purple-300/30`, `ring-purple-600/15` and the rest) | 59 in 47 | `bg-indigo-wash` | `bg-sunk` or nothing |
| `bg-purple-950`, `dark:bg-purple-950/40`, `dark:bg-purple-900` | 65, 4 | delete: the wash tokens theme themselves | delete; dark surfaces are `bg-raised` or `bg-sunk` |
| `bg-purple-300`, `bg-purple-400`, `bg-purple-500`, `bg-purple-600` | 4, 6, 1, 1 | `bg-indigo` where it marks a selected or active control | progress and meter fills: `bg-ink-2`; data: the variable's series token |
| `border-purple-300`, `border-purple-200`, `border-purple-400` | 49, 7, 9 | control edges: `border-rule-strong`, hover `hover:border-ink-1` | `border-rule` |
| `border-purple-700`, `border-purple-600`, `border-purple-500`, `border-purple-800/900` | 12, 7, 5, 15 | selected or focused edge: `border-indigo` | delete the dark variants; else `border-rule` |
| `ring-purple-*`, `focus:ring-purple-600/15`, `focus-visible:ring-purple-700`, `outline-purple-600` | 26 | delete: the global focus outline is indigo; fields keep their 2px ring | – |
| arbitrary and important variants (`[&>button]:bg-purple-700`, `text-gold-300!`, `sm:[&>*]:rounded-full!`) and `@apply` of any retired class | 3 child variants, 2 important | rewrite as the component's own class; the guard parses arbitrary, important and `@apply` forms | – |
| `fill-purple-*`, `stroke-purple-*` (maps, molecules, story SVGs) | 34 | selected map element: `stroke-[var(--map-selection)]` over a halo | land `--map-land`, water `--map-water`, borders `--map-border-*`, markers `--map-marker` and `--map-marker-ring`, choropleths the variable's ramp |
| `accent-purple-700`, `accent-purple-400` | 6 | `accent-indigo` | – |
| `decoration-purple-300/500` | 4 | `decoration-current` on indigo links | – |
| `--purple-700` in CSS (focus, flash rows, calendar) | 6 | `rgb(var(--c-indigo))` | `.fr-flash-row` flashes `turmeric-wash` |
| `ink-900`, `ink-700`, `ink-500`, `ink-300`, `ink-muted`, `ink-body`, `ink-soft` (text, bg, border, fill, stroke) | 688 in 176 | – | aliased: 900 → `ink-1`, 700 and body → `ink-2`, 500, 300, muted and soft → `ink-3`; migrate to `text-ink-1/2/3` |
| `border-line-200`, `ring-line-200`, `divide-line-200` | 185 in 106 | control edges: `border-rule-strong` | aliased to `rule`; migrate to `border-rule` |
| `bg-card` | 79 in 53 | interactive cards stay `bg-raised border border-rule rounded-card` | prose and sections lose the box |
| `bg-surface-50`, `bg-bg-0` | 77 in 58, 11 in 8 | – | aliased to `sunk` and `ground`; migrate to `bg-sunk`, `bg-ground` |
| `progress-track`, `progress-fill`, `progress-done` | 21 in 3 | – | aliased: track `sunk`, fill `ink-2`, done `success` |
| `text-error-600`, `bg-error-100`, `text-success-600`, `bg-success-100` and the other numeric status keys | 105 in 42 | `text-error`, `bg-error-wash`, `text-success`, `bg-success-wash` (aliased meanwhile) | – |
| `secondary`, `secondary-foreground`, `accent`, `accent-foreground` | 7 in 1 | `accent` → `indigo-wash`, its foreground → `indigo-hover` (aliased) | `secondary` → `ink-3` (aliased) |
| `text-white`, `bg-white` | 44 in 35, 4 in 4 | on indigo or madder fills: `text-indigo-on`, `text-madder-on` | on photographs: photo ink; `white` is aliased to #FFF only so nothing vanishes |
| `field-50`…`field-300`, `field-900` | 27 (all `field-*`) | – | `bg-ground`, `bg-raised`, `bg-sunk`, `border-rule`, `text-ink-1` |
| `field-400`…`field-700` (purple aliases) | in the 27 | `indigo`, `indigo-hover` | – |
| `.field-button` (48), `.field-button-secondary` (63), `.field-danger` (6), `.file-trigger` (3) | 120 | `Button` primary, quiet, danger; file trigger is a quiet Button with a file input | – |
| `.field-input` (28), `.field-label` (43), `.field-link` (1) | 72 | `Input`; `TextLink` | `field-label` becomes the sentence-case label (UI 13 500 ink-2), never uppercase |
| `.panel` (123), `.section-band` (3), `.surface-dark` (2), `.display-title` (5) | 133 | interactive cards keep `bg-raised border border-rule rounded-card` | prose and sections lose the box: hairline rules and spacing; `.surface-dark` becomes `bg-sunk`; `.display-title` becomes `font-headline` |
| `.eyebrow` (10) | 10 | – | `.kicker` (UI 12 600, 0.08em, ink-3), never indigo |
| `gold-*`, `thread` | 3 | – | turmeric only for a highlight rule; dates in ink-1; delete `text-gold-gradient` |
| `ministry-*` and every `[data-surface="ministry"]` rule | 22 | delete: KalaVigyan has no ministry surface | delete |
| `archive-*` (SpeciesCast, storyGeometry) | 10 | – | specimen tokens for species; map tokens for geometry |
| `errand-*` (TrendChart, RainfallBars, RiverStage, StoryKey) | 28 | – | rainfall bars `--series-rain`, rivers `--map-river`, trend lines `--chart-trend`, story keys ink and terracotta |
| `steward-*` (TrendChart, QuizQuestionCard) | 12 | quiz wrong answer: `error` with icon and words | chart: series token or `--chart-emph` |
| `evidence-*` (EvidenceBadge, MarketGiView, QuizQuestionCard, CraftHeader) | 34 | – | evidence states per EvidenceMark; GI marks the GI tag; quiz right answer `success` with icon and words |
| `dye-*` (today's config) | 12 in 1 | – | specimen tokens (`--dye-*`), framed swatches only |
| `mango-*` | 0 | – | delete the ramp |
| `amber-*`, `red-*`, `emerald-*`, `green-*`, `rose-*` (stock) | – | errors `error`; destructive `madder` | warnings `warning`, success `success`, hazards `madder` (only for real hazards) |
| `font-display` | 112 in 77 | stays sans during migration (alias of `font-ui`); nav labels, buttons, toasts and the code field move to `font-ui` | display lines change to `font-headline` by hand, file by file; the alias is deleted at zero |
| `font-serif` | 0 | – | now Newsreader; use `font-reading` in new code |
| `font-bold` | 112 in 76 | – | aliased to 600 (Plex has no 700); migrate to `font-semibold` |
| `text-xs`, `text-sm`, `text-base`, `text-lg`, `text-xl`, `text-2xl`…`text-4xl` | 582 in 168 | named tokens: `text-caption`, `text-ui`, `text-ui-lg` | aliased meanwhile (xs → caption, sm → ui, base → ui-lg, lg → body-sm, xl → lede, 2xl → h3, 3xl → h2, 4xl → h1) |
| `text-[11px]`, `text-[15px]`, `text-[10px]` and other arbitrary sizes | 63 in 49 | named tokens | `text-figcaption`, `text-body`, `text-lede`, `text-h3` and up; nothing below caption |
| `rounded-md` (12px today), `rounded-sm`, `rounded-lg`, `rounded-xl`, `rounded-2xl` | 128 in 72, 16 in 11, 50 | controls `rounded-control`, cards and popovers `rounded-card` | plates and photographs `rounded-plate`; aliased meanwhile (sm → 4px, md to 2xl → 6px); delete radii on sections |
| `rounded-full` | 127 in 79 | chips and toggle tracks `rounded-pill`; avatars and icon buttons keep `rounded-full` | – |
| `shadow-sm`, `shadow-soft`, `shadow-cta`, `shadow-glow*`, `shadow-island`, `shadow-panel`, `shadow-md/lg` | 19 in 12, and the rest | delete on buttons | popovers and toasts `shadow-pop`; nothing else (`shadow-sm` aliases to none) |
| `ease-spring`, `springy`, framer `type: "spring"` | 11 | `ease-out` (the alias drops the overshoot); a switch thumb keeps `ease-toggle` | – |
| `backdrop-blur-*` | 4 in 3 | – | delete (the theme defines no blur); the chapter rail is 96 per cent ground |
| physical left and right (`text-left`, `left-3`, `pl-10`, `ml-auto`, `border-l`, `rounded-r` …) | 122 in 51 | logical utilities (`text-start`, `start-3`, `ps-10`, `ms-auto`, `border-s`, `rounded-e`) | same; a lint rule rejects physical utilities in components |
| `glass-card`, `glass-dark`, `GlassSurface`, `LiquidGlass`, `grad-mesh`, `grad-brand`, `ambient-light`, `text-gradient-violet`, `text-gold-gradient` | 4, 1, 13, 13, 9, 4, 1, 1, 2 | – | delete; auth and landing panels become ground with the photograph and specimen label |
| `logo.*` tokens and `BrandMark` flask | – | – | the block-cut star and SVG wordmark |
| `THEME_COLOR` in `lib/preferences.ts` | – | – | light `#F4F5F1`, dark `#0E121C` |

**The guard spec** parses class strings including arbitrary (`[&>…]:`), important (`!`) and responsive or state prefixes, and `@apply` in CSS. It allows hex values only in the token files and in an allow-list of third-party brand marks (the Microsoft sign-in logo's #f25022, #7fba00, #00a4ef and #ffb900, and the Google logo's colours), and rejects any media query at a width that is not a token breakpoint.

Order of work: generate `tokens.css` and copy `tailwind.config.ts` (2.1, 2.2) in one change, with the aliases; re-point the base border, placeholder and focus; then migrate files as their owners touch them.

---

## 7. Copy rules

- Sentence case everywhere; title case only in proper names.
- Buttons are verbs: Request access, Sign in, Save, Cite this answer, Show all 97, Dip again, Play again, Copy citation.
- Counts are derived from the catalogue endpoint, never typed (461 active crafts today).
- Provenance names sources and dates: "Drawn from 20 sources · curated 17 Nov 2026".
- Stage prose starts with its verb; the heading already names the stage.
- Never on a reader screen: not built yet, coming soon, no data, not enough cited evidence, 0 results, stored findings, research trail, beta, AI-generated.
- Errors say what happened and what to do, in one sentence each.

## 8. Acceptance for every build task

- Board-against-implementation screenshots at 360, 390, 834, 1194, 1440 and 1920 in light and dark, plus high contrast and Larger text at 360, match `master-board.html` and `design-system.html`.
- No sideways scroll at any width, with Larger text on (shelves scroll sideways inside themselves on a phone by design).
- Contrast gate by class (2.3) and the generator's checks pass on every theme; the scrim check passes in every vat phase.
- Larger text: every type token computes to exactly 1.125 times its standard size at 360, 1440 and 1920.
- Nothing renders below 12px except citation numerals, SVG text included.
- No retired class, no hard-coded hex outside the token files and the brand allow-list, no `font-display` on a display line, no media query off the breakpoint list.
- Reduced motion: every named motion shows its end state; every control still works. The vat phases are screenshotted.
- Pictures: only standard Commons widths, every picture credited, no repeats on a page, crops from focal boxes, no shopping imagery.
- Native-script names only with a recorded, reviewed source that names the craft.
- Regression baseline from version 1.0, kept: every semantic text token passes its class in all four themes; neither board scrolls sideways at 320, 360 or 390, including with Larger text plus high-contrast dark; the migration counts above match the repository.

---

## 9. Decisions

What version 1.1 changed in answer to the two critiques, and where a critique was not followed.

**Amended 20 November 2026 (owner: "information density encompassing all the fields is spectacular on all the pages")**
- Principle 10, dense with every field, added. It changes no token, component or template; it is the bar every reading page and answer is reviewed against, together with rules 23 to 26 of the craft-pages skill's page checklist.

**Fixed as asked**
- The chart-grid and chart-series generator bug (pipe-joined hexes) is gone: values are split per theme with their own ratios and classes, and the generator, `tokens.css` and a complete `tailwind.config.ts` now ship in this folder.
- The vat moment tints only an authored dyed-region mask, intersected with the rising and withdrawing gradient; resist whites, kut black and the madder cloth at the photograph's foot keep their colour. The phases were screenshotted for acceptance (`shots/` holds the final set; the lifted phase was checked at 1440).
- Both maps draw land, neighbouring land, sea and the Great and Little Rann as stippled salt flat with italic labels; Kachchh is a terracotta outline and 45° hatch, Barmer an ink selection outline.
- Reserved-hue floor: every ramp step, series and family hue is 10 or more delta E from indigo, indigo-hover, madder, terracotta and turmeric in every theme; first steps, the pH neutral class and the highest elevation class clear ground, sunk, land, neighbouring land and water by 10. Heat no longer ends in madder; leather, metal and clay moved off madder, turmeric and terracotta; elevation above 4,000 m is a cool lavender-grey instead of near-white.
- Per-theme series tokens replace "use ramp step 4"; the ranked bars and the circles share `--series-count`; only the title's mark is `--chart-emph`.
- Ochre and neem are retired: dates in ink-1 tabular figures, botanical names in ink-2 italic. The accents are now indigo, madder, terracotta and turmeric.
- One look for the current step (the indigo fill when pressable, the ink rule when not); turmeric is never a state.
- Margin-note numbers are ink-3; notes anchor to their first citing sentence, push down on collision and never repeat within a chapter.
- A hatch grammar gives five meanings five patterns.
- Plate textures are seeded and irregular for irregular materials, with an opacity and a measured visibility per material, knocked out under kicker and name; wood and leather differ by 26 delta E; dark plates are warm and material.
- On the collection wall the strip always carries the English name in one place, tags drop to their own line, catch-all kickers are hidden, the lead alternates sides, and phone shelves scroll sideways.
- A sourced bilingual masthead (Kasuti Embroidery with ಕಸೂತಿ) and the uncurated craft page are on the master board; the label's size, line and width rules are specified.
- Generic labels are held back (Kutch Bandhani's બાંધણી, Lucknow Chikan Craft's चिकनकारी and nine more, listed in 2.10), with a rule that names the test.
- The Metal shelf leads with the Kondagaon workshop; the design system's plate demo is a printing block, not a sale table.
- Type: no text under 12px on either board (SVG text scales with `--k`); figcaption and note sizes are tokens; the answer's h1 is `--text-h1`; Larger text is exact at every width through `--text-zoom`; display sizes grow to 1920; the phone hero outranks a craft title; h4 is the UI voice; numerals have no phone or tablet sizes.
- Tailwind: semantic colours replace the stock palettes; headline needs no plugin because optical size follows the size.
- Focus on fields, options and photographs; `onFill` class for on-indigo and on-madder; turmeric is decorative and its failing text pair is removed.
- Map tokens carry classes and per-surface ratios; water is 10 or more from land in every theme including high-contrast dark; hillshade is ink, not terracotta.
- Specimen swatches sit in an ink-2 frame with a raised mat, visible in all four themes.
- Script coverage adds Konkani, Maithili, Dogri, Bhojpuri, Bodo, Meetei Mayek and Ol Chiki, Naskh for Sindhi, selection by `data-script`, display leading per script, the native-name data contract, bidi isolation and a font byte budget.
- Control sizes, breakpoints, margins, the spread's gaps and the tablet layout are tokens; every contradiction the critics listed (masthead ratio, press and oxidise durations, the hold token, Newsreader and Plex weights, atlas title size, Save as quiet, "Primary is the only indigo fill", "curated", 720px) resolves to one value.
- RTL rules and an Urdu answer opening; a keyboard model for figures; Commons widths through `commonsThumb`; focal boxes and cached derivatives.
- Cite this carries the lower-case permanent URL, the access date and `@misc` fields that styles actually print.
- The scrim is keyed to the text block and checked under every line in every vat phase.
- Engineering improvements taken: forced colours and `prefers-contrast`, the reduced-motion pattern, citation hit areas and ARIA, info moved off indigo, explicit high-contrast shadows, a three-family map in four themes, the guard's arbitrary and important variants and brand allow-list, `b`/`strong` at 600 with `font-synthesis: none`, link-or-button for "All N", busy width, Start again, toast durations, dialog focus, the `/` shortcut, the chart-or-diagram title rule, LCP and `sessionStorage`.
- Creative improvements taken: type to 1920, the h4 voice, the vat's meniscus and ragged edges with Play again, the Great Rann as the Why Kachchh opener, material-true dark plates, the shelf rhythm and sideways phone shelves, the Names view, hidden catch-all kickers, a deeper-notched star, plates instead of generic empty-state glyphs, the White pair as a comparison, dye-madder as alizarin crimson, stage prose starting with its verb, the rail's edge fade, the stacked kicker on phones, the legend under the ranked list, reliability D in How to read, and an uncurated craft in the label-on-paper demo.

**Not followed, and why**
- **Floor of 10, not 15.** The creative critique suggested 15. A six-step warm ramp must cross the lightness of turmeric, terracotta and madder; at 15 every warm ramp turns grey and the families lose their CVD separation. 10 is about five just-noticeable differences in OKLab, it is the floor the engineering critique asked for, and it matches the existing first-step rule. The heat ramp became blush to plum to clear it.
- **Margin entries are not buttons.** The creative critique offered live margin notes. The sentence's numeral already opens the source, so a second control for the same job would break principle 1; the numbers became ink-3 instead.
- **Family hues stay categorical, not material.** Brass, terracotta and oxblood would sit on turmeric, terracotta and madder, and the plate tones are too close in lightness to pass the CVD check. Instead plates keep the material, shelf swatches use the plate ground, and a family legend never sits beside plates.
- **Specimen dyes keep a documented exception.** The engineering critique offered refit or document. The interactive indigo was made more saturated (chroma 0.16) and the dyed blues duller (0.06 or less), which clears 10 against indigo and indigo-hover in light; harda, gach clay and dye-madder against the high-contrast madder stay closer, because they depict real materials, under the safeguards in 2.5.
- **The thread motion is retired, not given a spine.** A line drawing down as you scroll explains nothing about the process; principle 6 rules it out. The stage list keeps its numbers and hairlines.
- **No right rail on a tablet.** Version 1.0 said both "66ch plus a sticky right rail" and "below 1200px the margin folds into the popover". A 240px rail beside a 66ch column does not fit 834px with 40px margins, so the tablet is the single column and the board now matches.
- **The chapter rail does not sit under a sticky appbar.** On a reading page the appbar scrolls away and the rail sticks at the top, which keeps more of the page for reading; the spec changed to match the board rather than the reverse.
- **English stays visible on the Names view.** The creative critique suggested the English name on hover or focus. Hover-only text fails on touch and for many readers, so the English name sits under each native name in UI 13.
- **The vat steps are not themselves the control.** A list of steps cannot be a button and stay a list; one Play again text button sits beside the non-pressable steps (one control per job).
- **No pH or elevation map on the boards.** No district soil-pH or hypsometric dataset is in the repository, and the system forbids invented data; both ramps appear as keyed legends with their checks until a real dataset arrives.
- **Urdu digits are Western.** Extended Arabic-Indic digits would differ from the citation numerals, figure numbers and sources the answer points to.
- **Urdu on the board is a layout sample.** The Urdu question and lede on the sixth screen were written for the board; production answers come from the answering service, and the popovers keep the sources' verbatim English.
- **The masthead photograph is kept, re-cropped.** The creative critique called it a hallway snapshot. Among the licensed pictures it is the one that shows the whole cloth with its field and borders; its 16:7.4 and 4:3 crops now come from focal boxes that keep the cloth and drop the floor. Consent-gated field photography (2.15) is the real fix.

## How this specification is kept true

| What | Kept true by |
|---|---|
| The tokens in section 2 | `tools/design/system.json` and the generator (`tools/design_tokens.py`), whose checks refuse a set that breaks a rule; `tools/tests/test_design_tokens.py` fails when an output is stale |
| The depicted materials | `tools/design/materials.json`, generated into `backend/app/research/depicted_materials.py` and `frontend/lib/depictedMaterials.ts` |
| The migration counts of section 6 | the design guard's baseline, `frontend/e2e/design-guard-baseline.json`, which may only fall |
| Each component's home in section 3 | `frontend/components/`; on 2026-11-21 each "new" file was checked against the tree, and those since built lost the word |
| The decisions of section 9 | the owner's approval of 18 November 2026 and later; overturned only with a new decision |

Re-read it before overturning anything in it, and when the owner approves a new version.
