import { PRODUCTION_ORIGIN, siteRefusal } from "../production/preview";

export function siteOrigin(): string {
  const origin = new URL(process.env.E2E_BASE_URL || PRODUCTION_ORIGIN).origin;
  const refused = siteRefusal(origin);
  if (refused) throw new Error(refused);
  return origin;
}

export function apiOrigin(): string {
  const value = process.env.E2E_API_URL ?? "";
  if (!value) throw new Error("Set E2E_API_URL to the API origin, the repository variable API_BASE_URL (docs/RUNBOOK.md, MCP server).");
  const origin = new URL(value);
  if (origin.protocol !== "https:") throw new Error(`E2E_API_URL must be an https origin, not ${value}`);
  return origin.origin;
}

export function bypassToken(): string {
  return process.env.E2E_VERCEL_BYPASS ?? "";
}
