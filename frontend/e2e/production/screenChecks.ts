import { expect, type Page } from "@playwright/test";

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

export async function chooseFirstLayer(page: Page): Promise<{ problems: string[]; layer: string | null }> {
  const picker = page.getByTestId("layer-picker");
  if ((await picker.count()) === 0) return { problems: ["the map offers no environment layer to choose"], layer: null };
  await picker.locator("[data-searchable-select]").click();
  const option = page.getByRole("option").filter({ hasNotText: NO_LAYER_LABEL }).first();
  const layer = (await option.innerText()).trim();
  await option.click();
  await page.waitForURL(/[?&]layer=/, { timeout: LAYER_TIMEOUT_MS });
  await expect(page.getByTestId("choropleth-legend")).toBeVisible({ timeout: LAYER_TIMEOUT_MS });
  await expect(page.getByTestId("district-fills")).toBeAttached({ timeout: LAYER_TIMEOUT_MS });
  return { problems: [], layer };
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
