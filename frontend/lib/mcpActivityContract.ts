import { INSTANT, UUID } from "@/lib/answerShapes";
import { apiFetch, buildQuery } from "@/lib/api";
import { boolean, integer, list, matching, nullable, object, oneOf, parseShape, text, type Shape } from "@/lib/shape";

export const MCP_ACTIVITY_PATH = "/settings/mcp-activity";
export const MCP_ACTIVITY_SCHEMA_VERSION = 1;
export const MCP_PERIODS = [7, 30, 180] as const;
export const DEFAULT_MCP_PERIOD: McpPeriod = 30;
export const FAILED_OUTCOMES = ["TOOL_ERROR", "PROTOCOL_ERROR"] as const;
export const ALL_CLIENTS = "all";

export type McpPeriod = (typeof MCP_PERIODS)[number];
export type FailedOutcome = (typeof FAILED_OUTCOMES)[number];
export type Outcomes = { ok: number; toolErrors: number; protocolErrors: number };
export type ActivityPoint = Outcomes & { start: string };
export type ToolActivity = Outcomes & { tool: string };
export type ClientActivity = Outcomes & { clientName: string; connections: number; lastUsedAt: string | null };
export type ConnectionActivity = Outcomes & {
  id: string;
  clientName: string;
  accountName: string;
  accountEmail: string;
  scopes: string[];
  connectedAt: string;
  lastUsedAt: string | null;
  ended: boolean;
};
export type FailedCall = {
  calledAt: string;
  clientName: string;
  connectionId: string;
  tool: string;
  outcome: FailedOutcome;
  reason: string | null;
};
export type McpActivity = {
  schemaVersion: typeof MCP_ACTIVITY_SCHEMA_VERSION;
  days: number;
  firstDay: string;
  lastDay: string;
  unit: "day" | "week";
  client: string | null;
  connection: string | null;
  keptDays: number;
  series: ActivityPoint[];
  tools: ToolActivity[];
  clients: ClientActivity[];
  connections: ConnectionActivity[];
  failures: FailedCall[];
};
export type McpScope = { days: McpPeriod; client: string | null; connection: string | null };

const DAY = matching(/^\d{4}-\d{2}-\d{2}$/, "a calendar day");
const COUNT = integer;
const outcomes = { ok: COUNT, toolErrors: COUNT, protocolErrors: COUNT };

const activityShape: Shape<McpActivity> = object({
  schemaVersion: oneOf([MCP_ACTIVITY_SCHEMA_VERSION] as const),
  days: oneOf(MCP_PERIODS),
  firstDay: DAY,
  lastDay: DAY,
  unit: oneOf(["day", "week"] as const),
  client: nullable(text),
  connection: nullable(UUID),
  keptDays: COUNT,
  series: list(object<ActivityPoint>({ ...outcomes, start: DAY })),
  tools: list(object<ToolActivity>({ ...outcomes, tool: text })),
  clients: list(object<ClientActivity>({ ...outcomes, clientName: text, connections: COUNT, lastUsedAt: nullable(INSTANT) })),
  connections: list(
    object<ConnectionActivity>({
      ...outcomes,
      id: UUID,
      clientName: text,
      accountName: text,
      accountEmail: text,
      scopes: list(text),
      connectedAt: INSTANT,
      lastUsedAt: nullable(INSTANT),
      ended: boolean
    })
  ),
  failures: list(
    object<FailedCall>({
      calledAt: INSTANT,
      clientName: text,
      connectionId: UUID,
      tool: text,
      outcome: oneOf(FAILED_OUTCOMES),
      reason: nullable(text)
    })
  )
});

export function parseMcpActivity(raw: unknown): McpActivity {
  return parseShape(activityShape, raw);
}

export async function fetchMcpActivity(scope: McpScope): Promise<McpActivity> {
  return parseMcpActivity(await apiFetch<unknown>(`${MCP_ACTIVITY_PATH}${buildQuery(scope)}`));
}

export function callsMade(row: Outcomes): number {
  return row.ok + row.toolErrors + row.protocolErrors;
}

export function callsFailed(row: Outcomes): number {
  return row.toolErrors + row.protocolErrors;
}

export function totals(rows: readonly Outcomes[]): Outcomes {
  return rows.reduce<Outcomes>(
    (sum, row) => ({ ok: sum.ok + row.ok, toolErrors: sum.toolErrors + row.toolErrors, protocolErrors: sum.protocolErrors + row.protocolErrors }),
    { ok: 0, toolErrors: 0, protocolErrors: 0 }
  );
}

export function busiestPoint(series: readonly ActivityPoint[]): ActivityPoint | null {
  return series.reduce<ActivityPoint | null>((top, point) => (callsMade(point) > (top ? callsMade(top) : 0) ? point : top), null);
}

export function lastCallAt(clients: readonly ClientActivity[]): string | null {
  const stamps = clients.map((client) => client.lastUsedAt).filter((stamp): stamp is string => stamp !== null);
  return stamps.reduce<string | null>((latest, stamp) => (latest === null || Date.parse(stamp) > Date.parse(latest) ? stamp : latest), null);
}

export function scopeFromParams(params: Pick<URLSearchParams, "get">): McpScope {
  const asked = Number(params.get("days"));
  const days = (MCP_PERIODS as readonly number[]).includes(asked) ? (asked as McpPeriod) : DEFAULT_MCP_PERIOD;
  const connection = params.get("connection");
  const client = connection ? null : params.get("client");
  return { days, client: client || null, connection: connection || null };
}

export function scopeHref(scope: McpScope): string {
  return `/admin/mcp${buildQuery({ days: scope.days === DEFAULT_MCP_PERIOD ? null : scope.days, client: scope.client, connection: scope.connection })}`;
}

export function scopeValue(scope: McpScope): string {
  if (scope.connection) return `connection:${scope.connection}`;
  if (scope.client) return `client:${scope.client}`;
  return ALL_CLIENTS;
}

export function scopeChosen(value: string, days: McpPeriod): McpScope {
  if (value.startsWith("connection:")) return { days, client: null, connection: value.slice("connection:".length) };
  if (value.startsWith("client:")) return { days, client: value.slice("client:".length), connection: null };
  return { days, client: null, connection: null };
}
