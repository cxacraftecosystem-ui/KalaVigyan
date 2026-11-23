import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { mainLines, openedPage } from "../monographNativeBrowser";
import { specFile } from "../monographMarkup";
import { lineDiff } from "../parity/parityMeasure";
import { restingVat } from "../parity/parityRest";
import { selfHostedFaces, servedFaces } from "../parity/parityStyles";
import { passPreviewProtection } from "../production/preview";

import { drawnStyles, elementProps, matchedForms, outerMarkup, placedOffsets, placeProbe, readSheets } from "./figureBrowser";
import { heldDifferences, figureDifferences, offsetDifferences, tally } from "./figureCheck";
import { selectorForms } from "./figureCss";
import { emptyFrame, figureFragment } from "./figureMarkup";
import { figureStyles, inheritedResidue, residueRule } from "./figureRules";

const LABEL = "kutch-ajrakh/geography/why-here";
const SCOPE = ".kv-why-here[data-app]";
const DRAWN = `${SCOPE} [data-testid="ground-neighbours"]`;
const ID_PREFIX = "kv-why-here";
const RENDERED = "/crafts/Kutch-Ajrakh/monograph";
const APPROVED = "/monographs/kutch-ajrakh/index.html";
const DOCUMENT = "/api/crafts/Kutch-Ajrakh/monograph";
const KIT_CSS = "/monographs/kit/monograph.css";
const REPORT_DIR = process.env.E2E_REPORT_DIR ?? "figure-run";
const STEP = process.env.E2E_FIGURE_STEP ?? "capture";
const CAPTURE_PROJECT = "figure-desktop-light";
const CAPTURE_WIDTH_PROJECTS = /^figure-desktop-/;
const SUMMARY = "figure.json";
const PROBE = "data-kv-probe";
const DRAWN_TIMEOUT_MS = 30_000;
const RUN_TIMEOUT_MS = 10 * 60_000;

type Served = { component: unknown; spec: unknown };

function save(name: string, body: unknown): void {
  mkdirSync(REPORT_DIR, { recursive: true });
  writeFileSync(join(REPORT_DIR, name), typeof body === "string" ? body : `${JSON.stringify(body, null, 1)}\n`);
}

function report(name: string, body: unknown): void {
  save(`${test.info().project.name}/${name}`, body);
}

async function prepared(context: BrowserContext): Promise<void> {
  mkdirSync(join(REPORT_DIR, test.info().project.name), { recursive: true });
  await passPreviewProtection(context, process.env.E2E_BASE_URL ?? "", process.env.E2E_VERCEL_BYPASS ?? "");
  await restingVat(context);
}

async function frameResidue(page: Page, markup: string, css: string): Promise<Record<string, string>> {
  const host = await page.evaluate((scope) => document.querySelector(scope)?.parentElement?.id ?? null, SCOPE);
  if (!host) throw new Error(`${SCOPE} sits in no chapter with an id`);
  const drawn = await page.evaluate(elementProps, SCOPE);
  const parent = await page.evaluate(elementProps, `#${host}`);
  const approved = await page.context().newPage();
  await approved.goto(APPROVED, { waitUntil: "load" });
  const placed = await approved.evaluate(placeProbe, { host: `#${host}`, markup: emptyFrame(markup, css), probe: PROBE, scope: SCOPE });
  const probe = placed ? await approved.evaluate(elementProps, `[${PROBE}]`) : null;
  await approved.close();
  if (!drawn || !parent || !probe) throw new Error(`The figure's frame could not be read in #${host} on both pages`);
  return inheritedResidue(drawn, parent, probe);
}

async function servedDocument(page: Page): Promise<Served> {
  const response = await page.request.get(DOCUMENT);
  expect(response.ok(), `${DOCUMENT} answers`).toBe(true);
  const document = (await response.json()) as { content: { components: { label: string }[] }; specs: Record<string, unknown> };
  const component = document.content.components.find((found) => found.label === LABEL);
  expect(component, `the served document places ${LABEL}`).toBeTruthy();
  return { component, spec: document.specs[LABEL] };
}

test("the ground figure is captured from the React page with the styles that draw it", async ({ context, page }) => {
  test.skip(STEP !== "capture" || test.info().project.name !== CAPTURE_PROJECT, "the figure is captured once, at 1440 in light");
  test.setTimeout(RUN_TIMEOUT_MS);
  await prepared(context);
  await openedPage(page, RENDERED);
  await page.locator(DRAWN).waitFor({ state: "attached", timeout: DRAWN_TIMEOUT_MS });
  const read = await page.evaluate(readSheets, KIT_CSS);
  const matched = await page.evaluate(matchedForms, { scope: SCOPE, forms: selectorForms(read) });
  const markup = await page.evaluate(outerMarkup, SCOPE);
  if (markup === null) throw new Error(`${SCOPE} is not on ${RENDERED}`);
  const styles = figureStyles(read, new Set(matched.hits), markup, SCOPE);
  const residue = await frameResidue(page, markup, styles.css);
  const css = [styles.css, residueRule(residue, SCOPE)].filter(Boolean).join("\n");
  const fragment = figureFragment(markup, css, ID_PREFIX);
  const served = await servedDocument(page);
  save("fragment.html", fragment);
  save("served-component.json", served.component);
  save("served-spec.json", served.spec);
  save(SUMMARY, { label: LABEL, scope: SCOPE, sheets: read.sheets, kit: read.kit, layers: read.layers, matched: styles.matched, tokens: styles.tokens, properties: styles.properties, structural: styles.structural, refused: matched.refused, residue, cssBytes: css.length, fragmentBytes: fragment.length, vars: styles.vars });
  expect(read.kit, `${KIT_CSS} is one of the React page's stylesheets`).toBeGreaterThanOrEqual(0);
  expect(served.spec, "the committed spec is the served document's").toEqual(JSON.parse(readFileSync(specFile(LABEL), "utf8")));
});

test("the rebuilt approved page reads and measures as the React page, and draws the figure alike", async ({ context, page }) => {
  test.skip(STEP !== "check", "the check runs after the build");
  test.setTimeout(RUN_TIMEOUT_MS);
  await prepared(context);
  const built = resolve(process.env.E2E_FIGURE_PAGE ?? "");
  await context.route(`**${APPROVED}`, (route) => route.fulfill({ path: built, contentType: "text/html; charset=utf-8" }));
  await openedPage(page, RENDERED);
  const approved = await context.newPage();
  await servedFaces(approved, await selfHostedFaces(page));
  await openedPage(approved, APPROVED);
  const text = lineDiff(await mainLines(approved), await mainLines(page));
  const offsets = offsetDifferences(await approved.evaluate(placedOffsets), await page.evaluate(placedOffsets));
  const vars = (JSON.parse(readFileSync(join(REPORT_DIR, SUMMARY), "utf8")) as { vars: string[] }).vars;
  const differences = figureDifferences(await approved.evaluate(drawnStyles, { scope: SCOPE, vars }), await page.evaluate(drawnStyles, { scope: SCOPE, vars }));
  const held = heldDifferences(differences, CAPTURE_WIDTH_PROJECTS.test(test.info().project.name));
  report("check.json", { text, offsets, held: held.slice(0, 200), heldCount: held.length, tally: tally(differences) });
  expect(text.onlyApproved.length + text.onlyRendered.length, "lines that differ (see check.json)").toBe(0);
  expect(offsets, "ids placed differently (see check.json)").toEqual([]);
  expect(held.length, "figure styles that differ (see check.json)").toBe(0);
});
