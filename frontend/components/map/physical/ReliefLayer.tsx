"use client";

import { memo, useId, useMemo } from "react";

import { decodeRings, ringsPath } from "@/components/map/basemap";
import { RotatedLabel, TIER_HIDDEN } from "@/components/map/physical/RotatedLabel";
import { indiaOutlinePath, project } from "@/components/map/projection";
import type { Peak, ReliefFile } from "@/lib/mapPhysical";

export type PeakPlacement = { tier: number; side: "start" | "end" };

export const PEAK_TIERS: Readonly<Record<string, PeakPlacement>> = {
  "Nanda Devi": { tier: 2, side: "start" },
  Anamudi: { tier: 1, side: "start" },
  K2: { tier: 2, side: "start" },
  Kanchenjunga: { tier: 2, side: "end" },
  "Nanga Parbat": { tier: 2, side: "end" },
  Kangto: { tier: 2, side: "start" },
  "Guru Shikhar": { tier: 2, side: "start" },
  Mahendragiri: { tier: 2, side: "start" },
  "Mount Saramati": { tier: 3, side: "end" },
  Doddabetta: { tier: 3, side: "end" },
  Salher: { tier: 3, side: "start" },
  "Mount Nun": { tier: 3, side: "start" }
};

const PEAK_SIZE = 5.2;

export const ReliefUnder = memo(function ReliefUnder({ file }: { file: ReliefFile }) {
  const maskId = `kv-relief-shade-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const bands = useMemo(() => file.bands.map((band) => ringsPath(decodeRings(band.rings))), [file]);
  const corner = project(file.shade.west, file.shade.north);
  const far = project(file.shade.east, file.shade.south);
  const box = { x: corner.x, y: corner.y, width: far.x - corner.x, height: far.y - corner.y };
  return (
    <g className="pointer-events-none" data-testid="relief-layer">
      <path d={indiaOutlinePath()} fillRule="evenodd" fill="var(--elevation-1)" />
      {bands.map((d, at) => (
        <path key={file.bands[at].min} d={d} fillRule="evenodd" fill={`var(--elevation-${at + 2})`} stroke="var(--map-border-district)" strokeWidth={0.5} vectorEffect="non-scaling-stroke" data-band={file.bands[at].min} />
      ))}
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse" {...box}>
          <image href={file.shade.href} {...box} preserveAspectRatio="none" />
        </mask>
      </defs>
      <rect {...box} fill="var(--map-relief-shade)" mask={`url(#${maskId})`} style={{ opacity: "var(--map-hillshade-opacity)" }} data-testid="relief-shade" />
    </g>
  );
});

function PeakMark({ peak, scale }: { peak: Peak; scale: number }) {
  const placed = PEAK_TIERS[peak.name];
  if (!placed) return null;
  const at = project(peak.longitude, peak.latitude);
  const size = PEAK_SIZE * scale;
  const gap = (size + 3 * scale) * (placed.side === "start" ? 1 : -1);
  return (
    <g className={TIER_HIDDEN[placed.tier]} data-testid="relief-peak">
      <path d={`M${at.x} ${at.y - size}L${at.x + size} ${at.y + size * 0.7}L${at.x - size} ${at.y + size * 0.7}Z`} fill="var(--ink-1)" stroke="var(--map-label-halo)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      <RotatedLabel x={at.x} y={at.y} angle={0} dx={gap} tone="var(--ink-2)" anchor={placed.side}>
        {peak.text}
      </RotatedLabel>
    </g>
  );
}

export function ReliefOver({ file, scale }: { file: ReliefFile; scale: number }) {
  return (
    <g className="pointer-events-none" data-testid="relief-labels">
      {file.ranges.map((range) => {
        const at = project(range.longitude, range.latitude);
        return (
          <RotatedLabel key={range.text} x={at.x} y={at.y} angle={range.angle} tone="var(--map-label)" weight="medium" className={TIER_HIDDEN[range.tier]}>
            {range.text}
          </RotatedLabel>
        );
      })}
      {file.peaks.map((peak) => (
        <PeakMark key={peak.name} peak={peak} scale={scale} />
      ))}
    </g>
  );
}
