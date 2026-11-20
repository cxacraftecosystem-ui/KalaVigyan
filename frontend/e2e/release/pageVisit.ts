import { errors, type Page } from "@playwright/test";

import { clip } from "../production/checks";
import { DOCUMENT_ROOT, HUB_ROOT, RAIL_LINKS, RECORD_ROOT, documentShape, hubShape, recordShape } from "../production/pageShapes";

import type { DrawnShape, KeyPage, PageSeen } from "./keyPages";

const DRAW_TIMEOUT_MS = 20_000;
const QUIET_TIMEOUT_MS = 15_000;
const DRAWN = 'h1, section[data-testid^="error-"]';
const CITATION_LABEL = /^Sources? \d/;

export async function quiet(page: Page): Promise<void> {
  try {
    await page.waitForLoadState("networkidle", { timeout: QUIET_TIMEOUT_MS });
  } catch (error) {
    if (!(error instanceof errors.TimeoutError)) throw error;
  }
}

async function drawn(page: Page): Promise<boolean> {
  try {
    await page.locator(DRAWN).first().waitFor({ state: "visible", timeout: DRAW_TIMEOUT_MS });
    return true;
  } catch (error) {
    if (error instanceof errors.TimeoutError) return false;
    throw error;
  }
}

async function citations(page: Page, root: string): Promise<number> {
  return page.evaluate(
    ({ scope, label }) => Array.from(document.querySelectorAll(`${scope} button[aria-label]`)).filter((node) => new RegExp(label).test(node.getAttribute("aria-label") ?? "")).length,
    { scope: root, label: CITATION_LABEL.source }
  );
}

async function drawnShape(page: Page, keyPage: KeyPage): Promise<DrawnShape | null> {
  switch (keyPage.marker.kind) {
    case "document": {
      const shape = await page.evaluate(documentShape, { root: DOCUMENT_ROOT, rail: RAIL_LINKS });
      return shape && { heading: shape.heading, chapters: shape.chapters.length, citations: await citations(page, DOCUMENT_ROOT) };
    }
    case "record": {
      const shape = await page.evaluate(recordShape, { root: RECORD_ROOT, rail: RAIL_LINKS });
      return shape && { heading: shape.heading, chapters: 0, citations: 0 };
    }
    case "hub": {
      const shape = await page.evaluate(hubShape, HUB_ROOT);
      return shape && { heading: shape.heading, chapters: shape.chapters, citations: 0 };
    }
    default:
      return null;
  }
}

async function visibleHeading(page: Page): Promise<string> {
  return page.evaluate(() => {
    const heading = Array.from(document.querySelectorAll("h1")).find((node) => node.getClientRects().length > 0);
    return (heading?.textContent ?? "").replace(/\s+/g, " ").trim();
  });
}

async function errorPanels(page: Page): Promise<string[]> {
  return page.evaluate(() => Array.from(document.querySelectorAll('section[data-testid^="error-"]')).map((node) => node.getAttribute("data-testid") ?? ""));
}

async function appbars(page: Page): Promise<number> {
  return page.evaluate(() => Array.from(document.querySelectorAll('[data-testid="appbar"]')).filter((node) => node.getClientRects().length > 0).length);
}

async function signInFields(page: Page): Promise<boolean> {
  const email = page.getByLabel("Email", { exact: true });
  const password = page.getByLabel("Password", { exact: true });
  return (await email.count()) > 0 && (await password.count()) > 0 && (await email.first().isVisible()) && (await password.first().isVisible());
}

export async function visitKeyPage(page: Page, keyPage: KeyPage): Promise<PageSeen> {
  const crashes: string[] = [];
  page.on("pageerror", (error) => crashes.push(clip(error.message)));
  const response = await page.goto(keyPage.path, { waitUntil: "domcontentloaded" });
  await quiet(page);
  const wasDrawn = await drawn(page);
  const url = new URL(page.url());
  return {
    status: response?.status() ?? null,
    finalPath: `${url.pathname}${url.search}`,
    drawn: wasDrawn,
    heading: await visibleHeading(page),
    errorPanels: await errorPanels(page),
    shape: await drawnShape(page, keyPage),
    signInFields: keyPage.marker.kind === "sign-in" ? await signInFields(page) : false,
    appbars: await appbars(page),
    crashes
  };
}
