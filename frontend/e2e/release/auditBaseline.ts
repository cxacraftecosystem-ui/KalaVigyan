import recorded from "./audit-baseline.json";
import { LIGHTHOUSE_CATEGORIES, METRICS, NOISY_NUMBERS, type FormFactor } from "./auditBudgets";
import type { CheckNumbers, CheckRecord } from "./report";

export type AuditBaseline = {
  schemaVersion: 1;
  site: string;
  recordedAt: string;
  run: number | null;
  lighthouse: Record<string, Partial<Record<FormFactor, CheckNumbers>>>;
  axe: Record<string, CheckNumbers>;
};

export type BaselineMeta = Pick<AuditBaseline, "site" | "recordedAt" | "run">;

export const CANDIDATE_FILE = "audit-baseline.candidate.json";
export const LIGHTHOUSE_CHECK = "lighthouse";
export const AXE_CHECK = "axe";

const HIGHER_IS_BETTER = new Set<string>(LIGHTHOUSE_CATEGORIES);

function isTable(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function checkedBaseline(value: unknown): AuditBaseline {
  if (!isTable(value) || value.schemaVersion !== 1) throw new Error("audit-baseline.json is not an audit baseline of schema 1");
  if (!isTable(value.lighthouse) || !isTable(value.axe)) throw new Error("audit-baseline.json needs a lighthouse and an axe table");
  return value as AuditBaseline;
}

export const AUDIT_BASELINE = checkedBaseline(recorded);

export function recordedLighthouse(path: string, form: FormFactor, baseline: AuditBaseline = AUDIT_BASELINE): CheckNumbers | undefined {
  return baseline.lighthouse[path]?.[form];
}

export function recordedAxe(path: string, baseline: AuditBaseline = AUDIT_BASELINE): CheckNumbers | undefined {
  return baseline.axe[path];
}

function better(name: string, before: number | null | undefined, now: number | null | undefined): number | null {
  if (typeof before !== "number") return typeof now === "number" ? now : null;
  if (typeof now !== "number") return before;
  return HIGHER_IS_BETTER.has(name) ? Math.max(before, now) : Math.min(before, now);
}

function recordedNumber(name: string, before: number | null | undefined, now: number | null | undefined): number | null {
  if (NOISY_NUMBERS.has(name) && typeof now === "number") return now;
  return better(name, before, now);
}

function sorted<T>(entries: Record<string, T>): Record<string, T> {
  return Object.fromEntries(Object.entries(entries).sort(([a], [b]) => a.localeCompare(b)));
}

function lighthouseCandidate(baseline: AuditBaseline, records: readonly CheckRecord[]): AuditBaseline["lighthouse"] {
  const next: AuditBaseline["lighthouse"] = JSON.parse(JSON.stringify(baseline.lighthouse));
  for (const record of records.filter((item) => item.check === LIGHTHOUSE_CHECK && item.subject && item.variant)) {
    const form = record.variant as FormFactor;
    const before = next[record.subject as string]?.[form];
    const numbers: CheckNumbers = {};
    for (const name of [...LIGHTHOUSE_CATEGORIES, ...METRICS]) numbers[name] = recordedNumber(name, before?.[name], record.numbers[name]);
    next[record.subject as string] = { ...next[record.subject as string], [form]: numbers };
  }
  return sorted(next);
}

function measuredAxe(records: readonly CheckRecord[]): Record<string, CheckNumbers> {
  const measured: Record<string, CheckNumbers> = {};
  for (const record of records.filter((item) => item.check === AXE_CHECK && item.subject)) {
    const page = (measured[record.subject as string] ??= {});
    for (const [rule, nodes] of Object.entries(record.numbers)) page[rule] = Math.max(page[rule] ?? 0, nodes ?? 0);
  }
  return measured;
}

function axeCandidate(baseline: AuditBaseline, records: readonly CheckRecord[]): AuditBaseline["axe"] {
  const next: AuditBaseline["axe"] = { ...baseline.axe };
  for (const [path, rules] of Object.entries(measuredAxe(records))) {
    const before = baseline.axe[path];
    const kept = Object.entries(rules).filter(([rule]) => !before || typeof before[rule] === "number");
    next[path] = sorted(Object.fromEntries(kept.map(([rule, nodes]) => [rule, better(rule, before?.[rule], nodes)])));
  }
  return sorted(next);
}

export function baselineCandidate(baseline: AuditBaseline, records: readonly CheckRecord[], meta: BaselineMeta): AuditBaseline {
  return { schemaVersion: 1, ...meta, lighthouse: lighthouseCandidate(baseline, records), axe: axeCandidate(baseline, records) };
}
