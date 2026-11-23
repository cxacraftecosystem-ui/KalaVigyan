"use client";

import { useId, useMemo } from "react";

import { fitScale, fitStyle } from "@/components/charts/useFitScale";
import { decodeRings } from "@/components/map/basemap";
import { indiaRings } from "@/components/map/indiaGeometry";
import { mineralColour, symbolPath } from "@/components/map/physical/MineralsLayer";
import { RotatedLabel } from "@/components/map/physical/RotatedLabel";
import { AbroadPins, NamedRivers } from "@/components/map/place-context/GroundBeyond";
import type { DrawnRiver } from "@/components/map/place-context/useGroundRivers";
import { NEIGHBOUR_RINGS } from "@/components/map/place-context/neighbourLand";
import { RANN_RINGS } from "@/components/map/rannGeometry";
import { frameView, kmUnits, linePath, placed, ringsIn, ringsPath, type FrameView } from "@/lib/groundFrame";
import { riverWidth } from "@/lib/mapPhysical";
import type { GroundDeposit, GroundFrame, GroundPin } from "@/lib/placeGround";
import { elevationStep, km } from "@/lib/placeGroundView";

export type MapPin = { key: string; label: string; longitude: number; latitude: number };
export type GroundMarks = { abroad: readonly GroundPin[]; rivers: readonly DrawnRiver[] };
export type GroundMapProps = { frame: GroundFrame; pins: readonly MapPin[]; deposits: readonly GroundDeposit[]; radiusKm: number; title: string; description: string; marks?: GroundMarks };

const NO_MARKS: GroundMarks = { abroad: [], rivers: [] };

export const PIN_PX = 5.5;
export const DEPOSIT_PX = 3.2;
export const MATCHED_PX = 5;
const LABEL_GAP_PX = 6;

function Land({ frame, view, saltId }: { frame: GroundFrame; view: FrameView; saltId: string }) {
  const india = useMemo(() => ringsPath(view, ringsIn(frame, indiaRings().flat())), [frame, view]);
  const foreign = useMemo(() => ringsPath(view, ringsIn(frame, NEIGHBOUR_RINGS)), [frame, view]);
  const rann = useMemo(() => ringsPath(view, ringsIn(frame, decodeRings(RANN_RINGS))), [frame, view]);
  return (
    <g className="pointer-events-none">
      <rect width={view.width} height={view.height} fill="var(--map-water)" />
      {foreign ? <path d={foreign} fillRule="evenodd" fill="var(--map-land-foreign)" data-testid="ground-neighbours" /> : null}
      <path d={india} fillRule="evenodd" fill="var(--elevation-1)" data-testid="ground-land" />
      {frame.bands.map((band) => (
        <path key={band.lowM} d={ringsPath(view, band.rings)} fillRule="evenodd" fill={`var(--elevation-${elevationStep(band.lowM)})`} stroke="var(--map-border-district)" strokeWidth={0.5} vectorEffect="non-scaling-stroke" data-band={band.lowM} />
      ))}
      {rann ? <path d={rann} fillRule="evenodd" fill={`url(#${saltId})`} stroke="var(--map-salt-hatch)" strokeWidth={0.75} strokeDasharray="1 2" vectorEffect="non-scaling-stroke" data-testid="ground-salt" /> : null}
      <path d={india} fillRule="evenodd" fill="none" stroke="var(--map-coast)" strokeWidth={0.75} vectorEffect="non-scaling-stroke" />
    </g>
  );
}

function Water({ frame, view }: { frame: GroundFrame; view: FrameView }) {
  const ranks = [...new Set(frame.rivers.map((line) => line.rank))].sort((a, b) => b - a);
  return (
    <g className="pointer-events-none" data-testid="ground-water">
      {ranks.map((rank) => (
        <path
          key={rank}
          d={frame.rivers
            .filter((line) => line.rank === rank)
            .map((line) => linePath(view, line.points))
            .join("")}
          fill="none"
          stroke="var(--map-river)"
          strokeWidth={riverWidth(rank)}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
          data-rank={rank}
        />
      ))}
      {frame.lakes.length ? <path d={ringsPath(view, frame.lakes)} fillRule="evenodd" fill="var(--map-water)" stroke="var(--map-river)" strokeWidth={0.6} vectorEffect="non-scaling-stroke" data-testid="ground-lakes" /> : null}
    </g>
  );
}

