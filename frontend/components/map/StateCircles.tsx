"use client";

import type { MapBox } from "@/components/map/basemap";
import { MapText, PHONE_HIDDEN, type MapScene } from "@/components/map/MapCanvas";
import type { MapMark, MarkCraft } from "@/components/map/markPlacement";
import { project } from "@/components/map/projection";
import { isMonograph } from "@/lib/atlasCollection";
import { searchHref, type StateCraftList } from "@/lib/atlasIndex";
import type { CatalogueCraft } from "@/lib/craftCatalogueContract";
import { circleRadius, placeLabels, type LabelAsk, type StateMark } from "@/lib/mapStates";

export const LARGEST_RADIUS = 42.7;
export const LABELLED_STATES = 19;
export const STATE_KIND = "State or union territory";
const CAPTION_PX = 12;
const CHAR_WIDTH = 0.56;

export type PlacedCircle = StateMark & { x: number; y: number; r: number };

export function placedCircles(marks: readonly StateMark[]): PlacedCircle[] {
  const largest = marks.reduce((most, mark) => Math.max(most, mark.count), 0);
  return marks
    .map((mark) => ({ ...mark, ...project(mark.longitude, mark.latitude), r: circleRadius(mark.count, largest, LARGEST_RADIUS) }))
    .sort((a, b) => b.r - a.r);
}

export function markCraft(craft: CatalogueCraft): MarkCraft {
  return { slug: craft.slug, name: craft.displayName, monograph: isMonograph(craft) };
}

export function stateMapMarks(circles: readonly PlacedCircle[], lists: readonly StateCraftList[]): MapMark[] {
  const crafts = new Map(lists.map((list) => [list.name, list.crafts]));
  return circles.map((circle) => ({
    key: circle.name,
    name: circle.name,
    kind: STATE_KIND,
    x: circle.x,
    y: circle.y,
    r: circle.r,
    count: circle.count,
    crafts: (crafts.get(circle.name) ?? []).map(markCraft),
    more: { href: searchHref(circle.name), label: `Read ${circle.name}’s crafts in the atlas` }
  }));
}

function labelAsks(circles: readonly PlacedCircle[], scale: number): LabelAsk[] {
  return circles.slice(0, LABELLED_STATES).map((circle) => ({
    key: circle.name,
    x: circle.x,
    y: circle.y,
    r: circle.r,
    width: `${circle.count} ${circle.name}`.length * CHAR_WIDTH * CAPTION_PX * scale,
    height: CAPTION_PX * 1.3 * scale
  }));
}

function cores(circles: readonly PlacedCircle[]): MapBox[] {
  return circles.map((circle) => ({ x: circle.x - circle.r * 0.6, y: circle.y - circle.r * 0.6, width: circle.r * 1.2, height: circle.r * 1.2 }));
}

export function ActiveRing({ x, y, r }: { x: number; y: number; r: number }) {
  return (
    <g className="pointer-events-none" data-testid="map-mark-ring">
      <circle cx={x} cy={y} r={r + 3} fill="none" stroke="var(--map-selection-halo)" strokeWidth={4} vectorEffect="non-scaling-stroke" />
      <circle cx={x} cy={y} r={r + 3} fill="none" stroke="var(--map-selection)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
    </g>
  );
}

export function StateCircles({ circles, emphKey, scene, active = null }: { circles: readonly PlacedCircle[]; emphKey: string | null; scene: MapScene; active?: string | null }) {
  const counts = new Map(circles.map((circle) => [circle.name, circle.count]));
  const spots = placeLabels(labelAsks(circles, scene.scale), scene.frame, cores(circles));
  const lit = circles.find((circle) => circle.name === active) ?? null;
  return (
    <g data-testid="state-circles">
      {circles.map((circle) => (
        <circle
          key={circle.name}
          cx={circle.x}
          cy={circle.y}
          r={circle.r}
          fill={circle.name === emphKey ? "var(--chart-emph)" : "var(--series-count)"}
          fillOpacity={circle.name === emphKey ? 0.9 : 0.85}
          stroke="var(--ground)"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
          className="pointer-events-none"
        />
      ))}
      {lit ? <ActiveRing x={lit.x} y={lit.y} r={lit.r} /> : null}
      <g className={PHONE_HIDDEN} data-testid="state-labels">
        {spots.map((spot) => (
          <MapText key={spot.key} x={spot.x} y={spot.y} anchor={spot.anchor}>
            <tspan className="font-semibold [font-variant-numeric:tabular-nums]">{counts.get(spot.key)}</tspan> {spot.key}
          </MapText>
        ))}
      </g>
    </g>
  );
}
