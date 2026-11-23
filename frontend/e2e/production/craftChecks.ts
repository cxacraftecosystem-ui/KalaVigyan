import { expect, type Page, type Response } from "@playwright/test";

import { checkedCraftPage } from "@/lib/craftPageChecks";
import { CRAFT_PAGE_PATH, craftPageShape } from "@/lib/craftPageContract";
import { parseShape } from "@/lib/shape";

import { curatedOverviewProblems, overviewNote, type OverviewServed } from "./checks";
import { clickProblems } from "./clicks";
import { REST_WAIT_MS, documentProblems, recordProblems } from "./pageGates";
import { DOCUMENT_READ, DOCUMENT_ROOT, RAIL_LINKS, RECORD_ROOT, REST_HOLDER, documentShape, recordShape } from "./pageShapes";

export const CRAFT_TEMPLATES = {
  document: DOCUMENT_ROOT,
  tabbed: '[data-testid="craft-panel-overview"]',
  record: RECORD_ROOT
} as const;

export type CraftTemplate = keyof typeof CRAFT_TEMPLATES;

export const TEMPLATE_NOTES: Record<CraftTemplate, string> = {
  document: "drawn as its document",
  tabbed: "drawn on the tabbed page, the bridge for curated crafts",
  record: "drawn as a craft without a monograph"
};

export type CraftOutcome = { template: CraftTemplate | null; problems: string[]; notes: string[] };

const CRAFT_PAGE_TIMEOUT_MS = 30_000;
const TEMPLATE_TIMEOUT_MS = 30_000;

export function craftPageResponse(page: Page, slug: string): Promise<Response | null> {
  const path = `/api${CRAFT_PAGE_PATH(slug)}`;
  return page.waitForResponse((response) => new URL(response.url()).pathname === path, { timeout: CRAFT_PAGE_TIMEOUT_MS }).catch(() => null);
}

export async function drawnTemplate(page: Page): Promise<CraftTemplate | null> {
  const drawn = page.locator(Object.values(CRAFT_TEMPLATES).join(", ")).first();
  const shown = await drawn.waitFor({ state: "visible", timeout: TEMPLATE_TIMEOUT_MS }).then(
    () => true,
    () => false
  );
  if (!shown) return null;
  for (const template of Object.keys(CRAFT_TEMPLATES) as CraftTemplate[]) {
    if ((await page.locator(CRAFT_TEMPLATES[template]).count()) > 0) return template;
  }
  return null;
}

async function overviewOutcome(page: Page, served: Promise<Response | null>): Promise<{ problems: string[]; note: string | null }> {
  await expect(page.getByTestId("craft-panel-overview")).toBeVisible();
  const response = await served;
  if (!response) return { problems: [`the craft page route did not answer in ${CRAFT_PAGE_TIMEOUT_MS / 1000} s`], note: null };
  if (!response.ok()) return { problems: [`the craft page route answered ${response.status()}`], note: null };
  const body = checkedCraftPage(parseShape(craftPageShape, await response.json()));
  const summary: OverviewServed = {
    curated: body.curated,
    version: body.curation?.version ?? null,
    coverage: body.curation?.coverage ?? null,
    lede: body.overview.lede.length,
    keyFacts: body.overview.keyFacts.length
  };
  const shown = {
    lede: await page.getByTestId("craft-lede").getByTestId("answer-sentence").count(),
    keyFacts: await page.getByTestId("craft-key-facts").getByTestId("craft-fact").count()
  };
  return { problems: curatedOverviewProblems(summary, shown), note: overviewNote(summary) };
}

export async function documentOutcome(page: Page): Promise<string[]> {
  await page
    .locator(REST_HOLDER)
    .first()
    .waitFor({ state: "detached", timeout: REST_WAIT_MS })
    .catch(() => undefined);
  return documentProblems(await page.evaluate(documentShape, DOCUMENT_READ));
}

export function recordOutcome(page: Page): Promise<string[]> {
  return page.evaluate(recordShape, { root: RECORD_ROOT, rail: RAIL_LINKS }).then(recordProblems);
}

export async function craftOutcome(page: Page, served: Promise<Response | null>): Promise<CraftOutcome> {
  const template = await drawnTemplate(page);
  if (template === null) return { template, problems: [`the craft page drew none of its templates in ${TEMPLATE_TIMEOUT_MS / 1000} s`], notes: [] };
  const notes = [TEMPLATE_NOTES[template]];
  if (template === "document") return { template, problems: await documentOutcome(page), notes };
  if (template === "record") return { template, problems: await recordOutcome(page), notes };
  const overview = await overviewOutcome(page, served);
  return { template, problems: overview.problems, notes: overview.note ? [...notes, overview.note] : notes };
}

export async function openCraftTab(page: Page, label: string, panel: string, content: string): Promise<string[] | null> {
  const tab = page.getByRole("tab", { name: label, exact: true });
  if ((await tab.count()) === 0) return null;
  const refused = await clickProblems(page, tab, `the ${label} tab`);
  if (refused.length > 0) return refused;
  await expect(tab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId(panel)).toBeVisible();
  await expect(page.getByTestId(panel).getByTestId(content).first()).toBeVisible();
  return [];
}
