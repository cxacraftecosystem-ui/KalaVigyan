import { valuesLabel } from "@/components/answer/place/AnswerFigure";
import { DataTable } from "@/components/charts/DataTable";
import { formatMeasure } from "@/lib/measure";
import type { RegionDataset } from "@/lib/regionContract";
import { statCaption, valueLabel } from "@/lib/regionView";
import { extremes, seriesColour, seriesFinding, seriesSpan, sparkMarks, sparkPath, SPARK_VIEW, type YearlySeries } from "@/lib/yearlySeries";

const COLUMNS = [
  { key: "year", label: "Year" },
  { key: "value", label: "Value", numeric: true }
];

function Sparkline({ series }: { series: YearlySeries }) {
  const marks = sparkMarks(series);
  const { lowest, highest } = extremes(series);
  const named = marks.filter((mark) => mark.year === lowest.year || mark.year === highest.year);
  return (
    <svg viewBox={`0 0 ${SPARK_VIEW.width} ${SPARK_VIEW.height}`} className="block h-10 w-full max-w-60 [forced-color-adjust:none]" aria-hidden="true" focusable="false" data-testid="yearly-sparkline">
      <path d={sparkPath(marks)} fill="none" stroke={seriesColour(series)} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {named.map((mark) => (
        <circle key={mark.year} cx={mark.x} cy={mark.y} r={3} fill="var(--chart-emph)" stroke="var(--ground)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" data-testid="yearly-extreme" data-year={mark.year} />
      ))}
    </svg>
  );
}

export function YearlySeriesRow({ series, dataset }: { series: YearlySeries; dataset: RegionDataset }) {
  const value = series.first;
  const finding = seriesFinding(series);
  const span = seriesSpan(series);
  const rows = series.points.map((point) => ({ key: String(point.year), cells: { year: String(point.year), value: formatMeasure(point.value, value.unit) } }));
  return (
    <div className="grid min-w-0 gap-1" data-testid="yearly-series" data-years={series.points.length}>
      <dt className="font-ui text-caption text-ink-3">{`${valueLabel(value)}, each year ${span}`}</dt>
      <dd className="font-ui text-label text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]" data-testid="yearly-finding">
        {finding}
      </dd>
      <dd className="min-w-0">
        <Sparkline series={series} />
      </dd>
      <dd className="font-ui text-caption text-ink-3">{[statCaption(value), dataset.title, value.resolution, span].join(" · ")}</dd>
      <dd className="min-w-0">
        <details data-testid="yearly-values">
          <summary className="kv-link inline-flex min-h-target cursor-pointer items-center font-ui text-ui">{valuesLabel(rows.length)}</summary>
          <div className="mt-2 max-h-72 overflow-y-auto">
            <DataTable caption={`${valueLabel(value)}, ${statCaption(value).toLowerCase()}, by year`} columns={COLUMNS} rows={rows} />
          </div>
        </details>
      </dd>
    </div>
  );
}
