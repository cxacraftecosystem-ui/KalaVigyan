import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { contextOptions, DESKTOP, WIDE, type Scheme } from "../production/matrix";
import { passPreviewProtection } from "../production/preview";

import { borrowedCases, pagesToVisit, subjectPages } from "./parityBorrowed";
import { driftSteps, heightDifferences, sectionHeights, type DriftReport } from "./parityDrift";
import { chapterIds, lineDiff, pixelDifference, type PixelDifference } from "./parityMeasure";
import { alignPhase } from "./parityPhase";
import { fullSizePictures } from "./parityPictures";
import { playersAtRest, restingVat } from "./parityRest";
import { borrowedPass, failures, type PassReport } from "./parityRun";
import { sharedOnce } from "./parityShared";
import { ancestorLayers, chapterOffsets, elementStyles, fontReport, selfHostedFaces, servedFaces, styleDifferences, type StyleDifference } from "./parityStyles";

const APPROVED = "/monographs/kutch-ajrakh/index.html";
const RENDERED = "/crafts/Kutch-Ajrakh/monograph";
const REPORT_DIR = process.env.E2E_REPORT_DIR ?? "parity-run";
const SETTLE_MS = 1500;
const KIT_TIMEOUT_MS = 30_000;
const PIXEL_TOLERANCE = 0.02;
const SHOT_TIMEOUT_MS = 10_000;
const CHAPTERS_TIMEOUT_MS = 15 * 60_000;
const BORROWED_TIMEOUT_MS = 40 * 60_000;
const CHECK = process.env.E2E_PARITY_CHECK ?? "all";
const BORROWED_ONLY = CHECK === "borrowed";

async function opened(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "networkidle" });
  await page.waitForFunction(() => "KV" in window, undefined, { timeout: KIT_TIMEOUT_MS }).catch(() => undefined);
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 30));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(SETTLE_MS);
  await fullSizePictures(page);
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
  test.skip(BORROWED_ONLY, "this run checks the borrowed components only");
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
  test.skip(BORROWED_ONLY, "this run checks the borrowed components only");
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
  test.skip(BORROWED_ONLY, "this run checks the borrowed components only");
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

async function wideContext(browser: Browser, scheme: Scheme): Promise<BrowserContext> {
  const base = process.env.E2E_BASE_URL ?? "";
  const context = await browser.newContext({ ...contextOptions(WIDE, scheme), baseURL: base || undefined });
  await passPreviewProtection(context, base, process.env.E2E_VERCEL_BYPASS ?? "");
  await restingVat(context);
  return context;
}

test("every component borrowed from Kutch Ajrakh draws on each page that places it as on Kutch Ajrakh's page", async ({ browser, context, page }) => {
  test.skip(CHECK === "monograph", "this run checks the Kutch Ajrakh page only");
  test.setTimeout(BORROWED_TIMEOUT_MS);
  const pages = await sharedOnce(REPORT_DIR, "borrowed-enumeration", () => subjectPages(context.request, process.env.E2E_BASE_URL ?? ""));
  const cases = borrowedCases(pages);
  const visits = pagesToVisit(cases, pages);
  report("borrowed-pages.json", { pages: pages.map(({ components, ...page }) => ({ ...page, components: components.map((found) => `${found.kind} ${found.label}`) })), cases: cases.map((found) => `${found.label} on ${found.page.path}`) });
  const scheme: Scheme = test.info().project.use.colorScheme === "dark" ? "dark" : "light";
  const passes: { width: number; context: BrowserContext }[] = [{ width: page.viewportSize()?.width ?? 0, context }];
  if (page.viewportSize()?.width === DESKTOP.viewport.width) passes.push({ width: WIDE.viewport.width, context: await wideContext(browser, scheme) });
  const reports: Record<string, PassReport> = {};
  for (const pass of passes) reports[String(pass.width)] = await borrowedPass(pass.context, cases, visits, (name, image) => report(`${pass.width}-${name}`, image));
  report("borrowed.json", reports);
  expect(cases.length, "components borrowed from Kutch Ajrakh (see borrowed-pages.json)").toBeGreaterThan(0);
  expect(Object.values(reports).flatMap(failures), "borrowed components that draw unlike their home (see borrowed.json)").toEqual([]);
});