function Reach({ pins, view, radiusKm, k }: { pins: readonly MapPin[]; view: FrameView; radiusKm: number; k: number }) {
  const radius = kmUnits(view, radiusKm);
  const first = pins[0] ? placed(view, [pins[0].longitude, pins[0].latitude]) : null;
  return (
    <g className="pointer-events-none" data-testid="ground-reach">
      {pins.map((pin) => {
        const { x, y } = placed(view, [pin.longitude, pin.latitude]);
        return <circle key={pin.key} cx={x} cy={y} r={radius} fill="none" stroke="var(--chart-reference)" strokeWidth={1} strokeDasharray="3 4" vectorEffect="non-scaling-stroke" />;
      })}
      {first ? (
        <RotatedLabel x={first.x} y={first.y - radius - 4 * k} angle={0} tone="var(--chart-annotation)">
          {km(radiusKm)}
        </RotatedLabel>
      ) : null}
    </g>
  );
}

function Deposits({ deposits, view, k }: { deposits: readonly GroundDeposit[]; view: FrameView; k: number }) {
  const ordered = [...deposits].sort((a, b) => Number(a.matched) - Number(b.matched) || b.latitude - a.latitude);
  return (
    <g className="pointer-events-none" data-testid="ground-deposits">
      {ordered.map((deposit) => {
        const { x, y } = placed(view, [deposit.longitude, deposit.latitude]);
        const size = (deposit.matched ? MATCHED_PX : DEPOSIT_PX) * k;
        return (
          <path
            key={deposit.depId}
            d={symbolPath(deposit.classIndex, x, y, size)}
            fill={mineralColour(deposit.classIndex)}
            stroke="var(--map-marker-ring)"
            strokeWidth={deposit.matched ? 1.5 : 0.75}
            vectorEffect="non-scaling-stroke"
            data-class={deposit.classIndex}
            data-matched={deposit.matched ? "" : undefined}
          />
        );
      })}
    </g>
  );
}

function Labels({ frame, view }: { frame: GroundFrame; view: FrameView }) {
  return (
    <g className="pointer-events-none">
      {frame.labels.map((label) => {
        const { x, y } = placed(view, [label.longitude, label.latitude]);
        return (
          <RotatedLabel key={label.text} x={x} y={y} angle={label.angle} tone="var(--map-water-label)" italic lift>
            {label.text}
          </RotatedLabel>
        );
      })}
    </g>
  );
}

function Pins({ pins, view, k }: { pins: readonly MapPin[]; view: FrameView; k: number }) {
  return (
    <g className="pointer-events-none" data-testid="ground-pins">
      {pins.map((pin) => {
        const { x, y } = placed(view, [pin.longitude, pin.latitude]);
        return (
          <g key={pin.key}>
            <circle cx={x} cy={y} r={PIN_PX * k} fill="var(--terracotta)" stroke="var(--map-label-halo)" strokeWidth={2} vectorEffect="non-scaling-stroke" data-testid="ground-pin" />
            <RotatedLabel x={x} y={y} angle={0} anchor="start" dx={(PIN_PX + LABEL_GAP_PX) * k} weight="medium">
              {pin.label}
            </RotatedLabel>
          </g>
        );
      })}
    </g>
  );
}

function SaltPattern({ id }: { id: string }) {
  return (
    <defs>
      <pattern id={id} width={4} height={4} patternUnits="userSpaceOnUse">
        <rect width={4} height={4} fill="var(--map-salt)" />
        <circle cx={1} cy={1.2} r={0.55} fill="var(--map-salt-hatch)" />
        <circle cx={3.1} cy={3} r={0.55} fill="var(--map-salt-hatch)" />
      </pattern>
    </defs>
  );
}

export function groundScale(view: FrameView): number {
  return fitScale(view.width, 0);
}

export function GroundMap({ frame, pins, deposits, radiusKm, title, description, marks = NO_MARKS }: GroundMapProps) {
  const view = useMemo(() => frameView(frame), [frame]);
  const k = groundScale(view);
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  return (
    <svg
      viewBox={`0 0 ${view.width} ${view.height.toFixed(1)}`}
      role="img"
      aria-labelledby={`${id}-t ${id}-d`}
      data-fit=""
      className="block h-auto w-full rounded-plate border border-rule [forced-color-adjust:none]"
      style={fitStyle(k)}
      data-testid="ground-map"
    >
      <title id={`${id}-t`}>{title}</title>
      <desc id={`${id}-d`}>{description}</desc>
      <SaltPattern id={`${id}-salt`} />
      <Land frame={frame} view={view} saltId={`${id}-salt`} />
      <Water frame={frame} view={view} />
      <NamedRivers rivers={marks.rivers} frame={frame} view={view} />
      <Reach pins={pins} view={view} radiusKm={radiusKm} k={k} />
      <Deposits deposits={deposits} view={view} k={k} />
      <Labels frame={frame} view={view} />
      <Pins pins={pins} view={view} k={k} />
      <AbroadPins pins={marks.abroad} view={view} k={k} />
    </svg>
  );
}
