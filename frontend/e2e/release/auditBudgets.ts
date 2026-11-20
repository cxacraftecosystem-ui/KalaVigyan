import type { CheckNumbers } from "./report";

export type FormFactor = "mobile" | "desktop";
export type LighthouseCategory = "performance" | "accessibility" | "best-practices";
export type MetricName = "lcpMs" | "cls" | "tbtMs" | "bytes";

export type LighthouseForm = { key: FormFactor; width: number; flags: readonly string[] };
export type LighthouseBudget = { scores: Record<LighthouseCategory, number>; metrics: Record<MetricName, number> };

export type LighthouseResult = {
  runtimeError?: { code?: string; message?: string };
  categories?: Partial<Record<string, { score: number | null }>>;
  audits?: Partial<Record<string, { numericValue?: number }>>;
};

export type AxeViolation = { id: string; impact?: string | null; help: string; nodes: readonly unknown[] };

export const LIGHTHOUSE_CATEGORIES: readonly LighthouseCategory[] = ["performance", "accessibility", "best-practices"];

export const LIGHTHOUSE_FORMS: readonly LighthouseForm[] = [
  {
    key: "mobile",
    width: 360,
    flags: ["--form-factor=mobile", "--screenEmulation.mobile=true", "--screenEmulation.width=360", "--screenEmulation.height=800", "--screenEmulation.deviceScaleFactor=2"]
  },
  { key: "desktop", width: 1440, flags: ["--preset=desktop", "--screenEmulation.width=1440", "--screenEmulation.height=900"] }
];

export const LIGHTHOUSE_BUDGETS: Record<FormFactor, LighthouseBudget> = {
  mobile: {
    scores: { performance: 0.5, accessibility: 0.95, "best-practices": 0.9 },
    metrics: { lcpMs: 4000, cls: 0.1, tbtMs: 600, bytes: 5_000_000 }
  },
  desktop: {
    scores: { performance: 0.8, accessibility: 0.95, "best-practices": 0.9 },
    metrics: { lcpMs: 2500, cls: 0.1, tbtMs: 300, bytes: 5_000_000 }
  }
};

export const AXE_TAGS: readonly string[] = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
export const AXE_FAILING_IMPACTS: readonly string[] = ["critical", "serious"];
export const AXE_IMPACTS: readonly string[] = ["critical", "serious", "moderate", "minor"];

const METRIC_AUDITS: Record<MetricName, string> = {
  lcpMs: "largest-contentful-paint",
  cls: "cumulative-layout-shift",
  tbtMs: "total-blocking-time",
  bytes: "total-byte-weight"
};

const METRIC_LABELS: Record<MetricName, string> = {
  lcpMs: "Largest contentful paint (ms)",
  cls: "Cumulative layout shift",
  tbtMs: "Total blocking time (ms)",
  bytes: "Transferred bytes"
};

const METRIC_DIGITS: Record<MetricName, number> = { lcpMs: 0, cls: 3, tbtMs: 0, bytes: 0 };

function rounded(value: number, digits: number): number {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function score(result: LighthouseResult, category: LighthouseCategory): number | null {
  const value = result.categories?.[category]?.score;
  return typeof value === "number" ? value : null;
}

function metric(result: LighthouseResult, name: MetricName): number | null {
  const value = result.audits?.[METRIC_AUDITS[name]]?.numericValue;
  return typeof value === "number" && Number.isFinite(value) ? rounded(value, METRIC_DIGITS[name]) : null;
}

export function lighthouseNumbers(result: LighthouseResult): CheckNumbers {
  const numbers: CheckNumbers = {};
  for (const category of LIGHTHOUSE_CATEGORIES) {
    const value = score(result, category);
    numbers[category] = value === null ? null : Math.round(value * 100);
  }
  for (const name of Object.keys(METRIC_AUDITS) as MetricName[]) numbers[name] = metric(result, name);
  return numbers;
}

export function lighthouseProblems(result: LighthouseResult, budget: LighthouseBudget): string[] {
  if (result.runtimeError?.code) return [`Lighthouse could not audit the page: ${result.runtimeError.code} ${result.runtimeError.message ?? ""}`.trim()];
  const problems: string[] = [];
  for (const category of LIGHTHOUSE_CATEGORIES) {
    const value = score(result, category);
    const floor = Math.round(budget.scores[category] * 100);
    if (value === null) problems.push(`Lighthouse gave no ${category} score`);
    else if (Math.round(value * 100) < floor) problems.push(`${category} scores ${Math.round(value * 100)}; the budget is ${floor}`);
  }
  for (const name of Object.keys(METRIC_AUDITS) as MetricName[]) {
    const value = metric(result, name);
    if (value === null) problems.push(`Lighthouse measured no ${METRIC_LABELS[name].toLowerCase()}`);
    else if (value > budget.metrics[name]) problems.push(`${METRIC_LABELS[name]} is ${value}; the budget is ${budget.metrics[name]}`);
  }
  return problems;
}

export function axeNumbers(violations: readonly AxeViolation[]): CheckNumbers {
  const numbers: CheckNumbers = {};
  for (const impact of AXE_IMPACTS) numbers[impact] = violations.filter((violation) => violation.impact === impact).length;
  return numbers;
}

export function axeProblems(violations: readonly AxeViolation[]): string[] {
  return violations
    .filter((violation) => AXE_FAILING_IMPACTS.includes(violation.impact ?? ""))
    .map((violation) => `${violation.id} (${violation.impact}) on ${violation.nodes.length} ${violation.nodes.length === 1 ? "element" : "elements"}: ${violation.help}`);
}

export function axeNotes(violations: readonly AxeViolation[]): string[] {
  return violations
    .filter((violation) => !AXE_FAILING_IMPACTS.includes(violation.impact ?? ""))
    .map((violation) => `${violation.id} (${violation.impact ?? "no impact"}) on ${violation.nodes.length}`);
}
