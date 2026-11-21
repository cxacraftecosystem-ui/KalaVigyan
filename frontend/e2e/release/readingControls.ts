import type { Locator, Page } from "@playwright/test";

import { SEARCH_ANCHOR } from "@/lib/atlasIndex";
import { COMPARE_PARAM } from "@/lib/comparePage";

import { otherChoice, unchangedProblems } from "./controlPlan";
import { changedFrom, type ControlWatch } from "./controlWatch";

const TIMEOUT_MS = 30_000;
const QUICK_MS = 5_000;
const QUERY_PARAM = "q";
const SEARCH_TERM = "indigo";
const COLLECTION_CHOICE = "Show the collection as";
const COMPARED = [
  { name: "Kutch Ajrakh", slug: "Kutch-Ajrakh" },
  { name: "Bagru Hand Block Print", slug: "Bagru-Hand-Block-Print" }
] as const;

function search(page: Page): string {
  return new URL(page.url()).search;
}

function query(page: Page): string {
  return new URL(page.url()).searchParams.get(QUERY_PARAM) ?? "";
}

function compared(page: Page): string {
  return new URL(page.url()).searchParams.getAll(COMPARE_PARAM).join(",");
}

async function visibleWithin(target: Locator, timeout = TIMEOUT_MS): Promise<boolean> {
  return target.waitFor({ state: "visible", timeout }).then(
    () => true,
    () => false
  );
}

async function expander(control: Locator, label: string): Promise<string[]> {
  const read = async () => (await control.getAttribute("aria-expanded")) ?? "";
  const before = await read();
  await control.click();
  const opened = await changedFrom(read, before, QUICK_MS);
  await control.click();
  const closed = await changedFrom(read, opened, QUICK_MS);
  return [...unchangedProblems(label, before, opened), ...unchangedProblems(`${label}, pressed again`, opened, closed)];
}

export async function readingLink(page: Page, label: string, path: string): Promise<string[]> {
  await page.getByRole("navigation", { name: "Reading" }).getByRole("link", { name: label, exact: true }).click();
  await page.waitForURL((url) => url.pathname === path, { timeout: TIMEOUT_MS });
  return (await visibleWithin(page.getByRole("heading", { level: 1 }).first())) ? [] : [`${path} draws no heading after the ${label} link`];
}

export async function landingControls(watch: ControlWatch, page: Page): Promise<void> {
  await watch.step("Landing monographs expander", () => expander(page.getByTestId("landing-documents").locator("button[aria-expanded]").first(), "the Show all monographs expander"));
  await watch.step("Landing collection link to the atlas", async () => {
    await page.getByTestId("landing-collection").locator('a[href="/crafts"]').first().click();
    await page.waitForURL((url) => url.pathname === "/crafts", { timeout: TIMEOUT_MS });
    return (await visibleWithin(page.getByRole("heading", { level: 1, name: "The atlas" }))) ? [] : ["the atlas draws no heading after the collection link"];
  });
}

async function searchFilter(page: Page): Promise<string[]> {
  const box = page.getByRole("searchbox").first();
  await box.fill(SEARCH_TERM);
  const shown = await visibleWithin(page.getByTestId("atlas-results"));
  const written = await changedFrom(async () => query(page), "", QUICK_MS);
  return [...(shown ? [] : [`searching "${SEARCH_TERM}" shows no results`]), ...unchangedProblems("the search term in the address", "", written)];
}

async function suggestedFilter(page: Page): Promise<string[]> {
  const chip = page.locator(`#${SEARCH_ANCHOR} .kv-chip[aria-pressed="false"]`).first();
  if ((await chip.count()) === 0) return ["the atlas offers no suggested search to press"];
  const before = query(page);
  await chip.click();
  const after = await changedFrom(async () => query(page), before, QUICK_MS);
  return unchangedProblems("a suggested search", before, after);
}

async function clearedSearch(page: Page): Promise<string[]> {
  const before = query(page);
  await page.getByRole("searchbox").first().fill("");
  const after = await changedFrom(async () => query(page), before, QUICK_MS);
  const hidden = await page.getByTestId("atlas-results").waitFor({ state: "hidden", timeout: QUICK_MS }).then(
    () => true,
    () => false
  );
  return [...unchangedProblems("clearing the search", before, after), ...(hidden ? [] : ["the search results stay after the search is cleared"])];
}

async function collectionChoice(page: Page): Promise<string[]> {
  const group = page.getByRole("group", { name: COLLECTION_CHOICE });
  if ((await group.count()) === 0) return [];
  const pressed = async () => (await group.locator('button[aria-pressed="true"]').innerText()).trim();
  const before = await pressed();
  const labels = (await group.getByRole("button").allInnerTexts()).map((label) => label.trim());
  const other = otherChoice(labels, before);
  if (!other) return [`the ${COLLECTION_CHOICE} choice offers one view`];
  await group.getByRole("button", { name: other, exact: true }).click();
  const after = await changedFrom(pressed, before, QUICK_MS);
  const drawn = await visibleWithin(page.getByTestId(other === "Names" ? "names-wall" : "collection-shelf").first(), QUICK_MS);
  await group.getByRole("button", { name: before, exact: true }).click();
  return [...unchangedProblems(`the ${COLLECTION_CHOICE} choice`, before, after), ...(drawn ? [] : [`choosing ${other} draws nothing`])];
}

export async function atlasControls(watch: ControlWatch, page: Page): Promise<void> {
  await watch.step("Atlas search", () => searchFilter(page));
  await watch.step("Atlas suggested search", () => suggestedFilter(page));
  await watch.step("Atlas search cleared", () => clearedSearch(page));
  await watch.step("Atlas plates or names", () => collectionChoice(page));
  await watch.step("Atlas places expander", () => expander(page.getByTestId("atlas-index").locator("button[aria-expanded]").first(), "the atlas's places expander"));
}

async function pickCraft(page: Page, name: string, slug: string): Promise<string[]> {
  const before = compared(page);
  await page.getByTestId("compare-picker").locator("[data-searchable-select]").click();
  await page.getByPlaceholder("Type to filter").fill(name);
  await page.getByRole("option").filter({ hasText: name }).first().click();
  const after = await changedFrom(async () => compared(page), before, TIMEOUT_MS);
  return [...unchangedProblems(`picking ${name}`, before, after), ...(after.split(",").includes(slug) ? [] : [`picking ${name} compares "${after}"`])];
}

export async function compareControls(watch: ControlWatch, page: Page): Promise<void> {
  const [first, second] = COMPARED;
  await watch.step("Compare first picker", () => pickCraft(page, first.name, first.slug));
  await watch.step("Compare second picker", async () => {
    const problems = await pickCraft(page, second.name, second.slug);
    const shown = await visibleWithin(page.getByTestId("comparison"));
    return [...problems, ...(shown ? [] : [`${first.name} and ${second.name} draw no comparison in ${TIMEOUT_MS / 1000} s`])];
  });
  await watch.step("Compare removes a craft", async () => {
    const before = search(page);
    await page.getByRole("button", { name: `Remove ${second.name}` }).click();
    return unchangedProblems(`removing ${second.name}`, before, await changedFrom(async () => search(page), before, TIMEOUT_MS));
  });
}
