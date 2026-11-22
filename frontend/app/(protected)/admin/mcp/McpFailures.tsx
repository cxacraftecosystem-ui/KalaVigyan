import { DataTable, type DataColumn } from "@/components/charts/DataTable";
import { RecordSection } from "@/components/records/RecordSection";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime } from "@/lib/format";
import type { McpActivity } from "@/lib/mcpActivityContract";
import { FAILURES_NOTE, NO_FAILURES, OUTCOME_LABELS, REASON_NOT_KEPT } from "@/lib/mcpActivityView";

const TITLE = "Recent failures";
const COLUMNS: DataColumn[] = [
  { key: "when", label: "When" },
  { key: "client", label: "Client" },
  { key: "tool", label: "Tool" },
  { key: "outcome", label: "Outcome" },
  { key: "reason", label: "Reason" }
];

export function McpFailures({ activity }: { activity: McpActivity }) {
  const rows = activity.failures.map((failure, at) => ({
    key: `${failure.calledAt}-${at}`,
    cells: {
      when: formatDateTime(failure.calledAt),
      client: failure.clientName,
      tool: failure.tool,
      outcome: <StatusBadge tone={failure.outcome === "PROTOCOL_ERROR" ? "error" : "neutral"} label={OUTCOME_LABELS[failure.outcome]} />,
      reason: <span className="block min-w-xs max-w-measure whitespace-normal text-ink-2">{failure.reason ?? REASON_NOT_KEPT}</span>
    }
  }));
  return (
    <RecordSection title={TITLE} description={FAILURES_NOTE}>
      {rows.length === 0 ? (
        <p className="font-ui text-ui font-normal text-ink-2">{NO_FAILURES}</p>
      ) : (
        <div className="overflow-x-auto">
          <DataTable caption={TITLE} columns={COLUMNS} rows={rows} className="min-w-3xl" />
        </div>
      )}
    </RecordSection>
  );
}
