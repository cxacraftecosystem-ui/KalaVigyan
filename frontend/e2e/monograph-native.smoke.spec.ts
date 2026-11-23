import { mkdirSync, writeFileSync } from "node:fs";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { nativeComponents } from "./monographNative";
import { anchorPlans, mainLines, markAnchors, openedPage, pageAnswers, type AnchorPlan } from "./monographNativeBrowser";
import { lineDiff, pixelDifference, type PixelDifference } from "./parity/parityMeasure";
import { alignPhase } from "./parity/parityPhase";
import { restingVat } from "./parity/parityRest";
import { selfHostedFaces, servedFaces } from "./parity/parityStyles";
import { contextOptions, DESKTOP, SCHEMES, SMALL_PHONE, TABLET, type Scheme, type Width } from "./production/matrix";
import { FRAGMENT_VERSION, smokeApiAddress } from "./smokeApi";

const APPROVED = "/monographs/kutch-ajrakh/index.html";
const NATIVE = "/crafts/Kutch-Ajrakh/monograph";
const FRAGMENTS = `/crafts/Kutch-Ajrakh/v${FRAGMENT_VERSION}`;
const PIXEL_TOLERANCE = 0.02;
const SHOT_TIMEOUT_MS = 10_000;
const RUN_TIMEOUT_MS = 15 * 60_000;
const WIDTHS: readonly Width[] = [SMALL_PHONE, TABLET, DESKTOP];
const SMOKE_PROJECT = "desktop";
const REACT_FAILURE = /Minified React error|hydrat/i;

type Shot = PixelDifference | "missing" | "hidden";
type Pages = { approved: Page; native: Page; fragments: Page; errors: string[] };
type Run = { key: string; width: Width; scheme: Scheme };

test.beforeAll(() => {
  test.skip(test.info().project.name !== SMOKE_PROJECT || smokeApiAddress() === null, "runs once, against the local build with its API at a local address");
});

function differs(shot: Shot): boolean {
  return shot === "missing" || (typeof shot === "object" && shot.ratio > PIXEL_TOLERANCE);
}

function keep(name: string, body: Buffer | string): void {
  mkdirSync(test.info().outputDir, { recursive: true });
  writeFileSync(test.info().outputPath(name), body);
}

async function componentShot(pages: Pages, plan: AnchorPlan, run: Run): Promise<Shot> {
  const selector = `[data-native-parity="${plan.index}"]`;
  const before = pages.fragments.locator(selector);
  if (!(await before.count()) || !(await before.isVisible())) return "hidden";
  const left = await before.screenshot({ animations: "disabled", timeout: SHOT_TIMEOUT_MS }).catch(() => null);
  const right = await pages.native.locator(selector).screenshot({ animations: "disabled", timeout: SHOT_TIMEOUT_MS }).catch(() => null);
  if (!left || !right) return "missing";
  const shot = await pixelDifference(left, right);
  if (differs(shot)) {
    keep(`${run.key}-${plan.index}.fragment.png`, left);
    keep(`${run.key}-${plan.index}.native.png`, right);
    keep(`${run.key}-${plan.index}.fragment.html`, await before.evaluate((element) => element.outerHTML));
    keep(`${run.key}-${plan.index}.native.html`, await pages.native.locator(selector).evaluate((element) => element.outerHTML));
  }
  return shot;
}

async function reactPage(browser: Browser, run: Run, path: string, errors: string[]): Promise<Page> {
  const context = await browser.newContext(contextOptions(run.width, run.scheme));
  await restingVat(context);
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(`${path}: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && REACT_FAILURE.test(message.text())) errors.push(`${path}: ${message.text()}`);
  });
  await openedPage(page, path);
  return page;
}

async function allPages(browser: Browser, run: Run): Promise<Pages> {
  const errors: string[] = [];
  const native = await reactPage(browser, run, NATIVE, errors);
  const fragments = await reactPage(browser, run, FRAGMENTS, errors);
  const approved = await native.context().newPage();
  await servedFaces(approved, await selfHostedFaces(native));
  await openedPage(approved, APPROVED);
  return { approved, native, fragments, errors };
}

async function componentShots(pages: Pages, run: Run): Promise<Record<string, Shot>> {
  const plans = anchorPlans(nativeComponents());
  await markAnchors(pages.fragments, plans);
  await markAnchors(pages.native, plans);
  const shots: Record<string, Shot> = {};
  for (const plan of plans) shots[`${plan.index} ${plan.label}`] = await componentShot(pages, plan, run);
  return shots;
}

async function checkRun(browser: Browser, run: Run): Promise<void> {
  const pages = await allPages(browser, run);
  const text = lineDiff(await mainLines(pages.approved), await mainLines(pages.native));
  await alignPhase(pages.native, pages.fragments);
  const shots = await componentShots(pages, run);
  const answers = { approved: await pageAnswers(pages.approved), native: await pageAnswers(pages.native) };
  keep(`${run.key}-native-parity.json`, JSON.stringify({ text, shots, answers, errors: pages.errors }, null, 1));
  await pages.native.context().close();
  await pages.fragments.context().close();
  expect.soft(pages.errors, `${run.key}: errors the React pages threw`).toEqual([]);
  expect.soft(text.onlyApproved.length + text.onlyRendered.length, `${run.key}: lines that differ from the approved page`).toBe(0);
  expect.soft(answers.native, `${run.key}: a citation and the first figure answer as on the approved page`).toEqual(answers.approved);
  expect.soft(Object.keys(shots).filter((key) => differs(shots[key])), `${run.key}: native views that differ from their fragments`).toEqual([]);
}

test("Kutch Ajrakh's native views read and answer as the approved page and look as their fragments at 360, 834 and 1440 in light and dark", async ({ browser }) => {
  test.setTimeout(RUN_TIMEOUT_MS);
  for (const width of WIDTHS) {
    for (const scheme of SCHEMES) {
      const run = { key: `${width.key}-${scheme}`, width, scheme };
      await test.step(run.key, () => checkRun(browser, run));
    }
  }
});
