import { decodePolyline, type Ring } from "@/components/map/indiaGeometry";
import { bordersToPath, project } from "@/components/map/projection";
import { RANN_RINGS } from "@/components/map/rannGeometry";

export type MapBox = { x: number; y: number; width: number; height: number };

export type NeighbourFile = {
  source: string;
  licence: string;
  datasets: { dataset: string; version: string; url: string; sha256: string }[];
  scale: number;
  bounds: [number, number, number, number];
  countries: { iso: string; name: string; rings: string[] }[];
  coast: string;
  borders: string;
};

export type Neighbour = { iso: string; name: string; d: string };
export type Basemap = { neighbours: Neighbour[]; coast: string; borders: string };

export const NEIGHBOURS_ASSET = "/boundaries/neighbours.json";
export const NATURAL_EARTH_CREDIT = "Neighbouring land and the Rann salt flats: Natural Earth.";
export const MAP_FRAME_DEGREES = { west: 65, east: 98.2, south: 5.6, north: 37.6 } as const;

export function mapFrame(): MapBox {
  const corner = project(MAP_FRAME_DEGREES.west, MAP_FRAME_DEGREES.north);
  const far = project(MAP_FRAME_DEGREES.east, MAP_FRAME_DEGREES.south);
  return { x: corner.x, y: corner.y, width: far.x - corner.x, height: far.y - corner.y };
}

export function viewBoxOf(box: MapBox): string {
  return [box.x, box.y, box.width, box.height].map((value) => value.toFixed(1)).join(" ");
}

export function decodeRings(encoded: readonly string[]): Ring[] {
  return encoded.map((ring) => decodePolyline(ring, false)[0]?.points ?? []).filter((points) => points.length >= 3);
}

export function ringsPath(rings: readonly Ring[]): string {
  const parts: string[] = [];
  for (const ring of rings) {
    ring.forEach(([longitude, latitude], index) => {
      const { x, y } = project(longitude, latitude);
      parts.push(`${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`);
    });
    parts.push("Z");
  }
  return parts.join("");
}

export function linesPath(payload: string): string {
  return bordersToPath(decodePolyline(payload, false).map((record) => record.points));
}

export const RANN_PATH = ringsPath(decodeRings(RANN_RINGS));

export function decodeBasemap(file: NeighbourFile): Basemap {
  return {
    neighbours: file.countries.map((country) => ({ iso: country.iso, name: country.name, d: ringsPath(decodeRings(country.rings)) })),
    coast: linesPath(file.coast),
    borders: linesPath(file.borders)
  };
}

let pending: Promise<Basemap> | null = null;

export function loadBasemap(): Promise<Basemap> {
  if (pending) return pending;
  pending = fetch(NEIGHBOURS_ASSET, { cache: "force-cache" })
    .then((response) => {
      if (!response.ok) throw new Error(`${NEIGHBOURS_ASSET} returned ${response.status}`);
      return response.json() as Promise<NeighbourFile>;
    })
    .then(decodeBasemap)
    .catch((cause: unknown) => {
      pending = null;
      throw cause;
    });
  return pending;
}
