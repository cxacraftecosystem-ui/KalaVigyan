import { expect, type Locator, type Page } from "@playwright/test";

import { PHYSICAL_LAYERS } from "@/lib/mapPhysical";

import type { User } from "@/lib/types";

import { NO_LAYER_LABEL, clip, labelProblems, navExpectation } from "./checks";
import { essayProblems, hubProblems } from "./pageGates";
import { ESSAY_ROOT, HUB_ROOT, essayShape, hubShape } from "./pageShapes";

const LAYER_TIMEOUT_MS = 30_000;
const COMPARE_TIMEOUT_MS = 30_000;
const MAP_TIMEOUT_MS = 30_000;
const ESSAY_TIMEOUT_MS = 60_000;
const MAP_TITLE = "Map";

export async function depthProblems(page: Page, user: User): Promise<string[]> {
  const expected = navExpectation(user.role);
  if (!expected) return [];
  const shown = await page.getByRole("group", { name: "Depth" }).getByRole("button").allInnerTexts();
  return labelProblems("the Depth choice", expected.depths, shown);
}

export async function comparisonProblems(page: Page): Promise<string[]> {
  const table = page.getByTestId("comparison");
  const outcome = table.or(page.getByTestId("compare-empty")).or(page.getByTestId("compare-unknown")).or(page.getByRole("main").getByRole("alert"));
  await expect(outcome.first()).toBeVisible({ timeout: COMPARE_TIMEOUT_MS });
  if (await table.isVisible()) return [];
  return [`the pair shows no comparison: "${clip(await outcome.first().innerText())}"`];
}

export async function mapProblems(page: Page): Promise<string[]> {
  await expect(page.getByRole("heading", { level: 1, name: MAP_TITLE, exact: true })).toBeVisible();
  const ranked = page.getByTestId("ranked-list").first();
  const drawn = await ranked.waitFor({ state: "visible", timeout: MAP_TIMEOUT_MS }).then(
    () => true,
    () => false
  );
  if (!drawn) return [`the map draws no ranked list beside it in ${MAP_TIMEOUT_MS / 1000} s`];
  return (await ranked.getByTestId("ranked-row").count()) > 0 ? [] : ["the ranked list beside the map ranks nothing"];
}

const PHYSICAL_IDS = new Set(PHYSICAL_LAYERS.map((layer) => layer.id as string));
const ERROR_SCREEN = 'section[data-testid^="error-"]';
const DISTRICT_LAYERS_WALKED = 2;

export type LayerWalk = { problems: string[]; layers: string[] };

export function layerWalkOrder(physical: number, district: number): number[] {
  const own = Array.from({ length: physical }, (_, index) => index);
  const values = Array.from({ length: Math.min(district, DISTRICT_LAYERS_WALKED) }, (_, index) => physical + index);
  return [...own, ...values, ...own.slice(0, 1)];
}

export async function walkLayers(page: Page): Promise<LayerWalk> {
  const picker = page.getByTestId("layer-picker");
  if ((await picker.count()) === 0) return { problems: ["the map offers no layer to choose"], layers: [] };
  const layers: string[] = [];
  for (const index of layerWalkOrder(PHYSICAL_LAYERS.length, DISTRICT_LAYERS_WALKED)) {
    const chosen = await chooseLayer(page, picker, index);
    layers.push(chosen.layer);
    if (chosen.problems.length) return { problems: chosen.problems, layers };
  }
  return { problems: [], layers };
}

async function chooseLayer(page: Page, picker: Locator, index: number): Promise<{ problems: string[]; layer: string }> {
  const before = new URL(page.url()).searchParams.get("layer");
  await picker.locator("[data-searchable-select]").click();
  const option = page.getByRole("option").filter({ hasNotText: NO_LAYER_LABEL }).nth(index);
  const label = (await option.innerText()).trim().split(/\r?\n/)[0];
  await option.click();
  await page.waitForURL((url) => url.searchParams.get("layer") !== null && url.searchParams.get("layer") !== before, { timeout: LAYER_TIMEOUT_MS });
  const id = new URL(page.url()).searchParams.get("layer") ?? "";
  const drawn = PHYSICAL_IDS.has(id) ? page.locator(`[data-testid="physical-layer"][data-layer="${id}"] [data-testid="map-canvas"]`) : page.getByTestId("choropleth-legend");
  const settled = await drawn
    .or(page.locator(ERROR_SCREEN))
    .first()
    .waitFor({ state: "visible", timeout: LAYER_TIMEOUT_MS })
    .then(
      () => true,
      () => false
    );
  if (await page.locator(ERROR_SCREEN).count()) return { problems: [`choosing "${label}" after "${before ?? NO_LAYER_LABEL}" shows the error screen`], layer: label };
  if (!settled) return { problems: [`"${label}" draws nothing in ${LAYER_TIMEOUT_MS / 1000} s`], layer: label };
  if (!PHYSICAL_IDS.has(id)) await expect(page.getByTestId("district-fills")).toBeAttached({ timeout: LAYER_TIMEOUT_MS });
  return { problems: [], layer: label };
}

export async function hubOutcome(page: Page, family: string): Promise<{ problems: string[]; notes: string[] }> {
  await expect(page.locator(HUB_ROOT)).toBeVisible();
  return hubProblems(await page.evaluate(hubShape, HUB_ROOT), family);
}

export async function savedAnswerHref(page: Page): Promise<string | null> {
  const first = page.getByTestId("saved-explainer").first().locator("a").first();
  const listed = await page
    .getByTestId("saved-list")
    .or(page.getByTestId("saved-empty"))
    .first()
    .waitFor({ state: "visible", timeout: ESSAY_TIMEOUT_MS })
    .then(
      () => true,
      () => false
    );
  if (!listed || (await first.count()) === 0) return null;
  return first.getAttribute("href");
}

export async function essayOutcome(page: Page): Promise<string[]> {
  await expect(page.locator(ESSAY_ROOT)).toBeVisible({ timeout: ESSAY_TIMEOUT_MS });
  await expect(page.getByTestId("answer-progress")).toHaveCount(0, { timeout: ESSAY_TIMEOUT_MS });
  return essayProblems(await page.evaluate(essayShape, ESSAY_ROOT));
}
