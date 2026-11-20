"use client";

import { useId, useMemo, useRef } from "react";

import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import { GeneralFigure } from "@/components/monograph/kinds/general/GeneralFigure";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { eraYear, parsedSpec, timelineSpecShape, type TimelineEvent } from "@/lib/componentSpecsGeneral";

import "./general.css";

const WIDTH = 640;
const HEIGHT = 44;
const AXIS = { left: 16, right: 624, y: 14 } as const;
const MARK_RADIUS = 4.5;
const LABEL_SIZE = "calc(var(--text-caption) * var(--k, 1))";

export function axisPosition(year: number, first: number, last: number): number {
  const span = last - first;
  return AXIS.left + (span > 0 ? (year - first) / span : 0.5) * (AXIS.right - AXIS.left);
}

function TimelineAxis({ events, labelledBy }: { events: TimelineEvent[]; labelledBy: string }) {
  const ref = useRef<SVGSVGElement | null>(null);
  const scale = useFitScale(ref, WIDTH);
  const first = events[0].year;
  const last = events[events.length - 1].year;
  return (
    <svg ref={ref} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-labelledby={labelledBy} data-fit="" className="block h-auto w-full" style={fitStyle(scale)} data-testid="general-timeline-axis">
      <line x1={AXIS.left} x2={AXIS.right} y1={AXIS.y} y2={AXIS.y} stroke="var(--chart-axis-line)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      {events.map((event, at) => (
        <circle key={`${event.year}-${at}`} cx={axisPosition(event.year, first, last)} cy={AXIS.y} r={MARK_RADIUS * scale} fill="var(--chart-series)" stroke="var(--ground)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      ))}
      <text x={AXIS.left} y={HEIGHT - 6} fill="var(--chart-axis-text)" style={{ fontSize: LABEL_SIZE }}>
        {eraYear(first)}
      </text>
      <text x={AXIS.right} y={HEIGHT - 6} textAnchor="end" fill="var(--chart-axis-text)" style={{ fontSize: LABEL_SIZE }}>
        {eraYear(last)}
      </text>
    </svg>
  );
}

export function TimelineView({ spec, renderUnit }: ComponentViewProps) {
  const timeline = useMemo(() => parsedSpec(timelineSpecShape, spec), [spec]);
  const titleId = useId();
  if (!timeline) return null;
  return (
    <GeneralFigure kind="general_timeline" head={timeline.head} titleId={titleId} renderUnit={renderUnit}>
      <div className="grid gap-3">
        <TimelineAxis events={timeline.events} labelledBy={titleId} />
        <ol className="grid" data-testid="general-timeline">
          {timeline.events.map((event, at) => (
            <li key={`${event.year}-${at}`} className="grid gap-x-4 gap-y-1 border-t border-rule py-3 sm:grid-cols-[7rem_minmax(0,1fr)]">
              <p className="font-ui text-label font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{renderUnit(event.when)}</p>
              <div className="grid min-w-0 gap-1">
                <p className="font-ui text-h4 text-ink-1">{renderUnit(event.title)}</p>
                <p className="max-w-measure font-reading text-body-sm text-ink-1">{renderUnit(event.text)}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </GeneralFigure>
  );
}
