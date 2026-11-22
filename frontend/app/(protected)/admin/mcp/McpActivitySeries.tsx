import { DataTable, type DataColumn } from "@/components/charts/DataTable";
import { RecordSection } from "@/components/records/RecordSection";
import { Figure } from "@/components/ui/Figure";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { busiestPoint, callsFailed, callsMade, type McpActivity } from "@/lib/mcpActivityContract";
import { EMPTY_PERIOD, countLabel, pointLabel, seriesTitle } from "@/lib/mcpActivityView";

const COLUMNS: DataColumn[] = [
  { key: "when", label: "When" },
  { key: "ok", label: "Answered", numeric: true },
  { key: "tool", label: "Tool errors", numeric: true },
  { key: "protocol", label: "Protocol errors", numeric: true }
];

function SeriesTable({ activity }: { activity: McpActivity }) {
  const rows = activity.series.map((point) => ({
    key: point.start,
    cells: { when: pointLabel(point, activity.unit), ok: countLabel(point.ok), tool: countLabel(point.toolErrors), protocol: countLabel(point.protocolErrors) }
  }));
  return <DataTable caption="Calls by outcome over the period" columns={COLUMNS} rows={rows} className="min-w-md" />;
}

export function McpActivitySeries({ activity }: { activity: McpActivity }) {
  const title = seriesTitle(activity);
  const busiest = busiestPoint(activity.series);
  if (!title || !busiest) {
    return (
      <RecordSection title="Calls over time">
        <p className="font-ui text-ui font-normal text-ink-2">{EMPTY_PERIOD}</p>
      </RecordSection>
    );
  }
  const peak = callsMade(busiest);
  const dek = activity.unit === "week" ? "Calls per week, each bar against the busiest week, with the calls that failed." : "Calls per day, each bar against the busiest day, with the calls that failed.";
  return (
    <Figure number={1} title={title} dek={dek} table={<SeriesTable activity={activity} />} valueCount={activity.series.length}>
      <ol className="grid gap-2">
        {activity.series.map((point) => (
          <li key={point.start} className="grid grid-cols-[6.5rem_minmax(0,1fr)_auto_auto] items-center gap-3 font-ui text-label tabular-nums lining-nums sm:grid-cols-[9rem_minmax(0,1fr)_5rem_6rem]">
            <span className="text-ink-2">{pointLabel(point, activity.unit)}</span>
            <ProgressBar percent={(callsMade(point) / peak) * 100} aria-hidden />
            <span className="text-end text-ink-1">{countLabel(callsMade(point))}</span>
            <span className="text-end text-ink-3">{callsFailed(point) > 0 ? `${countLabel(callsFailed(point))} failed` : ""}</span>
          </li>
        ))}
      </ol>
    </Figure>
  );
}
