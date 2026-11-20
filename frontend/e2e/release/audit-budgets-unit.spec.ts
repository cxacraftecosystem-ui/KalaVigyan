import { expect, test } from "@playwright/test";

import {
  LIGHTHOUSE_FORMS,
  axeJudgement,
  axeRuleNodes,
  lighthouseJudgement,
  lighthouseNumbers,
  medianNumbers,
  metricCeiling,
  runtimeProblem,
  scoreFloor,
  type LighthouseBudget,
  type LighthouseResult
} from "./auditBudgets";
import { lighthouseArgs, reportPath } from "./lighthouseRun";

const TARGET: LighthouseBudget = {
  scores: { performance: 0.8, accessibility: 0.95, "best-practices": 0.9 },
  metrics: { lcpMs: 2500, cls: 0.1, tbtMs: 200, bytes: 2_000_000 }
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

function measured(scores: [number | null, number | null, number | null], metrics: [number, number, number, number]) {
  return lighthouseNumbers(result(scores, metrics));
}

const VIOLATIONS = [
  { id: "color-contrast", impact: "serious", help: "Elements must meet minimum color contrast ratio thresholds", nodes: [{}, {}] },
  { id: "button-name", impact: "critical", help: "Buttons must have discernible text", nodes: [{}] },
  { id: "region", impact: "moderate", help: "All page content should be contained by landmarks", nodes: [{}, {}, {}] }
];

test("Lighthouse numbers are whole scores and rounded metrics", () => {
  expect(lighthouseNumbers(result([0.934, 0.95, 0.9], [2500.4, 0.10049, 299.6, 2_000_000]))).toEqual({
    performance: 93,
    accessibility: 95,
    "best-practices": 90,
    lcpMs: 2500,
    cls: 0.1,
    tbtMs: 300,
    bytes: 2_000_000
  });
});

test("an unrecorded page is held to the targets and a recorded one may slip only by the slack from its record", () => {
  expect(scoreFloor("performance", TARGET, undefined)).toBe(80);
  expect(scoreFloor("performance", TARGET, { performance: 73 })).toBe(63);
  expect(scoreFloor("performance", TARGET, { performance: 99 })).toBe(80);
  expect(scoreFloor("accessibility", TARGET, { accessibility: 93 })).toBe(91);
  expect(metricCeiling("lcpMs", TARGET, undefined)).toBe(2500);
  expect(metricCeiling("lcpMs", TARGET, { lcpMs: 9913 })).toBe(14870);
  expect(metricCeiling("lcpMs", TARGET, { lcpMs: 347 })).toBe(2500);
  expect(metricCeiling("cls", TARGET, { cls: 0.154 })).toBe(0.204);
  expect(metricCeiling("tbtMs", TARGET, { tbtMs: 0 })).toBe(200);
  expect(metricCeiling("tbtMs", TARGET, { tbtMs: 292 })).toBe(584);
  expect(metricCeiling("bytes", TARGET, { bytes: 6_151_534 })).toBe(6_766_687);
});

test("a recorded page that holds its record passes and names what misses the target", () => {
  const judged = lighthouseJudgement(measured([0.7, 0.93, 1], [9913, 0.012, 245, 2_010_096]), TARGET, { performance: 70, accessibility: 93, "best-practices": 96, lcpMs: 9913, cls: 0.012, tbtMs: 245, bytes: 2_010_096 });
  expect(judged.problems).toEqual([]);
  expect(judged.notes).toEqual([
    "performance 70 is under the target 80",
    "accessibility 93 is under the target 95",
    "Largest contentful paint (ms) 9913 is over the target 2500",
    "Total blocking time (ms) 245 is over the target 200",
    "Transferred bytes 2010096 is over the target 2000000"
  ]);
});

test("a recorded page that meets its targets may move within them, and fails once it misses both the target and its record, except on weight, which is only reported", () => {
  const recorded = { performance: 90, accessibility: 100, "best-practices": 100, lcpMs: 1000, cls: 0, tbtMs: 100, bytes: 1_000_000 };
  expect(lighthouseJudgement(measured([0.81, 0.96, 0.91], [2400, 0.09, 190, 1_900_000]), TARGET, recorded).problems).toEqual([]);
  const judged = lighthouseJudgement(measured([0.79, 0.9, null], [3400, 0.2, 260, 2_600_000]), TARGET, recorded);
  expect(judged.problems).toEqual([
    "performance scores 79; the budget is 80",
    "accessibility scores 90; the budget is 95",
    "Lighthouse gave no best-practices score",
    "Largest contentful paint (ms) is 3400; the budget is 2500",
    "Cumulative layout shift is 0.2; the budget is 0.1",
    "Total blocking time (ms) is 260; the budget is 200"
  ]);
  expect(judged.notes).toContain("Transferred bytes 2600000 is over the target 2000000");
});

test("an unrecorded page that misses the targets is noted, not failed, unless Lighthouse could not measure it", () => {
  const judged = lighthouseJudgement(measured([0.5, 0.95, 0.9], [4000, 0.05, 100, 1_000_000]), TARGET, undefined);
  expect(judged.problems).toEqual([]);
  expect(judged.notes).toEqual(["not recorded yet, performance scores 50; the budget is 80", "not recorded yet, Largest contentful paint (ms) is 4000; the budget is 2500"]);
  expect(runtimeProblem({ runtimeError: { code: "NO_FCP", message: "The page did not paint any content." } })).toBe("Lighthouse could not audit the page: NO_FCP The page did not paint any content.");
  expect(runtimeProblem(result([1, 1, 1], [1, 0, 0, 1]))).toBeNull();
});

test("a page is judged on the median of its runs, the mean of the middle two when a run is missing", () => {
  const runs = [measured([0.7, 1, 1], [9913, 0.1, 245, 2_000_000]), measured([0.8, 1, 0.96], [3330, 0.106, 120, 2_000_100]), measured([0.75, 1, 1], [5000, 0.1, 400, 1_999_900])];
  expect(medianNumbers(runs)).toEqual({ performance: 75, accessibility: 100, "best-practices": 100, lcpMs: 5000, cls: 0.1, tbtMs: 245, bytes: 2_000_000 });
  expect(medianNumbers(runs.slice(0, 2))).toEqual({ performance: 75, accessibility: 100, "best-practices": 98, lcpMs: 6622, cls: 0.103, tbtMs: 183, bytes: 2_000_050 });
  expect(medianNumbers([])).toEqual({ performance: null, accessibility: null, "best-practices": null, lcpMs: null, cls: null, tbtMs: null, bytes: null });
});

test("a recorded page fails on a new serious or critical axe rule or on more elements than recorded", () => {
  const judged = axeJudgement(VIOLATIONS, { "color-contrast": 1 });
  expect(judged.problems).toEqual([
    "color-contrast (serious) grew to 2 elements from the recorded 1: Elements must meet minimum color contrast ratio thresholds",
    "button-name (critical) on 1 element: Buttons must have discernible text"
  ]);
  expect(judged.notes).toEqual(["region (moderate) on 3 elements"]);
});

test("a recorded axe violation that does not grow is noted, and an unrecorded page only notes what it finds", () => {
  expect(axeJudgement(VIOLATIONS, { "color-contrast": 2, "button-name": 4 })).toEqual({
    problems: [],
    notes: ["recorded, color-contrast (serious) on 2 elements", "recorded, button-name (critical) on 1 element", "region (moderate) on 3 elements"]
  });
  expect(axeJudgement(VIOLATIONS, undefined).problems).toEqual([]);
  expect(axeJudgement(VIOLATIONS, {}).problems).toHaveLength(2);
});

test("only serious and critical rules are counted, by the elements they touch", () => {
  expect(axeRuleNodes(VIOLATIONS)).toEqual({ "color-contrast": 2, "button-name": 1 });
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
  const audit = { url: "https://kalavigyan.vercel.app/map", port: 9333, form: LIGHTHOUSE_FORMS[1], outputBase: "audit/lighthouse/desktop/map.lighthouse-1", html: true };
  const args = lighthouseArgs(audit);
  expect(args.slice(0, 5)).toEqual(["https://kalavigyan.vercel.app/map", "--port=9333", "--output=json", "--output=html", "--output-path=audit/lighthouse/desktop/map.lighthouse-1"]);
  expect(args).toContain("--only-categories=performance,accessibility,best-practices");
  expect(args).toContain("--preset=desktop");
  expect(reportPath(audit)).toBe("audit/lighthouse/desktop/map.lighthouse-1.report.json");
  const repeat = { ...audit, outputBase: "audit/lighthouse/desktop/map.lighthouse-2", html: false };
  expect(lighthouseArgs(repeat).slice(0, 4)).toEqual(["https://kalavigyan.vercel.app/map", "--port=9333", "--output=json", "--output-path=audit/lighthouse/desktop/map.lighthouse-2.report.json"]);
});
