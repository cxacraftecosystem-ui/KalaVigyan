import { numberWord, type StateCount } from "@/lib/atlasIndex";
import type { CraftMapPoint } from "@/lib/types";

export const RANKED_SHOWN = 10;
export const STATE_KEY_PREFIX = "state-";

export type StateMark = StateCount & { longitude: number; latitude: number };
export type Box = { x: number; y: number; width: number; height: number };
export type LabelSpot = { key: string; x: number; y: number; anchor: "start" | "middle" | "end" };
export type LabelAsk = { key: string; x: number; y: number; r: number; width: number; height: number };

const NICE_STEPS = [1, 2, 2.5, 3, 5, 6, 10];

function fold(name: string): string {
  return name.normalize("NFKD").replace(/\p{M}+/gu, "").toLowerCase().replace(/&/g, "and").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

export function stateMarks(counts: readonly StateCount[], points: readonly CraftMapPoint[]): StateMark[] {
  const where = new Map(points.filter((point) => point.key.startsWith(STATE_KEY_PREFIX)).map((point) => [fold(point.name), point]));
  return counts.flatMap((state) => {
    const point = where.get(fold(state.name));
    return point ? [{ ...state, longitude: point.longitude, latitude: point.latitude }] : [];
  });
}

export function circleRadius(count: number, largest: number, largestRadius: number): number {
  if (largest <= 0 || count <= 0) return 0;
  return largestRadius * Math.sqrt(count / largest);
}

export function niceValue(value: number): number {
  if (value <= 1) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [...NICE_STEPS].reverse().find((candidate) => candidate * power <= value) ?? 1;
  return step * power;
}

export function circleKeys(largest: number): number[] {
  if (largest < 1) return [];
  return [...new Set([niceValue(largest / 6), niceValue(largest / 2), niceValue(largest)])].filter((value) => value <= largest);
}

export const NAMED_TIES = 3;

function names(states: readonly StateCount[]): string {
  if (states.length > NAMED_TIES) return "any other state";
  if (states.length <= 1) return states[0]?.name ?? "";
  return `${states
    .slice(0, -1)
    .map((state) => state.name)
    .join(", ")} or ${states[states.length - 1].name}`;
}

function andNames(states: readonly StateCount[]): string {
  if (states.length > NAMED_TIES) return `${numberWord(states.length)} states`;
  return names(states).replace(/ or ([^,]*)$/, " and $1");
}

function comparison(top: number, second: readonly StateCount[]): string {
  const ratio = top / second[0].count;
  if (ratio > 2) return `, more than twice as many as ${names(second)}`;
  if (ratio === 2) return `, twice as many as ${names(second)}`;
  if (ratio >= 1.7) return `, nearly twice as many as ${names(second)}`;
  const verb = second.length === 1 ? "follows" : "follow";
  return `; ${andNames(second)} ${verb} with ${second[0].count}${second.length > 1 ? " each" : ""}`;
}

export function rankFinding(states: readonly StateCount[]): string | null {
  const [top] = states;
  if (!top) return null;
  const leaders = states.filter((state) => state.count === top.count);
  if (leaders.length > 1) {
    const named = andNames(leaders);
    return `${named.charAt(0).toUpperCase()}${named.slice(1)} practise the most crafts, ${top.count} each.`;
  }
  const rest = states.filter((state) => state.count < top.count);
  const second = rest.filter((state) => state.count === rest[0]?.count);
  const head = `${top.name} practises the most crafts, ${top.count}`;
  return second.length > 0 ? `${head}${comparison(top.count, second)}.` : `${head}.`;
}

export function rankDek(allIndia: number): string {
  const tail = allIndia > 0 ? `, and ${allIndia} more ${allIndia === 1 ? "belongs" : "belong"} to all of India` : "";
  return `Circles are drawn to scale. A craft practised in several states counts in each${tail}.`;
}

export function mapDescription(states: readonly StateCount[]): string {
  const top = states.slice(0, 3).map((state) => `${state.name} ${state.count}`);
  const named = top.length ? ` The most: ${top.join(", ")}.` : "";
  return `One circle per state, its area drawn to scale by the number of crafts practised there.${named} India’s neighbours are drawn around it, and the Great and Little Rann of Kachchh are salt flat.`;
}

export function allStatesLabel(count: number): string {
  return `All ${count} ${count === 1 ? "state or union territory" : "states and union territories"}`;
}

export function stateAnchor(name: string): string {
  return `${STATE_KEY_PREFIX}${fold(name).replace(/ /g, "-")}`;
}

export function stateListDek(states: number, allIndia: number): string {
  const head = `Every craft is listed under each of the ${states} ${states === 1 ? "state or union territory" : "states and union territories"} where it is practised, monographs first.`;
  if (allIndia === 0) return head;
  return `${head} ${allIndia} ${allIndia === 1 ? "craft belongs" : "crafts belong"} to all of India.`;
}

export function allCraftsLabel(count: number): string {
  return `All ${count.toLocaleString("en-IN")} ${count === 1 ? "craft" : "crafts"} in the atlas`;
}

function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

function candidates(ask: LabelAsk): { spot: LabelSpot; box: Box }[] {
  const gap = 3;
  const top = ask.y - ask.height / 2;
  return [
    { spot: { key: ask.key, x: ask.x + ask.r + gap, y: ask.y, anchor: "start" }, box: { x: ask.x + ask.r + gap, y: top, width: ask.width, height: ask.height } },
    { spot: { key: ask.key, x: ask.x - ask.r - gap, y: ask.y, anchor: "end" }, box: { x: ask.x - ask.r - gap - ask.width, y: top, width: ask.width, height: ask.height } },
    { spot: { key: ask.key, x: ask.x, y: ask.y - ask.r - gap - ask.height / 2, anchor: "middle" }, box: { x: ask.x - ask.width / 2, y: ask.y - ask.r - gap - ask.height, width: ask.width, height: ask.height } }
  ];
}

function inside(box: Box, frame: Box): boolean {
  return box.x >= frame.x && box.y >= frame.y && box.x + box.width <= frame.x + frame.width && box.y + box.height <= frame.y + frame.height;
}

export function placeLabels(asks: readonly LabelAsk[], frame: Box, blocked: readonly Box[] = []): LabelSpot[] {
  const taken: Box[] = [...blocked];
  const placed: LabelSpot[] = [];
  for (const ask of asks) {
    const found = candidates(ask).find(({ box }) => inside(box, frame) && !taken.some((other) => overlaps(box, other)));
    if (!found) continue;
    taken.push(found.box);
    placed.push(found.spot);
  }
  return placed;
}
