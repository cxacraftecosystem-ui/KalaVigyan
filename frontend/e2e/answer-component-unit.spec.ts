import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { BLOCK_RENDERERS, hasRenderer } from "@/components/answer/blockRenderers";
import { ComponentFigure } from "@/components/answer/ComponentFigure";
import type { ComponentBlock } from "@/lib/explainerComponent";
import { BLOCK_KINDS, BLOCK_SHAPES, BUILT_BLOCK_KINDS, explainerBlockShape } from "@/lib/explainerContract";
import { parseExplainerStreamBlock } from "@/lib/explainerStream";
import { blockSourceIds } from "@/lib/explainerView";
import { parseShape, ShapeError } from "@/lib/shape";

import { shownText } from "./explainerRender";
import { readRepo } from "./phaseBFixture";

const BOOK = "1a2b3c4d-0000-4000-8000-000000000001";
const MADDER = "1a2b3c4d-0000-4000-8000-000000000009";

function written(changes: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "s1.b2",
    kind: "component",
    version: 1,
    reuse: null,
    label: "kutch-ajrakh/chemistry/red-alum-madder-player",
    componentKind: "reaction_player",
    title: "Red develops only where alum was printed",
    craft: { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" },
    href: "/crafts/Kutch-Ajrakh#rp-red",
    sources: [{ sourceId: BOOK }, { sourceId: MADDER }],
    ...changes
  };
}

function component(changes: Record<string, unknown> = {}): ComponentBlock {
  return parseShape(BLOCK_SHAPES.component, written(changes));
}

function drawn(block: ComponentBlock): string {
  return renderToStaticMarkup(createElement(ComponentFigure, { block }));
}

test("a component block parses exactly as the backend writes it, as a built kind the stream takes", () => {
  expect(component()).toEqual(written());
  expect(BLOCK_KINDS[BLOCK_KINDS.length - 1]).toBe("component");
  expect(BUILT_BLOCK_KINDS).toContain("component");
  expect(parseShape(explainerBlockShape, written())).toEqual(written());
  const frame = `event: block\ndata: ${JSON.stringify({ sectionId: "s1", block: written() })}`;
  expect(parseExplainerStreamBlock(frame)?.type).toBe("block");
});

test("a component links only its own craft's page, at most with an anchor naming an element", () => {
  expect(component({ href: "/crafts/Kutch-Ajrakh" }).href).toBe("/crafts/Kutch-Ajrakh");
  for (const changes of [
    { href: "/crafts/Bagru-Print#rp-red" },
    { href: '/crafts/Kutch-Ajrakh[class="mols"]' },
    { href: "https://example.org/crafts/Kutch-Ajrakh" },
    { href: "/crafts/Kutch-Ajrakh#" },
    { componentKind: "component" },
    { label: "Not a label" },
    { sources: [] },
    { title: " " }
  ]) {
    expect(() => component(changes)).toThrow(ShapeError);
  }
});

test("a component's sources are the ones the answer numbers for it", () => {
  expect(blockSourceIds(component())).toEqual([BOOK, MADDER]);
});

test("Kutch Ajrakh's red player parses as the server places it, resting on the sources its monograph load records", () => {
  const recorded = JSON.parse(readRepo("shared", "explainer.component.golden.json")) as { sections: { blocks: Record<string, unknown>[] }[]; sources: { id: string }[] };
  const [placed] = recorded.sections[0].blocks;
  expect(parseShape(explainerBlockShape, placed)).toEqual(placed);
  expect(blockSourceIds(component(placed))).toEqual(recorded.sources.map((source) => source.id));
});

test("the card names the monograph, titles the figure and offers one indigo link to it", () => {
  const html = drawn(component());
  expect(BLOCK_RENDERERS.component).toBe(ComponentFigure);
  expect(hasRenderer(component())).toBe(true);
  expect(shownText(html)).toContain('<p class="kicker">Figure from the Kutch Ajrakh monograph</p>');
  expect(html).toMatch(/<h4 id="s1\.b2-title" class="[^"]*text-h4[^"]*">Red develops only where alum was printed<\/h4>/);
  const links = [...html.matchAll(/<a [^>]*>/g)].map((found) => found[0]);
  expect(links).toHaveLength(1);
  expect(links[0]).toContain('href="/crafts/Kutch-Ajrakh#rp-red"');
  expect(links[0]).toContain('class="kv-link"');
  expect(links[0]).toContain("data-standalone");
  expect(html).toContain(">Open the figure<span class=\"sr-only\">: Red develops only where alum was printed</span></a>");
  expect(html).toContain('aria-labelledby="s1.b2-title"');
});

test("the card is complete at rest: no motion, no inline style and nothing hidden until pressed", () => {
  const html = drawn(component({ href: "/crafts/Kutch-Ajrakh" }));
  expect(html).not.toMatch(/style=|motion-|animate|transition|opacity-0|hidden=""/);
  expect(html).toContain('href="/crafts/Kutch-Ajrakh"');
  expect(html).toContain('data-component-kind="reaction_player"');
});
