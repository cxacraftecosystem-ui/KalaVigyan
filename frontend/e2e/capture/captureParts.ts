export const RAIL_STOPS = ["first", "middle", "last"] as const;
export const MAX_SLICES = 6;

export type RailStop = (typeof RAIL_STOPS)[number];

export function sliceTops(height: number, slice: number, most: number = MAX_SLICES): number[] {
  const tops: number[] = [];
  for (let top = 0; top < Math.max(height, 1) && tops.length < most; top += slice) tops.push(top);
  return tops;
}

export function railStops(links: readonly string[]): Partial<Record<RailStop, string>> {
  if (!links.length) return {};
  return { first: links[0], middle: links[Math.floor(links.length / 2)], last: links[links.length - 1] };
}

export function partFileName(stem: string, selector: string, at: number): string {
  const key = selector.replace(/[^A-Za-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
  return `${stem}-part-${key}-${at + 1}.png`;
}
