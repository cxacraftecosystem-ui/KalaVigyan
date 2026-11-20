import { unitRef } from "@/lib/componentSpecsPlates";
import { boolean, integer, list, matching, nullable, number, object, oneOf, ShapeError, type Shape } from "@/lib/shape";

export const GENERAL_KINDS = ["general_drawing", "general_chart", "general_table", "general_timeline", "general_map_layer"] as const;
export const CHART_FORMS = ["bars", "line"] as const;
export const MARK_RADIUS = 7;
export const MARK_RADIUS_MAX = 22;

export type GeneralKind = (typeof GENERAL_KINDS)[number];

export const GENERAL_KICKERS: Readonly<Record<GeneralKind, string>> = {
  general_drawing: "Drawing",
  general_chart: "Chart",
  general_table: "Table",
  general_timeline: "Timeline",
  general_map_layer: "Map"
};
export const MAP_BOUNDS = { west: 68, east: 97.5, south: 6.5, north: 37.5 } as const;

const SVG_ROOT = /^<svg[\s>]/;
const VIEW_BOX = /viewBox="\s*(-?\d+(?:\.\d+)?)[\s,]+(-?\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)\s*"/;

export type GeneralHead = { title: string; caption: string | null };
export type DrawingSpec = { head: GeneralHead; svg: string; alt: string };
export type ChartPoint = { label: string; value: number; reading: string };
export type ChartSeries = { name: string; points: ChartPoint[] };
export type ChartSpec = { head: GeneralHead; form: (typeof CHART_FORMS)[number]; valueLabel: string; series: ChartSeries[]; emphasis: number | null };
export type TableColumn = { label: string; numeric: boolean };
export type TableSpec = { head: GeneralHead; columns: TableColumn[]; rows: { cells: string[] }[] };
export type TimelineEvent = { year: number; when: string; title: string; text: string };
export type TimelineSpec = { head: GeneralHead; events: TimelineEvent[] };
export type MapPlace = { longitude: number; latitude: number; name: string; reading: string; value: number | null };
export type MapLayerSpec = { head: GeneralHead; places: MapPlace[]; valueLabel: string | null };
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

export const drawingSpecShape = object<DrawingSpec>({ head: headShape, svg: matching(SVG_ROOT, "an svg drawing"), alt: unitRef });
export const chartSpecShape = object<ChartSpec>({
  head: headShape,
  form: oneOf(CHART_FORMS),
  valueLabel: unitRef,
  series: list(object<ChartSeries>({ name: unitRef, points: list(object<ChartPoint>({ label: unitRef, value: number, reading: unitRef }), 1) }), 1),
  emphasis: nullable(integer)
});
export const tableSpecShape = object<TableSpec>({
  head: headShape,
  columns: list(object<TableColumn>({ label: unitRef, numeric: boolean }), 1),
  rows: list(object<{ cells: string[] }>({ cells: list(unitRef, 1) }), 1)
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
      value: nullable(number)
    }),
    1
  ),
  valueLabel: nullable(unitRef)
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
