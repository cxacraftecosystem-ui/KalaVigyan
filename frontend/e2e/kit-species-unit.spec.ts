import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { kitIds } from "../components/artkit/kitIds";
import { KitSceneArt } from "../components/artkit/KitScene";
import { ART_KIT } from "../lib/artKit";
import { kitSceneShape, type KitScene } from "../lib/componentSpecsKitScene";
import { parseShape, ShapeError } from "../lib/shape";

import { drawingProblems } from "./parity/drawingChecks";

const IDS = kitIds("test-craft/chemistry/alizarin-player");
const UNCOLOURED = /^draws (\d+) species with no colour, each an empty outline in its scene: give each its material or its mark \(clear, gas or ion\)$/;

function species(role: string, label: string, colour: Record<string, string> = {}): Record<string, unknown> {
  return { part: "species", role, label, ...colour };
}

function scene(parts: Record<string, unknown>[]): KitScene {
  return parseShape(kitSceneShape, { parts, motion: "react" });
}

function drawn(parts: Record<string, unknown>[]): string {
  return renderToStaticMarkup(createElement(KitSceneArt, { scene: scene(parts), ids: IDS, name: "r1" }));
}

const EMPTY = [species("reactant", "u5009"), species("reagent", "u5018"), species("product", "u5011", { material: "--dye-madder" })];
const FILLED = [species("reactant", "u5009", { material: "--dye-madder" }), species("reagent", "u5018", { mark: "gas" }), species("product", "u5011", { material: "--dye-madder" })];

test("a colourless species takes the lane's marks, one way to be drawn, and no other word", () => {
  expect(ART_KIT.parts.species.choices.mark).toEqual(["clear", "gas", "ion"]);
  for (const mark of ART_KIT.parts.species.choices.mark) expect(scene([species("reagent", "u1", { mark }), species("product", "u2")]).parts[0]).toMatchObject({ mark });
  expect(() => scene([species("reagent", "u1", { mark: "liquid" }), species("product", "u2")])).toThrow(ShapeError);
});

test("a species is drawn in its material, a colourless one by its mark, and only one with neither as a dashed outline that says so", () => {
  const filled = drawn(FILLED);
  expect(filled).not.toContain("data-kit-uncoloured");
  expect(filled).not.toContain("stroke-dasharray");
  expect(filled).toContain('data-kit-mark="gas"');
  const empty = drawn(EMPTY);
  expect(empty.match(/data-kit-uncoloured=""/g)).toHaveLength(2);
  expect(empty.match(/stroke-dasharray="6 4"/g)).toHaveLength(2);
  for (const mark of ["clear", "ion"]) {
    const marked = drawn([species("reagent", "u1", { mark }), species("product", "u2", { material: "--dye-kut" })]);
    expect(marked).toContain(`data-kit-mark="${mark}"`);
    expect(marked).not.toContain("stroke-dasharray");
  }
});

test("the release's drawing checks name a scene's species with no colour and pass one whose species each have a colour or a mark", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.setContent(`<div data-component="t/empty" style="width:240px">${drawn(EMPTY)}</div><div data-component="t/filled" style="width:240px">${drawn(FILLED)}</div>`);
  const empty = await page.$('[data-component="t/empty"]');
  const filled = await page.$('[data-component="t/filled"]');
  if (!empty || !filled) throw new Error("the scenes are not on the fixture page");
  const named = await drawingProblems(page, empty);
  expect(named.map((problem) => UNCOLOURED.exec(problem)?.[1]).filter(Boolean)).toEqual(["2"]);
  expect((await drawingProblems(page, filled)).filter((problem) => UNCOLOURED.test(problem))).toEqual([]);
});
