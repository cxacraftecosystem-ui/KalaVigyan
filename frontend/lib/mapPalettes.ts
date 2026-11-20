import { formatRange } from "@/lib/measure";
import type { MapLayer, MapLayerSummary } from "@/lib/regionContract";

export type PaletteName = "rain" | "heat" | "density" | "earth" | "cover" | "ph" | "elevation";
export type PaletteKind = "sequential" | "diverging" | "hypsometric";
export type LayerPalette = { ramp: PaletteName; kind: PaletteKind; reversed: boolean; breaks: readonly number[] | null };
export type ShownClass = { min: number | null; max: number | null; step: number; label: string };

export const PALETTE_STEPS: Record<PaletteName, number> = { rain: 6, heat: 6, density: 6, earth: 6, cover: 6, ph: 5, elevation: 7 };
export const PH_BREAKS = [5.5, 6.5, 7.5, 8.5] as const;
export const ELEVATION_BREAKS = [100, 300, 600, 1000, 2000, 4000] as const;

const SEQUENTIAL = (ramp: PaletteName, reversed = false): LayerPalette => ({ ramp, kind: "sequential", reversed, breaks: null });

export const LAYER_PALETTES: Readonly<Record<string, LayerPalette>> = {
  "soil-ph-0-5cm": { ramp: "ph", kind: "diverging", reversed: false, breaks: PH_BREAKS },
  "soil-organic-carbon-0-5cm": SEQUENTIAL("earth"),
  "clay-0-5cm": SEQUENTIAL("earth"),
  "sand-0-5cm": SEQUENTIAL("earth"),
  "cation-exchange-0-5cm": SEQUENTIAL("earth"),
  "bare-ground-share": SEQUENTIAL("earth"),
  "forest-loss-2001-2025": SEQUENTIAL("earth"),
  "annual-mean-temperature": SEQUENTIAL("heat"),
  "warmest-month-maximum": SEQUENTIAL("heat"),
  "coldest-month-minimum": SEQUENTIAL("heat"),
  "annual-precipitation": SEQUENTIAL("rain"),
  "monsoon-share": SEQUENTIAL("rain"),
  "river-density": SEQUENTIAL("rain"),
  "distance-to-major-river": SEQUENTIAL("rain", true),
  "tree-cover-2000": SEQUENTIAL("cover"),
  "tree-cover-share": SEQUENTIAL("cover"),
  "cropland-share": SEQUENTIAL("cover"),
  elevation: { ramp: "elevation", kind: "hypsometric", reversed: false, breaks: ELEVATION_BREAKS },
  "built-up-share": SEQUENTIAL("density"),
  slope: SEQUENTIAL("density"),
  "mineral-sites": SEQUENTIAL("density")
};

const BY_VARIABLE: readonly [RegExp, LayerPalette][] = [
  [/rain|precip|monsoon/i, SEQUENTIAL("rain")],
  [/temp/i, SEQUENTIAL("heat")],
  [/phh2o/i, LAYER_PALETTES["soil-ph-0-5cm"]],
  [/^elevation$/i, LAYER_PALETTES.elevation],
  [/tree|crop|forest_cover/i, SEQUENTIAL("cover")],
  [/soc|clay|sand|cec|bare/i, SEQUENTIAL("earth")]
];

export function layerPalette(layer: Pick<MapLayerSummary, "id" | "variable">): LayerPalette {
  return LAYER_PALETTES[layer.id] ?? BY_VARIABLE.find(([pattern]) => pattern.test(layer.variable))?.[1] ?? SEQUENTIAL("density");
}

export function paletteSeries(palette: LayerPalette): string {
  if (palette.ramp === "rain") return "var(--series-rain)";
  if (palette.ramp === "heat") return "var(--series-heat)";
  return "var(--chart-series)";
}

export function spreadStep(classIndex: number, classCount: number, steps: number): number {
  if (classCount < 1 || classIndex < 0 || classIndex >= classCount) throw new RangeError(`class ${classIndex} of ${classCount}`);
  if (classCount === 1) return Math.ceil(steps / 2);
  return 1 + Math.round((classIndex * (steps - 1)) / (classCount - 1));
}

function fixedClasses(breaks: readonly number[], unit: string): ShownClass[] {
  const edges: (number | null)[] = [null, ...breaks, null];
  return edges.slice(0, -1).map((min, at) => {
    const max = edges[at + 1];
    return { min, max, step: at + 1, label: formatRange(min, max, unit) ?? "" };
  });
}

export function paletteClasses(layer: MapLayer): ShownClass[] {
  const palette = layerPalette(layer.layer);
  if (palette.breaks) return fixedClasses(palette.breaks, layer.layer.unit);
  const steps = PALETTE_STEPS[palette.ramp];
  return layer.classes.map((band, at) => {
    const step = spreadStep(at, layer.classes.length, steps);
    return { min: band.min, max: band.max, step: palette.reversed ? steps + 1 - step : step, label: formatRange(band.min, band.max, layer.layer.unit) ?? "" };
  });
}

export function classIndexOf(classes: readonly ShownClass[], value: number): number {
  const found = classes.findIndex((band, at) => {
    const last = at === classes.length - 1;
    const aboveMin = band.min === null || value >= band.min;
    const belowMax = band.max === null || value < band.max || (last && value <= band.max);
    return aboveMin && belowMax;
  });
  if (found >= 0) return found;
  return value < (classes[0]?.min ?? value) ? 0 : classes.length - 1;
}

export function paletteColour(ramp: PaletteName, step: number): string {
  return `var(--${ramp}-${step})`;
}

export function districtSteps(layer: MapLayer): { classes: ShownClass[]; steps: Map<number, number> } {
  const classes = paletteClasses(layer);
  const steps = new Map(Object.entries(layer.values).map(([lgd, value]) => [Number(lgd), classes[classIndexOf(classes, value)].step] as const));
  return { classes, steps };
}

export function paletteSteps(layer: MapLayer): { label: string; colour: string }[] {
  const { ramp } = layerPalette(layer.layer);
  return paletteClasses(layer).map((band) => ({ label: band.label, colour: paletteColour(ramp, band.step) }));
}
