import { scaleOf } from "@/lib/climateSeries";
import { formatMeasure } from "@/lib/measure";
import type { RegionValue } from "@/lib/regionContract";

export const YEAR_PERIOD = /^\d{4}$/;
export const SERIES_YEARS_MIN = 3;
export const SPARK_VIEW = { width: 240, height: 40, inset: 4 } as const;

export type YearValue = { year: number; value: number };
export type YearlySeries = { key: string; first: RegionValue; points: YearValue[] };
export type FacetRow = { kind: "value"; value: RegionValue } | { kind: "series"; series: YearlySeries };
export type SparkMark = YearValue & { x: number; y: number };

const SERIES_TOKEN: Record<string, string> = {
  annual_precipitation: "var(--series-rain)",
  annual_mean_temperature: "var(--series-heat)"
};
const DEFAULT_SERIES = "var(--chart-series)";

function seriesKey(value: RegionValue): string | null {
  if (!YEAR_PERIOD.test(value.period) || value.value === null || value.valueText !== null) return null;
  return [value.datasetCode, value.variable, value.depth ?? "", value.stat, value.aggregation, value.unit].join("|");
}

export function foldedRows(values: readonly RegionValue[]): FacetRow[] {
  const groups = new Map<string, RegionValue[]>();
  for (const value of values) {
    const key = seriesKey(value);
    if (key !== null) groups.set(key, [...(groups.get(key) ?? []), value]);
  }
  const rows: FacetRow[] = [];
  const placed = new Set<string>();
  for (const value of values) {
    const key = seriesKey(value);
    const group = key === null ? undefined : groups.get(key);
    if (key === null || !group || group.length < SERIES_YEARS_MIN) {
      rows.push({ kind: "value", value });
    } else if (!placed.has(key)) {
      placed.add(key);
      rows.push({ kind: "series", series: yearlySeries(key, group) });
    }
  }
  return rows;
}

function yearlySeries(key: string, values: readonly RegionValue[]): YearlySeries {
  const points = values.map((value) => ({ year: Number(value.period), value: value.value as number })).sort((a, b) => a.year - b.year);
  return { key, first: values[0], points };
}

export function seriesSpan(series: YearlySeries): string {
  const first = series.points[0].year;
  const last = series.points[series.points.length - 1].year;
  return first === last ? String(first) : `${first}–${last}`;
}

export function extremes(series: YearlySeries): { lowest: YearValue; highest: YearValue } {
  let lowest = series.points[0];
  let highest = series.points[0];
  for (const point of series.points) {
    if (point.value < lowest.value) lowest = point;
    if (point.value > highest.value) highest = point;
  }
  return { lowest, highest };
}

export function seriesFinding(series: YearlySeries): string {
  const { lowest, highest } = extremes(series);
  const unit = series.first.unit;
  return `Highest ${formatMeasure(highest.value, unit)} in ${highest.year}, lowest ${formatMeasure(lowest.value, unit)} in ${lowest.year}`;
}

export function seriesColour(series: YearlySeries): string {
  return SERIES_TOKEN[series.first.variable] ?? DEFAULT_SERIES;
}

export function sparkMarks(series: YearlySeries): SparkMark[] {
  const { width, height, inset } = SPARK_VIEW;
  const values = series.points.map((point) => point.value);
  const x = scaleOf({ low: series.points[0].year, high: series.points[series.points.length - 1].year }, { start: inset, end: width - inset });
  const y = scaleOf({ low: Math.min(...values), high: Math.max(...values) }, { start: height - inset, end: inset });
  return series.points.map((point) => ({ ...point, x: x(point.year), y: y(point.value) }));
}

export function sparkPath(marks: readonly SparkMark[]): string {
  return marks.map((mark, at) => `${at === 0 || mark.year !== marks[at - 1].year + 1 ? "M" : "L"}${mark.x.toFixed(1)} ${mark.y.toFixed(1)}`).join(" ");
}
