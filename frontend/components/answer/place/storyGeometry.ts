import { boardBox, RANN_SALT_FLATS, type MapBox } from "@/components/map/boardGeometry";
import { PLACE_TONE } from "@/components/map/DistrictLayer";
import { project } from "@/components/map/projection";
import type { DistrictShape } from "@/components/map/shapeGeometry";
import type { RegionStoryBlock } from "@/lib/explainerPlace";
import {
  districtEntries,
  flowThresholds,
  riverCourse,
  stepBadges,
  stepFractions,
  stretchOf,
  STORY_FRAMING,
  type Course,
  type Rings,
  type StepBadge
} from "@/lib/regionStory";
import { boundsOf, framedView, pathData, withinView, type Point, type View } from "@/lib/riverGeometry";
import type { LonLat, RiverBasin } from "@/lib/riverTopology";

const CONTEXT_MARGIN = 100;

export const STORY_TONES: Record<"context" | "waiting" | "reached" | "story", string> = {
  context: "fill-transparent",
  waiting: "fill-transparent stroke-terracotta [stroke-width:1.25px]",
  reached: PLACE_TONE,
  story: PLACE_TONE
};

export type StoryDistrict = { lgd: number; shape: DistrictShape; rings: Rings; label: Point };
export type Tributaries = { order: number; d: string };
export type StoryRiver = { course: Course; d: string; tributaries: Tributaries[]; stretches: Map<number, string> };
export type PlacedBadge = StepBadge & { at: Point };
export type StoryGeometry = {
  view: View;
  districts: Map<number, StoryDistrict>;
  context: DistrictShape[];
  river: StoryRiver | null;
  entries: Map<number, number>;
  fractions: number[];
  thresholds: number[];
  badges: PlacedBadge[];
};

function projected(line: readonly LonLat[]): Point[] {
  return line.map(([longitude, latitude]) => {
    const { x, y } = project(longitude, latitude);
    return [x, y] as const;
  });
}

function storyDistricts(block: RegionStoryBlock, shapes: readonly DistrictShape[]): Map<number, StoryDistrict> {
  const byLgd = new Map(shapes.map((shape) => [shape.lgd, shape]));
  const drawn = new Map<number, StoryDistrict>();
  for (const { districtLgd } of block.districts) {
    const shape = byLgd.get(districtLgd);
    if (shape) drawn.set(districtLgd, { lgd: districtLgd, shape, rings: shape.rings.map(projected), label: projected([shape.centroid])[0] });
  }
  return drawn;
}

function basinLine(basin: RiverBasin, id: number): Point[] {
  const reach = basin.reaches.get(id);
  if (!reach) throw new Error(`reach ${id} is not in basin ${basin.mainRiv}`);
  return projected(reach.line);
}

function tributaries(basin: RiverBasin, path: ReadonlySet<number>, view: View): Tributaries[] {
  const byOrder = new Map<number, Point[][]>();
  for (const reach of basin.reaches.values()) {
    if (path.has(reach.id)) continue;
    const line = projected(reach.line);
    if (line.some((point) => withinView(point, view))) byOrder.set(reach.ordStra, [...(byOrder.get(reach.ordStra) ?? []), line]);
  }
  return [...byOrder].sort(([a], [b]) => a - b).map(([order, lines]) => ({ order, d: pathData(lines) }));
}

function storyRiver(course: Course, basin: RiverBasin, path: ReadonlySet<number>, story: { view: View; districts: Map<number, StoryDistrict> }): StoryRiver {
  const stretches = new Map([...story.districts].map(([lgd, district]) => [lgd, pathData(stretchOf(course, district.rings))]));
  return { course, d: pathData([course.points]), tributaries: tributaries(basin, path, story.view), stretches };
}

export function storyGeometry(block: RegionStoryBlock, shapes: readonly DistrictShape[], basin: RiverBasin | null): StoryGeometry | null {
  const districts = storyDistricts(block, shapes);
  const course = block.river && basin ? riverCourse(block.river.reachIds, (id) => basinLine(basin, id)) : null;
  const bounds = boundsOf([...(course ? [course.points] : []), ...[...districts.values()].flatMap((district) => district.rings)]);
  if (!bounds) return null;
  const view = framedView(bounds, STORY_FRAMING);
  const ringsOf = new Map([...districts].map(([lgd, district]) => [lgd, district.rings]));
  const entries = course && block.river ? districtEntries(course, block.river.districtLgds, ringsOf) : new Map<number, number>();
  const fractions = stepFractions(block.steps, entries);
  const river = course && basin && block.river ? storyRiver(course, basin, new Set(block.river.reachIds), { view, districts }) : null;
  const context = shapes.filter((shape) => districts.has(shape.lgd) || withinView(projected([shape.centroid])[0], view, CONTEXT_MARGIN));
  const badges = stepBadges(block.steps).flatMap((badge) => {
    const district = districts.get(badge.districtLgd);
    return district ? [{ ...badge, at: district.label }] : [];
  });
  return { view, districts, context, river, entries, fractions, thresholds: flowThresholds(entries, fractions), badges };
}

export function storyTone(geometry: StoryGeometry, lgd: number, passed: number): string {
  const entry = geometry.entries.get(lgd);
  if (entry !== undefined) return entry <= passed ? STORY_TONES.reached : STORY_TONES.waiting;
  return geometry.districts.has(lgd) ? STORY_TONES.story : STORY_TONES.context;
}

function pathBox(path: string): MapBox {
  const numbers = (path.match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number);
  const xs = numbers.filter((_, at) => at % 2 === 0);
  const ys = numbers.filter((_, at) => at % 2 === 1);
  const [minX, minY] = [Math.min(...xs), Math.min(...ys)];
  return { x: minX, y: minY, width: Math.max(...xs) - minX, height: Math.max(...ys) - minY };
}

export function boxesMeet(a: MapBox, b: MapBox): boolean {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

export function saltInView(view: View): boolean {
  return boxesMeet(boardBox(pathBox(RANN_SALT_FLATS)), view);
}
