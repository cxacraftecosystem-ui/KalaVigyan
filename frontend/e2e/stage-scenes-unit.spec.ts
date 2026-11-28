import { expect, test, type Page } from "@playwright/test";

import { stagePlayerShape } from "../lib/componentSpecsSciencePlayers";
import type { MonographDocument } from "../lib/monographDocument";
import { parseShape, ShapeError } from "../lib/shape";

import { KIT_JS, playersDocument, playersHtml, STAGES } from "./playersFixture";

type Spec = Record<string, unknown>;

const KIT_SCENE = { parts: [{ part: "water", form: "sprinkled", label: "u7024" }] };
const FIRED_SCENE = { parts: [{ part: "heat", source: "fire", label: "u7023" }, { part: "water", form: "sprinkled", label: "u7024" }] };
const DRAWN_SCENE = {
  tag: "svg",
  attrs: { viewBox: "0 0 120 80" },
  children: [{ tag: "rect", attrs: { x: "4", y: "20", width: "14", height: "14", fill: "var(--sunk)", stroke: "var(--ink-1)" } }]
};

function stageSpec(document: MonographDocument): { stages: Spec[] } & Spec {
  return document.specs[STAGES] as { stages: Spec[] } & Spec;
}

function scened(): MonographDocument {
  const document = playersDocument();
  const stages = stageSpec(document).stages;
  stages[1].scene = KIT_SCENE;
  stages[2].scene = DRAWN_SCENE;
  return document;
}

async function opened(page: Page, document: MonographDocument): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.setContent(playersHtml("page", document), { waitUntil: "domcontentloaded" });
  await page.addScriptTag({ content: KIT_JS });
  for (const scope of ["chem", "pt"]) await expect(page.locator(`#${scope}-theme-toggle[aria-pressed]`)).toBeAttached();
}

async function shownAt(page: Page, stage: number): Promise<string | null> {
  const cloth = page.locator('[data-comp="cloth"]');
  await cloth.locator(".rb").nth(stage - 1).click();
  await expect(cloth.locator("[data-k]")).toHaveText(new RegExp(`^Stage ${stage} of `));
  return cloth.locator(".lc-big > svg").getAttribute("data-kit-scene");
}

test("a stage's own scene is read as a kit scene or a drawing, and the player's drawing still rests", () => {
  const spec = stageSpec(scened());
  const player = parseShape(stagePlayerShape, spec);
  expect(player.stages.map((stage) => (stage.scene ? ("parts" in stage.scene ? "kit" : "drawn") : null))).toEqual([null, "kit", "drawn", null, null]);
  expect(() => parseShape(stagePlayerShape, { ...spec, stages: [{ ...(spec.stages[0] as Spec), scene: { parts: [] } }, ...spec.stages.slice(1)] })).toThrow(ShapeError);
  expect(() => parseShape(stagePlayerShape, { ...spec, drawing: { ...FIRED_SCENE, motion: "take" } })).toThrow(ShapeError);
});

test("each stage with its own scene draws it beside its text and in the stage box when it is shown", async ({ page }) => {
  await opened(page, scened());
  const cloth = page.locator('[data-comp="cloth"]');
  const steps = cloth.locator(".lc-step");
  await expect(steps.nth(0).locator(".lc-scene")).toHaveCount(0);
  await expect(steps.nth(1).locator('.lc-scene svg.kv-kit-scene[data-kit-scene="stage-2"]')).toHaveCount(1);
  await expect(steps.nth(1).locator(".lc-scene .kv-kit-scene-key")).toContainText(/\S/);
  await expect(steps.nth(2).locator('.lc-scene svg.kv-kit-scene[data-kit-scene="stage-3"]')).toHaveAttribute("aria-hidden", "true");
  await expect(cloth.locator(".lc-big > svg")).toHaveAttribute("data-kit-scene", "stage");
  expect(await shownAt(page, 2)).toBe("stage-2");
  expect(await shownAt(page, 3)).toBe("stage-3");
});

test("a stage without its own scene keeps the nearest earlier stage's scene, or the player's drawing", async ({ page }) => {
  await opened(page, scened());
  expect(await shownAt(page, 1)).toBe("stage");
  expect(await shownAt(page, 2)).toBe("stage-2");
  expect(await shownAt(page, 4)).toBe("stage-3");
  expect(await shownAt(page, 5)).toBe("stage");
  await expect(page.locator('[data-comp="cloth"] .lc-big > svg')).toHaveCount(1);
});

test("a player with one scene for all its stages draws that scene at every stage, as before", async ({ page }) => {
  await opened(page, playersDocument());
  await expect(page.locator('[data-comp="cloth"] .lc-scene')).toHaveCount(0);
  for (const stage of [1, 3, 5]) expect(await shownAt(page, stage)).toBe("stage");
});
