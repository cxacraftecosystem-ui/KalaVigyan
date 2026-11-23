import type { RegionStoryBlock, StoryStep } from "@/lib/explainerPlace";
import { listText, numberRuns } from "@/lib/format";
import { cumulativeLengths, joinLines, lineLength, orientDownstream, type Framing, type Point } from "@/lib/riverGeometry";
import type { ReachDistrict } from "@/lib/riverTopology";

export const FLOW_SECONDS = 5;
export const FLOW_EASE = [0.45, 0, 0.2, 1] as const;
export const STORY_FRAMING: Framing = { aspect: 4 / 3, minSpan: 120, padding: 0.1 };
export const NOT_YET = -1;
export const ALL_PASSED = 1;

export type Rings = readonly (readonly Point[])[];
export type CourseReach = { line: readonly Point[]; districts: readonly ReachDistrict[] | null };
export type CourseSpan = { start: number; length: number; districts: readonly ReachDistrict[] | null };
export type Course = { lines: Point[][]; points: Point[]; lengths: number[]; spans: CourseSpan[] };
export type StepBadge = { districtLgd: number; label: string; first: number };

export function missingReaches(reachIds: readonly number[], basin: ReadonlyMap<number, unknown>): number[] {
  return reachIds.filter((id) => !basin.has(id));
}

function courseSpans(lines: readonly Point[][], reaches: readonly CourseReach[]): CourseSpan[] {
  let start = 0;
  return lines.map((line, index) => {
    const previous = lines[index - 1];
    if (previous) start += lineLength([previous[previous.length - 1], line[0]]);
    const span = { start, length: lineLength(line), districts: reaches[index].districts };
    start += span.length;
    return span;
  });
}

export function riverCourse(reachIds: readonly number[], reachOf: (id: number) => CourseReach): Course {
  const reaches = reachIds.map(reachOf);
  const lines = orientDownstream(reaches.map((reach) => reach.line));
  const points = joinLines(lines);
  return { lines, points, lengths: cumulativeLengths(points), spans: courseSpans(lines, reaches) };
}

function listing(span: CourseSpan, lgd: number): ReachDistrict | undefined {
  return span.districts?.find((district) => district.lgd === lgd);
}

function entryAlong(course: Course, lgd: number): number | null {
  for (const span of course.spans) {
    const district = listing(span, lgd);
    if (district) return span.start + district.entry * span.length;
  }
  return null;
}

export function districtEntries(course: Course, order: readonly number[]): Map<number, number> {
  const total = course.lengths[course.lengths.length - 1];
  const entries = new Map<number, number>();
  let floor = 0;
  for (const lgd of order) {
    const along = entryAlong(course, lgd);
    const fraction = along === null || total === 0 ? floor : Math.max(floor, along / total);
    entries.set(lgd, fraction);
    floor = fraction;
  }
  return entries;
}

export function stretchOf(course: Course, lgd: number): Point[][] {
  return course.lines.filter((_, index) => listing(course.spans[index], lgd) !== undefined);
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
