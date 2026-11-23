import { decodeRings, type NeighbourFile } from "@/components/map/basemap";
import type { Ring } from "@/components/map/indiaGeometry";
import neighbours from "@/public/boundaries/neighbours.json";

export function neighbourRings(file: Pick<NeighbourFile, "countries">): Ring[] {
  return file.countries.flatMap((country) => decodeRings(country.rings));
}

export const NEIGHBOUR_RINGS: readonly Ring[] = neighbourRings(neighbours);
