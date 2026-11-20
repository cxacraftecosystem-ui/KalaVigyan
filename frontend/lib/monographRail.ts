export const RAIL_FADE_PX = 48;
export const RAIL_STEP_MIN_PX = 120;

export type RailEnds = { over: boolean; back: number; on: number };
export type RailBox = { left: number; right: number; width: number };
export type RailArrow = "back" | "on";

export function railEnds(scrollLeft: number, scrollWidth: number, clientWidth: number, fade: number = RAIL_FADE_PX): RailEnds {
  const max = Math.max(0, scrollWidth - clientWidth);
  if (max <= 1) return { over: false, back: 0, on: 0 };
  const at = Math.min(max, Math.abs(scrollLeft));
  return { over: true, back: Math.min(fade, at), on: Math.min(fade, max - at) };
}

export function railArrowShown(ends: RailEnds, arrow: RailArrow): boolean {
  return ends.over && ends[arrow] >= 1;
}

export function railStep(clientWidth: number, fade: number = RAIL_FADE_PX): number {
  return Math.max(RAIL_STEP_MIN_PX, clientWidth - 2 * fade);
}

export function railMask(ends: RailEnds, rtl = false): string {
  const angle = rtl ? 270 : 90;
  return `linear-gradient(${angle}deg, transparent, black ${ends.back}px, black calc(100% - ${ends.on}px), transparent)`;
}

export function railTarget(list: RailBox, link: RailBox, scrollLeft: number, fade: number = RAIL_FADE_PX): number | null {
  if (link.left >= list.left + fade && link.right <= list.right - fade) return null;
  return scrollLeft + (link.left - list.left) - (list.width - link.width) / 2;
}
