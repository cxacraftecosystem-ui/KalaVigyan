import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { BLOCK_RENDERERS } from "@/components/answer/blockRenderers";
import { QuantitiesView } from "@/components/answer/insight/QuantitiesView";
import { BLOCK_SHAPES, BUILT_BLOCK_KINDS, explainerBlockShape } from "@/lib/explainerContract";
import type { QuantitiesBlock } from "@/lib/explainerInsight";
import { blockSentences } from "@/lib/explainerView";
import { AMOUNT_KIND_LABEL } from "@/lib/insightView";
import { parseShape, ShapeError } from "@/lib/shape";

import { attribute, shownText, withReading } from "./explainerRender";
import { readRepo } from "./phaseBFixture";

type QuantitiesFixture = { sections: { blocks: unknown[] }[] };

const GOLDEN = JSON.parse(readRepo("shared", "explainer.quantities.golden.json")) as QuantitiesFixture;
const SANCHARA = "3 kg of sanchara (rock salt) is dissolved in 15 litres of water as one component of the mengni solution.";

function quantities(): QuantitiesBlock {
  return parseShape(BLOCK_SHAPES.quantities, structuredClone(GOLDEN.sections[0].blocks[0]));
}

function count(html: string, needle: string): number {
  return html.split(needle).length - 1;
}

test("the quantities table is a built kind with a renderer, read by the block shape", () => {
  expect(BUILT_BLOCK_KINDS).toContain("quantities");
  expect(BLOCK_RENDERERS.quantities).toBeDefined();
  expect(parseShape(explainerBlockShape, structuredClone(GOLDEN.sections[0].blocks[0])).kind).toBe("quantities");
  const block = quantities();
  expect(() => parseShape(BLOCK_SHAPES.quantities, { ...block, rows: block.rows.slice(0, 2) })).toThrow(ShapeError);
  expect(() => parseShape(BLOCK_SHAPES.quantities, { ...block, rows: [{ ...block.rows[0], measures: "SPEED" }, ...block.rows.slice(1)] })).toThrow(ShapeError);
});

test("each quantity shows what it measures and its stated words, and a sentence two quantities share is said once", () => {
  const block = quantities();
  const html = withReading(createElement(QuantitiesView, { block }));
  expect(attribute(html, "quantity-stated", "data-testid")).toHaveLength(5);
  expect(attribute(html, "quantity-row", "data-measures")).toEqual(["MASS", "VOLUME", "MASS", "TIME", "TIME"]);
  expect(attribute(html, "quantity-sentence", "data-testid")).toHaveLength(4);
  expect(count(html, SANCHARA)).toBe(1);
  const text = shownText(html.replace(/<[^>]+>/g, " "));
  for (const stated of ["3 kg", "15 litres", "80–100 g", "15–20 days", "10 minutes"]) expect(text).toContain(stated);
  expect(text).toContain(AMOUNT_KIND_LABEL.VOLUME);
  expect(html).toContain("<caption");
  expect(html).toContain('scope="row"');
  expect(blockSentences(block)).toHaveLength(5);
});
