import { expect, test, type Browser, type Page } from "@playwright/test";

import { contextOptions, DESKTOP, SCHEMES, SMALL_PHONE, type Scheme, type Width } from "./production/matrix";
import { smokeApiAddress, TEMPLATE_CRAFT } from "./smokeApi";

const PATH = `/crafts/${TEMPLATE_CRAFT}/monograph`;
const TABLET_768: Width = { key: "tablet-768", label: "Tablet 768", device: "Galaxy Tab S9", viewport: { width: 768, height: 1024 } };
const WIDTHS: readonly Width[] = [SMALL_PHONE, TABLET_768, DESKTOP];
const SPREAD_FROM = 1200;
const REST_TIMEOUT_MS = 30_000;
const SCROLL_PAUSE_MS = 40;
const SMOKE_PROJECT = "desktop";

test.beforeAll(() => {
  test.skip(test.info().project.name !== SMOKE_PROJECT || smokeApiAddress() === null, "runs once, against the local build with its API at a local address");
});

async function opened(browser: Browser, width: Width, scheme: Scheme, errors: string[]): Promise<Page> {
  const context = await browser.newContext(contextOptions(width, scheme));
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(PATH, { waitUntil: "networkidle" });
  await page.evaluate(async (pause) => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, pause));
    }
  }, SCROLL_PAUSE_MS);
  await page.locator("#kv-src-kin").waitFor({ state: "attached", timeout: REST_TIMEOUT_MS });
  await page.evaluate(() => window.scrollTo(0, 0));
  return page;
}

async function shown(page: Page, selector: string): Promise<boolean[]> {
  return page.locator(selector).evaluateAll((nodes) => nodes.map((node) => getComputedStyle(node).display !== "none" && (node as HTMLElement).offsetWidth > 0));
}

async function checkParts(page: Page, width: Width): Promise<void> {
  const run = width.key;
  expect.soft(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), `${run}: sideways scroll`).toBeLessThanOrEqual(0);
  expect.soft(await shown(page, "header.kv-open h1.kv-q"), `${run}: the name`).toEqual([true]);
  expect.soft(await shown(page, ".kv-open-label"), `${run}: the label on the photograph`).toEqual([true]);
  expect.soft(await page.locator(".kv-open-prov").innerText(), `${run}: the counts`).toContain("2 more for the kin crafts");
  expect.soft((await shown(page, "nav.kv-toc li")).filter(Boolean), `${run}: the table of contents`).toHaveLength(5);
  expect.soft(await shown(page, "nav.subrail"), `${run}: the sub-rail`).toEqual([true]);
  expect.soft((await shown(page, ".src-group h3")).filter(Boolean), `${run}: the source groups`).toHaveLength(5);
  const notes = await shown(page, ".spread.kv-run > aside.margin.note");
  expect.soft(notes.length > 0 && notes.every((visible) => visible === width.viewport.width >= SPREAD_FROM), `${run}: margin notes from 1200px`).toBe(true);
}

for (const width of WIDTHS) {
  for (const scheme of SCHEMES) {
    test(`a generated craft page draws the approved masthead, contents, margin notes, sub-rail and source groups at ${width.key} in ${scheme}`, async ({ browser }) => {
      const errors: string[] = [];
      const page = await opened(browser, width, scheme, errors);
      await checkParts(page, width);
      await page.screenshot({ path: test.info().outputPath(`template-${width.key}-${scheme}.png`), fullPage: true, animations: "disabled" });
      expect.soft(errors, `${width.key}: errors the page threw`).toEqual([]);
      await page.context().close();
    });
  }
}
