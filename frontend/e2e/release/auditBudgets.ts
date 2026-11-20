import type { CheckNumbers } from "./report";

export type FormFactor = "mobile" | "desktop";
export type LighthouseCategory = "performance" | "accessibility" | "best-practices";
export type MetricName = "lcpMs" | "cls" | "tbtMs" | "bytes";

export type LighthouseForm = { key: FormFactor; width: number; flags: readonly string[] };
export type LighthouseBudget = { scores: Record<LighthouseCategory, number>; metrics: Record<MetricName, number> };
export type Judgement = { problems: string[]; notes: string[] };

export type LighthouseResult = {
  runtimeError?: { code?: string; message?: string };
  categories?: Partial<Record<string, { score: number | null }>>;
  audits?: Partial<Record<string, { numericValue?: number }>>;
};

export type AxeViolation = { id: string; impact?: string | null; help: string; nodes: readonly unknown[] };

export const LIGHTHOUSE_CATEGORIES: readonly LighthouseCategory[] = ["performance", "accessibility", "best-practices"];
export const METRICS: readonly MetricName[] = ["lcpMs", "cls", "tbtMs", "bytes"];
export const REPORTED_ONLY: ReadonlySet<MetricName> = new Set(["bytes"]);

export const LIGHTHOUSE_FORMS: readonly LighthouseForm[] = [
  {
    key: "mobile",
    width: 360,
    flags: ["--form-factor=mobile", "--screenEmulation.mobile=true", "--screenEmulation.width=360", "--screenEmulation.height=800", "--screenEmulation.deviceScaleFactor=2"]
  },
  { key: "desktop", width: 1440, flags: ["--preset=desktop", "--screenEmulation.width=1440", "--screenEmulation.height=900"] }
];

export const LIGHTHOUSE_TARGETS: Record<FormFactor, LighthouseBudget> = {
  mobile: {
    scores: { performance: 0.8, accessibility: 0.95, "best-practices": 0.9 },
    metrics: { lcpMs: 2500, cls: 0.1, tbtMs: 200, bytes: 3_000_000 }
  },
  desktop: {
    scores: { performance: 0.9, accessibility: 0.95, "best-practices": 0.9 },
    metrics: { lcpMs: 2500, cls: 0.1, tbtMs: 200, bytes: 3_000_000 }
  }
};

export const LIGHTHOUSE_RUNS = 3;
export const SCORE_SLACK: Record<LighthouseCategory, number> = { performance: 10, accessibility: 2, "best-practices": 2 };
export const METRIC_SLACK: Record<Exclude<MetricName, "cls">, number> = { lcpMs: 1.5, tbtMs: 2, bytes: 1.1 };
export const CLS_SLACK = 0.05;
export const NOISY_NUMBERS: ReadonlySet<string> = new Set(["performance", "lcpMs", "tbtMs"]);

export const AXE_TAGS: readonly string[] = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
export const AXE_FAILING_IMPACTS: readonly string[] = ["critical", "serious"];
export const UNRECORDED = "not recorded yet, ";
export const RECORDED = "recorded, ";

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

function known(recorded: CheckNumbers | undefined, name: string): number | null {
  const value = recorded?.[name];
  return typeof value === "number" ? value : null;
}

export function lighthouseNumbers(result: LighthouseResult): CheckNumbers {
  const numbers: CheckNumbers = {};
  for (const category of LIGHTHOUSE_CATEGORIES) {
    const value = result.categories?.[category]?.score;
    numbers[category] = typeof value === "number" ? Math.round(value * 100) : null;
  }
  for (const name of METRICS) {
    const value = result.audits?.[METRIC_AUDITS[name]]?.numericValue;
    numbers[name] = typeof value === "number" && Number.isFinite(value) ? rounded(value, METRIC_DIGITS[name]) : null;
  }
  return numbers;
}

export function scoreFloor(category: LighthouseCategory, target: LighthouseBudget, recorded: CheckNumbers | undefined): number {
  const wanted = Math.round(target.scores[category] * 100);
  const before = known(recorded, category);
  return before === null ? wanted : Math.min(wanted, before - SCORE_SLACK[category]);
}

