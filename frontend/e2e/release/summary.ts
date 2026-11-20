import { writeFileSync } from "node:fs";
import { join } from "node:path";

import { PRODUCTION_ORIGIN } from "../production/preview";

import { AUDIT_BASELINE, AXE_CHECK, CANDIDATE_FILE, LIGHTHOUSE_CHECK, baselineCandidate } from "./auditBaseline";
import { readRecords, reportDir, writeSummary } from "./report";

const DEFAULT_TITLE = "Release checks";

function writeCandidate(dir: string): void {
  const records = readRecords(dir);
  if (!records.some((record) => record.check === AXE_CHECK || record.check === LIGHTHOUSE_CHECK)) return;
  const run = Number(process.env.GITHUB_RUN_ID ?? "");
  const candidate = baselineCandidate(AUDIT_BASELINE, records, {
    site: new URL(process.env.E2E_BASE_URL || PRODUCTION_ORIGIN).origin,
    recordedAt: new Date().toISOString().slice(0, 10),
    run: Number.isInteger(run) && run > 0 ? run : null
  });
  writeFileSync(join(dir, CANDIDATE_FILE), `${JSON.stringify(candidate, null, 2)}\n`, "utf8");
}

export default async function globalTeardown(): Promise<void> {
  const dir = reportDir();
  writeSummary(process.env.E2E_REPORT_TITLE || DEFAULT_TITLE, dir);
  writeCandidate(dir);
}
