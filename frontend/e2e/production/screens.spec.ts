import { expect, test, type Page } from "@playwright/test";

import { compareHref } from "@/lib/comparePage";
import { CRAFT_TAB_LABEL, type CraftTab } from "@/lib/craftPageView";
import { recordLoadFailure } from "@/lib/recordView";
import type { User } from "@/lib/types";

import { barProblems, menuProblems, readingBarProblems } from "./appbarChecks";
import { TEMPLATE_NOTES, craftOutcome, craftPageResponse, documentOutcome, openCraftTab, recordOutcome, type CraftTemplate } from "./craftChecks";
import type { Scheme } from "./matrix";
import { passPreviewProtection } from "./preview";
import {
  ALL_INDIA_CRAFT_SLUG,
  CATEGORY_FAMILY,
  CATEGORY_SLUG,
  COMPARED_CRAFTS,
  CRAFT_SLUG,
  EMPTY_CRAFT_SLUG,
  NOT_FOUND_PATH,
  PRINTED_CRAFT_SLUG,
  SCREENS_TIMEOUT_MS,
  UNCURATED_CRAFT_SLUG,
  UNKNOWN_CRAFT_SLUG,
  baseUrl,
  credentials,
  previewBypassToken
} from "./run";
import { comparisonProblems, depthProblems, essayOutcome, hubOutcome, mapProblems, savedAnswerHref, walkLayers } from "./screenChecks";
import { ScreenRun } from "./screenRun";
import { submitSignIn } from "./signIn";

type CraftVisit = { name: string; slug: string; expected: readonly CraftTemplate[] };

const CRAFT_TABS_SHOWN: readonly [CraftTab, string][] = [
  ["process", "process-stage"],
  ["region", "craft-region-map"],
  ["science", "concept-graph"],
  ["sources", "craft-source"],
  ["evidence", "evidence-entry"]
];
const CURATED: readonly CraftTemplate[] = ["document", "tabbed"];
const UNCURATED: readonly CraftTemplate[] = ["record", "document"];
const OTHER_CRAFTS: readonly CraftVisit[] = [
  { name: "Empty craft", slug: EMPTY_CRAFT_SLUG, expected: CURATED },
  { name: "All India craft", slug: ALL_INDIA_CRAFT_SLUG, expected: CURATED },
  { name: "Craft without a monograph", slug: UNCURATED_CRAFT_SLUG, expected: UNCURATED }
];
const MONOGRAPH_ASK = 'a[href^="/ask?"]';
const UNKNOWN_CRAFT_TEXT = recordLoadFailure("craft", 404);
const CRAFTS_LINK = "Crafts";

