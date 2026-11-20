import type { Locator, Page } from "@playwright/test";

import { RAIL_LINKS } from "../production/pageShapes";

import { citationMode, expectedProblems, flippedTheme, unchangedProblems, type CitationMode, type Theme } from "./controlPlan";
import { changedFrom, reached, type ControlWatch } from "./controlWatch";

const DRAW_TIMEOUT_MS = 30_000;
const QUICK_MS = 5_000;
const SCROLL_MS = 10_000;
const KIT_CITE = ".kcite:visible";
const ANSWER_CITE = '[data-testid="answer-block"] [data-testid="citation-chip"]:visible';
const MENU_BUTTON = "#kv-menu-btn";
const MENU = "#kv-menu";
const RAIL_PICK = 3;

type Surface = { open: boolean; mode: CitationMode | null };

export async function documentDrawn(page: Page): Promise<string[]> {
  const drawn = await page
    .locator(".kv-monograph h1")
    .first()
    .waitFor({ state: "visible", timeout: DRAW_TIMEOUT_MS })
    .then(
      () => true,
      () => false
    );
  if (!drawn) return [`the document draws no heading in ${DRAW_TIMEOUT_MS / 1000} s`];
  await page.waitForFunction(() => "KV" in window, undefined, { timeout: DRAW_TIMEOUT_MS }).catch(() => undefined);
  return (await page.evaluate(() => "KV" in window)) ? [] : ["the document's controls never started: its kit script did not load"];
}

function hash(page: Page): string {
  return decodeURIComponent(new URL(page.url()).hash);
}

async function chapterInView(page: Page, id: string): Promise<boolean> {
  return page.evaluate((target) => {
    const chapter = document.getElementById(target);
    if (!chapter) return false;
    const box = chapter.getBoundingClientRect();
    return box.top < window.innerHeight && box.bottom > 0;
  }, id);
}

export async function railJump(page: Page): Promise<string[]> {
  const links = page.locator(RAIL_LINKS);
  const count = await links.count();
  if (count < 2) return [`the chapter rail offers ${count} chapters`];
  const link = links.nth(Math.min(RAIL_PICK, count - 1));
  const target = (await link.getAttribute("href")) ?? "";
  const before = hash(page);
  await link.click();
  const after = await reached(async () => hash(page), target, SCROLL_MS);
  const current = await reached(async () => (await link.getAttribute("aria-current")) ?? "", "location", SCROLL_MS);
  const shown = await chapterInView(page, target.slice(1));
  return [
    ...unchangedProblems("the chapter rail", before, after),
    ...expectedProblems("the rail's current chapter", "location", current),
    ...(shown ? [] : [`the rail's ${target} link leaves its chapter off screen`])
  ];
}

export async function menuJump(page: Page): Promise<string[]> {
  const menu = page.locator(MENU);
  await page.locator(MENU_BUTTON).click();
  if (!(await menu.isVisible())) return ["the Chapters button opens no chapter menu"];
  const link = menu.locator('a[href^="#"]').nth(RAIL_PICK);
  const target = (await link.getAttribute("href")) ?? "";
  const before = hash(page);
  await link.click();
  const after = await reached(async () => hash(page), target, SCROLL_MS);
  const closed = await menu.waitFor({ state: "hidden", timeout: QUICK_MS }).then(
    () => true,
    () => false
  );
  return [...unchangedProblems("the chapter menu", before, after), ...(closed ? [] : ["the chapter menu stays open after a chapter is chosen"])];
}

async function shownTheme(page: Page): Promise<Theme> {
  return page.evaluate((): Theme => {
    const set = document.documentElement.getAttribute("data-theme");
    if (set === "dark" || set === "light") return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
}

export async function themeToggle(page: Page): Promise<string[]> {
  const menu = page.locator(MENU);
  await page.locator(MENU_BUTTON).click();
  const toggle = menu.getByRole("group", { name: "Display" }).getByRole("button", { name: "Dark" });
  const before = await shownTheme(page);
  await toggle.click();
  const after = await changedFrom(() => shownTheme(page), before, QUICK_MS);
  const pressed = (await toggle.getAttribute("aria-pressed")) ?? "";
  await toggle.click();
  const back = await changedFrom(() => shownTheme(page), after, QUICK_MS);
  await menu.locator(".kv-menu-close").click();
  return [
    ...expectedProblems("the theme toggle", flippedTheme(before), after),
    ...expectedProblems("the Dark tool's pressed state", after === "dark" ? "true" : "false", pressed),
    ...expectedProblems("the theme toggle pressed again", before, back)
  ];
}

async function surfaceOf(chip: Locator): Promise<Surface> {
  return chip.evaluate((node): Surface => {
    if (node.classList.contains("kcite")) {
      const pop = document.getElementById("kv-pop");
      if (!pop || pop.hidden) return { open: false, mode: null };
      return { open: true, mode: pop.classList.contains("sheet") ? "sheet" : "popover" };
    }
    const panel = document.getElementById(node.getAttribute("aria-controls") ?? "");
    if (!panel) return { open: false, mode: null };
    return { open: true, mode: panel.closest('[data-testid="sheet"]') ? "sheet" : "popover" };
  });
}

async function citationProblems(page: Page, chip: Locator, label: string): Promise<string[]> {
  const wanted = citationMode(page.viewportSize()?.width ?? 0);
  await chip.scrollIntoViewIfNeeded();
  await chip.click();
  const expanded = await reached(async () => (await chip.getAttribute("aria-expanded")) ?? "", "true", QUICK_MS);
  const opened = await surfaceOf(chip);
  await page.keyboard.press("Escape");
  const closed = await reached(async () => (await chip.getAttribute("aria-expanded")) ?? "", "false", QUICK_MS);
  if (expanded !== "true" || !opened.open) return [`${label} opens nothing`];
  return [...expectedProblems(`${label}'s surface`, wanted, opened.mode ?? "none"), ...expectedProblems(`${label} after Escape`, "false", closed)];
}

export async function citationClusters(page: Page): Promise<string[]> {
  const kit = page.locator(KIT_CITE).first();
  const answer = page.locator(ANSWER_CITE).first();
  const found = [(await kit.count()) ? kit : null, (await answer.count()) ? answer : null];
  if (!found[0] && !found[1]) return ["the document has no citation cluster to open"];
  const problems: string[] = [];
  if (found[0]) problems.push(...(await citationProblems(page, found[0], "a sentence's citation")));
  if (found[1]) problems.push(...(await citationProblems(page, found[1], "a figure's citation")));
  return problems;
}

export async function documentSession(watch: ControlWatch, page: Page): Promise<void> {
  await watch.step("Document drawn with its controls", () => documentDrawn(page));
  await watch.step("Document chapter rail", () => railJump(page));
  await watch.step("Document citation clusters", () => citationClusters(page));
}

export async function phoneDocumentSession(watch: ControlWatch, page: Page): Promise<void> {
  await watch.step("Document drawn with its controls", () => documentDrawn(page));
  await watch.step("Document theme toggle", () => themeToggle(page));
  await watch.step("Document chapter menu", () => menuJump(page));
  await watch.step("Document citation sheets", () => citationClusters(page));
}
