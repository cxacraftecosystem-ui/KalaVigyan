import { mkdirSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { goldenText, nativeComponents } from "./monographNative";
import { anchorPlans, mainLines, markAnchors, nativeDocumentPath, openedPage, pageAnswers, type AnchorPlan } from "./monographNativeBrowser";
import { lineDiff, pixelDifference, type PixelDifference } from "./parity/parityMeasure";
import { alignPhase } from "./parity/parityPhase";
import { selfHostedFaces, servedFaces } from "./parity/parityStyles";
import { contextOptions, DESKTOP, SCHEMES, SMALL_PHONE, TABLET, type Scheme, type Width } from "./production/matrix";

const APPROVED = "/monographs/kutch-ajrakh/index.html";
const RENDERED = "/crafts/Kutch-Ajrakh/monograph";
const PIXEL_TOLERANCE = 0.02;
const SHOT_TIMEOUT_MS = 10_000;
const RUN_TIMEOUT_MS = 17 * 60_000;
const WIDTHS: readonly Width[] = [SMALL_PHONE, TABLET, DESKTOP];
const SMOKE_PROJECT = "desktop";
const LOCAL_API = /^http:\/\/(127\.0\.0\.1|localhost):\d+$/;
const REACT_FAILURE = /Minified React error|hydrat/i;

type Shot = PixelDifference | "missing" | "hidden";
type Pages = { approved: Page; rendered: Page; errors: string[] };
type Run = { key: string; width: Width; scheme: Scheme };

let api: Server | null = null;

function apiAddress(): URL | null {
  const origin = process.env.API_ORIGIN ?? process.env.NEXT_PUBLIC_API_URL ?? "";
  return LOCAL_API.test(origin) ? new URL(origin) : null;
}

async function servedApi(address: URL): Promise<Server> {
  const body = goldenText();
  const server = createServer((request, response) => {
    if (request.method === "GET" && (request.url ?? "").split("?")[0] === nativeDocumentPath()) {
      response.writeHead(200, { "content-type": "application/json", "content-language": "en" });
      response.end(body);
      return;
    }
    request.socket.destroy();
  });
  await new Promise<void>((resolve, reject) => server.once("error", reject).listen(Number(address.port), address.hostname, resolve));
  return server;
}

test.beforeAll(async () => {
  const address = apiAddress();
  test.skip(test.info().project.name !== SMOKE_PROJECT || address === null, "runs once, against the local build with its API at a local address");
  if (address) api = await servedApi(address);
});

test.afterAll(async () => {
  const server = api;
  api = null;
  if (server) await new Promise<void>((resolve) => server.close(() => resolve()));
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
  const before = pages.approved.locator(selector);
  if (!(await before.count()) || !(await before.isVisible())) return "hidden";
  const left = await before.screenshot({ animations: "disabled", timeout: SHOT_TIMEOUT_MS }).catch(() => null);
  const right = await pages.rendered.locator(selector).screenshot({ animations: "disabled", timeout: SHOT_TIMEOUT_MS }).catch(() => null);
  if (!left || !right) return "missing";
  const shot = await pixelDifference(left, right);
  if (differs(shot)) {
    keep(`${run.key}-${plan.index}.approved.png`, left);
    keep(`${run.key}-${plan.index}.rendered.png`, right);
  }
  return shot;
}

async function bothPages(browser: Browser, run: Run): Promise<Pages> {
  const context = await browser.newContext(contextOptions(run.width, run.scheme));
  const rendered = await context.newPage();
  const errors: string[] = [];
  rendered.on("pageerror", (error) => errors.push(error.message));
  rendered.on("console", (message) => {
    if (message.type() === "error" && REACT_FAILURE.test(message.text())) errors.push(message.text());
  });
  await openedPage(rendered, RENDERED);
  const approved = await context.newPage();
  await servedFaces(approved, await selfHostedFaces(rendered));
  await openedPage(approved, APPROVED);
  return { approved, rendered, errors };
}

async function componentShots(pages: Pages, run: Run): Promise<Record<string, Shot>> {
  const plans = anchorPlans(nativeComponents());
  await markAnchors(pages.approved, plans);
  await markAnchors(pages.rendered, plans);
  const shots: Record<string, Shot> = {};
  for (const plan of plans) shots[`${plan.index} ${plan.label}`] = await componentShot(pages, plan, run);
  return shots;
}

async function checkRun(browser: Browser, run: Run): Promise<void> {
  const pages = await bothPages(browser, run);
  const text = lineDiff(await mainLines(pages.approved), await mainLines(pages.rendered));
  await alignPhase(pages.approved, pages.rendered);
  const shots = await componentShots(pages, run);
  const answers = { approved: await pageAnswers(pages.approved), rendered: await pageAnswers(pages.rendered) };
  keep(`${run.key}-native-parity.json`, JSON.stringify({ text, shots, answers, errors: pages.errors }, null, 1));
  await pages.rendered.context().close();
  expect.soft(pages.errors, `${run.key}: errors the React page threw`).toEqual([]);
  expect.soft(text.onlyApproved.length + text.onlyRendered.length, `${run.key}: lines that differ`).toBe(0);
  expect.soft(answers.rendered, `${run.key}: a citation and the first figure answer as on the approved page`).toEqual(answers.approved);
  expect.soft(Object.keys(shots).filter((key) => differs(shots[key])), `${run.key}: native views that differ`).toEqual([]);
}

test("Kutch Ajrakh's native views read, look and answer as the approved page at 360, 834 and 1440 in light and dark", async ({ browser }) => {
  test.setTimeout(RUN_TIMEOUT_MS);
  for (const width of WIDTHS) {
    for (const scheme of SCHEMES) {
      const run = { key: `${width.key}-${scheme}`, width, scheme };
      await test.step(run.key, () => checkRun(browser, run));
    }
  }
});
