import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { passPreviewProtection } from "../production/preview";

import { AXE_TAGS, axeNotes, axeNumbers, axeProblems } from "./auditBudgets";
import { auditPaths } from "./keyPages";
import { quiet } from "./pageVisit";
import { checkRecord, keepRecord, pathFileName, reportDir } from "./report";
import { bypassToken, siteOrigin } from "./site";

const CHECK = "axe";
const SETTLE_MS = 800;

test.beforeEach(async ({ context }) => {
  await passPreviewProtection(context, siteOrigin(), bypassToken());
});

for (const path of auditPaths()) {
  test(`axe finds no serious or critical violation on ${path}`, async ({ page }, info) => {
    await page.goto(path, { waitUntil: "domcontentloaded" });
    await quiet(page);
    await page.waitForTimeout(SETTLE_MS);
    const results = await new AxeBuilder({ page }).withTags([...AXE_TAGS]).analyze();
    const folder = join(reportDir(), CHECK, info.project.name);
    mkdirSync(folder, { recursive: true });
    writeFileSync(join(folder, pathFileName(path, "json")), JSON.stringify(results, null, 2), "utf8");
    const target = `${path} at ${info.project.name}`;
    const problems = axeProblems(results.violations);
    keepRecord(checkRecord(CHECK, target, problems, { notes: axeNotes(results.violations), numbers: axeNumbers(results.violations) }));
    expect(problems, `${target}: ${problems.join("; ")}`).toEqual([]);
  });
}
