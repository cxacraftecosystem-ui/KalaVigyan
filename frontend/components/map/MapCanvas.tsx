"use client";

import { useId, useMemo, useRef, type ReactNode } from "react";

import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import { BOARD_FRAME, boardBox, viewBoxOf, type MapBox } from "@/components/map/boardGeometry";
import { MapCoast, MapLand, MapPatterns, SaltFlats, StateLines } from "@/components/map/MapBase";
import { project } from "@/components/map/projection";
import { cn } from "@/lib/utils";

export const LABEL_SIZE = "calc(var(--text-caption) * var(--k, 1))";
export const HALO_WIDTH = "calc(3px * var(--k, 1))";
export const PHONE_HIDDEN = "max-sm:hidden";

const WATER_LABELS = [
  { key: "arabian", text: "Arabian Sea", longitude: 66.1, latitude: 15.2 },
  { key: "bengal", text: "Bay of Bengal", longitude: 87.1, latitude: 15.3 }
] as const;

export type MapScene = { frame: MapBox; scale: number };

export function MapText({ x, y, anchor = "start", tone = "var(--map-label)", italic = false, bold = false, children }: { x: number; y: number; anchor?: "start" | "middle" | "end"; tone?: string; italic?: boolean; bold?: boolean; children: ReactNode }) {
  return (
    <text
      x={x}
      y={y}
      textAnchor={anchor}
      dominantBaseline="central"
      fill={tone}
      stroke="var(--map-label-halo)"
      strokeLinejoin="round"
      paintOrder="stroke"
      className={cn("pointer-events-none", italic ? "font-reading italic" : "font-ui", bold ? "font-semibold" : "font-normal")}
      style={{ fontSize: LABEL_SIZE, strokeWidth: HALO_WIDTH }}
    >
      {children}
    </text>
  );
}

const RANN_LABEL = { x: 36.6, y: 276.7, width: 0, height: 0 };

function WaterLabels() {
  const rann = boardBox(RANN_LABEL);
  return (
    <>
      <g className={PHONE_HIDDEN}>
        <MapText x={rann.x} y={rann.y} anchor="end" tone="var(--ink-2)" italic>
          Great Rann
        </MapText>
      </g>
      {WATER_LABELS.map((label) => {
        const at = project(label.longitude, label.latitude);
        return (
          <text key={label.key} x={at.x} y={at.y} fill="var(--map-water-label)" className="pointer-events-none font-reading italic" style={{ fontSize: LABEL_SIZE }}>
            {label.text}
          </text>
        );
      })}
    </>
  );
}

export type MapCanvasProps = { title: string; description: string; under?: ReactNode; over?: (scene: MapScene) => ReactNode; className?: string };

export function MapCanvas({ title, description, under, over, className }: MapCanvasProps) {
  const ref = useRef<SVGSVGElement | null>(null);
  const frame = useMemo(() => boardBox(BOARD_FRAME), []);
  const scale = useFitScale(ref, frame.width);
  const id = useId();
  return (
    <svg ref={ref} viewBox={viewBoxOf(frame)} role="img" aria-labelledby={`${id}-t ${id}-d`} data-fit="" className={cn("block h-auto w-full rounded-plate [forced-color-adjust:none]", className)} style={fitStyle(scale)} data-testid="map-canvas">
      <title id={`${id}-t`}>{title}</title>
      <desc id={`${id}-d`}>{description}</desc>
      <MapPatterns />
      <MapLand frame={frame} />
      {under}
      <StateLines />
      <SaltFlats />
      <MapCoast />
      <WaterLabels />
      {over ? over({ frame, scale }) : null}
    </svg>
  );
}
