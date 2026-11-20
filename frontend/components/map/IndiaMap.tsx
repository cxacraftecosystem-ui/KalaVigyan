"use client";

import { useMemo, type ReactNode } from "react";

import { layoutPins, type MapPoint } from "@/components/map/layout";
import { MapCoast, MapLand, MapPatterns, SaltFlats } from "@/components/map/MapBase";
import { MapHoverCard } from "@/components/map/MapHoverCard";
import { Pin } from "@/components/map/MapMarks";
import { PinControls } from "@/components/map/PinControls";
import { VIEW_BOX } from "@/components/map/projection";
import { cn } from "@/lib/utils";

export type { MapPoint } from "@/components/map/layout";

const FRAME = { x: 0, y: 0, width: VIEW_BOX.width, height: VIEW_BOX.height };

export interface IndiaMapProps {
  points: MapPoint[];
  selectedKey?: string | null;
  hoveredKey?: string | null;
  onSelect?: (key: string) => void;
  onHover?: (key: string | null) => void;
  underlay?: ReactNode;
  overlay?: ReactNode;
  className?: string;
}

export function IndiaMapBase({ underlay }: { underlay?: ReactNode }) {
  return (
    <>
      <MapPatterns />
      <MapLand frame={FRAME} />
      {underlay}
      <SaltFlats />
      <MapCoast />
    </>
  );
}

export function IndiaMap({ points, selectedKey = null, hoveredKey = null, onSelect, onHover, underlay = null, overlay = null, className }: IndiaMapProps) {
  const pins = useMemo(() => layoutPins(points), [points]);
  const ordinals = useMemo(() => new Map(points.map((point, index) => [point.key, index + 1])), [points]);
  const active = pins.find((pin) => pin.point.key === (hoveredKey ?? selectedKey)) ?? null;

  return (
    <div className={cn("relative", className)}>
      <svg viewBox={`0 0 ${VIEW_BOX.width} ${VIEW_BOX.height}`} className="h-auto w-full max-w-full rounded-plate" role="presentation" aria-hidden="true" focusable="false">
        <IndiaMapBase underlay={underlay} />
        <g>
          {pins
            .filter((pin) => pin.displaced)
            .map((pin) => (
              <g key={`leader-${pin.point.key}`}>
                <line x1={pin.anchorX} y1={pin.anchorY} x2={pin.x} y2={pin.y} stroke="var(--map-marker-ring)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
                <circle cx={pin.anchorX} cy={pin.anchorY} r={2.5} fill="var(--map-marker-ring)" />
              </g>
            ))}
        </g>
        {pins.map((pin) => (
          <Pin key={pin.point.key} pin={pin} isActive={pin.point.key === selectedKey || pin.point.key === hoveredKey} onSelect={onSelect} onHover={onHover} />
        ))}
        {overlay}
      </svg>
      {onSelect && pins.length ? <PinControls pins={pins} frame={FRAME} selectedKey={selectedKey} onSelect={onSelect} onHover={onHover} /> : null}
      {active ? <MapHoverCard key={active.point.key} pin={active} ordinal={ordinals.get(active.point.key)} /> : null}
    </div>
  );
}
