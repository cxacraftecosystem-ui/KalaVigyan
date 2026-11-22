# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: lighthouse.spec.ts >> Lighthouse at 360 keeps every page within its mobile budget
- Location: e2e/release/lighthouse.spec.ts:45:3

# Error details

```
Error: /crafts/Kutch-Ajrakh: performance scores 78; the budget is 80
/crafts/Kutch-Ajrakh: Largest contentful paint (ms) is 5711; the budget is 5442

expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 4

- Array []
+ Array [
+   "/crafts/Kutch-Ajrakh: performance scores 78; the budget is 80",
+   "/crafts/Kutch-Ajrakh: Largest contentful paint (ms) is 5711; the budget is 5442",
+ ]
```

# Test source

```ts
  1  | import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
  2  | import { tmpdir } from "node:os";
  3  | import { join } from "node:path";
  4  | 
  5  | import { chromium, expect, test } from "@playwright/test";
  6  | 
  7  | import { passPreviewProtection } from "../production/preview";
  8  | 
  9  | import { LIGHTHOUSE_CHECK, recordedLighthouse } from "./auditBaseline";
  10 | import { LIGHTHOUSE_FORMS, LIGHTHOUSE_RUNS, LIGHTHOUSE_TARGETS, lighthouseJudgement, lighthouseNumbers, medianNumbers, runtimeProblem, type LighthouseForm } from "./auditBudgets";
  11 | import { auditPaths } from "./keyPages";
  12 | import { runLighthouse } from "./lighthouseRun";
  13 | import { checkRecord, keepRecord, pathFileName, reportDir, type CheckNumbers } from "./report";
  14 | import { bypassToken, siteOrigin } from "./site";
  15 | 
  16 | const DEBUGGING_PORT = 9333;
  17 | const FORM_TIMEOUT_MS = 50 * 60_000;
  18 | 
  19 | type Measured = { runs: CheckNumbers[]; failures: string[] };
  20 | 
  21 | async function measure(form: LighthouseForm, path: string, port: number): Promise<Measured> {
  22 |   const folder = join(reportDir(), LIGHTHOUSE_CHECK, form.key);
  23 |   mkdirSync(folder, { recursive: true });
  24 |   const measured: Measured = { runs: [], failures: [] };
  25 |   for (let run = 1; run <= LIGHTHOUSE_RUNS; run += 1) {
  26 |     const outputBase = join(folder, pathFileName(path, `lighthouse-${run}`));
  27 |     const result = await runLighthouse({ url: new URL(path, siteOrigin()).href, port, form, outputBase, html: run === 1 });
  28 |     const failure = runtimeProblem(result);
  29 |     if (failure) measured.failures.push(`run ${run}: ${failure}`);
  30 |     else measured.runs.push(lighthouseNumbers(result));
  31 |   }
  32 |   return measured;
  33 | }
  34 | 
  35 | async function auditPage(form: LighthouseForm, path: string, port: number): Promise<string[]> {
  36 |   const { runs, failures } = await measure(form, path, port);
  37 |   const numbers = medianNumbers(runs);
  38 |   const judged = runs.length ? lighthouseJudgement(numbers, LIGHTHOUSE_TARGETS[form.key], recordedLighthouse(path, form.key)) : { problems: failures, notes: [] };
  39 |   const notes = runs.length ? [`median of ${runs.length} runs`, ...failures, ...judged.notes] : judged.notes;
  40 |   keepRecord(checkRecord(LIGHTHOUSE_CHECK, `${path} at ${form.width} (${form.key})`, judged.problems, { subject: path, variant: form.key, notes, numbers }));
  41 |   return judged.problems.map((problem) => `${path}: ${problem}`);
  42 | }
  43 | 
  44 | LIGHTHOUSE_FORMS.forEach((form, index) => {
  45 |   test(`Lighthouse at ${form.width} keeps every page within its ${form.key} budget`, async () => {
  46 |     test.setTimeout(FORM_TIMEOUT_MS);
  47 |     const port = DEBUGGING_PORT + index;
  48 |     const profile = mkdtempSync(join(tmpdir(), "kv-lighthouse-"));
  49 |     const context = await chromium.launchPersistentContext(profile, { channel: "chromium", headless: true, viewport: null, args: [`--remote-debugging-port=${port}`] });
  50 |     try {
  51 |       await passPreviewProtection(context, siteOrigin(), bypassToken());
  52 |       const problems: string[] = [];
  53 |       for (const path of auditPaths()) problems.push(...(await auditPage(form, path, port)));
> 54 |       expect(problems, problems.join("\n")).toEqual([]);
     |                                             ^ Error: /crafts/Kutch-Ajrakh: performance scores 78; the budget is 80
  55 |     } finally {
  56 |       await context.close();
  57 |       rmSync(profile, { recursive: true, force: true });
  58 |     }
  59 |   });
  60 | });
  61 | 
```