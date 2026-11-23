import { mkdirSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { firstScreen, latinPreloads, latinUses, type FaceUse } from "./firstScreenFonts";
import { contextOptions, SMALL_PHONE } from "./production/matrix";
import { smokeApiAddress } from "./smokeApi";

const FIRST_SCREENS = ["/crafts/Kutch-Ajrakh/monograph", "/", "/login"];
const SMOKE_PROJECT = "desktop";
const SETTLE_MS = 1500;

type Measured = { uses: FaceUse[]; preloaded: string[] };

test.beforeAll(() => {
  test.skip(test.info().project.name !== SMOKE_PROJECT || smokeApiAddress() === null, "runs once, against the local build with its API at a local address");
});

test("the first screens at 360 preload every Latin face they draw, so their type never swaps, and no face none of them draws", async ({ browser }) => {
  const measured: Record<string, Measured> = {};
  for (const path of FIRST_SCREENS) {
    const context = await browser.newContext(contextOptions(SMALL_PHONE, "light"));
    const page = await context.newPage();
    await page.goto(path, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    await page.waitForTimeout(SETTLE_MS);
    const screen = await firstScreen(page);
    measured[path] = { uses: latinUses(screen), preloaded: latinPreloads(screen) };
    await context.close();
  }
  mkdirSync(test.info().outputDir, { recursive: true });
  writeFileSync(test.info().outputPath("first-screen-faces.json"), JSON.stringify(measured, null, 1));
  for (const [path, found] of Object.entries(measured)) {
    expect(found.uses.length, `${path} draws Latin text on its first screen`).toBeGreaterThan(0);
    expect(found.uses.filter((use) => !found.preloaded.includes(use.url)), `${path}: faces its first screen draws that it does not preload`).toEqual([]);
  }
  const drawn = [...new Set(Object.values(measured).flatMap((found) => found.uses.map((use) => use.url)))].sort();
  const preloaded = [...new Set(Object.values(measured).flatMap((found) => found.preloaded))].sort();
  expect(preloaded.filter((url) => !drawn.includes(url)), `faces preloaded that no first screen draws (${JSON.stringify(measured)})`).toEqual([]);
});
