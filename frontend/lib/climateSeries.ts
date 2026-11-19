import { niceCeiling } from "@/lib/climateView";
import type { ClimateSeries, ClimateTrend } from "@/lib/explainerInsight";

export type SeriesPoint = { year: number; value: number };
export type SeriesDomain = { low: number; high: number; ticks: number[] };
export type TrendLine = { from: SeriesPoint; to: SeriesPoint };

const DECADE = 10;
const TICK_COUNT = 3;

export function seriesPoints(series: ClimateSeries): SeriesPoint[] {
  return series.values.flatMap((value, index) => (value === null ? [] : [{ year: series.firstYear + index, value }]));
}

export function median(values: readonly number[]): number {
  if (values.length === 0) throw new RangeError("the median of no values");
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function theilSenIntercept(points: readonly SeriesPoint[], slopePerYear: number): number {
  return median(points.map((point) => point.value - slopePerYear * point.year));
}

export function trendLine(points: readonly SeriesPoint[], trend: Pick<ClimateTrend, "slopePerDecade">): TrendLine {
  const slope = trend.slopePerDecade / DECADE;
  const intercept = theilSenIntercept(points, slope);
  const first = points[0].year;
  const last = points[points.length - 1].year;
  return { from: { year: first, value: intercept + slope * first }, to: { year: last, value: intercept + slope * last } };
}

function evenTicks(low: number, high: number): number[] {
  const step = (high - low) / (TICK_COUNT - 1);
  return Array.from({ length: TICK_COUNT }, (_, index) => Number((low + step * index).toFixed(6)));
}

export function seriesDomain(values: readonly number[], fromZero: boolean): SeriesDomain {
  const most = Math.max(...values);
  if (fromZero) {
    const high = niceCeiling(most);
    return { low: 0, high, ticks: evenTicks(0, high) };
  }
  const least = Math.min(...values);
  const low = Math.floor(least);
  const high = Math.max(Math.ceil(most), low + 1);
  return { low, high, ticks: evenTicks(low, high) };
}

export function scaleOf(domain: { low: number; high: number }, range: { start: number; end: number }): (value: number) => number {
  const span = domain.high - domain.low || 1;
  return (value: number) => range.start + ((value - domain.low) / span) * (range.end - range.start);
}

export function matchingTrend(series: ClimateSeries, trends: readonly ClimateTrend[]): ClimateTrend | null {
  return trends.find((trend) => trend.variable === series.variable && trend.district.districtLgd === series.district.districtLgd && trend.datasetCode === series.datasetCode) ?? null;
}
