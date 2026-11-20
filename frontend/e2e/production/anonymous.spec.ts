import { expect, test, type Page } from "@playwright/test";

import { readingBarProblems } from "./appbarChecks";
import { passPreviewProtection } from "./preview";
import { CATEGORY_SLUG, COMPARED_CRAFTS, CRAFT_SLUG, UNCURATED_CRAFT_SLUG, baseUrl, previewBypassToken, type Credentials } from "./run";
import { submitSignIn } from "./signIn";

type ReadingPage = { name: string; path: string; heading: RegExp; way: "sign-in" | "ask"; current: string | null };

const REFUSED_STATUSES = new Set([401, 403]);
const MONOGRAPH_ASK = 'a[href^="/ask?"]';

const ANONYMOUS_PAGES: readonly ReadingPage[] = [
  { name: "the atlas", path: "/crafts", heading: /^The atlas$/, way: "sign-in", current: "Crafts" },
  { name: "Kutch Ajrakh", path: `/crafts/${CRAFT_SLUG}`, heading: /Ajrakh/, way: "ask", current: "Crafts" },
  { name: "a craft without a monograph", path: `/crafts/${UNCURATED_CRAFT_SLUG}`, heading: /\S/, way: "ask", current: "Crafts" },
  { name: "a category hub", path: `/categories/${CATEGORY_SLUG}`, heading: /\S/, way: "sign-in", current: null },
  { name: "the map", path: "/map", heading: /^Map$/, way: "sign-in", current: "Map" },
  { name: "compare", path: `/compare?${COMPARED_CRAFTS.map((slug) => `crafts=${slug}`).join("&")}`, heading: /^Compare crafts$/, way: "sign-in", current: "Compare" }
];

function watchRefusals(page: Page): string[] {
  const refused: string[] = [];
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (url.pathname.startsWith("/api/") && REFUSED_STATUSES.has(response.status())) refused.push(`${response.status()} ${url.pathname}`);
  });
  return refused;
}

function optionalAccount(): Credentials | null {
  const email = process.env.E2E_EMAIL ?? "";
  const password = process.env.E2E_PASSWORD ?? "";
  return email && password ? { email, password } : null;
}

test.beforeEach(async ({ page }) => {
  await passPreviewProtection(page.context(), baseUrl(), previewBypassToken());
});

for (const reading of ANONYMOUS_PAGES) {
  test(`an anonymous reader opens ${reading.name} without signing in`, async ({ page }) => {
    const refused = watchRefusals(page);
    await page.goto(reading.path, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { level: 1, name: reading.heading })).toBeVisible();
    await page.waitForLoadState("networkidle");
    expect(new URL(page.url()).pathname).toBe(reading.path.split("?")[0]);
    await expect(reading.way === "ask" ? page.locator(MONOGRAPH_ASK).first() : page.getByTestId("sign-in-link")).toBeVisible();
    expect(await readingBarProblems(page, reading.current)).toEqual([]);
    expect(refused).toEqual([]);
  });
}

test("Ask on Kutch Ajrakh sends an anonymous reader to sign in and back to the question", async ({ page }) => {
  await page.goto(`/crafts/${CRAFT_SLUG}`, { waitUntil: "domcontentloaded" });
  await page.locator(MONOGRAPH_ASK).first().click();
  await page.waitForURL((url) => url.pathname === "/login");
  const next = new URL(new URL(page.url()).searchParams.get("next") ?? "/", baseUrl());
  expect([next.pathname, next.searchParams.get("craft"), Boolean(next.searchParams.get("q"))]).toEqual(["/ask", CRAFT_SLUG, true]);
  const account = optionalAccount();
  test.skip(account === null, "Set E2E_EMAIL and E2E_PASSWORD to finish signing in.");
  if (!account) return;
  await submitSignIn(page, account);
  await page.waitForURL((url) => url.pathname === "/ask");
  expect(new URL(page.url()).searchParams.get("craft")).toBe(CRAFT_SLUG);
});
