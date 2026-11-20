"use client";

import type { MapScene } from "@/components/map/MapCanvas";
import type { MapMark } from "@/components/map/markPlacement";
import { project } from "@/components/map/projection";
import { ActiveRing } from "@/components/map/StateCircles";
import type { PlaceMarker } from "@/lib/mapFamilies";

export const MARKER_PX = 4.5;
export const PLACE_KIND = "Craft place";

export function placeMapMarks(markers: readonly PlaceMarker[], scale: number): MapMark[] {
  return [...markers]
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name, "en"))
    .map((marker) => {
      const at = project(marker.longitude, marker.latitude);
      return { key: marker.key, name: marker.name, kind: PLACE_KIND, x: at.x, y: at.y, r: MARKER_PX * scale, count: marker.crafts.length, crafts: marker.crafts, more: null };
    });
}

export function PlaceMarkers({ markers, scene, active = null }: { markers: readonly PlaceMarker[]; scene: MapScene; active?: string | null }) {
  const radius = MARKER_PX * scene.scale;
  const lit = markers.find((marker) => marker.key === active) ?? null;
  const ring = lit ? project(lit.longitude, lit.latitude) : null;
  return (
    <g className="pointer-events-none" data-testid="place-markers">
      {markers.map((marker) => {
        const at = project(marker.longitude, marker.latitude);
        return (
          <circle
            key={marker.key}
            cx={at.x}
            cy={at.y}
            r={radius}
            fill={marker.family ? marker.family.colour : "var(--map-marker)"}
            stroke="var(--map-marker-ring)"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
            data-testid="place-marker"
          />
        );
      })}
      {ring ? <ActiveRing x={ring.x} y={ring.y} r={radius} /> : null}
    </g>
  );
}
