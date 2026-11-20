import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { test, type Page } from "@playwright/test";

import { passPreviewProtection } from "../production/preview";

import { partFileName, railStops, sliceTops, RAIL_STOPS } from "./captureParts";

const REPORT_DIR = process.env.E2E_REPORT_DIR ?? "capture-run";
const DEFAULT_PATHS = ["/", "/crafts", "/crafts/Kutch-Ajrakh", "/crafts/Bastar-Dhokra", "/crafts/Kasuti-Embroidery", "/categories/Textiles-Based-Craft-Category", "/map", "/login", "/ask"];
const BOARD = pathToFileURL(join(__dirname, "..", "..", "..", "docs", "design", "master-board.html")).href;
const BOARD_SCREENS = ["landing", "atlas", "craft", "answer", "uncurated", "urdu"];
const PARTS = [".kv-alt-comic", ".kv-doc-open", "dl.glance", ".kv-differs", ".rec-list", ".kv-entries"];
const PARTS_PER_SELECTOR = 3;
const MAX_HEIGHT_PX = 6000;
const SLICE_QUALITY = 72;
const RAIL_SHOT_PX = 320;
const SETTLE_MS = 1200;
const PART_SETTLE_MS = 700;
const PAGE_TIMEOUT_MS = 6 * 60_000;
const SHOT_TIMEOUT_MS = 15_000;

function screenPaths(): string[] {
  const asked = (process.env.E2E_SCREEN_PATHS ?? "").split(",").map((path) => path.trim()).filter(Boolean);
  return asked.length ? asked : DEFAULT_PATHS;
}

function fileStem(path: string): string {
  return path === "/" ? "landing" : path.replace(/^\/+/, "").replace(/[^A-Za-z0-9-]+/g, "_");
}

function save(name: string, image: Buffer): void {
  const folder = join(REPORT_DIR, test.info().project.name);
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, name), image);
}

async function settled(page: Page): Promise<void> {
  await page.evaluate(async () => {
    for (let y = 0; y < Math.min(document.body.scrollHeight, 6000); y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 40));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(SETTLE_MS);
}

async function capture(page: Page, top: number, height: number, type: "png" | "jpeg" = "png"): Promise<Buffer> {
  const width = page.viewportSize()?.width ?? 0;
  const quality = type === "jpeg" ? SLICE_QUALITY : undefined;
  return page.screenshot({ fullPage: true, animations: "disabled", type, quality, clip: { x: 0, y: top, width, height: Math.min(height, MAX_HEIGHT_PX) } });
}

async function partShots(page: Page, stem: string): Promise<void> {
  for (const selector of PARTS) {
    const parts = page.locator(selector);
    const count = Math.min(await parts.count(), PARTS_PER_SELECTOR);
    for (let at = 0; at < count; at += 1) {
      const part = parts.nth(at);
      if (!(await part.isVisible())) continue;
      await part.scrollIntoViewIfNeeded();
      await page.waitForTimeout(PART_SETTLE_MS);
      const shot = await part.screenshot({ animations: "disabled", timeout: SHOT_TIMEOUT_MS }).catch(() => null);
      if (shot) save(partFileName(stem, selector, at), shot);
    }
  }
}

async function railShots(page: Page, stem: string): Promise<void> {
  const rail = page.locator(".kv-rail").first();
  if (!(await rail.count()) || !(await rail.isVisible())) return;
  const links = await page.locator(".kv-rail a[href^='#']").evaluateAll((found) => found.map((link) => (link.getAttribute("href") ?? "").slice(1)));
  const stops = railStops(links);
  for (const stop of RAIL_STOPS) {
    const id = stops[stop];
    if (!id) continue;
    await page.evaluate((target) => document.getElementById(target)?.scrollIntoView({ block: "start" }), id);
    await page.waitForTimeout(PART_SETTLE_MS * 2);
    const width = page.viewportSize()?.width ?? 0;
    save(`${stem}-rail-${stop}.png`, await page.screenshot({ animations: "disabled", clip: { x: 0, y: 0, width, height: RAIL_SHOT_PX } }));
  }
}

for (const path of screenPaths()) {
  test(`the page ${path} as a reader sees it`, async ({ page }) => {
    test.setTimeout(PAGE_TIMEOUT_MS);
    await page.goto(path, { waitUntil: "networkidle" });
    await settled(page);
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    const stem = fileStem(path);
    for (const [at, top] of sliceTops(height, MAX_HEIGHT_PX).entries()) save(at ? `${stem}-${at + 1}.jpg` : `${stem}.png`, await capture(page, top, height - top, at ? "jpeg" : "png"));
    await partShots(page, stem);
    await railShots(page, stem);
  });
}

test.beforeEach(async ({ context }) => {
  await passPreviewProtection(context, process.env.E2E_BASE_URL ?? "", process.env.E2E_VERCEL_BYPASS ?? "");
});

test("the master board's screens at this width and theme", async ({ page }, info) => {
  const dark = info.project.name.endsWith("-dark");
  await page.addInitScript((theme) => localStorage.setItem("kv-theme", theme), dark ? "dark" : "light");
  await page.goto(BOARD, { waitUntil: "load" });
  await settled(page);
  for (const id of BOARD_SCREENS) {
    const box = await page.locator(`section.screen#${id}`).boundingBox();
    if (!box) continue;
    const top = box.y + (await page.evaluate(() => window.scrollY));
    save(`board-${id}.png`, await capture(page, top, box.height));
  }
});
