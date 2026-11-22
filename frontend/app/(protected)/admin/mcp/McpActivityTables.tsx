import { DataTable, type DataColumn, type DataRow } from "@/components/charts/DataTable";
import { RecordSection } from "@/components/records/RecordSection";
import { formatDate, formatDateTime } from "@/lib/format";
import { callsFailed, callsMade, type McpActivity } from "@/lib/mcpActivityContract";
import { EMPTY_PERIOD, NO_CLIENTS, NO_CONNECTIONS, countLabel } from "@/lib/mcpActivityView";

const TOOL_COLUMNS: DataColumn[] = [
  { key: "tool", label: "Tool" },
  { key: "calls", label: "Calls", numeric: true },
  { key: "ok", label: "Answered", numeric: true },
  { key: "toolErrors", label: "Tool errors", numeric: true },
  { key: "protocolErrors", label: "Protocol errors", numeric: true }
];
const CLIENT_COLUMNS: DataColumn[] = [
  { key: "client", label: "Client" },
  { key: "connections", label: "Live connections", numeric: true },
  { key: "calls", label: "Calls", numeric: true },
  { key: "failed", label: "Failed", numeric: true },
  { key: "lastUsed", label: "Last used" }
];
const CONNECTION_COLUMNS: DataColumn[] = [
  { key: "client", label: "Client" },
  { key: "account", label: "Account" },
  { key: "connected", label: "Connected" },
  { key: "lastUsed", label: "Last used" },
  { key: "calls", label: "Calls", numeric: true },
  { key: "failed", label: "Failed", numeric: true },
  { key: "state", label: "State" }
];

function ActivityTable({ title, empty, columns, rows }: { title: string; empty: string; columns: DataColumn[]; rows: DataRow[] }) {
  return (
    <RecordSection title={title}>
      {rows.length === 0 ? (
        <p className="font-ui text-ui font-normal text-ink-2">{empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <DataTable caption={title} columns={columns} rows={rows} className="min-w-xl" />
        </div>
      )}
    </RecordSection>
  );
}

function account(name: string, email: string) {
  return (
    <span className="grid">
      <span>{name}</span>
      <span className="font-ui text-caption text-ink-3">{email}</span>
    </span>
  );
}

export function McpActivityTables({ activity }: { activity: McpActivity }) {
  const tools = activity.tools.map((row) => ({
    key: row.tool,
    cells: { tool: row.tool, calls: countLabel(callsMade(row)), ok: countLabel(row.ok), toolErrors: countLabel(row.toolErrors), protocolErrors: countLabel(row.protocolErrors) }
  }));
  const clients = activity.clients.map((row) => ({
    key: row.clientName,
    cells: { client: row.clientName, connections: countLabel(row.connections), calls: countLabel(callsMade(row)), failed: countLabel(callsFailed(row)), lastUsed: formatDateTime(row.lastUsedAt) }
  }));
  const connections = activity.connections.map((row) => ({
    key: row.id,
    cells: {
      client: row.clientName,
      account: account(row.accountName, row.accountEmail),
      connected: formatDate(row.connectedAt),
      lastUsed: formatDateTime(row.lastUsedAt),
      calls: countLabel(callsMade(row)),
      failed: countLabel(callsFailed(row)),
      state: row.ended ? "Ended" : "Live"
    }
  }));
  return (
    <>
      <ActivityTable title="By tool" empty={EMPTY_PERIOD} columns={TOOL_COLUMNS} rows={tools} />
      <ActivityTable title="By client" empty={NO_CLIENTS} columns={CLIENT_COLUMNS} rows={clients} />
      <ActivityTable title="Connections" empty={NO_CONNECTIONS} columns={CONNECTION_COLUMNS} rows={connections} />
    </>
  );
}
