import { mkdirSync } from "node:fs";
import { join } from "node:path";

import type { Page } from "@playwright/test";

import { contrastRatio, GRAPHIC_CONTRAST, PLACE_TONE_PAIRS, rgbOf, toneProblems } from "./contrast";
import type { ControlWatch } from "./controlWatch";
import { documentDrawn } from "./documentControls";
import { quiet } from "./pageVisit";
import { reportDir } from "./report";

export const PLACE_FIGURES = ["region-story", "seasons-strip", "supply-map", "map-layer-block", "why-here"] as const;
export const SHOTS_FOLDER = "place-figures";
export const SHOTS_PER_FIGURE = 2;

export type DrawnMark = { mark: string; selector: string; property: "stroke" | "fill" | "background-color"; ground: string };

export const DRAWN_MARKS: readonly DrawnMark[] = [
  { mark: "the drawn river course", selector: '[data-testid="river-course"]', property: "stroke", ground: "--map-land" },
  { mark: "a drawn story district", selector: '[data-testid="river-stage"] path[data-lgd][class*="terracotta"]', property: "stroke", ground: "--map-land" },
  { mark: "a drawn month of rainfall", selector: '[data-testid="rainfall-bars"] [data-month] > span', property: "background-color", ground: "--c-ground" },
  { mark: "a pin of the ground figure", selector: '[data-testid="ground-pin"]', property: "fill", ground: "--elevation-1" },
  { mark: "a river of the ground figure", selector: '[data-testid="ground-water"] path[data-rank]', property: "stroke", ground: "--elevation-1" }
];

const STILL_PASSED = "1";
const SCROLL_STEP_MS = 60;

async function scrollThrough(page: Page): Promise<void> {
  await page.evaluate(async (pause) => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, pause));
    }
    window.scrollTo(0, 0);
  }, SCROLL_STEP_MS);
  await quiet(page);
}

async function stillProblems(page: Page): Promise<string[]> {
  const flows = await page.locator('[data-testid="river-course"]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-flow") ?? ""));
  const passed = await page.locator('[data-testid="river-stage"]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-passed") ?? ""));
  return [
    ...(flows.some((flow) => flow !== "still") ? ["a river flows under reduced motion instead of resting drawn"] : []),
    ...(passed.some((value) => value !== STILL_PASSED) ? ["a river story rests short of its outlet under reduced motion"] : [])
  ];
}

export async function placeFigureShots(watch: ControlWatch, page: Page, target: string): Promise<string[]> {
  await scrollThrough(page);
  const folder = join(reportDir(), SHOTS_FOLDER, target.replace(/[^A-Za-z0-9-]+/g, "_"));
  mkdirSync(folder, { recursive: true });
  const shot: string[] = [];
  for (const id of PLACE_FIGURES) {
    const figures = page.getByTestId(id);
    const count = Math.min(await figures.count(), SHOTS_PER_FIGURE);
    for (let at = 0; at < count; at += 1) {
      const figure = figures.nth(at);
      await figure.scrollIntoViewIfNeeded();
      await figure.screenshot({ path: join(folder, `${id}-${at + 1}.png`), animations: "disabled" });
      shot.push(`${id} ${at + 1}`);
    }
  }
  watch.note(shot.length ? `captured ${shot.join(", ")} in dark mode with reduced motion` : "this page draws no place figure to capture");
  return stillProblems(page);
}

function markProblems(drawn: readonly (readonly [string, string, string])[]): string[] {
  return drawn.flatMap(([mark, paint, ground]) => {
    const [a, b] = [rgbOf(paint), rgbOf(ground)];
    if (!a || !b) return [];
    const ratio = contrastRatio(a, b);
    return ratio < GRAPHIC_CONTRAST ? [`dark: ${mark} is ${ratio.toFixed(2)}:1 on its ground, under ${GRAPHIC_CONTRAST}:1`] : [];
  });
}

export async function placeToneProblems(page: Page): Promise<string[]> {
  const names = [...new Set([...PLACE_TONE_PAIRS.flatMap((pair) => [pair.paint, pair.ground]), ...DRAWN_MARKS.map((mark) => mark.ground)])];
  const read = await page.evaluate(
    ({ wanted, marks }) => {
      const root = getComputedStyle(document.documentElement);
      const tokens = wanted.map((name) => [name, root.getPropertyValue(name).trim()] as const);
      const drawn = marks.flatMap((mark) => {
        const node = document.querySelector(mark.selector);
        return node ? [[mark.mark, getComputedStyle(node).getPropertyValue(mark.property), root.getPropertyValue(mark.ground).trim()] as const] : [];
      });
      const dark = document.documentElement.getAttribute("data-theme") === "dark" || window.matchMedia("(prefers-color-scheme: dark)").matches;
      return { tokens, drawn, dark };
    },
    { wanted: names, marks: DRAWN_MARKS }
  );
  if (!read.dark) return ["the page did not take the dark theme the reader's device asks for"];
  return [...toneProblems(new Map(read.tokens), "dark"), ...markProblems(read.drawn)];
}

export async function darkStillSession(watch: ControlWatch, page: Page, target: string): Promise<void> {
  await watch.step("Document drawn with its controls", () => documentDrawn(page));
  await watch.step("Place figures at rest in dark mode with reduced motion", () => placeFigureShots(watch, page, target));
  await watch.step("Place tones in dark mode", () => placeToneProblems(page));
}
