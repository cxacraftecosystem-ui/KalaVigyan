import { expect, test } from "@playwright/test";

import { answersScript, DEBUGGER_CALL_MS, PAUSE_WAIT_MS, stopScript, stuckStack, watchScript, within } from "./production/stuckPage";

const ANSWER_MS = 2_000;
const SPIN_AFTER_MS = 100;
const SPIN = `setTimeout(function spinForever() { for (;;) {} }, ${SPIN_AFTER_MS})`;

test.use({ trace: "off" });

test("a bounded call gives up on a promise that never settles and on one that fails", async () => {
  const never = new Promise<string>(() => undefined);
  expect(await within(never, 50)).toBeNull();
  expect(await within(Promise.reject(new Error("closed")), 50)).toBeNull();
  expect(await within(Promise.resolve("answered"), 50)).toBe("answered");
  expect(PAUSE_WAIT_MS + DEBUGGER_CALL_MS * 8 + ANSWER_MS * 3).toBeLessThan(test.info().timeout);
});

test("a page whose script never yields is caught, its stack names the function that spins, and the spin is stopped", async ({ page }) => {
  await page.setContent("<p>Waiting</p>");
  const watcher = await watchScript(page);
  expect(await answersScript(page, ANSWER_MS)).toBe(true);
  await page.evaluate(SPIN);
  await new Promise((resolve) => setTimeout(resolve, SPIN_AFTER_MS + 300));
  expect(await answersScript(page, ANSWER_MS)).toBe(false);
  const stack = await stuckStack(watcher);
  expect(stack[0]).toContain("stuck in spinForever");
  expect(await stopScript(watcher)).toBe(true);
  expect(await answersScript(page, ANSWER_MS)).toBe(true);
  await page.close({ runBeforeUnload: false });
});
