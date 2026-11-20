import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export type CheckNumbers = Record<string, number | null>;

export type CheckRecord = {
  check: string;
  target: string;
  subject: string | null;
  variant: string | null;
  ok: boolean;
  problems: string[];
  notes: string[];
  numbers: CheckNumbers;
};

type RecordExtra = Partial<Pick<CheckRecord, "subject" | "variant" | "notes" | "numbers">>;

export const SUMMARY_FILE = "summary.md";

const RECORDS = "records";
const UNSAFE_NAME = /[^A-Za-z0-9-]+/g;

export function reportDir(): string {
  return process.env.E2E_REPORT_DIR || "release-run";
}

export function recordFileName(record: Pick<CheckRecord, "check" | "target">): string {
  return `${record.check}-${record.target}`.replace(UNSAFE_NAME, "_").replace(/^_+|_+$/g, "") + ".json";
}

export function pathFileName(path: string, extension: string): string {
  const name = path === "/" ? "landing" : path.replace(/^\/+/, "").replace(UNSAFE_NAME, "_");
  return `${name}.${extension}`;
}

export function checkRecord(check: string, target: string, problems: string[], extra: RecordExtra = {}): CheckRecord {
  return {
    check,
    target,
    subject: extra.subject ?? null,
    variant: extra.variant ?? null,
    ok: problems.length === 0,
    problems,
    notes: extra.notes ?? [],
    numbers: extra.numbers ?? {}
  };
}

export function keepRecord(record: CheckRecord, dir: string = reportDir()): void {
  const folder = join(dir, RECORDS);
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, recordFileName(record)), JSON.stringify(record, null, 2), "utf8");
}

export function readRecords(dir: string = reportDir()): CheckRecord[] {
  const folder = join(dir, RECORDS);
  if (!existsSync(folder)) return [];
  return readdirSync(folder)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => JSON.parse(readFileSync(join(folder, name), "utf8")) as CheckRecord);
}

function cell(text: string): string {
  return text.replace(/\|/g, "\\|").replace(/\s+/g, " ").trim();
}

function numbersText(numbers: CheckNumbers): string {
  return Object.entries(numbers)
    .map(([name, value]) => `${name} ${value === null ? "none" : value}`)
    .join(", ");
}

function outcomeText(record: CheckRecord): string {
  if (record.ok) return record.notes.length ? `passed (${record.notes.join("; ")})` : "passed";
  return `failed: ${record.problems.join("; ")}`;
}

export function summaryMarkdown(title: string, records: readonly CheckRecord[]): string {
  const failed = records.filter((record) => !record.ok).length;
  const lines = [`## ${title}`, "", `${records.length} checks, ${failed} failed.`, ""];
  if (records.length === 0) return [...lines, "No check wrote a record.", ""].join("\n");
  lines.push("| Check | Target | Outcome | Measured |", "|---|---|---|---|");
  for (const record of records) {
    lines.push(`| ${cell(record.check)} | ${cell(record.target)} | ${cell(outcomeText(record))} | ${cell(numbersText(record.numbers))} |`);
  }
  return [...lines, ""].join("\n");
}

export function writeSummary(title: string, dir: string = reportDir()): string {
  const markdown = summaryMarkdown(title, readRecords(dir));
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, SUMMARY_FILE), markdown, "utf8");
  return markdown;
}
