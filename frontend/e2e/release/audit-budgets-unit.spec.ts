import { expect, test } from "@playwright/test";

import { LIGHTHOUSE_FORMS, axeNotes, axeNumbers, axeProblems, lighthouseNumbers, lighthouseProblems, type LighthouseBudget, type LighthouseResult } from "./auditBudgets";
import { lighthouseArgs, reportPath } from "./lighthouseRun";

const BUDGET: LighthouseBudget = {
  scores: { performance: 0.8, accessibility: 0.95, "best-practices": 0.9 },
  metrics: { lcpMs: 2500, cls: 0.1, tbtMs: 300, bytes: 2_000_000 }
};

function result(scores: [number | null, number | null, number | null], metrics: [number, number, number, number]): LighthouseResult {
  return {
    categories: { performance: { score: scores[0] }, accessibility: { score: scores[1] }, "best-practices": { score: scores[2] } },
    audits: {
      "largest-contentful-paint": { numericValue: metrics[0] },
      "cumulative-layout-shift": { numericValue: metrics[1] },
      "total-blocking-time": { numericValue: metrics[2] },
      "total-byte-weight": { numericValue: metrics[3] }
    }
  };
}

test("a page at its budget passes and the numbers are read as whole scores and rounded metrics", () => {
  const measured = result([0.8, 0.95, 0.9], [2500.4, 0.1, 299.6, 2_000_000]);
  expect(lighthouseProblems(measured, BUDGET)).toEqual([]);
  expect(lighthouseNumbers(measured)).toEqual({ performance: 80, accessibility: 95, "best-practices": 90, lcpMs: 2500, cls: 0.1, tbtMs: 300, bytes: 2_000_000 });
});

test("each score under its floor and each metric over its ceiling is named", () => {
  const problems = lighthouseProblems(result([0.79, 0.9, null], [3100, 0.25, 450, 2_500_000]), BUDGET);
  expect(problems).toEqual([
    "performance scores 79; the budget is 80",
    "accessibility scores 90; the budget is 95",
    "Lighthouse gave no best-practices score",
    "Largest contentful paint (ms) is 3100; the budget is 2500",
    "Cumulative layout shift is 0.25; the budget is 0.1",
    "Total blocking time (ms) is 450; the budget is 300",
    "Transferred bytes is 2500000; the budget is 2000000"
  ]);
});

test("a page Lighthouse could not load fails on its runtime error alone", () => {
  expect(lighthouseProblems({ runtimeError: { code: "NO_FCP", message: "The page did not paint any content." } }, BUDGET)).toEqual([
    "Lighthouse could not audit the page: NO_FCP The page did not paint any content."
  ]);
});

test("serious and critical axe violations fail, moderate and minor ones are noted and every impact is counted", () => {
  const violations = [
    { id: "color-contrast", impact: "serious", help: "Elements must meet minimum color contrast ratio thresholds", nodes: [{}, {}] },
    { id: "button-name", impact: "critical", help: "Buttons must have discernible text", nodes: [{}] },
    { id: "region", impact: "moderate", help: "All page content should be contained by landmarks", nodes: [{}, {}, {}] }
  ];
  expect(axeProblems(violations)).toEqual([
    "color-contrast (serious) on 2 elements: Elements must meet minimum color contrast ratio thresholds",
    "button-name (critical) on 1 element: Buttons must have discernible text"
  ]);
  expect(axeNotes(violations)).toEqual(["region (moderate) on 3"]);
  expect(axeNumbers(violations)).toEqual({ critical: 1, serious: 1, moderate: 1, minor: 0 });
});

test("Lighthouse audits at 360 as a phone and at 1440 as a desktop", () => {
  expect(LIGHTHOUSE_FORMS.map((form) => [form.key, form.width])).toEqual([
    ["mobile", 360],
    ["desktop", 1440]
  ]);
  expect(LIGHTHOUSE_FORMS[0].flags).toContain("--screenEmulation.width=360");
  expect(LIGHTHOUSE_FORMS[1].flags).toContain("--screenEmulation.width=1440");
});

test("Lighthouse is driven on the shared browser's port and writes its JSON and HTML reports beside each other", () => {
  const audit = { url: "https://kalavigyan.vercel.app/map", port: 9333, form: LIGHTHOUSE_FORMS[1], outputBase: "audit/lighthouse/desktop/map.lighthouse" };
  const args = lighthouseArgs(audit);
  expect(args.slice(0, 5)).toEqual(["https://kalavigyan.vercel.app/map", "--port=9333", "--output=json", "--output=html", "--output-path=audit/lighthouse/desktop/map.lighthouse"]);
  expect(args).toContain("--only-categories=performance,accessibility,best-practices");
  expect(args).toContain("--preset=desktop");
  expect(reportPath(audit)).toBe("audit/lighthouse/desktop/map.lighthouse.report.json");
});
