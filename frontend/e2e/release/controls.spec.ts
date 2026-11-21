import { expect, test, type Browser, type Page } from "@playwright/test";

import { SMALL_PHONE, contextOptions } from "../production/matrix";
import { passPreviewProtection } from "../production/preview";

import { answerSession } from "./answerControls";
import { ControlWatch } from "./controlWatch";
import { documentSession, phoneDocumentSession } from "./documentControls";
import { walkMapLayers } from "./mapControls";
import { playerSession, whatIf } from "./playerControls";
import { atlasControls, compareControls, landingControls, readingLink } from "./readingControls";
import { bypassToken, siteOrigin } from "./site";

const CURATED = "/crafts/Kutch-Ajrakh";
const GENERATED = "/crafts/Bagru-Hand-Block-Print";
const SESSION_TIMEOUT_MS = 8 * 60_000;

type Session = (watch: ControlWatch, page: Page) => Promise<void>;

function settled(watch: ControlWatch): void {
  const problems = watch.keep();
  expect(problems, problems.join("\n")).toEqual([]);
}

async function opened(page: Page, target: string, path: string): Promise<ControlWatch> {
  await passPreviewProtection(page.context(), siteOrigin(), bypassToken());
  const watch = new ControlWatch(page, target, siteOrigin());
  await watch.step(`Open ${path}`, async () => {
    const response = await page.goto(path, { waitUntil: "domcontentloaded" });
    return response?.ok() ? [] : [`${path} answered ${response?.status() ?? "nothing"}`];
  });
  return watch;
}

async function onPhone(browser: Browser, target: string, path: string, session: Session): Promise<string[]> {
  const context = await browser.newContext({ ...contextOptions(SMALL_PHONE, "light"), baseURL: siteOrigin() });
  try {
    const page = await context.newPage();
    const watch = await opened(page, target, path);
    await session(watch, page);
    return watch.keep();
  } finally {
    await context.close();
  }
}

test.describe("a reader operates every control", () => {
  test.describe.configure({ timeout: SESSION_TIMEOUT_MS });

  test("the landing, the atlas, the map and compare, one after another without reloading", async ({ page }) => {
    const watch = await opened(page, "landing, atlas, map and compare", "/");
    await landingControls(watch, page);
    await atlasControls(watch, page);
    await watch.step("Reading bar to the map", () => readingLink(page, "Map", "/map"));
    await walkMapLayers(watch, page);
    await watch.step("Reading bar to compare", () => readingLink(page, "Compare", "/compare"));
    await compareControls(watch, page);
    settled(watch);
  });

  test("Kutch Ajrakh: rail, citations, players, what-if and the 3D molecule", async ({ page }) => {
    const watch = await opened(page, "Kutch Ajrakh", CURATED);
    await documentSession(watch, page);
    await playerSession(watch, page);
    await watch.step("What-if toggle", () => whatIf(page));
    settled(watch);
  });

  test("a generated document, Bagru Hand Block Print: rail, citations, players and the 3D molecule", async ({ page }) => {
    const watch = await opened(page, "Bagru Hand Block Print", GENERATED);
    await documentSession(watch, page);
    await playerSession(watch, page);
    settled(watch);
  });

  test("on a phone: the theme toggle, the chapter menu and citation sheets", async ({ browser }) => {
    const curated = await onPhone(browser, "Kutch Ajrakh on a phone", CURATED, phoneDocumentSession);
    const generated = await onPhone(browser, "Bagru Hand Block Print on a phone", GENERATED, phoneDocumentSession);
    const problems = [...curated, ...generated];
    expect(problems, problems.join("\n")).toEqual([]);
  });

  test("an answer page: its choices and reading tools, signed in", async ({ page }) => {
    const email = process.env.E2E_EMAIL ?? "";
    const password = process.env.E2E_PASSWORD ?? "";
    test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to sign in to the answer page.");
    const watch = await opened(page, "the answer page", "/login");
    await answerSession(watch, page, { email, password });
    settled(watch);
  });
});