function heading(page: Page, name: string | null): () => Promise<string[]> {
  return async () => {
    await expect(name ? page.getByRole("heading", { name, level: 1 }) : page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    return [];
  };
}

function templateProblems(visit: CraftVisit, drawn: CraftTemplate | null): string[] {
  if (drawn === null || visit.expected.includes(drawn)) return [];
  return [`${visit.slug} is ${TEMPLATE_NOTES[drawn]}; it should be ${visit.expected.map((template) => TEMPLATE_NOTES[template]).join(" or ")}`];
}

async function signedOutReading(run: ScreenRun, page: Page): Promise<void> {
  await run.visit("Craft monograph", `/crafts/${CRAFT_SLUG}`, async () => {
    await expect(page.getByRole("heading", { level: 1, name: /Ajrakh/ })).toBeVisible();
    await expect(page.locator(MONOGRAPH_ASK).first()).toBeVisible();
    return [...(await documentOutcome(page)), ...(await readingBarProblems(page, CRAFTS_LINK))];
  });
  await run.visit("Craft without a monograph", `/crafts/${UNCURATED_CRAFT_SLUG}`, async () => [...(await recordOutcome(page)), ...(await readingBarProblems(page, CRAFTS_LINK))]);
  await run.visit("Category hub", `/categories/${CATEGORY_SLUG}`, async () => {
    const hub = await hubOutcome(page, CATEGORY_FAMILY);
    run.note(...hub.notes);
    return hub.problems;
  });
}

async function signedOutScreens(run: ScreenRun, page: Page): Promise<void> {
  await run.visit("Landing", "/", heading(page, null));
  await run.visit("Sign up", "/signup", heading(page, "Request access"));
  await run.visit("Forgot password", "/forgot-password", heading(page, "Forgot your password?"));
  await run.visit("Privacy", "/privacy", heading(page, null));
  await run.visit("Session ended", "/session-ended", async () => {
    await expect(page.getByTestId("error-session")).toBeVisible();
    return [];
  });
  await signedOutReading(run, page);
  await run.visit("Login", "/login", async () => {
    await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
    return [];
  });
}

async function craftScreen(run: ScreenRun, page: Page, visit: CraftVisit): Promise<CraftTemplate | null> {
  const seen: { template: CraftTemplate | null } = { template: null };
  const served = craftPageResponse(page, visit.slug);
  await run.visit(visit.name, `/crafts/${visit.slug}`, async () => {
    const outcome = await craftOutcome(page, served);
    seen.template = outcome.template;
    run.note(...outcome.notes);
    return [...outcome.problems, ...templateProblems(visit, outcome.template)];
  });
  return seen.template;
}

async function craftTabs(run: ScreenRun, page: Page): Promise<void> {
  for (const [tab, content] of CRAFT_TABS_SHOWN) {
    await run.step(`Craft ${CRAFT_TAB_LABEL[tab]}`, async () => {
      const opened = await openCraftTab(page, CRAFT_TAB_LABEL[tab], `craft-panel-${tab}`, content);
      if (opened === null) run.note(`no ${CRAFT_TAB_LABEL[tab]} tab`);
      return opened ?? [];
    });
  }
}

async function craftPages(run: ScreenRun, page: Page): Promise<void> {
  const printed = await craftScreen(run, page, { name: `Craft ${CRAFT_TAB_LABEL.overview}`, slug: PRINTED_CRAFT_SLUG, expected: CURATED });
  if (printed === "tabbed") await craftTabs(run, page);
  for (const visit of OTHER_CRAFTS) await craftScreen(run, page, visit);
  await run.visit(
    "Unknown craft",
    `/crafts/${UNKNOWN_CRAFT_SLUG}`,
    async () => {
      await expect(page.getByRole("alert").filter({ hasText: UNKNOWN_CRAFT_TEXT })).toBeVisible();
      return [];
    },
    { expectedResponses: [{ pathPrefix: `/api/crafts/${UNKNOWN_CRAFT_SLUG}`, status: 404 }], expectedAlert: UNKNOWN_CRAFT_TEXT }
  );
}

async function readingScreens(run: ScreenRun, page: Page, user: User): Promise<void> {
  await run.visit("Ask", "/ask", async () => [...(await barProblems(page, user, "Ask")), ...(await depthProblems(page, user))]);
  await run.visit("Atlas", "/crafts", heading(page, "The atlas"));
  await craftPages(run, page);
  await run.visit("Category hub", `/categories/${CATEGORY_SLUG}`, async () => {
    const hub = await hubOutcome(page, CATEGORY_FAMILY);
    run.note(...hub.notes);
    return hub.problems;
  });
}

async function savedScreens(run: ScreenRun, page: Page): Promise<void> {
  const saved: { href: string | null } = { href: null };
  await run.visit("Saved", "/saved", async () => {
    await expect(page.getByRole("heading", { name: "Saved", level: 1 })).toBeVisible();
    saved.href = await savedAnswerHref(page);
    if (saved.href === null) run.note("nothing is saved, so no answer essay was opened");
    return [];
  });
  if (saved.href !== null) await run.visit("Answer essay", saved.href, () => essayOutcome(page));
}

async function toolScreens(run: ScreenRun, page: Page): Promise<void> {
  await run.visit("Compare", "/compare", heading(page, "Compare crafts"));
  await run.visit("Compare pair", compareHref(COMPARED_CRAFTS), () => comparisonProblems(page));
  await savedScreens(run, page);
  await run.visit("Map", "/map", () => mapProblems(page));
  await run.step("Map layers, one after another", async () => {
    const walk = await walkLayers(page);
    if (walk.layers.length) run.note(`layers: ${walk.layers.join(", ")}`);
    return walk.problems;
  });
  await run.visit("Settings", "/settings", heading(page, "Settings"));
}

test("every screen of production at this width", async ({ page }, testInfo) => {
  test.setTimeout(SCREENS_TIMEOUT_MS);
  const account = credentials();
  const metadata = testInfo.project.metadata as { label?: string; scheme?: Scheme };
  const run = new ScreenRun(page, metadata.label ?? testInfo.project.name, { scheme: metadata.scheme ?? null });
  await passPreviewProtection(page.context(), baseUrl(), previewBypassToken());
  await run.watch();
  const session: { user: User | null } = { user: null };

  await signedOutScreens(run, page);
  await run.step("Signed in", async () => {
    run.markSignedIn(null);
    session.user = await submitSignIn(page, account);
    run.markSignedIn(session.user.role);
    return [];
  });

  const signedIn = session.user;
  if (signedIn) {
    run.checkEveryScreen(() => menuProblems(page, signedIn));
    await readingScreens(run, page, signedIn);
    await toolScreens(run, page);
    run.checkEveryScreen(null);
  }
  await run.visit("Not found", NOT_FOUND_PATH, async () => {
    await expect(page.getByTestId("error-not-found")).toBeVisible();
    return [];
  }, { expectStatus: 404 });

  run.write();
  expect(signedIn, "the E2E account could not sign in, so the signed-in screens were not visited").not.toBeNull();
  expect(run.problemCount(), run.problemText()).toBe(0);
});
