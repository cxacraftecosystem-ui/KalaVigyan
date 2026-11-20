"use client";

import { useId, useMemo, useRef, type ReactNode } from "react";

import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import { mapFrame, viewBoxOf, type MapBox } from "@/components/map/basemap";
import { MapCoast, MapLand, MapPatterns, SaltFlats } from "@/components/map/MapBase";
import { project } from "@/components/map/projection";
import { cn } from "@/lib/utils";

export const LABEL_SIZE = "calc(var(--text-caption) * var(--k, 1))";
export const HALO_WIDTH = "calc(3px * var(--k, 1))";
export const PHONE_HIDDEN = "max-sm:hidden";

const WATER_LABELS = [
  { key: "arabian", text: "Arabian Sea", longitude: 66.1, latitude: 15.2 },
  { key: "bengal", text: "Bay of Bengal", longitude: 87.1, latitude: 15.3 }
] as const;

export const COUNTRY_LABELS = [
  { key: "AFG", text: "Afghanistan", longitude: 66.9, latitude: 34.6 },
  { key: "PAK", text: "Pakistan", longitude: 66.9, latitude: 28.4 },
  { key: "CHN", text: "China", longitude: 86.5, latitude: 33.4 },
  { key: "NPL", text: "Nepal", longitude: 83.9, latitude: 28.45 },
  { key: "BTN", text: "Bhutan", longitude: 90.45, latitude: 27.5 },
  { key: "BGD", text: "Bangladesh", longitude: 90.15, latitude: 23.95 },
  { key: "MMR", text: "Myanmar", longitude: 96.0, latitude: 21.6 },
  { key: "LKA", text: "Sri Lanka", longitude: 80.7, latitude: 7.75 }
] as const;

export const RANN_LABEL = { text: "Great Rann", longitude: 68.95, latitude: 24.15 };

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

function PlaceLabels() {
  const rann = project(RANN_LABEL.longitude, RANN_LABEL.latitude);
  return (
    <g className={PHONE_HIDDEN} data-testid="map-place-labels">
      <MapText x={rann.x} y={rann.y} anchor="end" tone="var(--ink-2)" italic>
        {RANN_LABEL.text}
      </MapText>
      {COUNTRY_LABELS.map((label) => {
        const at = project(label.longitude, label.latitude);
        return (
          <MapText key={label.key} x={at.x} y={at.y} anchor="middle" tone="var(--map-label-minor)">
            {label.text}
          </MapText>
        );
      })}
    </g>
  );
}

function WaterLabels() {
  return (
    <>
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

export type MapCanvasProps = {
  title: string;
  description: string;
  under?: ReactNode;
  over?: (scene: MapScene) => ReactNode;
  controls?: (scene: MapScene) => ReactNode;
  className?: string;
};

export function MapCanvas({ title, description, under, over, controls, className }: MapCanvasProps) {
  const ref = useRef<SVGSVGElement | null>(null);
  const frame = useMemo(() => mapFrame(), []);
  const scale = useFitScale(ref, frame.width);
  const id = useId();
  const scene = { frame, scale };
  return (
    <div className="relative" data-testid="map-frame">
      <svg ref={ref} viewBox={viewBoxOf(frame)} role="img" aria-labelledby={`${id}-t ${id}-d`} data-fit="" className={cn("block h-auto w-full rounded-plate [forced-color-adjust:none]", className)} style={fitStyle(scale)} data-testid="map-canvas">
        <title id={`${id}-t`}>{title}</title>
        <desc id={`${id}-d`}>{description}</desc>
        <MapPatterns />
        <MapLand frame={frame} />
        {under}
        <SaltFlats />
        <MapCoast />
        <WaterLabels />
        <PlaceLabels />
        {over ? over(scene) : null}
      </svg>
      {controls ? controls(scene) : null}
    </div>
  );
}
