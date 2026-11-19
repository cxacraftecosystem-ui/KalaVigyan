import type { RegionStoryBlock, StoryStep } from "@/lib/explainerPlace";
import { listText, numberRuns } from "@/lib/format";
import { cumulativeLengths, insideRings, joinLines, orientDownstream, type Framing, type Point } from "@/lib/riverGeometry";

export const FLOW_SECONDS = 5;
export const FLOW_EASE = [0.45, 0, 0.2, 1] as const;
export const STORY_FRAMING: Framing = { aspect: 4 / 3, minSpan: 120, padding: 0.1 };
export const NOT_YET = -1;
export const ALL_PASSED = 1;

export type Rings = readonly (readonly Point[])[];
export type Course = { lines: Point[][]; points: Point[]; lengths: number[] };
export type StepBadge = { districtLgd: number; label: string; first: number };

export function missingReaches(reachIds: readonly number[], basin: ReadonlyMap<number, unknown>): number[] {
  return reachIds.filter((id) => !basin.has(id));
}

export function riverCourse(reachIds: readonly number[], lineOf: (id: number) => readonly Point[]): Course {
  const lines = orientDownstream(reachIds.map(lineOf));
  const points = joinLines(lines);
  return { lines, points, lengths: cumulativeLengths(points) };
}

export function districtEntries(course: Course, order: readonly number[], ringsOf: ReadonlyMap<number, Rings>): Map<number, number> {
  const total = course.lengths[course.lengths.length - 1];
  const entries = new Map<number, number>();
  let floor = 0;
  for (const lgd of order) {
    const rings = ringsOf.get(lgd);
    const at = rings ? course.points.findIndex((point) => insideRings(point, rings)) : -1;
    const fraction = at < 0 || total === 0 ? floor : Math.max(floor, course.lengths[at] / total);
    entries.set(lgd, fraction);
    floor = fraction;
  }
  return entries;
}

export function stretchOf(course: Course, rings: Rings): Point[][] {
  return course.lines.filter((line) => line.some((point) => insideRings(point, rings)));
}

export function stepFractions(steps: readonly StoryStep[], entries: ReadonlyMap<number, number>): number[] {
  return steps.map((step) => (step.districtLgd === null ? undefined : entries.get(step.districtLgd)) ?? ALL_PASSED);
}

export function flowThresholds(entries: ReadonlyMap<number, number>, steps: readonly number[]): number[] {
  return [...new Set([...entries.values(), ...steps, ALL_PASSED])].sort((a, b) => a - b);
}

export function passedFraction(thresholds: readonly number[], value: number): number {
  let passed = NOT_YET;
  for (const threshold of thresholds) if (threshold <= value && threshold > passed) passed = threshold;
  return passed;
}

export function playingStep(fractions: readonly number[], passed: number): number | null {
  if (passed < 0 || passed >= ALL_PASSED) return null;
  let found: number | null = null;
  fractions.forEach((fraction, index) => {
    if (fraction <= passed && (found === null || fraction > fractions[found])) found = index;
  });
  return found;
}

export function stepBadges(steps: readonly StoryStep[]): StepBadge[] {
  const byDistrict = new Map<number, number[]>();
  steps.forEach((step, index) => {
    if (step.districtLgd !== null) byDistrict.set(step.districtLgd, [...(byDistrict.get(step.districtLgd) ?? []), index + 1]);
  });
  return [...byDistrict].map(([districtLgd, numbers]) => ({ districtLgd, label: numberRuns(numbers).join(", "), first: numbers[0] - 1 }));
}

export function riverLabel(block: RegionStoryBlock): string {
  return block.river?.name ?? "River";
}

export function storySummary(block: RegionStoryBlock): string {
  const places = listText(block.districts.map((district) => district.name));
  return block.river ? `${riverLabel(block)} from its source to its outlet, with ${places}.` : `${places}.`;
}

export function storyTitle(block: RegionStoryBlock): string {
  const places = listText(block.districts.map((district) => district.name));
  return block.river?.name ? `${block.river.name} and ${places}` : places;
}

export function districtLine(block: RegionStoryBlock, lgd: number | null): string | null {
  const district = lgd === null ? undefined : block.districts.find((entry) => entry.districtLgd === lgd);
  return district ? `${district.name} · ${district.stateName}` : null;
}
