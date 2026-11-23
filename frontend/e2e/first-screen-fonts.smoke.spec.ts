import { mkdirSync, writeFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { facesDrawn, latinFaces, type DrawnText } from "./latinFaces";
import { contextOptions, SMALL_PHONE } from "./production/matrix";
import { smokeApiAddress } from "./smokeApi";

const FIRST_SCREENS = ["/crafts/Kutch-Ajrakh", "/", "/login"];
const SMOKE_PROJECT = "desktop";
const SETTLE_MS = 1500;

test.beforeAll(() => {
  test.skip(test.info().project.name !== SMOKE_PROJECT || smokeApiAddress() === null, "runs once, against the local build with its API at a local address");
});

async function firstScreenText(page: Page): Promise<DrawnText[]> {
  return page.evaluate(() => {
    const found: { family: string; style: string; weight: number; text: string }[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const element = node.parentElement;
      if (!element || !(node.textContent ?? "").trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const shown = [...range.getClientRects()].some((rect) => rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth);
      const style = getComputedStyle(element);
      if (!shown || style.visibility !== "visible" || Number(style.opacity) === 0) continue;
      const family = style.fontFamily.split(",")[0].replace(/["']/g, "").trim();
      found.push({ family, style: style.fontStyle === "normal" ? "normal" : "italic", weight: Number(style.fontWeight), text: node.textContent ?? "" });
    }
    return found;
  });
}

test("every Latin face the first screen draws at 360 is preloaded, and no other face is", async ({ browser }) => {
  const faces = latinFaces();
  const drawn: Record<string, string[]> = {};
  for (const path of FIRST_SCREENS) {
    const context = await browser.newContext(contextOptions(SMALL_PHONE, "light"));
    const page = await context.newPage();
    await page.goto(path, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    await page.waitForTimeout(SETTLE_MS);
    drawn[path] = [...facesDrawn(faces, await firstScreenText(page))].sort();
    await context.close();
  }
  mkdirSync(test.info().outputDir, { recursive: true });
  writeFileSync(test.info().outputPath("first-screen-faces.json"), JSON.stringify(drawn, null, 1));
  const union = [...new Set(Object.values(drawn).flat())].sort();
  const preloaded = faces.filter((face) => face.preloaded).map((face) => face.name).sort();
  expect(drawn["/crafts/Kutch-Ajrakh"].length, "Kutch Ajrakh's first screen draws Latin text").toBeGreaterThan(0);
  expect(union, `the faces the first screens draw (${JSON.stringify(drawn)})`).toEqual(preloaded);
});
