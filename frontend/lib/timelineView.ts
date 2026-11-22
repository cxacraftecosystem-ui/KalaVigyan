import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import type { TimelineMapBlock } from "@/lib/explainerPlay";
import { bySentence, type SentenceGroup } from "@/lib/sentenceGroups";
import type { LongitudeLatitudeBox } from "@/lib/supplyView";

export type TimelineEntryKind = "point" | "route";
export type TimelineEntryState = "past" | "current" | "later";
export type TimelineEntry = { key: string; kind: TimelineEntryKind; yearFrom: number; yearTo: number; places: number[]; sentence: ExplainerSentence };
export type PlacedPlace = { index: number; name: string; wikidataId: string; latitude: number; longitude: number; pin: number; beyond: boolean };
export type TimelineRouteLine = { key: string; start: PlacedPlace; end: PlacedPlace; entry: TimelineEntry };

const YEARS_PER_CENTURY = 100;
const YEARS_PER_DECADE = 10;

function ordinal(value: number): string {
  const tens = value % 100;
  if (tens >= 11 && tens <= 13) return `${value}th`;
  return `${value}${["th", "st", "nd", "rd"][value % 10] ?? "th"}`;
}

export function yearSpanText(yearFrom: number, yearTo: number): string {
  if (yearFrom === yearTo) return String(yearFrom);
  if ((yearFrom - 1) % YEARS_PER_CENTURY === 0 && yearTo % YEARS_PER_CENTURY === 0 && yearTo > yearFrom) {
    const first = (yearFrom - 1) / YEARS_PER_CENTURY + 1;
    const last = yearTo / YEARS_PER_CENTURY;
    return first === last ? `${ordinal(first)} century` : `${ordinal(first)}–${ordinal(last)} century`;
  }
  if (yearFrom % YEARS_PER_DECADE === 0 && yearTo === yearFrom + YEARS_PER_DECADE - 1) return `${yearFrom}s`;
  return `${yearFrom}–${yearTo}`;
}

export function timelineEntries(block: TimelineMapBlock): TimelineEntry[] {
  const points = block.points.map((point, index) => ({ key: `point:${index}`, kind: "point" as const, yearFrom: point.yearFrom, yearTo: point.yearTo, places: [point.place], sentence: point.sentence }));
  const routes = block.routes.map((route, index) => ({ key: `route:${index}`, kind: "route" as const, yearFrom: route.yearFrom, yearTo: route.yearTo, places: [route.start, route.end], sentence: route.sentence }));
  return [...points, ...routes].sort((a, b) => a.yearFrom - b.yearFrom || a.yearTo - b.yearTo);
}

export function entryGroups(entries: readonly TimelineEntry[]): SentenceGroup<TimelineEntry>[] {
  return bySentence(entries, (entry) => entry.sentence);
}

export function groupState(entries: readonly TimelineEntry[], year: number): TimelineEntryState {
  const yearFrom = Math.min(...entries.map((entry) => entry.yearFrom));
  const yearTo = Math.max(...entries.map((entry) => entry.yearTo));
  return entryState({ yearFrom, yearTo }, year);
}

export function timelineStops(entries: readonly TimelineEntry[]): number[] {
  return [...new Set(entries.map((entry) => entry.yearFrom))].sort((a, b) => a - b);
}

export function stopLabel(entries: readonly TimelineEntry[], year: number): string {
  const first = entries.find((entry) => entry.yearFrom === year);
  return first ? yearSpanText(first.yearFrom, first.yearTo) : String(year);
}

export function entryState(entry: Pick<TimelineEntry, "yearFrom" | "yearTo">, year: number): TimelineEntryState {
  if (entry.yearFrom > year) return "later";
  return entry.yearTo < year ? "past" : "current";
}

function inBox(latitude: number, longitude: number, box: LongitudeLatitudeBox): boolean {
  return longitude >= box.minLongitude && longitude <= box.maxLongitude && latitude >= box.minLatitude && latitude <= box.maxLatitude;
}

export function placedPlaces(block: TimelineMapBlock, box: LongitudeLatitudeBox): PlacedPlace[] {
  const placed: PlacedPlace[] = [];
  block.places.forEach((place, index) => {
    const { wikidataId, latitude, longitude } = place;
    if (wikidataId === null || latitude === null || longitude === null) return;
    placed.push({ index, name: place.name, wikidataId, latitude, longitude, pin: placed.length + 1, beyond: !inBox(latitude, longitude, box) });
  });
  return placed;
}

export function reachedPlaces(entries: readonly TimelineEntry[], year: number): Set<number> {
  return new Set(entries.filter((entry) => entry.yearFrom <= year).flatMap((entry) => entry.places));
}

export function routeLines(entries: readonly TimelineEntry[], placed: readonly PlacedPlace[]): TimelineRouteLine[] {
  const byIndex = new Map(placed.map((place) => [place.index, place]));
  return entries.flatMap((entry) => {
    if (entry.kind !== "route") return [];
    const start = byIndex.get(entry.places[0]);
    const end = byIndex.get(entry.places[1]);
    return start && end ? [{ key: entry.key, start, end, entry }] : [];
  });
}

export function timelineSummary(block: TimelineMapBlock, entries: readonly TimelineEntry[]): string {
  const stops = timelineStops(entries);
  if (stops.length === 0) return "";
  const first = stopLabel(entries, stops[0]);
  const last = stopLabel(entries, stops[stops.length - 1]);
  const span = first === last ? first : `${first} to ${last}`;
  return `${block.places.map((place) => place.name).join(", ")}, ${span}`;
}
