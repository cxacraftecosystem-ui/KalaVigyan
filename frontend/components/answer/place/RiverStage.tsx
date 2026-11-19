"use client";

import { useRef, type ReactNode } from "react";
import { motion, useTransform } from "framer-motion";

import type { PlacedBadge, StoryGeometry, StoryRiver } from "@/components/answer/place/storyGeometry";
import type { RiverFlow } from "@/components/answer/place/useRiverFlow";
import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import { DistrictFills, SelectedDistrict, type DistrictFill } from "@/components/map/DistrictLayer";
import { MapCoast, MapLand, SaltFlats, StateLines } from "@/components/map/MapBase";
import { MapText } from "@/components/map/MapCanvas";
import { pointAlong, viewPercent, type Point, type View } from "@/lib/riverGeometry";
import { cn } from "@/lib/utils";

const RIVER_WIDTH = 0.007;
const SOURCE_RADIUS = 0.009;
const LABEL_LIFT = 2.6;

export type StageFocus = { district: number | null; stretch: boolean; reached: readonly boolean[]; onStep: (index: number) => void };
export type StageDrawing = { geometry: StoryGeometry; flow: RiverFlow; fillOf: DistrictFill };

const BADGE = "absolute inline-flex h-7 min-w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border px-1.5 font-ui text-caption font-semibold [font-variant-numeric:lining-nums_tabular-nums] transition-colors duration-state pointer-coarse:h-11 pointer-coarse:min-w-11";

function tributaryWidth(order: number): number {
  return 0.0012 + order * 0.0006;
}

function WaterFront({ river, flow, radius }: { river: StoryRiver; flow: RiverFlow; radius: number }) {
  const { points, lengths } = river.course;
  const cx = useTransform(flow.progress, (value) => pointAlong(points, lengths, value)[0]);
  const cy = useTransform(flow.progress, (value) => pointAlong(points, lengths, value)[1]);
  const opacity = useTransform(flow.progress, [0, 0.02, 0.97, 1], [0, 1, 1, 0]);
  return <motion.circle cx={cx} cy={cy} r={radius} style={{ opacity }} fill="var(--map-river)" stroke="var(--map-label-halo)" strokeWidth={radius * 0.4} />;
}

function RiverEnds({ river, radius }: { river: StoryRiver; radius: number }) {
  const [source] = river.course.points;
  const outlet = river.course.points[river.course.points.length - 1];
  return (
    <>
      <circle cx={source[0]} cy={source[1]} r={radius} fill="var(--map-marker)" stroke="var(--map-marker-ring)" strokeWidth={radius * 0.35} data-testid="river-source" />
      <circle cx={outlet[0]} cy={outlet[1]} r={radius * 0.8} fill="var(--map-river)" stroke="var(--map-marker-ring)" strokeWidth={radius * 0.35} />
    </>
  );
}

function RiverLines({ river, flow, view, stretch }: { river: StoryRiver; flow: RiverFlow; view: View; stretch: string | null }) {
  const width = view.width * RIVER_WIDTH;
  const course = { d: river.d, stroke: "var(--map-river)", strokeWidth: width, "data-testid": "river-course" };
  const radius = view.width * SOURCE_RADIUS;
  return (
    <g fill="none" strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none">
      {river.tributaries.map((line) => (
        <path key={line.order} d={line.d} stroke="var(--map-river)" strokeWidth={view.width * tributaryWidth(line.order)} />
      ))}
      <path d={river.d} stroke="var(--map-label-halo)" strokeWidth={width * 2.2} />
      {flow.moving ? <motion.path {...course} data-flow="moving" style={{ pathLength: flow.progress }} /> : <path {...course} data-flow="still" />}
      {stretch ? (
        <>
          <path d={stretch} stroke="var(--map-selection-halo)" strokeWidth={width * 2.6} />
          <path d={stretch} stroke="var(--map-selection)" strokeWidth={width * 1.5} data-testid="river-stretch" />
        </>
      ) : null}
      <RiverEnds river={river} radius={radius} />
      {flow.moving ? <WaterFront river={river} flow={flow} radius={radius * 0.75} /> : null}
    </g>
  );
}

function RiverLabels({ points, view }: { points: readonly Point[]; view: View }) {
  if (points.length < 2) return null;
  const lift = view.width * SOURCE_RADIUS * LABEL_LIFT;
  const ends = [
    { key: "source", text: "Source", at: points[0] },
    { key: "outlet", text: "Outlet", at: points[points.length - 1] }
  ];
  return (
    <>
      {ends.map((end) => (
        <MapText key={end.key} x={end.at[0]} y={end.at[1] - lift} anchor="middle" bold>
          {end.text}
        </MapText>
      ))}
    </>
  );
}

function StepBadgeButton({ badge, view, focus }: { badge: PlacedBadge; view: View; focus: StageFocus }) {
  const reached = focus.reached[badge.first] ?? false;
  const on = focus.district === badge.districtLgd;
  const tone = on ? "border-indigo bg-indigo text-indigo-on" : reached ? "border-ink-1 bg-raised text-ink-1 hover:bg-sunk" : "border-dashed border-rule-strong bg-raised text-ink-3";
  return (
    <button
      type="button"
      tabIndex={-1}
      onClick={() => focus.onStep(badge.first)}
      style={viewPercent(badge.at, view)}
      aria-label={`Step ${badge.label}`}
      data-testid="story-badge"
      data-reached={reached ? "true" : "false"}
      className={cn(BADGE, tone)}
    >
      {badge.label}
    </button>
  );
}

function StageMap({ drawing, focus, summary }: { drawing: StageDrawing; focus: StageFocus; summary: string }) {
  const { geometry, flow, fillOf } = drawing;
  const { view, river } = geometry;
  const ref = useRef<SVGSVGElement | null>(null);
  const scale = useFitScale(ref, view.width);
  const focused = focus.district === null ? undefined : geometry.districts.get(focus.district);
  const stretch = focused && river && focus.stretch ? (river.stretches.get(focused.lgd) ?? null) : null;
  return (
    <svg ref={ref} viewBox={`${view.x} ${view.y} ${view.width} ${view.height}`} className="absolute inset-0 h-full w-full" role="img" aria-label={summary} data-fit="" style={fitStyle(scale)}>
      <MapLand frame={view} />
      <DistrictFills shapes={geometry.context} fillOf={fillOf} />
      <StateLines />
      <SaltFlats />
      <MapCoast />
      {focused ? <SelectedDistrict shape={focused.shape} /> : null}
      {river ? <RiverLines river={river} flow={flow} view={view} stretch={stretch} /> : null}
      {river ? <RiverLabels points={river.course.points} view={view} /> : null}
    </svg>
  );
}

export function RiverStage({ geometry, flow, fillOf, focus, summary, inset = null }: StageDrawing & { focus: StageFocus; summary: string; inset?: ReactNode }) {
  return (
    <div className="relative aspect-[4/3] w-full overflow-hidden rounded-plate [forced-color-adjust:none]" data-testid="river-stage" data-passed={flow.passed}>
      <StageMap drawing={{ geometry, flow, fillOf }} focus={focus} summary={summary} />
      {inset}
      {geometry.badges.map((badge) => (
        <StepBadgeButton key={badge.districtLgd} badge={badge} view={geometry.view} focus={focus} />
      ))}
    </div>
  );
}
