"use client";

import { useId, useMemo } from "react";

import { ChartLine } from "@/components/monograph/kinds/general/ChartLine";
import { GeneralFigure, UnitTable, type RenderUnit } from "@/components/monograph/kinds/general/GeneralFigure";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { chartRange, chartSpecShape, parsedSpec, share, type ChartSeries, type ChartSpec } from "@/lib/componentSpecsGeneral";

import "./general.css";

type Range = { low: number; high: number };

function BarRows({ series, range, emphasis, renderUnit }: { series: ChartSeries; range: Range; emphasis: number | null; renderUnit: RenderUnit }) {
  return (
    <ol className="grid" data-testid="general-bars">
      {series.points.map((point, at) => (
        <li key={point.reading} className="grid grid-cols-[minmax(5rem,9rem)_minmax(0,1fr)_auto] items-center gap-3 border-t border-rule py-2 font-ui text-label">
          <span className="min-w-0 break-words text-ink-1">{renderUnit(point.label)}</span>
          <span className="kv-general-track relative h-2" aria-hidden>
            <i className="kv-general-bar absolute inset-y-0 start-0" data-emph={at === emphasis || undefined} style={{ width: `${(share(point.value, range) * 100).toFixed(2)}%` }} />
          </span>
          <span className="text-end text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{renderUnit(point.reading)}</span>
        </li>
      ))}
    </ol>
  );
}

function Panel({ chart, series, index, range, renderUnit }: { chart: ChartSpec; series: ChartSeries; index: number; range: Range; renderUnit: RenderUnit }) {
  const nameId = useId();
  const emphasis = index === 0 ? chart.emphasis : null;
  return (
    <section className="grid min-w-0 content-start gap-2" aria-labelledby={nameId}>
      <p id={nameId} className="font-ui text-label font-semibold text-ink-1">
        {renderUnit(series.name)}
      </p>
      {chart.form === "bars" ? (
        <BarRows series={series} range={range} emphasis={emphasis} renderUnit={renderUnit} />
      ) : (
        <ChartLine series={series} range={range} emphasis={emphasis} labelledBy={nameId} renderUnit={renderUnit} />
      )}
    </section>
  );
}

function valuesTable(chart: ChartSpec, titleId: string, renderUnit: RenderUnit) {
  const head = [{ key: "label", content: "" }, ...chart.series.map((series, at) => ({ key: `s${at}`, content: renderUnit(series.name), numeric: true }))];
  const rows = chart.series[0].points.map((point, at) => ({
    key: point.reading,
    cells: [{ key: "label", content: renderUnit(point.label) }, ...chart.series.map((series, s) => ({ key: `s${s}`, content: renderUnit(series.points[at].reading), numeric: true }))]
  }));
  return <UnitTable labelledBy={titleId} head={head} rows={rows} />;
}

export function ChartView({ spec, renderUnit }: ComponentViewProps) {
  const chart = useMemo(() => parsedSpec(chartSpecShape, spec), [spec]);
  const titleId = useId();
  if (!chart) return null;
  const range = chartRange(chart);
  const values = chart.form === "line" ? { count: chart.series[0].points.length * chart.series.length, table: valuesTable(chart, titleId, renderUnit) } : undefined;
  return (
    <GeneralFigure kind="general_chart" head={chart.head} titleId={titleId} renderUnit={renderUnit} values={values}>
      <div className="grid gap-3">
        <p className="font-ui text-caption text-ink-3">{renderUnit(chart.valueLabel)}</p>
        <div className="grid gap-6 md:grid-cols-[repeat(auto-fit,minmax(18rem,1fr))]" data-testid="general-chart-panels">
          {chart.series.map((series, at) => (
            <Panel key={series.name} chart={chart} series={series} index={at} range={range} renderUnit={renderUnit} />
          ))}
        </div>
      </div>
    </GeneralFigure>
  );
}
