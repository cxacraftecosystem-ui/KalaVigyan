"use client";

import { useMemo, useRef } from "react";

import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import { abroadFrame, INSET_PIN_RADIUS, INSET_WIDTH, namesFit, type GeoPoint } from "@/components/map/abroadFrame";
import { outlinePath, type FrameProjection } from "@/components/map/projection";

export type InsetPin = GeoPoint & { key: string; label: string; name: string };
export type InsetRoute = { key: string; from: GeoPoint; to: GeoPoint };

const LABEL = { fontSize: "calc(var(--text-caption) * var(--k, 1))" };
const HALO = { strokeWidth: "calc(6px * var(--k, 1))" };
const TEXT_HALO = { strokeWidth: "calc(3px * var(--k, 1))" };
const END_SHARE = 0.7;

function Routes({ routes, frame }: { routes: readonly InsetRoute[]; frame: FrameProjection }) {
  return (
    <g className="pointer-events-none">
      {routes.map((route) => {
        const from = frame.project(route.from.longitude, route.from.latitude);
        const to = frame.project(route.to.longitude, route.to.latitude);
        return (
          <g key={route.key} data-testid="timeline-abroad-route">
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="var(--map-label-halo)" strokeLinecap="round" style={HALO} />
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="var(--terracotta)" strokeWidth={2} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
          </g>
        );
      })}
    </g>
  );
}

function Pins({ pins, frame, scale }: { pins: readonly InsetPin[]; frame: FrameProjection; scale: number }) {
  const placed = pins.map((pin) => ({ pin, ...frame.project(pin.longitude, pin.latitude) }));
  const named = namesFit(placed, scale);
  const radius = INSET_PIN_RADIUS * scale;
  return (
    <g className="font-ui [font-variant-numeric:lining-nums_tabular-nums]">
      {placed.map(({ pin, x, y }) => {
        const atEnd = x > frame.viewBox.width * END_SHARE;
        return (
          <g key={pin.key} data-testid="timeline-abroad-pin" data-pin={pin.label}>
            <circle cx={x} cy={y} r={radius} fill="var(--map-marker)" stroke="var(--map-marker-ring)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
            <text x={x} y={y} textAnchor="middle" dominantBaseline="central" fill="var(--map-label)" className="font-semibold" style={LABEL}>
              {pin.label}
            </text>
            {named ? (
              <text x={atEnd ? x - radius - 4 * scale : x + radius + 4 * scale} y={y} textAnchor={atEnd ? "end" : "start"} dominantBaseline="central" fill="var(--map-label)" stroke="var(--map-label-halo)" paintOrder="stroke" style={{ ...LABEL, ...TEXT_HALO }} data-testid="timeline-abroad-name">
                {pin.name}
              </text>
            ) : null}
          </g>
        );
      })}
    </g>
  );
}

export function AbroadInset({ pins, routes, label }: { pins: readonly InsetPin[]; routes: readonly InsetRoute[]; label: string }) {
  const frame = useMemo(() => abroadFrame(pins), [pins]);
  const outline = useMemo(() => outlinePath(frame), [frame]);
  const box = useRef<SVGSVGElement | null>(null);
  const scale = useFitScale(box, INSET_WIDTH);
  const { width, height } = frame.viewBox;
  return (
    <svg ref={box} viewBox={`0 0 ${width} ${height.toFixed(1)}`} role="img" aria-label={label} className="block h-auto w-full rounded-plate border border-rule [forced-color-adjust:none]" data-fit="" style={fitStyle(scale)} data-testid="timeline-abroad">
      <rect width={width} height={height} fill="var(--sunk)" />
      <path d={outline} fillRule="evenodd" fill="var(--map-land)" stroke="var(--map-coast)" strokeWidth={0.75} strokeLinejoin="round" vectorEffect="non-scaling-stroke" data-testid="timeline-abroad-india" />
      <Routes routes={routes} frame={frame} />
      <Pins pins={pins} frame={frame} scale={scale} />
    </svg>
  );
}
