import { expect, test } from "@playwright/test";

import { LATER_BACKEND_CRAFT, LATER_BACKEND_NAME, smokeApiAddress } from "./smokeApi";

test("the built site draws a craft page whose payload carries a field this build does not know", async ({ page }) => {
  test.skip(smokeApiAddress() === null, "needs the local build with its API at a local address");
  const response = await page.goto(`/crafts/${LATER_BACKEND_CRAFT}`);
  expect(response?.status()).toBe(200);
  const record = page.getByTestId("craft-without-monograph");
  await expect(record.getByRole("heading", { level: 1 })).toContainText(LATER_BACKEND_NAME);
});
