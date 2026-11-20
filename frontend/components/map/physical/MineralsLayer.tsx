"use client";

import { memo } from "react";

import { project } from "@/components/map/projection";
import type { MineralSite } from "@/lib/mapPhysical";

export const MINERAL_PX = 3.6;

const SHAPES: readonly (readonly [number, number][])[] = [
  [
    [-0.85, -0.85],
    [0.85, -0.85],
    [0.85, 0.85],
    [-0.85, 0.85]
  ],
  [
    [0, -1.15],
    [1.15, 0],
    [0, 1.15],
    [-1.15, 0]
  ],
  [
    [0, -1.15],
    [1.05, 0.8],
    [-1.05, 0.8]
  ],
  [
    [-1.05, -0.8],
    [1.05, -0.8],
    [0, 1.15]
  ],
  [
    [0.5, -0.9],
    [1, 0],
    [0.5, 0.9],
    [-0.5, 0.9],
    [-1, 0],
    [-0.5, -0.9]
  ],
  [
    [-0.35, -1],
    [0.35, -1],
    [0.35, -0.35],
    [1, -0.35],
    [1, 0.35],
    [0.35, 0.35],
    [0.35, 1],
    [-0.35, 1],
    [-0.35, 0.35],
    [-1, 0.35],
    [-1, -0.35],
    [-0.35, -0.35]
  ]
];

export function mineralColour(classIndex: number): string {
  return `var(--mineral-${classIndex + 1})`;
}

export function symbolPath(classIndex: number, x: number, y: number, size: number): string {
  const shape = SHAPES[classIndex] ?? SHAPES[0];
  return `${shape.map(([dx, dy], at) => `${at === 0 ? "M" : "L"}${(x + dx * size).toFixed(1)} ${(y + dy * size).toFixed(1)}`).join("")}Z`;
}

export function MineralSymbol({ classIndex, size = 7 }: { classIndex: number; size?: number }) {
  const half = size / 2 + 1;
  return (
    <svg width={size + 2} height={size + 2} viewBox={`0 0 ${size + 2} ${size + 2}`} aria-hidden className="shrink-0 [forced-color-adjust:none]">
      <path d={symbolPath(classIndex, half, half, size / 2)} fill={mineralColour(classIndex)} stroke="var(--map-marker-ring)" strokeWidth={1} />
    </svg>
  );
}

export const MineralSymbols = memo(function MineralSymbols({ sites, scale }: { sites: readonly MineralSite[]; scale: number }) {
  const size = MINERAL_PX * scale;
  const ordered = [...sites].sort((a, b) => b.latitude - a.latitude);
  return (
    <g className="pointer-events-none" data-testid="mineral-symbols">
      {ordered.map((site) => {
        const at = project(site.longitude, site.latitude);
        return <path key={site.depId} d={symbolPath(site.classIndex, at.x, at.y, size)} fill={mineralColour(site.classIndex)} stroke="var(--map-marker-ring)" strokeWidth={0.75} vectorEffect="non-scaling-stroke" data-class={site.classIndex} />;
      })}
    </g>
  );
});
