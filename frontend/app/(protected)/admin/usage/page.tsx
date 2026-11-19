"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { RecordNotice } from "@/components/records/RecordNotice";
import { RecordSection } from "@/components/records/RecordSection";
import { RECORD_CELL, RECORD_HEAD_CELL, RECORD_HEAD_ROW, RECORD_NUMBER_CELL, RECORD_ROW, RECORD_TABLE } from "@/components/records/recordTable";
import { Button } from "@/components/ui/button";
import { Figure } from "@/components/ui/Figure";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { Skeleton } from "@/components/ui/Skeleton";
import { resolveRange, type RangeId } from "@/lib/dateRange";
import { byCount, formatDate } from "@/lib/format";
import { ceilingShare, fetchUsage, formatCount, formatUsd, money, monthlyCeiling, type UsageDayRow, type UsageReport } from "@/lib/usage";

const PERIODS: { value: RangeId; label: string }[] = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "month", label: "This month" }
];

type Stat = { label: string; value: string; note: string };

function usageStats(report: UsageReport): Stat[] {
  const ceiling = monthlyCeiling(report);
  const share = ceilingShare(report);
  return [
    { label: "Spend", value: formatUsd(report.spentUsd), note: `${formatDate(report.from)} to ${formatDate(report.to)}` },
    { label: "Calls", value: formatCount(report.calls), note: report.failures > 0 ? `${formatCount(report.failures)} failed` : "None failed" },
    {
      label: ceiling === null ? "This month" : "Monthly ceiling",
      value: formatUsd(report.spentThisMonthUsd),
      note: ceiling === null ? "No monthly ceiling" : `of ${formatUsd(report.ceilingUsd)}${share === null ? "" : `, ${Math.round(share)}% used`}`
    }
  ];
}

function UsageStats({ report }: { report: UsageReport }) {
  const share = ceilingShare(report);
  return (
    <dl className="grid border-t border-ink-1 sm:grid-cols-3 sm:gap-x-8" data-testid="usage-stats">
      {usageStats(report).map((stat, index) => (
        <div key={stat.label} className="grid content-start gap-1.5 border-b border-rule py-5">
          <dt className="font-ui text-label text-ink-3">{stat.label}</dt>
          <dd className="font-headline text-stat text-ink-1 tabular-nums lining-nums">{stat.value}</dd>
          <dd className="font-ui text-label text-ink-2 tabular-nums lining-nums">{stat.note}</dd>
          {index === 2 && share !== null ? (
            <dd>
              <ProgressBar className="mt-1 h-2" percent={share} role="progressbar" aria-label="Monthly ceiling used" aria-valuenow={Math.round(share)} aria-valuemin={0} aria-valuemax={100} />
            </dd>
          ) : null}
        </div>
      ))}
    </dl>
  );
}

function UsageTable({ title, head, rows, textColumns = 1 }: { title: string; head: string[]; rows: string[][]; textColumns?: number }) {
  return (
    <RecordSection title={title}>
      {rows.length === 0 ? (
        <p className="font-ui text-ui font-normal text-ink-2">Calls in this period appear here, with their tokens and spend.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className={`${RECORD_TABLE} min-w-xl`}>
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr className={RECORD_HEAD_ROW}>
                {head.map((cell, index) => (
                  <th key={cell} scope="col" className={index < textColumns ? RECORD_HEAD_CELL : `${RECORD_HEAD_CELL} text-end`}>
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`${row[0]}-${rowIndex}`} className={RECORD_ROW}>
                  {row.map((cell, index) =>
                    index === 0 ? (
                      <th key={index} scope="row" className={`${RECORD_CELL} text-start font-medium`}>
                        {cell}
                      </th>
                    ) : index < textColumns ? (
                      <td key={index} className={`${RECORD_CELL} text-ink-2`}>
                        {cell}
                      </td>
                    ) : (
                      <td key={index} className={`${RECORD_NUMBER_CELL} text-ink-2`}>
                        {cell}
                      </td>
                    )
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </RecordSection>
  );
}

function SpendByDay({ report }: { report: UsageReport }) {
  const busiest = useMemo(() => report.byDay.reduce<UsageDayRow | null>((top, row) => ((money(row.costUsd) ?? 0) > (top ? (money(top.costUsd) ?? 0) : -1) ? row : top), null), [report]);
  if (!busiest || report.byDay.length === 0) return null;
  const peak = money(busiest.costUsd) ?? 0;
  return (
    <Figure number={1} title={`The busiest day was ${formatDate(busiest.day)}, at ${formatUsd(busiest.costUsd)}`} dek="Calls and spend per day in the period. Each bar is a day's spend against the busiest day.">
      <ol className="grid gap-2">
        {report.byDay.map((row) => {
          const cost = money(row.costUsd) ?? 0;
          return (
            <li key={row.day} className="grid grid-cols-[5.5rem_minmax(0,1fr)_auto_auto] sm:grid-cols-[6.5rem_minmax(0,1fr)_6rem_5rem] items-center gap-3 font-ui text-label tabular-nums lining-nums">
              <span className="text-ink-2">{formatDate(row.day)}</span>
              <ProgressBar percent={peak > 0 ? (cost / peak) * 100 : 0} aria-hidden />
              <span className="text-end text-ink-3">{`${formatCount(row.calls)} ${byCount(row.calls, "call", "calls")}`}</span>
              <span className="text-end text-ink-1">{formatUsd(row.costUsd)}</span>
            </li>
          );
        })}
      </ol>
    </Figure>
  );
}

export default function UsagePage() {
  const [period, setPeriod] = useState<RangeId>("month");
  const [report, setReport] = useState<UsageReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [round, setRound] = useState(0);
  const generation = useRef(0);

  useEffect(() => {
    const mine = ++generation.current;
    fetchUsage(resolveRange({ range: period, from: "", to: "" }))
      .then((next) => {
        if (mine !== generation.current) return;
        setReport(next);
        setError(null);
      })
      .catch((err) => {
        if (mine !== generation.current) return;
        setError(err instanceof Error ? err.message : "Couldn't load usage.");
      });
  }, [period, round]);

  return (
    <>
      <PageHeader
        title="Usage"
        kicker="Admin"
        description="Model calls and spend."
        actions={<SegmentedChoice label="Period" value={period} options={PERIODS} onChange={(next) => setPeriod(next as RangeId)} />}
      />
      {error ? (
        <RecordNotice tone="error" className="mb-8" action={<Button variant="quiet" size="sm" onClick={() => setRound((value) => value + 1)}>Try again</Button>}>
          {error}
        </RecordNotice>
      ) : null}
      {report === null ? (
        error ? null : <Skeleton shape="chart" label="Reading the usage" />
      ) : (
        <div className="grid gap-12">
          <UsageStats report={report} />
          <SpendByDay report={report} />
          <UsageTable
            title="By task"
            head={["Task", "Calls", "Failed", "Tokens in", "Tokens out", "Spend"]}
            rows={report.byTask.map((row) => [row.label, formatCount(row.calls), formatCount(row.failures), formatCount(row.inputTokens), formatCount(row.outputTokens), formatUsd(row.costUsd)])}
          />
          <UsageTable
            title="By model"
            head={["Model", "Provider", "Calls", "Failed", "p95", "Spend"]}
            textColumns={2}
            rows={report.byProvider.map((row) => [row.model, row.name, formatCount(row.calls), formatCount(row.failures), row.p95LatencyMs === null ? "-" : `${(row.p95LatencyMs / 1000).toFixed(1)} s`, formatUsd(row.costUsd)])}
          />
        </div>
      )}
    </>
  );
}
