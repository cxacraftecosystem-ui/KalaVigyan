import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { STORY_TONES } from "@/components/answer/place/storyGeometry";
import { PLACE_TONE } from "@/components/map/DistrictLayer";
import { MapPatterns } from "@/components/map/MapBase";

import { FRONTEND } from "../moduleGraph";
import { contrastRatio, GRAPHIC_CONTRAST, pairRatio, PLACE_TONE_PAIRS, rgbOf, toneProblems } from "./contrast";

const TOKENS = readFileSync(join(FRONTEND, "app", "tokens.css"), "utf8");
const GENERATED = JSON.parse(readFileSync(join(FRONTEND, "..", ".claude", "skills", "kalavigyan-design", "references", "tokens.json"), "utf8")) as {
  dataviz: { map: Record<string, Record<string, { contrast?: Record<string, number> }>> };
};
const THEMES = { light: ":root", dark: ':root[data-theme="dark"]' } as const;

function declared(selector: string): Map<string, string> {
  const start = TOKENS.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`tokens.css opens no ${selector} block`);
  const body = TOKENS.slice(start, TOKENS.indexOf("}", start));
  return new Map([...body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((found) => [found[1], found[2].trim()]));
}

test("the contrast formula gives the WCAG ratios worked out by hand", () => {
  expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 9);
  expect(contrastRatio([255, 255, 255], [0, 0, 0])).toBeCloseTo(21, 9);
  expect(contrastRatio([119, 119, 119], [119, 119, 119])).toBe(1);
  expect(contrastRatio([119, 119, 119], [255, 255, 255])).toBeCloseTo(4.48, 2);
  expect([rgbOf("#7896A7"), rgbOf("224 145 108"), rgbOf("rgb(120, 150, 167)"), rgbOf("rgba(120, 150, 167, 0.5)")]).toEqual([[120, 150, 167], [224, 145, 108], [120, 150, 167], [120, 150, 167]]);
  expect([rgbOf("var(--map-river)"), rgbOf("300 0 0"), rgbOf("")]).toEqual([null, null, null]);
});

test("the river on land reads at the ratio the token generator records, in light and in dark", () => {
  const recorded = GENERATED.dataviz.map["map-river"];
  for (const [theme, selector] of Object.entries(THEMES)) {
    const ratio = pairRatio(declared(selector), PLACE_TONE_PAIRS[0]);
    expect(ratio, theme).not.toBeNull();
    expect(ratio ?? 0, theme).toBeCloseTo(recorded[theme].contrast?.land ?? 0, 2);
  }
});

test("every tone the place renderers draw in dark mode stands 3:1 or more off the ground it is drawn on", () => {
  const dark = declared(THEMES.dark);
  expect(toneProblems(dark, "dark")).toEqual([]);
  for (const pair of PLACE_TONE_PAIRS) expect(pairRatio(dark, pair) ?? 0, pair.mark).toBeGreaterThanOrEqual(GRAPHIC_CONTRAST);
  expect(toneProblems(declared(THEMES.light), "light")).toEqual([]);
  expect(toneProblems(new Map([["--map-river", "#262C3A"], ["--map-land", "#262C3A"]]), "dark")[0]).toBe("dark: the river course (--map-river on --map-land) is 1.00:1, under 3:1");
});

test("the place tones the renderers draw are the tokens the contrast check reads", () => {
  expect(PLACE_TONE).toContain("stroke-[var(--terracotta)]");
  expect(STORY_TONES.reached).toBe(PLACE_TONE);
  expect(STORY_TONES.waiting).toContain("stroke-terracotta");
  expect(renderToStaticMarkup(createElement("svg", null, createElement(MapPatterns)))).toContain('stroke="var(--terracotta)"');
  expect(declared(THEMES.light).get("--terracotta")).toBe("rgb(var(--c-terracotta))");
  for (const pair of PLACE_TONE_PAIRS) for (const token of [pair.paint, pair.ground]) expect(declared(THEMES.dark).has(token), token).toBe(true);
});
