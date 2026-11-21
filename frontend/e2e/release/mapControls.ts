import type { Locator, Page } from "@playwright/test";

import { DISTRICT_PARAM } from "@/lib/districtView";
import { LAYER_PARAM } from "@/lib/mapLayers";
import { PHYSICAL_LAYERS } from "@/lib/mapPhysical";

import { NO_LAYER_LABEL } from "../production/checks";

import { layerSwitches, optionIndex, switchKinds, unchangedProblems, type LayerChoice } from "./controlPlan";
import { changedFrom, ERROR_SCREEN, type ControlWatch } from "./controlWatch";

const LAYER_TIMEOUT_MS = 30_000;
const TOGGLE_TIMEOUT_MS = 5_000;
const DISTRICT_TIMEOUT_MS = 30_000;
const PICKER = '[data-testid="layer-picker"] [data-searchable-select]';
const LAND = PHYSICAL_LAYERS.length;

type Point = { x: number; y: number; lgd: string };

function param(page: Page, name: string): string {
  return new URL(page.url()).searchParams.get(name) ?? "";
}

function drawnLayer(page: Page, id: string): Locator {
  if (!id) return page.getByTestId("map-states-plot");
  if (PHYSICAL_LAYERS.some((layer) => layer.id === id)) return page.locator(`[data-testid="physical-layer"][data-layer="${id}"] [data-testid="map-canvas"]`);
  return page.locator('[data-testid="choropleth-legend"]');
}

async function districtLayers(page: Page): Promise<number> {
  await page.locator(PICKER).click();
  const options = await page.getByRole("option").count();
  await page.keyboard.press("Escape");
  return Math.max(0, options - 1 - LAND);
}

async function pickOption(page: Page, choice: LayerChoice): Promise<string> {
  await page.locator(PICKER).click();
  const index = optionIndex(choice, LAND);
  const option = index === null ? page.getByRole("option").filter({ hasText: NO_LAYER_LABEL }).first() : page.getByRole("option").filter({ hasNotText: NO_LAYER_LABEL }).nth(index);
  const label = ((await option.innerText()).trim().split(/\r?\n/)[0] ?? "").trim();
  await option.click();
  return label;
}

async function chooseLayer(watch: ControlWatch, page: Page, choice: LayerChoice, kind: string): Promise<string[]> {
  const before = param(page, LAYER_PARAM);
  const label = await pickOption(page, choice);
  watch.note(`chose "${label}"`);
  const after = await changedFrom(async () => param(page, LAYER_PARAM), before, LAYER_TIMEOUT_MS);
  const moved = unchangedProblems(`choosing "${label}" (${kind})`, before || NO_LAYER_LABEL, after || NO_LAYER_LABEL);
  if (moved.length) return moved;
  const drawn = await drawnLayer(page, after)
    .or(page.locator(ERROR_SCREEN))
    .first()
    .waitFor({ state: "visible", timeout: LAYER_TIMEOUT_MS })
    .then(
      () => true,
      () => false
    );
  if (await page.locator(ERROR_SCREEN).count()) return [`choosing "${label}" (${kind}) shows the error screen`];
  return drawn ? [] : [`"${label}" (${kind}) draws nothing in ${LAYER_TIMEOUT_MS / 1000} s`];
}

async function firstOnLayer(watch: ControlWatch, page: Page, kind: LayerChoice["kind"]): Promise<void> {
  if (kind === "land") await watch.step("Map craft places toggle on a land layer", () => togglePlaces(page));
  if (kind !== "districts") return;
  await watch.step("Map district picked and its panel closed", () => pickDistrict(page));
  await watch.step("Map craft places toggle on a district layer", () => togglePlaces(page));
}

export async function walkMapLayers(watch: ControlWatch, page: Page): Promise<void> {
  const walk = layerSwitches(LAND, await districtLayers(page));
  const kinds = switchKinds(walk);
  const seen = new Set<LayerChoice["kind"]>();
  for (const [at, choice] of walk.entries()) {
    await watch.step(`Map layer switch ${at + 1}, ${kinds[at]}`, () => chooseLayer(watch, page, choice, kinds[at]));
    if (seen.has(choice.kind)) continue;
    seen.add(choice.kind);
    await firstOnLayer(watch, page, choice.kind);
  }
}

async function placeMarkers(page: Page): Promise<string> {
  return String(await page.getByTestId("place-marker").count());
}

export async function togglePlaces(page: Page): Promise<string[]> {
  const toggle = page.getByTestId("places-toggle");
  const checked = async () => (await toggle.getAttribute("aria-checked")) ?? "";
  const before = await checked();
  const markers = await placeMarkers(page);
  await toggle.click();
  const after = await changedFrom(checked, before, TOGGLE_TIMEOUT_MS);
  const shown = await changedFrom(() => placeMarkers(page), markers, TOGGLE_TIMEOUT_MS);
  const problems = [...unchangedProblems("the craft places toggle", before, after), ...unchangedProblems("the craft places on the map", `${markers} discs`, `${shown} discs`)];
  await toggle.click();
  return [...problems, ...unchangedProblems("the craft places toggle turned back", after, await changedFrom(checked, after, TOGGLE_TIMEOUT_MS))];
}

function insideLargestDistrict(): Point | null {
  const paths = Array.from(document.querySelectorAll<SVGPathElement>('[data-testid="district-fills"] path[data-lgd]'));
  const area = (path: SVGPathElement) => {
    const box = path.getBoundingClientRect();
    return box.width * box.height;
  };
  const largest = paths.sort((a, b) => area(b) - area(a)).slice(0, 5);
  for (const path of largest) {
    const box = path.getBoundingClientRect();
    for (let row = 1; row < 8; row += 1) {
      for (let column = 1; column < 8; column += 1) {
        const x = box.left + (box.width * column) / 8;
        const y = box.top + (box.height * row) / 8;
        if (document.elementFromPoint(x, y) === path) return { x, y, lgd: path.getAttribute("data-lgd") ?? "" };
      }
    }
  }
  return null;
}

export async function pickDistrict(page: Page): Promise<string[]> {
  await page.getByTestId("district-fills").scrollIntoViewIfNeeded();
  const point = await page.evaluate(insideLargestDistrict);
  if (!point) return ["no district on the map can be clicked"];
  await page.mouse.click(point.x, point.y);
  const picked = await changedFrom(async () => param(page, DISTRICT_PARAM), "", DISTRICT_TIMEOUT_MS);
  if (picked !== point.lgd) return [`clicking district ${point.lgd} picked "${picked}"`];
  const view = page.getByTestId("district-view");
  await view.waitFor({ state: "visible", timeout: DISTRICT_TIMEOUT_MS });
  await view.getByRole("button", { name: "Close the district" }).click();
  const closed = await changedFrom(async () => param(page, DISTRICT_PARAM), picked, DISTRICT_TIMEOUT_MS);
  const panel = await page.getByTestId("district-panel").count();
  return [...unchangedProblems("closing the district panel", picked, closed), ...(panel ? ["the district panel stays open after Close the district"] : [])];
}
