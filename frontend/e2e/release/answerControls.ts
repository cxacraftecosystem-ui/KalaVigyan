import type { Locator, Page } from "@playwright/test";

import { submitSignIn } from "../production/signIn";
import type { Credentials } from "../production/run";

import { expectedProblems, otherChoice, unchangedProblems } from "./controlPlan";
import { changedFrom, reached, type ControlWatch } from "./controlWatch";

const TIMEOUT_MS = 60_000;
const QUICK_MS = 5_000;
const SEGMENTED = ".kv-seg";

async function pressedLabel(group: Locator): Promise<string> {
  const pressed = group.locator('button[aria-pressed="true"]');
  return (await pressed.count()) ? (await pressed.first().innerText()).trim() : "";
}

async function segmented(group: Locator): Promise<string[]> {
  const name = (await group.getAttribute("aria-label")) ?? "a choice";
  const enabled = group.locator("button:not([disabled])");
  const labels = (await enabled.allInnerTexts()).map((label) => label.trim());
  const before = await pressedLabel(group);
  const other = otherChoice(labels, before);
  if (!other) return [];
  await enabled.filter({ hasText: other }).first().click();
  const after = await changedFrom(() => pressedLabel(group), before, QUICK_MS);
  const problems = expectedProblems(`the ${name} choice`, other, after);
  if (before) {
    await enabled.filter({ hasText: before }).first().click();
    problems.push(...expectedProblems(`the ${name} choice pressed back`, before, await reached(() => pressedLabel(group), before, QUICK_MS)));
  }
  return problems;
}

export async function segmentedChoices(page: Page, scope: string): Promise<string[]> {
  const groups = page.locator(`${scope} ${SEGMENTED}:visible`);
  const count = await groups.count();
  const problems: string[] = [];
  for (let at = 0; at < count; at += 1) problems.push(...(await segmented(groups.nth(at))));
  return problems;
}

async function mainLink(page: Page, label: string, path: string): Promise<void> {
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: label, exact: true }).click();
  await page.waitForURL((url) => url.pathname === path, { timeout: TIMEOUT_MS });
}

async function listen(page: Page): Promise<string[]> {
  const start = page.getByTestId("listen-start");
  if ((await start.count()) === 0) return [];
  await start.click();
  const dock = page.getByTestId("listen-dock");
  const shown = await dock.waitFor({ state: "visible", timeout: TIMEOUT_MS }).then(
    () => true,
    () => false
  );
  if (!shown) return ["Listen opens no player"];
  await dock.getByRole("button", { name: "Stop listening" }).click();
  const gone = await dock.waitFor({ state: "hidden", timeout: QUICK_MS }).then(
    () => true,
    () => false
  );
  return gone ? [] : ["Stop listening leaves the player open"];
}

async function film(page: Page): Promise<string[]> {
  const start = page.getByTestId("film-start");
  if ((await start.count()) === 0) return [];
  await start.click();
  const player = page.getByTestId("film-player");
  const shown = await player.waitFor({ state: "visible", timeout: TIMEOUT_MS }).then(
    () => true,
    () => false
  );
  await page.keyboard.press("Escape");
  const gone = await player.waitFor({ state: "hidden", timeout: QUICK_MS }).then(
    () => true,
    () => false
  );
  return [...(shown ? [] : ["Film opens no player"]), ...(gone ? [] : ["Escape leaves the film open"])];
}

async function saveToggle(page: Page): Promise<string[]> {
  const save = page.getByTestId("save-answer");
  if ((await save.count()) === 0) return [];
  await reached(async () => String(await save.isEnabled()), "true", TIMEOUT_MS);
  const pressed = async () => (await save.getAttribute("aria-pressed")) ?? "";
  const before = await pressed();
  await save.click();
  const after = await changedFrom(pressed, before, TIMEOUT_MS);
  await save.click();
  const back = await changedFrom(pressed, after, TIMEOUT_MS);
  return [...unchangedProblems("Save", before, after), ...expectedProblems("Save pressed again", before, back)];
}

async function openSaved(watch: ControlWatch, page: Page): Promise<boolean> {
  const first = page.getByTestId("saved-explainer").locator("a").first();
  await page.getByTestId("saved-list").or(page.getByTestId("saved-empty")).first().waitFor({ state: "visible", timeout: TIMEOUT_MS });
  if ((await first.count()) === 0) {
    watch.note("nothing is saved on the E2E account, so no answer's reading tools were operated");
    return false;
  }
  await first.click();
  await page.getByTestId("answer-view").waitFor({ state: "visible", timeout: TIMEOUT_MS });
  await page.getByTestId("answer-progress").waitFor({ state: "detached", timeout: TIMEOUT_MS });
  return true;
}

export async function answerSession(watch: ControlWatch, page: Page, account: Credentials): Promise<void> {
  await watch.step("Signed in", async () => {
    watch.markSignedIn();
    await submitSignIn(page, account);
    if (new URL(page.url()).pathname !== "/ask") await mainLink(page, "Ask", "/ask");
    return [];
  });
  await watch.step("Ask choices", () => segmentedChoices(page, '[data-testid="ask-options"]'));
  const opened = { answer: false };
  await watch.step("Saved answer opens", async () => {
    await mainLink(page, "Saved", "/saved");
    opened.answer = await openSaved(watch, page);
    return [];
  });
  if (!opened.answer) return;
  await watch.step("Answer choices", () => segmentedChoices(page, "main"));
  await watch.step("Answer Listen", () => listen(page));
  await watch.step("Answer Film", () => film(page));
  await watch.step("Answer Save", () => saveToggle(page));
}
