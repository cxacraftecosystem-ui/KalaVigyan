"use client";

import { useMemo, useRef, useState, type KeyboardEvent } from "react";

import { TREND_SERIES } from "@/components/answer/insight/TrendChart";
import { AnswerFigure, type FigureTable } from "@/components/answer/place/AnswerFigure";
import { DataTable } from "@/components/charts/DataTable";
import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import { scaleOf, seriesDomain, seriesPoints, trendLine, type SeriesDomain, type SeriesPoint } from "@/lib/climateSeries";
import { slopeText, TREND_WORDS } from "@/lib/climateView";
import type { ClimateSeries, ClimateTrend } from "@/lib/explainerInsight";
import { formatMeasure } from "@/lib/measure";

const VIEW = { width: 640, height: 220 };
const PLOT = { start: 56, end: 512, top: 16, bottom: 188 };
const LABEL = { fontSize: "calc(var(--text-caption) * var(--k, 1))" };
const HALO = { strokeWidth: "calc(6px * var(--k, 1))" };
const COLUMNS = [
  { key: "year", label: "Year" },
  { key: "value", label: "Value", numeric: true }
];

type Scales = { x: (year: number) => number; y: (value: number) => number; domain: SeriesDomain };

function useScales(points: readonly SeriesPoint[], fromZero: boolean): Scales {
  return useMemo(() => {
    const domain = seriesDomain(points.map((point) => point.value), fromZero);
    const x = scaleOf({ low: points[0].year, high: points[points.length - 1].year }, { start: PLOT.start, end: PLOT.end });
    const y = scaleOf(domain, { start: PLOT.bottom, end: PLOT.top });
    return { x, y, domain };
  }, [points, fromZero]);
}

function Grid({ scales, unit, years }: { scales: Scales; unit: string; years: readonly number[] }) {
  return (
    <g className="font-ui [font-variant-numeric:lining-nums_tabular-nums]">
      {scales.domain.ticks.map((tick) => (
        <g key={tick}>
          <line x1={PLOT.start} x2={PLOT.end} y1={scales.y(tick)} y2={scales.y(tick)} stroke={tick === 0 ? "var(--chart-axis-line)" : "var(--chart-grid)"} strokeWidth={1} vectorEffect="non-scaling-stroke" />
          <text x={PLOT.start - 8} y={scales.y(tick)} textAnchor="end" dominantBaseline="central" fill="var(--chart-axis-text)" style={LABEL}>
            {formatMeasure(tick, unit)}
          </text>
        </g>
      ))}
      {years.map((year, index) => (
        <text key={year} x={scales.x(year)} y={PLOT.bottom + 18} textAnchor={index === 0 ? "start" : "end"} fill="var(--chart-axis-text)" style={LABEL}>
          {year}
        </text>
      ))}
    </g>
  );
}

function TrendMarks({ points, trend, scales }: { points: readonly SeriesPoint[]; trend: ClimateTrend; scales: Scales }) {
  const line = trendLine(points, trend);
  const [x1, y1, x2, y2] = [scales.x(line.from.year), scales.y(line.from.value), scales.x(line.to.year), scales.y(line.to.value)];
  return (
    <g data-testid="trend-series-trend">
      <line x1={PLOT.start} x2={PLOT.end} y1={scales.y(trend.mean)} y2={scales.y(trend.mean)} stroke="var(--chart-reference)" strokeDasharray="3 4" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--ground)" strokeLinecap="round" style={HALO} />
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--chart-trend)" strokeWidth={2.5} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <text x={x2 + 10} y={y2} dominantBaseline="central" fill="var(--chart-annotation)" className="font-ui font-semibold" style={LABEL}>
        {slopeText(trend)}
      </text>
      <text x={PLOT.end + 10} y={scales.y(trend.mean)} dominantBaseline="central" fill="var(--chart-annotation)" className="font-ui" style={LABEL}>
        Mean
      </text>
    </g>
  );
}

function nextIndex(key: string, at: number, count: number): number | null {
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (key === "ArrowRight" || key === "ArrowUp") return Math.min(count - 1, at + 1);
  if (key === "ArrowLeft" || key === "ArrowDown") return Math.max(0, at - 1);
  return null;
}

function seriesTable(series: ClimateSeries, points: readonly SeriesPoint[]): FigureTable {
  const rows = points.map((point) => ({ key: String(point.year), cells: { year: String(point.year), value: formatMeasure(point.value, series.unit) } }));
  return { node: <DataTable caption={`${TREND_WORDS[series.variable].noun} in ${series.district.name}, by year`} columns={COLUMNS} rows={rows} />, count: rows.length };
}

export function TrendSeries({ series, trend }: { series: ClimateSeries; trend: ClimateTrend | null }) {
  const points = useMemo(() => seriesPoints(series), [series]);
  const ref = useRef<SVGSVGElement | null>(null);
  const k = useFitScale(ref, VIEW.width);
  const scales = useScales(points, series.variable === "annual_precipitation");
  const [at, setAt] = useState(points.length - 1);
  const shown = points[Math.min(at, points.length - 1)];
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"}${scales.x(point.year).toFixed(1)} ${scales.y(point.value).toFixed(1)}`).join(" ");
  const move = (event: KeyboardEvent<HTMLDivElement>) => {
    const next = nextIndex(event.key, at, points.length);
    if (next === null) return;
    event.preventDefault();
    setAt(next);
  };
  const words = TREND_WORDS[series.variable];
  const texts = { kicker: `${words.noun} · ${series.district.name}`, title: `${words.noun} in ${series.district.name}, ${points[0].year} to ${points[points.length - 1].year}` };
  return (
    <AnswerFigure texts={texts} table={seriesTable(series, points)} data-testid="trend-series" data-variable={series.variable}>
      <div tabIndex={0} role="group" aria-label={`${texts.title}. Use the arrow keys to read each year.`} onKeyDown={move} className="min-w-0 rounded-plate" dir="ltr">
        <svg ref={ref} viewBox={`0 0 ${VIEW.width} ${VIEW.height}`} className="block h-auto w-full [forced-color-adjust:none]" aria-hidden data-fit="" style={fitStyle(k)}>
          <Grid scales={scales} unit={series.unit} years={[points[0].year, points[points.length - 1].year]} />
          <path d={path} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinejoin="round" vectorEffect="non-scaling-stroke" style={TREND_SERIES[series.variable]} />
          {trend ? <TrendMarks points={points} trend={trend} scales={scales} /> : null}
          <circle cx={scales.x(shown.year)} cy={scales.y(shown.value)} r={4} fill="var(--chart-emph)" stroke="var(--ground)" strokeWidth={2} />
        </svg>
      </div>
      <p className="mt-1.5 font-ui text-label text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]" aria-live="polite" data-testid="trend-series-reading">
        {shown.year} · {formatMeasure(shown.value, series.unit)}
      </p>
    </AnswerFigure>
  );
}
