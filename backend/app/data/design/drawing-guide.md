# Drawing for KalaVigyan

For an agent that draws KalaVigyan's knowledge itself: a chart, a diagram or a page rendered in its
own chat from the facts, pages and answers the server gives, or a drawing it delivers as a
component. Whatever you draw follows the same design as the site (Alum & Indigo): alum-white paper,
iron-black ink and one interactive indigo. The tokens as CSS are `kalavigyan://design/tokens.css`;
every token with its contrast and use is `kalavigyan://design/tokens.json`.

## Colours are roles

Name a colour by its role, never by a hex, rgb, hsl or named colour. In your own chat, paste
`kalavigyan://design/tokens.css` into the page and write `fill="var(--ink-1)"`, so the drawing
follows light, dark and high contrast. In a drawing you deliver, write the same `var(--role)`: the
server refuses any other colour and draws the drawing once per theme for the reader.

- **Lines, words and grounds**: `--ink-1` for strokes, text and the baseline, `--ink-2` for
  captions and annotation, `--ink-3` for credits and axis labels; `--rule` for hairlines,
  `--rule-strong` for the edge of anything that reads as a control; `--ground`, `--raised` and
  `--sunk` for paper, cards and wells.
- **Data**: bars and lines in `--chart-series`, or `--series-rain`, `--series-heat` and
  `--series-count` for rain, temperature and craft counts; only the mark the title names in
  `--chart-emph`; axes in `--chart-axis-text` and `--chart-axis-line`, gridlines in `--chart-grid`;
  a mean or threshold in `--chart-reference`, dashed 3 4. Area fills take a ramp step
  (`--rain-1` to `--rain-6`, `--heat-*`, `--density-*`, `--ph-*`, `--elevation-*`, `--earth-*`,
  `--cover-*`), never a bar or a line, because ramps flip in dark.
- **Maps**: `--map-land`, `--map-water`, `--map-coast`, `--map-river`, `--map-salt` and the other
  `--map-*` roles; the Rann is salt flat, stippled, never water.
- **Materials**: a dye, clay, metal or soil a source states is drawn in its depicted-material token
  (`--dye-*`, `--dip-1` to `--dip-4`), framed and named in a key; never a control or a series.
- **Identity colours never on data.** `--indigo` is only for what a reader can press (a link, a
  citation numeral, a selected control), so a drawing never uses it. `--madder` marks a real hazard
  or the span where sources differ, `--terracotta` marks the place a page is about (an outline and
  45 degree hatch, never a fill), and turmeric only highlights.

{{roles}}

## Type

Text is set in the design's faces: IBM Plex Sans for anything read at a glance (labels, axes, keys,
buttons), Newsreader for prose, captions and titles. A drawing you deliver names no font; the server
sets its text in the UI face. Sentence case everywhere; kickers alone are uppercase.

{{type}}

- **The floor is 12 px.** Nothing is drawn smaller, SVG text included, at the narrowest width the
  drawing is shown (320 px for a delivered drawing): set its font size to at least 12 times the
  viewBox width divided by 320, so a drawing 640 units wide sets text at 24 units or more.
- Tables, axes, counts and dates take lining tabular figures. Words are text, never outlines or
  pictures of letters.

## Figures

- A chart's title states its finding; a diagram's or map's title says what it shows.
- Caption first, then the credit: "Drawing: name, licence" or the dataset's credit, under the figure.
- Every figure has words for a reader who cannot see it: a title, an alt text that says what it
  shows, and the values behind it as a table.
- No gradients that blend two roles, no blur, glow, glass or drop shadow: flat ink on paper. A
  gradient may fade one role, step through one ramp or pass between depicted materials.
- Motion only to explain a process or a reaction, and the drawing reads complete at rest; nothing
  moves when the reader has asked for reduced motion.

## When you render a page in your chat

Follow the answer kit (`kalavigyan://design/answer-kit.md`) for the order of a page: the question
or title as the one heading, the cited sentences with their indigo citation numerals, sections
under 1px ink rules, the sources with their attribution and licence, and KalaVigyan's credit with
the link to the page. Draw figures with the roles above and link the site's own figures rather
than redrawing them.
