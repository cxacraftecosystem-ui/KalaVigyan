import { INDIA_BOUNDS } from "@/components/map/indiaBounds";
import { indiaRings, type Polygon } from "@/components/map/indiaGeometry";

const VIEW_WIDTH = 1000;

const PADDING = 24;

export type FrameBounds = { minLongitude: number; maxLongitude: number; minLatitude: number; maxLatitude: number };
export type ViewBox = { width: number; height: number };
export type Projected = { x: number; y: number };
export type FrameProjection = { viewBox: ViewBox; project: (longitude: number, latitude: number) => Projected };

export function frameProjection(bounds: FrameBounds, width: number = VIEW_WIDTH, padding: number = PADDING): FrameProjection {
  const longitudeScale = Math.cos((((bounds.minLatitude + bounds.maxLatitude) / 2) * Math.PI) / 180);
  const spanX = (bounds.maxLongitude - bounds.minLongitude) * longitudeScale;
  const spanY = bounds.maxLatitude - bounds.minLatitude;
  const unitsPerDegree = (width - padding * 2) / spanX;
  return {
    viewBox: { width, height: spanY * unitsPerDegree + padding * 2 },
    project: (longitude, latitude) => ({
      x: padding + (longitude - bounds.minLongitude) * longitudeScale * unitsPerDegree,
      y: padding + (bounds.maxLatitude - latitude) * unitsPerDegree
    })
  };
}

const INDIA_FRAME = frameProjection(INDIA_BOUNDS);

export const VIEW_BOX = INDIA_FRAME.viewBox;

export function project(longitude: number, latitude: number): Projected {
  return INDIA_FRAME.project(longitude, latitude);
}

export function bordersToPath(lines: Array<Array<[number, number]>>): string {
  const parts: string[] = [];
  for (const line of lines) {
    let out = "";
    let previousX = Number.NaN;
    let previousY = Number.NaN;
    let emitted = 0;
    for (const [longitude, latitude] of line) {
      const { x, y } = project(longitude, latitude);
      const rx = Math.round(x * 10) / 10;
      const ry = Math.round(y * 10) / 10;
      if (emitted > 0 && rx === previousX && ry === previousY) continue;
      out += `${emitted === 0 ? "M" : "L"}${rx} ${ry}`;
      previousX = rx;
      previousY = ry;
      emitted += 1;
    }
    if (emitted >= 2) parts.push(out);
  }
  return parts.join("");
}

export function outlinePath(frame: FrameProjection): string {
  const parts: string[] = [];
  for (const polygon of indiaRings() as Polygon[]) {
    for (const ring of polygon) {
      let command = "M";
      for (const [longitude, latitude] of ring) {
        const { x, y } = frame.project(longitude, latitude);
        parts.push(`${command}${x.toFixed(1)} ${y.toFixed(1)}`);
        command = "L";
      }
      parts.push("Z");
    }
  }
  return parts.join("");
}

let outline: string | null = null;

export function indiaOutlinePath(): string {
  outline ??= outlinePath(INDIA_FRAME);
  return outline;
}
