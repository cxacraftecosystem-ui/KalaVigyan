import { AxeBuilder } from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

import { VOICE_BOARD_PATH } from "../../lib/voiceBoard";

import { HEARD_SENTENCE, routeRelayCall, type SentTurn } from "./voiceDock";

const RECORDED_MS = 1_500;
const REPLY_TIMEOUT_MS = 20_000;

async function expectWithinTheScreen(page: Page, dock: Locator): Promise<void> {
  const box = await dock.boundingBox();
  const screen = page.viewportSize();
  expect(box && screen).toBeTruthy();
  if (!box || !screen) return;
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(screen.width + 0.5);
  expect(box.y + box.height).toBeLessThanOrEqual(screen.height + 0.5);
  const sideways = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(sideways).toBeLessThanOrEqual(0);
}

async function expectReadable(page: Page): Promise<void> {
  const checked = await new AxeBuilder({ page }).include('[data-testid="voice-panel"]').withRules(["color-contrast"]).analyze();
  expect(checked.violations.map((violation) => violation.id)).toEqual([]);
}

test("the voice dock agrees, records a relay turn from a fake microphone, plays the reply and ends", async ({ page }) => {
  const sent: SentTurn[] = [];
  await routeRelayCall(page, sent);
  await page.goto(VOICE_BOARD_PATH);
  await page.getByRole("button", { name: "Open the voice dock" }).click();
  const dock = page.getByTestId("voice-panel");
  await expect(dock.getByTestId("voice-consent")).toBeVisible();
  await expectWithinTheScreen(page, dock);
  await expectReadable(page);

  await dock.getByRole("button", { name: "Agree and start" }).click();
  await expect(dock.getByTestId("voice-status")).toHaveText("Listening · tap to send");
  await page.waitForTimeout(RECORDED_MS);
  await dock.getByRole("button", { name: "Send" }).click();
  await expect(dock).toContainText(HEARD_SENTENCE, { timeout: REPLY_TIMEOUT_MS });
  await expect(dock.getByTestId("voice-status")).toHaveText("Tap to talk", { timeout: REPLY_TIMEOUT_MS });
  expect(sent).toHaveLength(1);
  expect(sent[0].contentType).toContain("multipart/form-data");
  expect(sent[0].bytes).toBeGreaterThan(0);
  await expectWithinTheScreen(page, dock);
  await expectReadable(page);

  await dock.getByTestId("voice-end").click();
  await expect(dock.getByRole("button", { name: "Talk again" })).toBeVisible();
  await expectWithinTheScreen(page, dock);
});
