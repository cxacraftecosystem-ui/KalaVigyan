import { execFile } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { promisify } from "node:util";

import { previewBlockedUrls } from "../production/preview";

import { LIGHTHOUSE_CATEGORIES, type LighthouseForm, type LighthouseResult } from "./auditBudgets";

export type LighthouseRun = { url: string; port: number; form: LighthouseForm; outputBase: string; html: boolean };

const run = promisify(execFile);
const RUN_TIMEOUT_MS = 4 * 60_000;
const OUTPUT_BYTES = 64 * 1024 * 1024;
const JSON_SUFFIX = ".report.json";

export function reportPath(audit: Pick<LighthouseRun, "outputBase">): string {
  return `${audit.outputBase}${JSON_SUFFIX}`;
}

export function lighthouseArgs(audit: LighthouseRun): string[] {
  const outputs = audit.html ? ["--output=json", "--output=html", `--output-path=${audit.outputBase}`] : ["--output=json", `--output-path=${reportPath(audit)}`];
  const blocked = previewBlockedUrls(audit.url).map((pattern) => `--blocked-url-patterns=${pattern}`);
  return [audit.url, `--port=${audit.port}`, ...outputs, `--only-categories=${LIGHTHOUSE_CATEGORIES.join(",")}`, "--quiet", ...blocked, ...audit.form.flags];
}

export async function runLighthouse(audit: LighthouseRun): Promise<LighthouseResult> {
  const cli = require.resolve("lighthouse/cli/index.js");
  try {
    await run(process.execPath, [cli, ...lighthouseArgs(audit)], { timeout: RUN_TIMEOUT_MS, maxBuffer: OUTPUT_BYTES });
  } catch (error) {
    if (!existsSync(reportPath(audit))) throw new Error(`Lighthouse wrote no report for ${audit.url}: ${error instanceof Error ? error.message : String(error)}`);
  }
  return JSON.parse(readFileSync(reportPath(audit), "utf8")) as LighthouseResult;
}
