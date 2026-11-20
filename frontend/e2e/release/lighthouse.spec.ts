import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { chromium, expect, test } from "@playwright/test";

import { passPreviewProtection } from "../production/preview";

import { LIGHTHOUSE_CHECK, recordedLighthouse } from "./auditBaseline";
import { LIGHTHOUSE_FORMS, LIGHTHOUSE_RUNS, LIGHTHOUSE_TARGETS, lighthouseJudgement, lighthouseNumbers, medianNumbers, runtimeProblem, type LighthouseForm } from "./auditBudgets";
import { auditPaths } from "./keyPages";
import { runLighthouse } from "./lighthouseRun";
import { checkRecord, keepRecord, pathFileName, reportDir, type CheckNumbers } from "./report";
import { bypassToken, siteOrigin } from "./site";

const DEBUGGING_PORT = 9333;
const FORM_TIMEOUT_MS = 50 * 60_000;

type Measured = { runs: CheckNumbers[]; failures: string[] };

async function measure(form: LighthouseForm, path: string, port: number): Promise<Measured> {
  const folder = join(reportDir(), LIGHTHOUSE_CHECK, form.key);
  mkdirSync(folder, { recursive: true });
  const measured: Measured = { runs: [], failures: [] };
  for (let run = 1; run <= LIGHTHOUSE_RUNS; run += 1) {
    const outputBase = join(folder, pathFileName(path, `lighthouse-${run}`));
    const result = await runLighthouse({ url: new URL(path, siteOrigin()).href, port, form, outputBase, html: run === 1 });
    const failure = runtimeProblem(result);
    if (failure) measured.failures.push(`run ${run}: ${failure}`);
    else measured.runs.push(lighthouseNumbers(result));
  }
  return measured;
}

async function auditPage(form: LighthouseForm, path: string, port: number): Promise<string[]> {
  const { runs, failures } = await measure(form, path, port);
  const numbers = medianNumbers(runs);
  const judged = runs.length ? lighthouseJudgement(numbers, LIGHTHOUSE_TARGETS[form.key], recordedLighthouse(path, form.key)) : { problems: failures, notes: [] };
  const notes = runs.length ? [`median of ${runs.length} runs`, ...failures, ...judged.notes] : judged.notes;
  keepRecord(checkRecord(LIGHTHOUSE_CHECK, `${path} at ${form.width} (${form.key})`, judged.problems, { subject: path, variant: form.key, notes, numbers }));
  return judged.problems.map((problem) => `${path}: ${problem}`);
}

LIGHTHOUSE_FORMS.forEach((form, index) => {
  test(`Lighthouse at ${form.width} keeps every page within its ${form.key} budget`, async () => {
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
