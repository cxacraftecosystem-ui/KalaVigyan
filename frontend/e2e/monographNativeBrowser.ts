import type { Page } from "@playwright/test";

import { MONOGRAPH_DOCUMENT_PATH, type MonographComponent } from "../lib/monographDocument";

import { tokenize, type Open } from "./monographMarkup";
import { servedMain } from "./monographNative";
import { fullSizePictures } from "./parity/parityPictures";
import { playersAtRest } from "./parity/parityRest";

export type AnchorPlan = { label: string; index: number; id: string | null; attribute: [string, string] | null; classes: string[]; nth: number };

const BY_ID = /^#([\w-]+)$/;
const BY_ATTRIBUTE = /^\[([\w-]+)="([^"]*)"\]$/;
const SETTLE_MS = 1500;
const KIT_TIMEOUT_MS = 30_000;
const SCROLL_PAUSE_MS = 30;
const AJRAKH = "Kutch-Ajrakh";

export function nativeDocumentPath(): string {
  return `/api${MONOGRAPH_DOCUMENT_PATH(AJRAKH)}`;
}

function classTokens(open: Open): string[] {
  return (open.attrs.class ?? "").split(/\s+/).filter(Boolean);
}

function nthOfClasses(opens: readonly Open[], value: string): number {
  const wanted = value.split(/\s+/).filter(Boolean);
  const holding = opens.filter((open) => wanted.every((name) => classTokens(open).includes(name)));
  return holding.findIndex((open) => open.attrs.class === value);
}

function anchorPlan(opens: readonly Open[], component: MonographComponent, index: number): AnchorPlan {
  const plan: AnchorPlan = { label: component.label, index, id: BY_ID.exec(component.anchor)?.[1] ?? null, attribute: null, classes: [], nth: 0 };
  const found = BY_ATTRIBUTE.exec(component.anchor);
  if (!found) return plan;
  if (found[1] !== "class") return { ...plan, attribute: [found[1], found[2]] };
  return { ...plan, classes: found[2].split(/\s+/).filter(Boolean), nth: nthOfClasses(opens, found[2]) };
}

export function anchorPlans(components: readonly MonographComponent[]): AnchorPlan[] {
  const opens = tokenize(servedMain()).filter((token): token is Open => token.kind === "open");
  return components.map((component, index) => anchorPlan(opens, component, index));
}

export async function markAnchors(page: Page, plans: readonly AnchorPlan[]): Promise<void> {
  await page.evaluate((all) => {
    const main = document.getElementById("kv-main");
    if (!main) return;
    for (const plan of all) {
      let element: Element | null = null;
      if (plan.id) element = document.getElementById(plan.id);
      else if (plan.attribute) element = [...main.querySelectorAll(`[${plan.attribute[0]}]`)].find((found) => found.getAttribute(plan.attribute![0]) === plan.attribute![1]) ?? null;
      else if (plan.classes.length) element = main.querySelectorAll(plan.classes.map((name) => `.${CSS.escape(name)}`).join(""))[plan.nth] ?? null;
      element?.setAttribute("data-native-parity", String(plan.index));
    }
  }, plans);
}

export async function openedPage(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "networkidle" });
  await page.waitForFunction(() => "KV" in window, undefined, { timeout: KIT_TIMEOUT_MS }).catch(() => undefined);
  await page.evaluate(async (pause) => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, pause));
    }
    window.scrollTo(0, 0);
  }, SCROLL_PAUSE_MS);
  await page.waitForTimeout(SETTLE_MS);
  await fullSizePictures(page);
  await playersAtRest(page);
}

export async function mainLines(page: Page): Promise<string[]> {
  const text = await page.evaluate(() => (document.querySelector("#kv-main") as HTMLElement | null)?.innerText ?? "");
  return text
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

export const OVERLAY_ATTRIBUTE = "data-native-overlay";
export const OVERLAYS_HIDDEN = `[${OVERLAY_ATTRIBUTE}] { visibility: hidden !important; }`;

export async function markOverlays(page: Page): Promise<number> {
  return page.evaluate((attribute) => {
    const pinned = [...document.body.querySelectorAll("*")].filter((element) => ["sticky", "fixed"].includes(getComputedStyle(element).position));
    for (const element of pinned) element.setAttribute(attribute, "");
    return pinned.length;
  }, OVERLAY_ATTRIBUTE);
}

export type PageAnswers = { quote: string | null; dipsBefore: string | null; dipsAfter: string | null };

export async function pageAnswers(page: Page): Promise<PageAnswers> {
  const cite = page.locator("main .kcite").first();
  await cite.scrollIntoViewIfNeeded();
  await cite.click();
  const popover = page.locator("[role='dialog']:visible").first();
  const quote = (await popover.count()) ? await popover.innerText() : null;
  await page.keyboard.press("Escape");
  const dip = page.locator("#fig1 button").first();
  const dipsBefore = await page.locator("#fig1").getAttribute("data-dips");
  if (await dip.count()) await dip.click();
  const dipsAfter = await page.locator("#fig1").getAttribute("data-dips");
  return { quote: quote?.replace(/\s+/g, " ").trim() ?? null, dipsBefore, dipsAfter };
}
