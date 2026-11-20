"use client";

import { boardBox, boardScale, type MapBox } from "@/components/map/boardGeometry";
import { MapText, PHONE_HIDDEN, type MapScene } from "@/components/map/MapCanvas";
import { project } from "@/components/map/projection";
import { circleRadius, placeLabels, type LabelAsk, type StateMark } from "@/lib/mapStates";

export const LARGEST_RADIUS_BOARD = 26.4;
export const LABELLED_STATES = 19;
const CAPTION_PX = 12;
const CHAR_WIDTH = 0.56;
const PIN_ANCHOR = { x: 33.3, y: 322.4 };
const PIN_FOOT = { x: 17.3, y: 380.4 };
const PIN_TEXT = { x: 17.3, y: 394.4, width: 0, height: 0 };

export type PlacedCircle = StateMark & { x: number; y: number; r: number };

export function largestRadius(): number {
  return LARGEST_RADIUS_BOARD * boardScale().scaleX;
}

export function placedCircles(marks: readonly StateMark[]): PlacedCircle[] {
  const largest = marks.reduce((most, mark) => Math.max(most, mark.count), 0);
  const radius = largestRadius();
  return marks
    .map((mark) => ({ ...mark, ...project(mark.longitude, mark.latitude), r: circleRadius(mark.count, largest, radius) }))
    .sort((a, b) => b.r - a.r);
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

export function StateCircles({ circles, emphKey, scene }: { circles: readonly PlacedCircle[]; emphKey: string | null; scene: MapScene }) {
  const counts = new Map(circles.map((circle) => [circle.name, circle.count]));
  const spots = placeLabels(labelAsks(circles, scene.scale), scene.frame, cores(circles));
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
        />
      ))}
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

export function KachchhPin({ lines, scene }: { lines: readonly [string, string]; scene: MapScene }) {
  const anchor = boardBox({ ...PIN_ANCHOR, width: 0, height: 0 });
  const foot = boardBox({ ...PIN_FOOT, width: 0, height: 0 });
  const text = boardBox(PIN_TEXT);
  const leading = CAPTION_PX * 1.3 * scene.scale;
  return (
    <g className="pointer-events-none" data-testid="map-place-pin">
      <line x1={anchor.x} y1={anchor.y} x2={foot.x} y2={foot.y} stroke="var(--terracotta)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
      <MapText x={text.x} y={text.y} bold>
        {lines[0]}
      </MapText>
      <MapText x={text.x} y={text.y + leading} bold>
        {lines[1]}
      </MapText>
    </g>
  );
}
