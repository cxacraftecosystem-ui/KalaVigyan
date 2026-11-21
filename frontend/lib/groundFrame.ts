import type { GroundFrame, Point } from "@/lib/placeGround";

export const FRAME_WIDTH = 640;
export const EARTH_RADIUS_KM = 6371.0088;
export const KM_PER_DEGREE = (Math.PI * EARTH_RADIUS_KM) / 180;

export type FrameView = { width: number; height: number; scale: number; squeeze: number; west: number; north: number };
export type Box = { west: number; south: number; east: number; north: number };

export function frameView(frame: Box, width: number = FRAME_WIDTH): FrameView {
  const squeeze = Math.cos((((frame.south + frame.north) / 2) * Math.PI) / 180);
  const scale = width / ((frame.east - frame.west) * squeeze);
  return { width, height: (frame.north - frame.south) * scale, scale, squeeze, west: frame.west, north: frame.north };
}

export function placed(view: FrameView, [longitude, latitude]: readonly [number, number]): { x: number; y: number } {
  return { x: (longitude - view.west) * view.squeeze * view.scale, y: (view.north - latitude) * view.scale };
}

function step(view: FrameView, point: readonly [number, number], first: boolean): string {
  const { x, y } = placed(view, point);
  return `${first ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
}

export function linePath(view: FrameView, points: readonly (readonly [number, number])[]): string {
  return points.map((point, at) => step(view, point, at === 0)).join("");
}

export function ringsPath(view: FrameView, rings: readonly (readonly (readonly [number, number])[])[]): string {
  return rings
    .filter((ring) => ring.length >= 3)
    .map((ring) => `${linePath(view, ring)}Z`)
    .join("");
}

export function kmUnits(view: FrameView, distanceKm: number): number {
  return (distanceKm / KM_PER_DEGREE) * view.scale;
}

export function ringBox(ring: readonly (readonly [number, number])[]): Box {
  const longitudes = ring.map((point) => point[0]);
  const latitudes = ring.map((point) => point[1]);
  return { west: Math.min(...longitudes), south: Math.min(...latitudes), east: Math.max(...longitudes), north: Math.max(...latitudes) };
}

export function overlaps(a: Box, b: Box): boolean {
  return a.west <= b.east && a.east >= b.west && a.south <= b.north && a.north >= b.south;
}

export function ringsIn(frame: Box, rings: readonly (readonly (readonly [number, number])[])[]): (readonly (readonly [number, number])[])[] {
  return rings.filter((ring) => ring.length >= 3 && overlaps(ringBox(ring), frame));
}

export function inFrame(frame: GroundFrame | Box, point: Point): boolean {
  return point[0] >= frame.west && point[0] <= frame.east && point[1] >= frame.south && point[1] <= frame.north;
}
