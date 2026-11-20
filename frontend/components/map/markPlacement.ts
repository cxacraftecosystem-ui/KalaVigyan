import type { CSSProperties } from "react";

import type { MapBox } from "@/components/map/basemap";

export type MarkCraft = { slug: string; name: string; monograph: boolean };
export type MarkMore = { href: string; label: string };
export type MapMark = { key: string; name: string; kind: string; x: number; y: number; r: number; count: number; crafts: readonly MarkCraft[]; more: MarkMore | null };

export const MARK_MIN_PX = 24;
export const CARD_CRAFTS = 3;
export const CARD_WIDTH_PX = 240;
const CARD_GAP_PX = 10;
const ABOVE_FROM = 0.42;

function percent(value: number, start: number, span: number): string {
  return `${(((value - start) / span) * 100).toFixed(3)}%`;
}

export function markBox(mark: Pick<MapMark, "x" | "y" | "r">, frame: MapBox): CSSProperties {
  const diameter = ((mark.r * 2) / frame.width) * 100;
  return {
    left: percent(mark.x, frame.x, frame.width),
    top: percent(mark.y, frame.y, frame.height),
    width: `max(${MARK_MIN_PX}px, ${diameter.toFixed(3)}%)`
  };
}

export function cardAbove(mark: Pick<MapMark, "y">, frame: MapBox): boolean {
  return (mark.y - frame.y) / frame.height > ABOVE_FROM;
}

export function cardPlacement(mark: Pick<MapMark, "x" | "y" | "r">, scene: { frame: MapBox; scale: number }): CSSProperties {
  const { frame } = scene;
  const reach = Math.max(mark.r, (MARK_MIN_PX / 2) * scene.scale);
  const across = `clamp(0px, calc(${percent(mark.x, frame.x, frame.width)} - ${CARD_WIDTH_PX / 2}px), calc(100% - ${CARD_WIDTH_PX}px))`;
  if (cardAbove(mark, frame)) {
    const fromBottom = percent(frame.y + frame.height, mark.y - reach, frame.height);
    return { left: across, bottom: `calc(${fromBottom} + ${CARD_GAP_PX}px)` };
  }
  return { left: across, top: `calc(${percent(mark.y + reach, frame.y, frame.height)} + ${CARD_GAP_PX}px)` };
}

export function countLine(count: number): string {
  return `${count.toLocaleString("en-IN")} ${count === 1 ? "craft" : "crafts"}`;
}

export function markLabel(mark: Pick<MapMark, "name" | "count">): string {
  return `${mark.name}, ${countLine(mark.count)}`;
}

export function firstCrafts(mark: Pick<MapMark, "crafts" | "count">): { names: string[]; rest: number } {
  const names = mark.crafts.slice(0, CARD_CRAFTS).map((craft) => craft.name);
  return { names, rest: Math.max(0, mark.count - names.length) };
}

export function steppedKey(keys: readonly string[], current: string | null, key: string): string | null {
  if (keys.length === 0) return null;
  const at = current === null ? -1 : keys.indexOf(current);
  if (key === "Home") return keys[0];
  if (key === "End") return keys[keys.length - 1];
  if (key === "ArrowRight" || key === "ArrowDown") return keys[(at + 1) % keys.length];
  if (key === "ArrowLeft" || key === "ArrowUp") return keys[(at - 1 + keys.length) % keys.length];
  return null;
}
