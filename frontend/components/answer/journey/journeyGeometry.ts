import { project, VIEW_BOX } from "@/components/map/projection";
import type { DistrictShape } from "@/components/map/shapeGeometry";

export const MAX_ZOOM = 3;
export const ZOOM_ROOM = 2.5;
export const EDGE_MARGIN = 10;
export const POST_FONT = 13;
export const POST_HEIGHT = 26;

export type ZoomFrame = { scale: number; x: string; y: string };
export type EdgePost = { left: number; top: number; width: number; height: number; angle: number; middle: number };

const AT_REST: ZoomFrame = { scale: 1, x: "0%", y: "0%" };

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

function shift(centre: number, size: number, scale: number): string {
  const share = (centre / size) * 100;
  return `${clamp(50 - share * scale, 100 - 100 * scale, 0).toFixed(2)}%`;
}

export function districtFrame(shape: DistrictShape | null): ZoomFrame {
  const points = (shape?.rings ?? []).flat().map(([longitude, latitude]) => project(longitude, latitude));
  if (points.length === 0) return AT_REST;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const width = Math.max(maxX - minX, 1);
  const height = Math.max(maxY - minY, 1);
  const scale = clamp(Math.min(VIEW_BOX.width / (width * ZOOM_ROOM), VIEW_BOX.height / (height * ZOOM_ROOM)), 1, MAX_ZOOM);
  return { scale: Number(scale.toFixed(2)), x: shift((minX + maxX) / 2, VIEW_BOX.width, scale), y: shift((minY + maxY) / 2, VIEW_BOX.height, scale) };
}

export function inFrame(longitude: number, latitude: number): { x: number; y: number } {
  const { x, y } = project(longitude, latitude);
  return { x: clamp(x, EDGE_MARGIN, VIEW_BOX.width - EDGE_MARGIN), y: clamp(y, EDGE_MARGIN, VIEW_BOX.height - EDGE_MARGIN) };
}

export function edgePost(longitude: number, latitude: number, text: string, scale = 1): EdgePost {
  const anchor = project(longitude, latitude);
  const { x, y } = inFrame(longitude, latitude);
  const angle = Math.round((Math.atan2(anchor.y - y, anchor.x - x) * 180) / Math.PI);
  const height = POST_HEIGHT * scale;
  const width = Math.round((text.length * POST_FONT * 0.58 + 34) * scale);
  const left = clamp(x >= VIEW_BOX.width / 2 ? x - width : x, EDGE_MARGIN, VIEW_BOX.width - width - EDGE_MARGIN);
  const top = clamp(y - height / 2, EDGE_MARGIN, VIEW_BOX.height - height - EDGE_MARGIN);
  return { left, top, width, height, angle, middle: top + height / 2 };
}
