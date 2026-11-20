import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { passPreviewProtection } from "../production/preview";

import { driftSteps, heightDifferences, sectionHeights, type DriftReport } from "./parityDrift";
import { chapterIds, lineDiff, pixelDifference, type PixelDifference } from "./parityMeasure";
import { alignPhase } from "./parityPhase";
import { playersAtRest, restingVat } from "./parityRest";
import { ancestorLayers, chapterOffsets, elementStyles, fontReport, selfHostedFaces, servedFaces, styleDifferences, type StyleDifference } from "./parityStyles";

const APPROVED = "/monographs/kutch-ajrakh/index.html";
const RENDERED = "/crafts/Kutch-Ajrakh/monograph";
const REPORT_DIR = process.env.E2E_REPORT_DIR ?? "parity-run";
const SETTLE_MS = 1500;
const PIXEL_TOLERANCE = 0.02;
const SHOT_TIMEOUT_MS = 10_000;
const CHAPTERS_TIMEOUT_MS = 15 * 60_000;

async function opened(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "networkidle" });
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 30));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(SETTLE_MS);
  await playersAtRest(page);
}

async function mainText(page: Page): Promise<string[]> {
  const text = await page.evaluate(() => (document.querySelector("#kv-main") as HTMLElement | null)?.innerText ?? "");
  return text.split("\n").map((line) => line.replace(/\s+/g, " ").trim()).filter(Boolean);
}

function report(name: string, body: unknown): void {
  const folder = join(REPORT_DIR, test.info().project.name);
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, name), Buffer.isBuffer(body) ? body : JSON.stringify(body, null, 1));
}

async function bothPages(context: BrowserContext): Promise<{ approved: Page; rendered: Page }> {
  const rendered = await context.newPage();
  await opened(rendered, RENDERED);
  const approved = await context.newPage();
  await servedFaces(approved, await selfHostedFaces(rendered));
  await opened(approved, APPROVED);
  return { approved, rendered };
}

test.beforeEach(async ({ context }) => {
  await passPreviewProtection(context, process.env.E2E_BASE_URL ?? "", process.env.E2E_VERCEL_BYPASS ?? "");
  await restingVat(context);
});

test("the React page reads exactly as the approved page", async ({ context }) => {
  const { approved, rendered } = await bothPages(context);
  const diff = lineDiff(await mainText(approved), await mainText(rendered));
  report("text.json", diff);
  expect(diff.onlyApproved.length + diff.onlyRendered.length, "lines that differ (see text.json)").toBe(0);
});

async function driftReports(approved: Page, rendered: Page, offsets: { approved: Record<string, string>; rendered: Record<string, string> }): Promise<DriftReport[]> {
  const reports: DriftReport[] = [];
  for (const step of driftSteps(offsets.approved, offsets.rendered).slice(0, 6)) {
    const after = heightDifferences(await sectionHeights(approved, step.after), await sectionHeights(rendered, step.after));
    const before = heightDifferences(await sectionHeights(approved, step.before), await sectionHeights(rendered, step.before));
    reports.push({ step, differences: [...before, ...after] });
  }
  return reports;
}

test("every chapter of the React page looks as the approved page does", async ({ context }) => {
  test.setTimeout(CHAPTERS_TIMEOUT_MS);
  const { approved, rendered } = await bothPages(context);
  report("phase.json", { marginPx: await alignPhase(approved, rendered) });
  const ids = chapterIds(await approved.evaluate(() => [...document.querySelectorAll("main [id]")].map((element) => element.id)));
  const differences: Record<string, PixelDifference | "missing"> = {};
  const styles: Record<string, StyleDifference[]> = {};
  report("fonts.json", { approved: await fontReport(approved), rendered: await fontReport(rendered) });
  const offsets = { approved: await chapterOffsets(approved), rendered: await chapterOffsets(rendered) };
  report("offsets.json", offsets);
  report("drift.json", await driftReports(approved, rendered, offsets));
  const layers: Record<string, { approved: string[]; rendered: string[] }> = {};
  for (const id of ids) {
    const selector = `[id="${id}"]`;
    if (!(await rendered.locator(selector).count())) {
      differences[id] = "missing";
      continue;
    }
    if (!(await approved.locator(selector).first().isVisible())) continue;
    const before = await approved.locator(selector).first().screenshot({ animations: "disabled", timeout: SHOT_TIMEOUT_MS }).catch(() => null);
    if (!before) continue;
    const after = await rendered.locator(selector).first().screenshot({ animations: "disabled", timeout: SHOT_TIMEOUT_MS }).catch(() => null);
    if (!after) {
      differences[id] = "missing";
      continue;
    }
    const found = await pixelDifference(before, after);
    differences[id] = found;
    if (found.ratio > PIXEL_TOLERANCE) {
      report(`${id}.approved.png`, before);
      report(`${id}.rendered.png`, after);
      styles[id] = styleDifferences(await elementStyles(approved, id), await elementStyles(rendered, id));
      layers[id] = { approved: await ancestorLayers(approved, id), rendered: await ancestorLayers(rendered, id) };
    }
  }
  report("pixels.json", differences);
  report("styles.json", styles);
  report("layers.json", layers);
  const failing = Object.entries(differences).filter(([, found]) => found === "missing" || found.ratio > PIXEL_TOLERANCE);
  expect(failing.map(([id]) => id), "chapters that differ (see pixels.json)").toEqual([]);
});

test("a citation and the first figure answer as on the approved page", async ({ context }) => {
  const pages = { approved: await context.newPage(), rendered: await context.newPage() };
  const answers: Record<string, Record<string, string | null>> = {};
  for (const [name, page] of Object.entries(pages)) {
    await opened(page, name === "approved" ? APPROVED : RENDERED);
    const cite = page.locator("main .kcite").first();
    await cite.scrollIntoViewIfNeeded();
    await cite.click();
    const popover = page.locator("[role='dialog']:visible").first();
    const quote = (await popover.count()) ? await popover.innerText() : null;
    await page.keyboard.press("Escape");
    const dip = page.locator("#fig1 button").first();
    const before = await page.locator("#fig1").getAttribute("data-dips");
    if (await dip.count()) await dip.click();
    const after = await page.locator("#fig1").getAttribute("data-dips");
    answers[name] = { quote: quote?.replace(/\s+/g, " ").trim() ?? null, dipsBefore: before, dipsAfter: after };
  }
  report("interactions.json", answers);
  expect(answers.rendered).toEqual(answers.approved);
});