export function metricCeiling(name: MetricName, target: LighthouseBudget, recorded: CheckNumbers | undefined): number {
  const before = known(recorded, name);
  if (before === null) return target.metrics[name];
  const allowance = name === "cls" ? rounded(before + CLS_SLACK, 3) : Math.round(before * METRIC_SLACK[name]);
  return Math.max(target.metrics[name], allowance);
}

function breach(judged: Judgement, recorded: CheckNumbers | undefined, text: string): void {
  if (recorded) judged.problems.push(text);
  else judged.notes.push(`${UNRECORDED}${text}`);
}

function scoreJudgement(numbers: CheckNumbers, target: LighthouseBudget, recorded: CheckNumbers | undefined, judged: Judgement): void {
  for (const category of LIGHTHOUSE_CATEGORIES) {
    const value = numbers[category];
    const floor = scoreFloor(category, target, recorded);
    const wanted = Math.round(target.scores[category] * 100);
    if (value === null) judged.problems.push(`Lighthouse gave no ${category} score`);
    else if (value < floor) breach(judged, recorded, `${category} scores ${value}; the budget is ${floor}`);
    else if (value < wanted) judged.notes.push(`${category} ${value} is under the target ${wanted}`);
  }
}

function metricJudgement(numbers: CheckNumbers, target: LighthouseBudget, recorded: CheckNumbers | undefined, judged: Judgement): void {
  for (const name of METRICS) {
    const value = numbers[name];
    const ceiling = metricCeiling(name, target, recorded);
    if (value === null) judged.problems.push(`Lighthouse measured no ${METRIC_LABELS[name].toLowerCase()}`);
    else if (value > ceiling && !REPORTED_ONLY.has(name)) breach(judged, recorded, `${METRIC_LABELS[name]} is ${value}; the budget is ${ceiling}`);
    else if (value > target.metrics[name]) judged.notes.push(`${METRIC_LABELS[name]} ${value} is over the target ${target.metrics[name]}`);
  }
}

export function runtimeProblem(result: LighthouseResult): string | null {
  const failure = result.runtimeError;
  return failure?.code ? `Lighthouse could not audit the page: ${failure.code} ${failure.message ?? ""}`.trim() : null;
}

function median(values: number[], digits: number): number {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : rounded((ordered[middle - 1] + ordered[middle]) / 2, digits);
}

export function medianNumbers(runs: readonly CheckNumbers[]): CheckNumbers {
  const numbers: CheckNumbers = {};
  for (const name of [...LIGHTHOUSE_CATEGORIES, ...METRICS]) {
    const values = runs.map((run) => run[name]).filter((value): value is number => typeof value === "number");
    numbers[name] = values.length ? median(values, name === "cls" ? 3 : 0) : null;
  }
  return numbers;
}

export function lighthouseJudgement(numbers: CheckNumbers, target: LighthouseBudget, recorded?: CheckNumbers): Judgement {
  const judged: Judgement = { problems: [], notes: [] };
  scoreJudgement(numbers, target, recorded, judged);
  metricJudgement(numbers, target, recorded, judged);
  return judged;
}

function failing(violation: AxeViolation): boolean {
  return AXE_FAILING_IMPACTS.includes(violation.impact ?? "");
}

function elements(count: number): string {
  return `${count} ${count === 1 ? "element" : "elements"}`;
}

export function axeRuleNodes(violations: readonly AxeViolation[]): CheckNumbers {
  const numbers: CheckNumbers = {};
  for (const violation of violations.filter(failing)) numbers[violation.id] = violation.nodes.length;
  return numbers;
}

export function axeJudgement(violations: readonly AxeViolation[], recorded?: CheckNumbers): Judgement {
  const judged: Judgement = { problems: [], notes: [] };
  for (const violation of violations) {
    const count = violation.nodes.length;
    const before = known(recorded, violation.id);
    if (!failing(violation)) judged.notes.push(`${violation.id} (${violation.impact ?? "no impact"}) on ${elements(count)}`);
    else if (before === null) breach(judged, recorded, `${violation.id} (${violation.impact}) on ${elements(count)}: ${violation.help}`);
    else if (count > before) judged.problems.push(`${violation.id} (${violation.impact}) grew to ${elements(count)} from the recorded ${before}: ${violation.help}`);
    else judged.notes.push(`${RECORDED}${violation.id} (${violation.impact}) on ${elements(count)}`);
  }
  return judged;
}
