import type { ReactNode } from "react";

import { decodeRings } from "@/components/map/basemap";
import { MineralSymbol } from "@/components/map/physical/MineralsLayer";
import { RANN_RINGS } from "@/components/map/rannGeometry";
import { ringsIn } from "@/lib/groundFrame";
import type { GroundDeposit, GroundFrame, MineralClass } from "@/lib/placeGround";
import { bandText, elevationStep } from "@/lib/placeGroundView";

export type NamedMarks = { abroad: boolean; rivers: boolean };
export type GroundLegendProps = { frame: GroundFrame; deposits: readonly GroundDeposit[]; classes: readonly MineralClass[]; radiusKm: number; placed: string; named?: NamedMarks };

export const ABROAD_LABEL = "A place outside India the sources name";
export const NAMED_RIVER_LABEL = "A river the sources name";
const NONE_NAMED: NamedMarks = { abroad: false, rivers: false };

const SWATCH = "inline-block h-3.5 w-5 shrink-0 rounded-plate border border-ink-2 [forced-color-adjust:none]";
const ELEVATION_FILLS = [
  "bg-[var(--elevation-1)]",
  "bg-[var(--elevation-2)]",
  "bg-[var(--elevation-3)]",
  "bg-[var(--elevation-4)]",
  "bg-[var(--elevation-5)]",
  "bg-[var(--elevation-6)]",
  "bg-[var(--elevation-7)]"
] as const;

function Row({ mark, children }: { mark: ReactNode; children: ReactNode }) {
  return (
    <li className="flex min-w-0 items-center gap-2 font-ui text-label text-ink-2">
      {mark}
      <span className="min-w-0">{children}</span>
    </li>
  );
}

function PinMark() {
  return (
    <svg width={20} height={14} viewBox="0 0 20 14" aria-hidden className="shrink-0 [forced-color-adjust:none]">
      <circle cx={10} cy={7} r={5} fill="var(--terracotta)" stroke="var(--map-label-halo)" strokeWidth={2} />
    </svg>
  );
}

function AbroadMark() {
  return (
    <svg width={20} height={14} viewBox="0 0 20 14" aria-hidden className="shrink-0 [forced-color-adjust:none]">
      <circle cx={10} cy={7} r={4.5} fill="var(--map-label-halo)" stroke="var(--terracotta)" strokeWidth={2.5} />
    </svg>
  );
}

function NamedRiverMark() {
  return (
    <svg width={20} height={14} viewBox="0 0 20 14" aria-hidden className="shrink-0 [forced-color-adjust:none]">
      <path d="M1 7 H19" stroke="var(--map-label-halo)" strokeWidth={5} strokeLinecap="round" />
      <path d="M1 7 H19" stroke="var(--map-river)" strokeWidth={2.25} strokeLinecap="round" />
    </svg>
  );
}

function SaltMark() {
  return (
    <svg width={20} height={14} viewBox="0 0 20 14" aria-hidden className="shrink-0 [forced-color-adjust:none]">
      <rect x={0.5} y={0.5} width={19} height={13} rx={2} fill="var(--map-salt)" stroke="var(--map-salt-hatch)" strokeDasharray="1 2" />
      {[2, 6, 10, 14, 18].flatMap((x) => [3, 7, 11].map((y) => <circle key={`${x}-${y}`} cx={x + (y % 2)} cy={y} r={0.6} fill="var(--map-salt-hatch)" />))}
    </svg>
  );
}

function Relief({ frame }: { frame: GroundFrame }) {
  const lows: (number | null)[] = [null, ...frame.bands.map((band) => band.lowM)];
  return (
    <ul className="grid gap-1.5" aria-label="Elevation">
      {lows.map((low) => (
        <Row key={low ?? "base"} mark={<span className={`${SWATCH} ${ELEVATION_FILLS[elevationStep(low) - 1]}`} aria-hidden />}>
          {bandText(low)}
        </Row>
      ))}
    </ul>
  );
}

function Marks({ frame, radiusKm, placed, named }: Pick<GroundLegendProps, "frame" | "radiusKm" | "placed"> & { named: NamedMarks }) {
  const salt = ringsIn(frame, decodeRings(RANN_RINGS)).length > 0;
  return (
    <ul className="grid gap-1.5" aria-label="Marks">
      <Row mark={<PinMark />}>{placed}</Row>
      {named.abroad ? <Row mark={<AbroadMark />}>{ABROAD_LABEL}</Row> : null}
      <Row mark={<span className="inline-block h-3.5 w-5 shrink-0 rounded-full border border-dashed border-[var(--chart-reference)]" aria-hidden />}>{`${radiusKm} km around each place`}</Row>
      <Row mark={<span className="inline-block h-0.5 w-5 shrink-0 bg-[var(--map-river)]" aria-hidden />}>River</Row>
      {named.rivers ? <Row mark={<NamedRiverMark />}>{NAMED_RIVER_LABEL}</Row> : null}
      <Row mark={<span className={`${SWATCH} bg-[var(--map-water)]`} aria-hidden />}>Sea, lake or reservoir</Row>
      {salt ? <Row mark={<SaltMark />}>Salt flat</Row> : null}
    </ul>
  );
}

function Minerals({ deposits, classes }: Pick<GroundLegendProps, "deposits" | "classes">) {
  const shown = [...new Set(deposits.map((deposit) => deposit.classIndex))].sort((a, b) => a - b);
  if (!shown.length) return null;
  const matched = deposits.some((deposit) => deposit.matched);
  return (
    <ul className="grid gap-1.5" aria-label="Mineral deposits">
      {shown.map((index) => (
        <Row key={index} mark={<MineralSymbol classIndex={index} size={9} />}>
          {classes[index]?.label ?? ""}
        </Row>
      ))}
      {matched ? <Row mark={<MineralSymbol classIndex={shown[0]} size={13} />}>Larger: a mineral the craft’s materials name</Row> : null}
    </ul>
  );
}

export function GroundLegend({ frame, deposits, classes, radiusKm, placed, named = NONE_NAMED }: GroundLegendProps) {
  return (
    <div className="grid gap-x-8 gap-y-4 border-t border-rule pt-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="ground-legend">
      <Relief frame={frame} />
      <Marks frame={frame} radiusKm={radiusKm} placed={placed} named={named} />
      <Minerals deposits={deposits} classes={classes} />
    </div>
  );
}
