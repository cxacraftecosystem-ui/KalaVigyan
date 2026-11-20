"use client";

import { memo, useMemo } from "react";

import { decodeRings, linesPath, ringsPath } from "@/components/map/basemap";
import { RotatedLabel, TIER_HIDDEN } from "@/components/map/physical/RotatedLabel";
import { project } from "@/components/map/projection";
import { riverWidth, type RiversFile } from "@/lib/mapPhysical";

export const RiversUnder = memo(function RiversUnder({ file }: { file: RiversFile }) {
  const lakes = useMemo(() => ringsPath(decodeRings(file.lakes)), [file]);
  const ranks = useMemo(() => [...file.ranks].sort((a, b) => b.rank - a.rank).map((group) => ({ rank: group.rank, d: linesPath(group.lines) })), [file]);
  return (
    <g className="pointer-events-none" data-testid="rivers-layer">
      {ranks.map((group) => (
        <path key={group.rank} d={group.d} fill="none" stroke="var(--map-river)" strokeWidth={riverWidth(group.rank)} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" data-rank={group.rank} />
      ))}
      <path d={lakes} fillRule="evenodd" fill="var(--map-water)" stroke="var(--map-river)" strokeWidth={0.6} vectorEffect="non-scaling-stroke" data-testid="rivers-lakes" />
    </g>
  );
});

export function RiversOver({ file }: { file: RiversFile }) {
  return (
    <g className="pointer-events-none" data-testid="rivers-labels">
      {file.labels.map((label) => {
        const at = project(label.longitude, label.latitude);
        return (
          <RotatedLabel key={label.text} x={at.x} y={at.y} angle={label.angle} tone="var(--map-water-label)" italic lift className={TIER_HIDDEN[label.tier]}>
            {label.text}
          </RotatedLabel>
        );
      })}
    </g>
  );
}
