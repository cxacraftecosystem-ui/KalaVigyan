import type { APIRequestContext } from "@playwright/test";

import { riverBasinOf } from "@/lib/riverTopology";
import { ShapeError } from "@/lib/shape";

export const KACHCHH_BASIN = 41063203;
export const RIVER_BASIN_ROUTE = (mainRiv: number) => `/api/rivers/${mainRiv}`;

export function basinCarriesDistricts(topology: unknown, mainRiv: number): boolean {
  try {
    const basin = riverBasinOf(topology, mainRiv);
    return basin.reaches.size > 0 && [...basin.reaches.values()].every((reach) => reach.districts !== null);
  } catch (error) {
    if (error instanceof ShapeError) return false;
    throw error;
  }
}

export async function riversLoadedOn(request: APIRequestContext, base: string): Promise<boolean> {
  const response = await request.get(new URL(RIVER_BASIN_ROUTE(KACHCHH_BASIN), base).href);
  if (!response.ok()) return false;
  return basinCarriesDistricts(await response.json(), KACHCHH_BASIN);
}
