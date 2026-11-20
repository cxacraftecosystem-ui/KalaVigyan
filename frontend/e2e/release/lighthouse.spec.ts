import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { chromium, expect, test } from "@playwright/test";

import { passPreviewProtection } from "../production/preview";

import { LIGHTHOUSE_BUDGETS, LIGHTHOUSE_FORMS, lighthouseNumbers, lighthouseProblems, type LighthouseForm } from "./auditBudgets";
import { auditPaths } from "./keyPages";
import { runLighthouse } from "./lighthouseRun";
import { checkRecord, keepRecord, pathFileName, reportDir } from "./report";
import { bypassToken, siteOrigin } from "./site";

const CHECK = "lighthouse";
const DEBUGGING_PORT = 9333;
const FORM_TIMEOUT_MS = 40 * 60_000;

async function auditPage(form: LighthouseForm, path: string, port: number): Promise<string[]> {
  const folder = join(reportDir(), CHECK, form.key);
  mkdirSync(folder, { recursive: true });
  const result = await runLighthouse({ url: new URL(path, siteOrigin()).href, port, form, outputBase: join(folder, pathFileName(path, "lighthouse")) });
  const problems = lighthouseProblems(result, LIGHTHOUSE_BUDGETS[form.key]);
  keepRecord(checkRecord(CHECK, `${path} at ${form.width} (${form.key})`, problems, { numbers: lighthouseNumbers(result) }));
  return problems.map((problem) => `${path}: ${problem}`);
}

LIGHTHOUSE_FORMS.forEach((form, index) => {
  test(`Lighthouse at ${form.width} keeps every page within the ${form.key} budget`, async () => {
    test.setTimeout(FORM_TIMEOUT_MS);
    const port = DEBUGGING_PORT + index;
    const profile = mkdtempSync(join(tmpdir(), "kv-lighthouse-"));
    const context = await chromium.launchPersistentContext(profile, { channel: "chromium", headless: true, viewport: null, args: [`--remote-debugging-port=${port}`] });
    try {
      await passPreviewProtection(context, siteOrigin(), bypassToken());
      const problems: string[] = [];
      for (const path of auditPaths()) problems.push(...(await auditPage(form, path, port)));
      expect(problems, problems.join("\n")).toEqual([]);
    } finally {
      await context.close();
      rmSync(profile, { recursive: true, force: true });
    }
  });
});
