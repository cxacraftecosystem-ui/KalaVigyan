import { writeSummary } from "./report";

const DEFAULT_TITLE = "Release checks";

export default async function globalTeardown(): Promise<void> {
  writeSummary(process.env.E2E_REPORT_TITLE || DEFAULT_TITLE);
}
