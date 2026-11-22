import type { SelectOption } from "@/components/ui/selectFilter";
import { byCount, formatCalendarDay, formatDateTime } from "@/lib/format";
import {
  ALL_CLIENTS,
  MCP_PERIODS,
  busiestPoint,
  callsFailed,
  callsMade,
  lastCallAt,
  totals,
  type ActivityPoint,
  type FailedOutcome,
  type McpActivity
} from "@/lib/mcpActivityContract";

export type ActivityStat = { label: string; value: string; note: string };

export const PERIOD_OPTIONS = MCP_PERIODS.map((days) => ({ value: String(days), label: `${days} days` }));
export const OUTCOME_LABELS: Record<FailedOutcome, string> = { TOOL_ERROR: "Tool error", PROTOCOL_ERROR: "Protocol error" };
export const EMPTY_PERIOD = "Calls from connected AI clients appear here, by tool and outcome, with the reason for each failure.";
export const NO_FAILURES = "Every call in this period was answered.";
export const FAILURES_NOTE = "The newest fifty, each with the refusal's own words; arguments and results are never kept.";
export const REASON_NOT_KEPT = "Recorded before reasons were kept.";
export const NO_CLIENTS = "Each AI client that connects is listed here with its connections and calls.";
export const NO_CONNECTIONS = "Each connection a person makes from an AI client is listed here with its calls.";
export const KEPT_NOTE = (keptDays: number) =>
  `Each call is kept ${keptDays} days with its connection; the daily count by client, tool and outcome is kept for good.`;

export function countLabel(count: number): string {
  return count.toLocaleString("en-IN");
}

export function pointLabel(point: ActivityPoint, unit: McpActivity["unit"]): string {
  const day = formatCalendarDay(point.start);
  return unit === "week" ? `Week of ${day}` : day;
}

export function seriesTitle(activity: McpActivity): string | null {
  const busiest = busiestPoint(activity.series);
  if (!busiest) return null;
  const calls = `${countLabel(callsMade(busiest))} ${byCount(callsMade(busiest), "call", "calls")}`;
  const day = formatCalendarDay(busiest.start);
  return activity.unit === "week" ? `The busiest week began ${day}, with ${calls}` : `The busiest day was ${day}, with ${calls}`;
}

export function scopedLastCall(activity: McpActivity): string | null {
  if (activity.connection) return activity.connections.find((item) => item.id === activity.connection)?.lastUsedAt ?? null;
  if (activity.client) return activity.clients.find((item) => item.clientName === activity.client)?.lastUsedAt ?? null;
  return lastCallAt(activity.clients);
}

export function activityStats(activity: McpActivity): ActivityStat[] {
  const sum = totals(activity.series);
  const last = scopedLastCall(activity);
  return [
    { label: "Calls", value: countLabel(callsMade(sum)), note: `${formatCalendarDay(activity.firstDay)} to ${formatCalendarDay(activity.lastDay)}` },
    {
      label: "Failed",
      value: countLabel(callsFailed(sum)),
      note: `${countLabel(sum.toolErrors)} ${byCount(sum.toolErrors, "tool error", "tool errors")}, ${countLabel(sum.protocolErrors)} ${byCount(sum.protocolErrors, "protocol error", "protocol errors")}`
    },
    { label: "Last call", value: last ? formatDateTime(last) : "-", note: `${countLabel(activity.clients.length)} ${byCount(activity.clients.length, "client", "clients")}` }
  ];
}

export function scopeOptions(activity: McpActivity): SelectOption[] {
  const clients = activity.clients.map((client) => ({
    value: `client:${client.clientName}`,
    label: client.clientName,
    hint: `${countLabel(client.connections)} ${byCount(client.connections, "connection", "connections")}`,
    group: "Clients"
  }));
  const connections = activity.connections.map((connection) => ({
    value: `connection:${connection.id}`,
    label: `${connection.clientName} for ${connection.accountName}`,
    hint: connection.accountEmail,
    group: "Connections"
  }));
  return [{ value: ALL_CLIENTS, label: "Every client" }, ...clients, ...connections];
}
