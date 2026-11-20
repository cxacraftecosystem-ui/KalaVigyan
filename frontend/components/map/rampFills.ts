import type { PaletteName } from "@/lib/mapPalettes";
import type { RampName } from "@/lib/mapRamps";

export const RAMP_FILLS: Record<RampName, readonly string[]> = {
  rain: ["fill-[var(--rain-1)]", "fill-[var(--rain-2)]", "fill-[var(--rain-3)]", "fill-[var(--rain-4)]", "fill-[var(--rain-5)]", "fill-[var(--rain-6)]"],
  heat: ["fill-[var(--heat-1)]", "fill-[var(--heat-2)]", "fill-[var(--heat-3)]", "fill-[var(--heat-4)]", "fill-[var(--heat-5)]", "fill-[var(--heat-6)]"],
  density: ["fill-[var(--density-1)]", "fill-[var(--density-2)]", "fill-[var(--density-3)]", "fill-[var(--density-4)]", "fill-[var(--density-5)]", "fill-[var(--density-6)]"]
};

export const PALETTE_FILLS: Record<PaletteName, readonly string[]> = {
  ...RAMP_FILLS,
  earth: ["fill-[var(--earth-1)]", "fill-[var(--earth-2)]", "fill-[var(--earth-3)]", "fill-[var(--earth-4)]", "fill-[var(--earth-5)]", "fill-[var(--earth-6)]"],
  cover: ["fill-[var(--cover-1)]", "fill-[var(--cover-2)]", "fill-[var(--cover-3)]", "fill-[var(--cover-4)]", "fill-[var(--cover-5)]", "fill-[var(--cover-6)]"],
  ph: ["fill-[var(--ph-1)]", "fill-[var(--ph-2)]", "fill-[var(--ph-3)]", "fill-[var(--ph-4)]", "fill-[var(--ph-5)]"],
  elevation: [
    "fill-[var(--elevation-1)]",
    "fill-[var(--elevation-2)]",
    "fill-[var(--elevation-3)]",
    "fill-[var(--elevation-4)]",
    "fill-[var(--elevation-5)]",
    "fill-[var(--elevation-6)]",
    "fill-[var(--elevation-7)]"
  ]
};

export function paletteFill(ramp: PaletteName, step: number): string {
  const fills = PALETTE_FILLS[ramp];
  return fills[Math.min(Math.max(step, 1), fills.length) - 1];
}

export const CHOROPLETH_COLOURS = ["var(--density-1)", "var(--density-2)", "var(--density-3)", "var(--density-5)", "var(--density-6)"] as const;
