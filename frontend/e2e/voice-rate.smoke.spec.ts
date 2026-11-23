import { expect, test } from "@playwright/test";

import { VOICE_BOARD_PATH } from "../lib/voiceBoard";

import { FAKE_MICROPHONE_ARGS } from "./production/matrix";
import { HEARD_SENTENCE, RELAY_STARTED, routeRelayCall, type SentTurn } from "./production/voiceDock";
import { formFile, fullMinuteCeiling, recordedRate } from "./voiceRate";

const RECORDED_MS = 4_000;
const REPLY_TIMEOUT_MS = 20_000;

test.use({ permissions: ["microphone"], launchOptions: { args: FAKE_MICROPHONE_ARGS } });

test("the dock records a turn from the fake microphone at a rate a full minute fits under the send point", async ({ page }) => {
  const sent: SentTurn[] = [];
  await routeRelayCall(page, sent);
  await page.goto(VOICE_BOARD_PATH);
  await page.getByRole("button", { name: "Open the voice dock" }).click();
  const dock = page.getByTestId("voice-panel");
  await dock.getByRole("button", { name: "Agree and start" }).click();
  await expect(dock.getByTestId("voice-status")).toHaveText("Listening · tap to send");
  await page.waitForTimeout(RECORDED_MS);
  await dock.getByRole("button", { name: "Send" }).click();
  await expect(dock).toContainText(HEARD_SENTENCE, { timeout: REPLY_TIMEOUT_MS });
  expect(sent).toHaveLength(1);

  const rate = await recordedRate(page, formFile(sent[0].body, sent[0].contentType, "audio"));
  const measured = `${rate.type} at ${rate.bitsPerSecond} bit/s (${rate.bytes} bytes over ${rate.seconds.toFixed(2)} s, asked ${RELAY_STARTED.audioBitsPerSecond})`;
  test.info().annotations.push({ type: "recorded bit rate", description: measured });
  console.log(`recorded bit rate: ${measured}`);
  expect(rate.seconds).toBeGreaterThan(RECORDED_MS / 2_000);
  expect(rate.bitsPerSecond).toBeLessThanOrEqual(fullMinuteCeiling(RELAY_STARTED.maxAudioBytes, RELAY_STARTED.maxTurnSeconds));
});
