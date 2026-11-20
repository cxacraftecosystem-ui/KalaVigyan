import { RANN_PATH, type MapBox } from "@/components/map/basemap";

export type { MapBox };

export const RANN_SALT_FLATS = RANN_PATH;

export function boardBox(box: MapBox): MapBox {
  return { ...box };
}
