import { INDIA_BOUNDS } from "@/components/map/indiaBounds";
import { frameProjection, type FrameBounds, type FrameProjection } from "@/components/map/projection";

export const INSET_WIDTH = 640;
export const INSET_PADDING = 28;
export const INSET_MARGIN_DEGREES = 4;
export const INSET_LATITUDE_LIMIT = 80;
export const INSET_PIN_RADIUS = 11;
export const INSET_NAME_ROOM = 120;

export type GeoPoint = { longitude: number; latitude: number };

export function abroadBounds(points: readonly GeoPoint[]): FrameBounds {
  const longitudes = [INDIA_BOUNDS.minLongitude, INDIA_BOUNDS.maxLongitude, ...points.map((point) => point.longitude)];
  const latitudes = [INDIA_BOUNDS.minLatitude, INDIA_BOUNDS.maxLatitude, ...points.map((point) => point.latitude)];
  return {
    minLongitude: Math.max(-180, Math.min(...longitudes) - INSET_MARGIN_DEGREES),
    maxLongitude: Math.min(180, Math.max(...longitudes) + INSET_MARGIN_DEGREES),
    minLatitude: Math.max(-INSET_LATITUDE_LIMIT, Math.min(...latitudes) - INSET_MARGIN_DEGREES),
    maxLatitude: Math.min(INSET_LATITUDE_LIMIT, Math.max(...latitudes) + INSET_MARGIN_DEGREES)
  };
}

export function abroadFrame(points: readonly GeoPoint[]): FrameProjection {
  return frameProjection(abroadBounds(points), INSET_WIDTH, INSET_PADDING);
}

export function namesFit(points: readonly { x: number; y: number }[], scale: number): boolean {
  const room = INSET_NAME_ROOM * scale;
  return points.every((point, at) => points.every((other, index) => index === at || Math.abs(point.y - other.y) > room / 3 || Math.abs(point.x - other.x) > room));
}
