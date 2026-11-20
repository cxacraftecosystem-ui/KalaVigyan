"use client";

import { useRef } from "react";

import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import type { RenderUnit } from "@/components/monograph/kinds/general/GeneralFigure";
import { share, type ChartSeries } from "@/lib/componentSpecsGeneral";

const WIDTH = 640;
const HEIGHT = 220;
const PLOT = { left: 56, right: 624, top: 14, bottom: 196 } as const;
const TICKS = [0, 0.5, 1] as const;
const LABEL_SIZE = "calc(var(--text-caption) * var(--k, 1))";
const POINT_RADIUS = 3.5;
const EMPHASIS_RADIUS = 5.5;

type Range = { low: number; high: number };

export function tickLabel(value: number): string {
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function linePoints(series: ChartSeries, range: Range): { x: number; y: number }[] {
  const count = series.points.length;
  return series.points.map((point, at) => ({
    x: PLOT.left + (count > 1 ? (at / (count - 1)) * (PLOT.right - PLOT.left) : 0),
    y: PLOT.bottom - share(point.value, range) * (PLOT.bottom - PLOT.top)
  }));
}

type LineProps = { series: ChartSeries; range: Range; emphasis: number | null; labelledBy: string; renderUnit: RenderUnit };

export function ChartLine({ series, range, emphasis, labelledBy, renderUnit }: LineProps) {
  const ref = useRef<SVGSVGElement | null>(null);
  const scale = useFitScale(ref, WIDTH);
  const points = linePoints(series, range);
  const first = series.points[0];
  const last = series.points[series.points.length - 1];
  return (
    <div className="grid gap-1">
      <svg ref={ref} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-labelledby={labelledBy} data-fit="" className="block h-auto w-full" style={fitStyle(scale)} data-testid="general-line">
        {TICKS.map((tick) => {
          const y = PLOT.bottom - tick * (PLOT.bottom - PLOT.top);
          return (
            <g key={tick}>
              <line x1={PLOT.left} x2={PLOT.right} y1={y} y2={y} stroke={tick === 0 ? "var(--chart-axis-line)" : "var(--chart-grid)"} strokeWidth={1} vectorEffect="non-scaling-stroke" />
              <text x={PLOT.left - 8} y={y} textAnchor="end" dominantBaseline="central" fill="var(--chart-axis-text)" style={{ fontSize: LABEL_SIZE }}>
                {tickLabel(range.low + tick * (range.high - range.low))}
              </text>
            </g>
          );
        })}
        <polyline points={points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ")} fill="none" stroke="var(--chart-series)" strokeWidth={2} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        {points.map((point, at) => (
          <circle key={series.points[at].reading} cx={point.x} cy={point.y} r={(at === emphasis ? EMPHASIS_RADIUS : POINT_RADIUS) * scale} fill={at === emphasis ? "var(--chart-emph)" : "var(--chart-series)"} stroke="var(--ground)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        ))}
      </svg>
      <div className="flex justify-between gap-4 font-ui text-caption text-ink-3">
        <span>{renderUnit(first.label)}</span>
        {series.points.length > 1 ? <span className="text-end">{renderUnit(last.label)}</span> : null}
      </div>
    </div>
  );
}
