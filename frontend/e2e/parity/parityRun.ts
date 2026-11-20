import type { BrowserContext, ElementHandle, Page } from "@playwright/test";

import { AUTHORED_PATH, pageKind, type BorrowedCase, type SubjectPage } from "./parityBorrowed";
import { authoredRoot, drawing, gatedDifferences, generatedRoot, sanityProblems, widthAs, type SanityProblem } from "./parityComponent";
import { pixelDifference } from "./parityMeasure";
import { fullSizePictures } from "./parityPictures";
import { playersAtRest } from "./parityRest";
import type { StyleDifference } from "./parityStyles";

export type CaseResult = { label: string; kind: string; page: string; pageKind: string; found: boolean; widths: [number, number]; differences: StyleDifference[]; count: number; pixels: number | null };
export type Shots = (name: string, image: Buffer) => void;

const SETTLE_MS = 1500;
const KIT_TIMEOUT_MS = 30_000;
const STEP_MS = 30;
const SHOWN_DIFFERENCES = 40;
const SHOT_TIMEOUT_MS = 20_000;
const CHAPTER = "#chem";
const CHAPTER_QUALITY = 70;

async function scrolled(page: Page): Promise<void> {
  await page.evaluate(async (step) => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, step));
    }
    window.scrollTo(0, 0);
  }, STEP_MS);
}

export async function readPage(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "networkidle", timeout: 120_000 });
  await scrolled(page);
  await page.waitForFunction(() => "KV" in window, undefined, { timeout: KIT_TIMEOUT_MS }).catch(() => undefined);
  await scrolled(page);
  await page.waitForTimeout(SETTLE_MS);
  await fullSizePictures(page);
  await playersAtRest(page);
}

async function inView(page: Page, root: ElementHandle<Element>): Promise<void> {
  await root.scrollIntoViewIfNeeded().catch(() => undefined);
  await page.waitForTimeout(SETTLE_MS);
}

function fileName(label: string): string {
  return label.replace(/[^A-Za-z0-9-]+/g, "_");
}

async function shot(root: ElementHandle<Element>, type: "png" | "jpeg" = "png"): Promise<Buffer | null> {
  await root.scrollIntoViewIfNeeded().catch(() => undefined);
  const quality = type === "jpeg" ? CHAPTER_QUALITY : undefined;
  return root.screenshot({ animations: "disabled", timeout: SHOT_TIMEOUT_MS, scale: "css", type, quality }).catch(() => null);
}

async function pixels(approved: ElementHandle<Element>, rendered: ElementHandle<Element>, name: string, save: Shots): Promise<number | null> {
  const [before, after] = [await shot(approved), await shot(rendered)];
  if (before) save(`${name}.authored.png`, before);
  if (after) save(`${name}.page.png`, after);
  return before && after ? (await pixelDifference(before, after)).ratio : null;
}

function missing(found: BorrowedCase): CaseResult {
  return { label: found.label, kind: found.kind, page: found.page.path, pageKind: pageKind(found.page), found: false, widths: [0, 0], differences: [], count: 1, pixels: null };
}

export async function compareCase(authored: Page, rendered: Page, found: BorrowedCase, save: Shots): Promise<CaseResult> {
  const mine = await generatedRoot(rendered, found.label, found.frame);
  if (!mine || !found.root) return missing(found);
  const text = await mine.evaluate((element) => (element as HTMLElement).innerText ?? "");
  const theirs = await authoredRoot(authored, found.root, text);
  if (!theirs) return missing(found);
  await inView(authored, theirs);
  const approved = await drawing(theirs);
  const before = (await drawing(mine)).width;
  if (Math.abs(before - approved.width) > 1) await widthAs(mine, approved.width);
  await inView(rendered, mine);
  const shown = await drawing(mine);
  const differences = gatedDifferences(approved.styles, shown.styles);
  const ratio = await pixels(theirs, mine, `${fileName(found.page.slug)}--${fileName(found.label)}`, save);
  return { label: found.label, kind: found.kind, page: found.page.path, pageKind: pageKind(found.page), found: true, widths: [approved.width, before], differences: differences.slice(0, SHOWN_DIFFERENCES), count: differences.length, pixels: ratio };
}

export async function pageSanity(page: Page, subject: SubjectPage): Promise<SanityProblem[]> {
  const problems: SanityProblem[] = [];
  for (const component of subject.components) {
    const root = await page.$(`[data-component="${component.label.replace(/"/g, '\\"')}"]`);
    if (!root) continue;
    await inView(page, root);
    problems.push(...(await sanityProblems(page, component.label, root)));
  }
  return problems;
}

export async function chapterShot(page: Page, subject: SubjectPage, save: Shots): Promise<boolean> {
  const chapter = await page.$(CHAPTER);
  if (!chapter) return false;
  const image = await shot(chapter, "jpeg");
  if (image) save(`${fileName(subject.slug)}--chemistry.jpg`, image);
  return image !== null;
}

export type PassReport = { results: CaseResult[]; sanity: SanityProblem[]; chapters: string[] };

export async function borrowedPass(context: BrowserContext, cases: readonly BorrowedCase[], visits: readonly SubjectPage[], save: Shots): Promise<PassReport> {
  const authored = await context.newPage();
  await readPage(authored, AUTHORED_PATH);
  const report: PassReport = { results: [], sanity: [], chapters: [] };
  for (const visit of visits) {
    const page = await context.newPage();
    await readPage(page, visit.path);
    if (await chapterShot(page, visit, save)) report.chapters.push(visit.path);
    report.sanity.push(...(await pageSanity(page, visit)));
    for (const found of cases.filter((item) => item.page.path === visit.path)) report.results.push(await compareCase(authored, page, found, save));
    await page.close();
  }
  await authored.close();
  return report;
}

export function failures(report: PassReport): string[] {
  const unlike = report.results.filter((result) => !result.found || result.count > 0).map((result) => `${result.label} on ${result.page}: ${result.found ? `${result.count} differences` : "not found"}`);
  return [...unlike, ...report.sanity.map((problem) => `${problem.label}: ${problem.problem}`)];
}
