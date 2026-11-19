import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { SignatureFigure } from "@/components/answer/SignatureFigure";
import { VatFigure } from "@/components/answer/VatFigure";
import { atomRows, currentFrame, dipStatus, formulaAtoms, hillOrder, nextDip, vatEquation } from "@/lib/answerVat";
import { signatureFigureShape } from "@/lib/explainerContract";
import type { IndigoVatBlock, SignatureBlock } from "@/lib/explainerSignature";
import { signatureSentences, signatureSourceIds } from "@/lib/explainerSignature";
import { parseShape } from "@/lib/shape";

import { attribute, shownText, withApp } from "./explainerRender";

const FIGURES = JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", "explainer.signature.golden.json"), "utf8")) as unknown[];
const figure = (index: number): SignatureBlock => parseShape(signatureFigureShape, FIGURES[index]);
const vat = (): IndigoVatBlock => {
  const block = figure(0);
  if (block.kind !== "indigo_vat") throw new Error("the first golden figure is the indigo vat");
  return block;
};

test("a formula reads as its atoms, and anything that is not a formula reads as nothing", () => {
  expect([...(formulaAtoms("C16H10N2O2") ?? new Map()).entries()]).toEqual([
    ["C", 16],
    ["H", 10],
    ["N", 2],
    ["O", 2]
  ]);
  expect([...(formulaAtoms("H2O") ?? new Map()).entries()]).toEqual([
    ["H", 2],
    ["O", 1]
  ]);
  expect(formulaAtoms("c16h10")).toBeNull();
  expect(formulaAtoms("")).toBeNull();
  expect(hillOrder(["O", "N", "H", "C", "S"])).toEqual(["C", "H", "N", "O", "S"]);
  expect(hillOrder(["O", "H"])).toEqual(["H", "O"]);
});

test("leucoindigo and oxygen give indigo and water, and the atoms count the same on both sides", () => {
  const equation = vatEquation({ formula: "C16H12N2O2", name: "indigo white" }, { formula: "C16H10N2O2", name: "indigo blue" });
  expect(equation?.reactants.map((species) => [species.coefficient, species.formula])).toEqual([
    [2, "C16H12N2O2"],
    [1, "O2"]
  ]);
  expect(equation?.products.map((species) => [species.coefficient, species.formula])).toEqual([
    [2, "C16H10N2O2"],
    [2, "H2O"]
  ]);
  expect(equation?.rows).toEqual([
    { atom: "C", before: "2 × 16 = 32", after: "2 × 16 = 32" },
    { atom: "H", before: "2 × 12 = 24", after: "2 × 10 + 2 × 2 = 24" },
    { atom: "N", before: "2 × 2 = 4", after: "2 × 2 = 4" },
    { atom: "O", before: "2 × 2 + 2 = 6", after: "2 × 2 + 2 = 6" }
  ]);
  expect(equation?.spoken).toBe("2 indigo white plus oxygen gives 2 indigo blue plus 2 water");
});

test("no equation is drawn when the forms do not differ by one hydrogen molecule or a formula is missing", () => {
  expect(vatEquation({ formula: "C16H10N2O2", name: "a" }, { formula: "C16H10N2O2", name: "b" })).toBeNull();
  expect(vatEquation({ formula: null, name: "a" }, { formula: "C16H10N2O2", name: "b" })).toBeNull();
  expect(atomRows([{ coefficient: 1, formula: "H2", name: "hydrogen" }], [{ coefficient: 1, formula: "H2O", name: "water" }])).toBeNull();
});

test("the vat steps four dips and names each phase in its status", () => {
  expect(dipStatus(1, "rest")).toBe("Dip 1 of 4. In the air the cloth turns from green to blue.");
  expect(dipStatus(3, "lifted")).toBe("Dip 3 of 4. Lifted out, the cloth is green.");
  expect([nextDip(1), nextDip(3), nextDip(4)]).toEqual([2, 4, 1]);
  expect([currentFrame("rest"), currentFrame("in"), currentFrame("lifted"), currentFrame("air")]).toEqual(["air", "in", "lifted", "air"]);
});

test("the vat figure rests on its third frame with every sentence of the block cited once, the equation and its atom count", () => {
  const block = vat();
  const numbers = new Map([...signatureSentences(block).flatMap((sentence) => sentence.citations.map((citation) => citation.sourceId)), ...signatureSourceIds(block)].map((id, index): [string, number] => [id, index + 1]));
  const html = withApp(createElement(VatFigure, { block, number: 1 }), { numbers, sourcesById: new Map() });
  expect(html).toMatch(/Fig\.(?: |<!-- -->)+<b>1<\/b>/);
  expect(attribute(html, "vat-frames", "data-testid")).toHaveLength(1);
  expect([...html.matchAll(/data-frame="([a-z]+)"/g)].map((found) => found[1])).toEqual(["in", "lifted", "air"]);
  expect([...html.matchAll(/<li aria-current="step"[^>]*data-frame="([a-z]+)"/g)].map((found) => found[1])).toEqual(["air"]);
  expect(shownText(html)).toContain("Dip 1 of 4. In the air the cloth turns from green to blue.");
  expect(attribute(html, "vat-dip", "data-variant")).toEqual(["quiet"]);
  const drawn = attribute(html, "answer-sentence", "data-sentence-id");
  expect(new Set(drawn).size).toBe(drawn.length);
  expect(attribute(html, "citation-chip", "data-numbers").join(",")).not.toContain("·");
  if (block.forms.every((form) => form.compound?.formula)) {
    expect(attribute(html, "vat-equation", "aria-label")[0]).toContain("gives");
    expect(attribute(html, "vat-atoms", "data-testid")).toHaveLength(1);
  }
  expect(html).not.toMatch(/purple|field-|bg-card|text-white/);
});

test("every built signature figure draws as Fig. 1 with its own sentences", () => {
  for (let index = 0; index < FIGURES.length; index += 1) {
    const block = figure(index);
    const html = withApp(createElement(SignatureFigure, { block, number: 1 }));
    expect(attribute(html, "figure", "data-kind")).toEqual(["diagram"]);
    expect(attribute(html, "answer-sentence", "data-sentence-id")).toContain(signatureSentences(block)[0].id);
  }
});
