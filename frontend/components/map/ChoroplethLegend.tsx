import type { ReactNode } from "react";

import { DatasetCredit } from "@/components/DatasetCredit";
import { CHOROPLETH_TONES } from "@/components/map/DistrictLayer";
import { MapPatterns, NO_READING_PATTERN, PLACE_PATTERN, SALT_PATTERN } from "@/components/map/MapBase";
import { CHOROPLETH_COLOURS } from "@/components/map/rampFills";
import { NO_READING_LABEL } from "@/lib/mapRamps";
import type { MapLayer } from "@/lib/regionContract";
import { layerCaption, layerClassLabels, layerSummary, toneIndex } from "@/lib/regionView";
import { cn } from "@/lib/utils";

export type LegendStep = { label: string; colour: string };
export type LegendExtra = { key: string; label: string; fill: string; dashed?: boolean; edge?: string; disc?: boolean };

export const SALT_EXTRA: LegendExtra = { key: "salt", label: "Salt flat: the Great and Little Rann", fill: `url(#${SALT_PATTERN})`, dashed: true, edge: "var(--map-salt-hatch)" };
export const WATER_EXTRA: LegendExtra = { key: "water", label: "Sea", fill: "var(--map-water)" };
export const FOREIGN_EXTRA: LegendExtra = { key: "foreign", label: "Neighbouring countries", fill: "var(--map-land-foreign)" };
export const NO_READING_EXTRA: LegendExtra = { key: "none", label: NO_READING_LABEL, fill: `url(#${NO_READING_PATTERN})` };

export function placeExtra(label: string): LegendExtra {
  return { key: "place", label, fill: `url(#${PLACE_PATTERN})`, edge: "var(--terracotta)" };
}

export function choroplethTone(classIndex: number, classCount: number): string {
  return CHOROPLETH_TONES[toneIndex(classIndex, classCount, CHOROPLETH_TONES.length)];
}

export function choroplethColour(classIndex: number, classCount: number): string {
  return CHOROPLETH_COLOURS[toneIndex(classIndex, classCount, CHOROPLETH_COLOURS.length)];
}

export function Swatch({ className, fill, edge, dashed }: { className?: string; fill?: string; edge?: string; dashed?: boolean }) {
  return (
    <svg width={18} height={12} aria-hidden className="shrink-0 [forced-color-adjust:none]">
      <rect x={0.5} y={0.5} width={17} height={11} fill={fill} stroke={edge ?? "var(--map-coast)"} strokeDasharray={dashed ? "1 2" : undefined} className={className} />
    </svg>
  );
}

export function Disc({ fill }: { fill: string }) {
  return (
    <svg width={18} height={12} aria-hidden className="shrink-0 [forced-color-adjust:none]">
      <circle cx={9} cy={6} r={4.5} fill={fill} stroke="var(--map-marker-ring)" strokeWidth={1.5} />
    </svg>
  );
}

export function LegendExtras({ extras }: { extras: readonly LegendExtra[] }) {
  return (
    <>
      {extras.map((extra) => (
        <li key={extra.key} className="inline-flex items-center gap-2">
          {extra.disc ? <Disc fill={extra.fill} /> : <Swatch fill={extra.fill} edge={extra.edge} dashed={extra.dashed} />}
          {extra.label}
        </li>
      ))}
    </>
  );
}

export type MapLegendProps = { title: ReactNode; steps: readonly LegendStep[]; extras?: readonly LegendExtra[]; note?: ReactNode; caption?: ReactNode; summary?: string; className?: string };

export function MapLegend({ title, steps, extras = [], note, caption, summary, className }: MapLegendProps) {
  return (
    <div className={cn("relative grid gap-2 border-t border-rule pt-3 font-ui text-caption text-ink-2", className)} data-testid="choropleth-legend">
      <svg width={0} height={0} aria-hidden className="absolute">
        <MapPatterns />
      </svg>
      <p className="text-label text-ink-1">{title}</p>
      {note ? (
        <p className="text-ink-3" data-testid="choropleth-scope">
          {note}
        </p>
      ) : null}
      {summary ? <p className="sr-only">{summary}</p> : null}
      <ol className="flex max-w-sm" aria-hidden>
        {steps.map((step) => (
          <li key={step.label} className="h-2.5 flex-1 first:rounded-s-plate last:rounded-e-plate" style={{ backgroundColor: step.colour }} />
        ))}
      </ol>
      <ul className="grid gap-x-4 gap-y-1.5 [font-variant-numeric:lining-nums_tabular-nums] sm:grid-cols-2">
        {steps.map((step) => (
          <li key={step.label} className="inline-flex items-center gap-2">
            <Swatch fill={step.colour} />
            {step.label}
          </li>
        ))}
        <LegendExtras extras={extras} />
      </ul>
      {caption ? <p className="text-ink-3">{caption}</p> : null}
    </div>
  );
}

export function ChoroplethLegend({ layer, note }: { layer: MapLayer; note?: string }) {
  const labels = layerClassLabels(layer);
  const steps = labels.map((label, index) => ({ label, colour: choroplethColour(index, labels.length) }));
  return (
    <div className="mt-4 grid gap-2">
      <MapLegend title={layer.layer.title} steps={steps} extras={[NO_READING_EXTRA]} note={note} caption={layerCaption(layer)} summary={layerSummary(layer)} />
      <DatasetCredit dataset={layer.dataset} />
    </div>
  );
}
