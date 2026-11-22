import { unitRef } from "@/lib/componentSpecsPlates";
import { boolean, integer, list, matching, nullable, number, object, oneOf, optional, ShapeError, text, type Shape } from "@/lib/shape";

export const GENERAL_KINDS = ["drawing", "chart", "fact_table", "timeline", "map_layer"] as const;
export const DECLARED_KEY = "head";
export const CHART_FORMS = ["bars", "line"] as const;
export const MARK_RADIUS = 7;
export const MARK_RADIUS_MAX = 22;

export type GeneralKind = (typeof GENERAL_KINDS)[number];

export const GENERAL_KICKERS: Readonly<Record<GeneralKind, string>> = {
  drawing: "Drawing",
  chart: "Chart",
  fact_table: "Table",
  timeline: "Timeline",
  map_layer: "Map"
};
export const MAP_BOUNDS = { west: 68, east: 97.5, south: 6.5, north: 37.5 } as const;

const SVG_ROOT = /^<svg[\s>]/;
const ROLE = /var\(\s*--[a-z0-9-]+\s*\)/;
const ROLE_ALL = /var\(\s*--([a-z0-9-]+)\s*\)/g;
const VIEW_BOX = /viewBox="\s*(-?\d+(?:\.\d+)?)[\s,]+(-?\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)\s*"/;

export type GeneralHead = { title: string; caption: string | null };
export type DataCell = { row: number; column: string };
export type DatasetCite = { code: string; credit?: string; url?: string };
export const THEME_VARIANTS = ["light", "dark", "hcLight", "hcDark"] as const;
export type ThemeVariant = (typeof THEME_VARIANTS)[number];
export type DrawingThemes = Record<ThemeVariant, string>;
export type DrawingSpec = { head: GeneralHead; svg: string; alt: string; themes?: DrawingThemes };
export type ChartPoint = { label: string; value: number; reading: string; cell?: DataCell };
export type ChartSeries = { name: string; points: ChartPoint[] };
export type ChartSpec = { head: GeneralHead; form: (typeof CHART_FORMS)[number]; valueLabel: string; series: ChartSeries[]; emphasis: number | null; dataset?: DatasetCite };
export type TableColumn = { label: string; numeric: boolean; column?: string };
export type TableRow = { cells: string[]; row?: number };
export type TableSpec = { head: GeneralHead; columns: TableColumn[]; rows: TableRow[]; dataset?: DatasetCite };
export type TimelineEvent = { year: number; when: string; title: string; text: string };
export type TimelineSpec = { head: GeneralHead; events: TimelineEvent[] };
export type MapPlace = { longitude: number; latitude: number; name: string; reading: string; value: number | null; cell?: DataCell };
export type MapLayerSpec = { head: GeneralHead; places: MapPlace[]; valueLabel: string | null; dataset?: DatasetCite };
export type ViewBox = { x: number; y: number; width: number; height: number };

const within = (low: number, high: number, label: string): Shape<number> => ({
  expected: `${label} from ${low} to ${high}`,
  parse(value, path) {
    const parsed = number.parse(value, path);
    if (parsed < low || parsed > high) throw new ShapeError(path, `${label} from ${low} to ${high}`);
    return parsed;
  }
});

const headShape = object<GeneralHead>({ title: unitRef, caption: nullable(unitRef) });
const cellShape = optional(object<DataCell>({ row: integer, column: text }));
const datasetShape = optional(object<DatasetCite>({ code: text, credit: optional(text), url: optional(text) }));

export function isDeclared(spec: unknown): boolean {
  return typeof spec === "object" && spec !== null && !Array.isArray(spec) && Object.hasOwn(spec, DECLARED_KEY);
}

const svgMarkup = matching(SVG_ROOT, "an svg drawing");
const themesShape = object<DrawingThemes>({ light: svgMarkup, dark: svgMarkup, hcLight: svgMarkup, hcDark: svgMarkup });
export const drawingSpecShape = object<DrawingSpec>({ head: headShape, svg: svgMarkup, alt: unitRef, themes: optional(themesShape) });
export const chartSpecShape = object<ChartSpec>({
  head: headShape,
  form: oneOf(CHART_FORMS),
  valueLabel: unitRef,
  series: list(object<ChartSeries>({ name: unitRef, points: list(object<ChartPoint>({ label: unitRef, value: number, reading: unitRef, cell: cellShape }), 1) }), 1),
  emphasis: nullable(integer),
  dataset: datasetShape
});
export const tableSpecShape = object<TableSpec>({
  head: headShape,
  columns: list(object<TableColumn>({ label: unitRef, numeric: boolean, column: optional(text) }), 1),
  rows: list(object<TableRow>({ cells: list(unitRef, 1), row: optional(integer) }), 1),
  dataset: datasetShape
});
export const timelineSpecShape = object<TimelineSpec>({
  head: headShape,
  events: list(object<TimelineEvent>({ year: integer, when: unitRef, title: unitRef, text: unitRef }), 2)
});
export const mapLayerSpecShape = object<MapLayerSpec>({
  head: headShape,
  places: list(
    object<MapPlace>({
      longitude: within(MAP_BOUNDS.west, MAP_BOUNDS.east, "a longitude"),
      latitude: within(MAP_BOUNDS.south, MAP_BOUNDS.north, "a latitude"),
      name: unitRef,
      reading: unitRef,
      value: nullable(number),
      cell: cellShape
    }),
    1
  ),
  valueLabel: nullable(unitRef),
  dataset: datasetShape
});

export function parsedSpec<T>(target: Shape<T>, spec: unknown): T | null {
  try {
    return target.parse(spec, "");
  } catch (error) {
    if (error instanceof ShapeError) return null;
    throw error;
  }
}

export function drawingViewBox(svg: string): ViewBox | null {
  const found = VIEW_BOX.exec(svg);
  if (!found) return null;
  const [x, y, width, height] = found.slice(1).map(Number);
  return width > 0 && height > 0 ? { x, y, width, height } : null;
}

export function drawingRoles(svg: string): boolean {
  return ROLE.test(svg);
}

export function resolvedDrawing(svg: string, value: (role: string) => string): string {
  return svg.replace(ROLE_ALL, (found, role: string) => value(role).trim() || found);
}

export function drawingSource(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function chartLabels(spec: ChartSpec): string[] {
  return spec.series[0].points.map((point) => point.label);
}

export function chartRange(spec: ChartSpec): { low: number; high: number } {
  const values = spec.series.flatMap((series) => series.points.map((point) => point.value));
  const high = Math.max(...values);
  const low = spec.form === "bars" ? 0 : Math.min(...values);
  return high === low ? { low: Math.min(0, low), high: high === 0 ? 1 : Math.max(high, 0) } : { low, high };
}

export function share(value: number, range: { low: number; high: number }): number {
  const span = range.high - range.low;
  return span > 0 ? (value - range.low) / span : 0;
}

export function eraYear(year: number): string {
  return year < 0 ? `${-year} BCE` : String(year);
}

export function placeRadius(value: number | null, largest: number): number {
  if (value === null || largest <= 0) return MARK_RADIUS;
  return MARK_RADIUS + (MARK_RADIUS_MAX - MARK_RADIUS) * Math.sqrt(Math.max(0, value) / largest);
}
