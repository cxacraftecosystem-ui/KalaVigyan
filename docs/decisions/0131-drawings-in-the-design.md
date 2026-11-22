# 0131. Whatever an AI draws for KalaVigyan speaks the design and follows the reader's theme

A contributed drawing or SVG picture names its colours only by design role, is served in the four
themes, and is judged by the preview report; AI clients read the design as MCP resources, so what
they draw in their own chats speaks it too.

Date: 2026-11-22. Status: accepted (owner, 2026-11-21: "even in the MCP, all the components that
even the AI tools create and render should follow our design theme"). It amends
[decision 0114](0114-kinds-and-datasets.md). The contract is
`docs/contracts/component-specs-general.md`.

| For | Read |
|---|---|
| The kinds it amends | [decision 0114](0114-kinds-and-datasets.md) |
| The design it holds drawings to | [decision 0092](0092-design-system.md) and the kalavigyan-design skill, sections 2.7 and 3 |
| The contract it changes | [component-specs-general.md](../contracts/component-specs-general.md) |
| What amended it | [0141](0141-design-system-and-answer-screens-without-debt.md), item 12: a themed SVG picture's ETag carries its theme and the token set's hash |
| Every decision, by group | [README.md](README.md) |

## Context

The approved kinds and the declared general kinds (chart, table, timeline, map layer) are drawn by
KalaVigyan's own views and take the theme. A delivered drawing was the contributor's own cleaned SVG
drawn as an image, so it kept whatever colours, fonts and sizes it was given and stayed light in a
dark page: no CSS variable reaches inside an image. Science specs and swatches could carry raw
colours too, and nothing told an AI client what the design is when it drew KalaVigyan's knowledge in
its own chat.

## Decision

1. **A drawing names colours only by design role.** The roles are the surfaces, rules and inks, the
   chart and series tokens, the ramp steps, the map tokens, depicted `dye-*` and `dip-*` materials,
   terracotta for place and madder for a hazard (`research/drawing_roles.py`). Intake refuses a hex,
   rgb, hsl or named colour, indigo (it means a control), any other token, a named font, text under
   12px at a 320px width, a gradient blending two roles, gradient-filled text, blur and drop-shadow
   filters, and words drawn as outlines, each refusal naming the element and the allowed roles. The
   rule holds for the drawing kind and for contributed SVG pictures.
2. **A drawing follows the reader's theme and stays an image.** It never runs script. Each role's
   value in light, dark, high-contrast light and high-contrast dark comes from `tokens.json`; a
   served drawing carries the four variants (`themes`) and SVG pictures are served by `?theme=`.
   Variants are made when a page is served, not stored, so no migration is needed; the web client
   draws the variant whose selectors match `tokens.css`.
3. **Every other place a spec carries colour obeys the same roles.** Science drawing nodes, swatches,
   dips and colour tokens are checked at delivery (check 8 of the spec problems); a swatch or dip
   must be a depicted material.
4. **The preview report judges it.** Checklist rule 27 fails a delivered figure off the vocabulary,
   a drawing without its four variants and a figure or picture without alt text, with the evidence.
5. **AI clients read the design.** Two MCP resources, `kalavigyan://design/tokens.css` (every role in
   the four themes and the type scale) and `kalavigyan://design/drawing.md` ("Drawing for
   KalaVigyan"), and the contributor skill and components reference teach them. The answer and
   page-preview MCP App views take all four themes and the type tokens.

## Consequences

- A delivered drawing reads in a dark or high-contrast page as the site does; a cached SVG picture
  takes a token change within its five-minute max-age.
- The authored Kutch Ajrakh specs stay valid in the models; delivery is where the vocabulary is
  enforced.
- Captures prove light and dark at 360, 834 and 1440px; high contrast is proven by the selector
  parity spec and the four-palette tests.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/research/test_drawing_vocabulary.py`, `test_page_report_design.py`,
`backend/tests/mcp/test_design_kit.py` and `frontend/e2e/design-conformance-unit.spec.ts`.
