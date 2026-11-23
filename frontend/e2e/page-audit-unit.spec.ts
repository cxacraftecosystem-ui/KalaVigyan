import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { renderChemistry } from "@/lib/chemistry";

import { auditPage, sidewaysProblems, type AuditOptions } from "./production/pageAudit";

const KATEX_CSS = readFileSync(join(__dirname, "..", "node_modules", "katex", "dist", "katex.min.css"), "utf8");
const OPTIONS: AuditOptions = { citedSelector: "[data-cited]", limit: 12 };
const ALUM_LAKE = "2 Al^3+ + 3 C14H6O2(OH)2 -> Al2(C14H6O2(O)2)3 + 6 H+";
const NARROW = "This sentence runs past its narrow box";

function pageWith(equation: string): string {
  return [
    "<!doctype html><html><head><style>",
    KATEX_CSS,
    "body{margin:0;font-size:16px} main{width:300px;padding:16px} .equation{display:block;max-width:100%;overflow-x:auto}",
    ".sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}",
    "</style></head><body><main>",
    `<p>Alum fixes the dye.<span class="sr-only">(read aloud)</span></p>`,
    `<span role="math" class="equation">${equation}</span>`,
    `<p data-testid="narrow" class="katex-mathml-note" style="width:40px;white-space:nowrap">${NARROW}</p>`,
    "</main></body></html>"
  ].join("");
}

test("the audit skips KaTeX's hidden MathML copy, and only it", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.setContent(pageWith(renderChemistry(ALUM_LAKE, true)));
  await expect(page.locator(".katex-mathml")).toHaveCount(1);
  const audited = await page.evaluate(auditPage, OPTIONS);
  await page.locator(".katex-mathml").evaluate((copy) => copy.remove());
  expect(audited).toEqual(await page.evaluate(auditPage, OPTIONS));
  expect(audited.textOverflow).toEqual([`main > p[data-testid="narrow"]: "${NARROW}" spills out of its box`]);
  expect(audited.copy.startsWith("Alum fixes the dye. (read aloud) ")).toBe(true);
  expect(audited.copy.endsWith(NARROW)).toBe(true);
  expect(audited.pageOverflowPx).toBe(0);
});

const FORMULA = "display:block;font-size:20px;line-height:1";
const CHARGE = "font-size:12px;line-height:0;vertical-align:10px";

function chargedPage(): string {
  return [
    "<!doctype html><html><head><style>body{margin:0} main{width:300px;padding:40px 16px}</style></head><body><main>",
    `<div><b data-testid="formula" style="${FORMULA}">Fe<sup style="${CHARGE}">3+</sup></b></div>`,
    `<div><b data-testid="lifted" style="${FORMULA}">Fe<sup style="${CHARGE};position:relative;top:-24px">2+</sup></b></div>`,
    "</main></body></html>"
  ].join("");
}

test("a charge set as a superscript may rise above its formula's line, but not out of it", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.setContent(chargedPage());
  const audited = await page.evaluate(auditPage, OPTIONS);
  expect(audited.textOverflow).toEqual(['main > div > b[data-testid="lifted"]: "2+" spills out of its box']);
});

test("a page that scrolls sideways names the outermost box past the screen, not its children", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const wide = `<figure data-testid="wide" style="width:380px;margin:0"><div style="width:380px;height:10px"></div></figure>`;
  await page.setContent(`<!doctype html><html><head><style>body{margin:0} main{padding:0 16px}</style></head><body><main><section data-testid="answer-view">${wide}<p>Short.</p></section></main></body></html>`);
  const audited = await page.evaluate(auditPage, OPTIONS);
  expect(audited.widest).toEqual(['main > section[data-testid="answer-view"] > figure[data-testid="wide"] (6px past the screen)']);
  expect(sidewaysProblems(audited)).toEqual([`the page scrolls sideways by ${audited.pageOverflowPx}px: ${audited.widest[0]}`]);
  expect(sidewaysProblems({ pageOverflowPx: 1, widest: [] })).toEqual([]);
});
