import { atlasPlate, familyCrafts, familyShelves, sortedFamilies, type AtlasPlate, type AtlasShelf } from "@/lib/atlasCollection";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";

export function withPlateLead(shelf: AtlasShelf, pool: readonly AtlasPlate[]): AtlasShelf {
  if (shelf.lead || pool.length === 0) return shelf;
  const [lead, ...rest] = pool;
  const shown = shelf.plates.length;
  return { ...shelf, lead, plates: rest.slice(0, shown), more: rest.slice(shown) };
}

export function ledFamilyShelves(catalogue: CraftCatalogue): AtlasShelf[] {
  const families = sortedFamilies(catalogue);
  return familyShelves(catalogue).map((shelf, at) => {
    const family = families[at];
    if (shelf.lead || !family) return shelf;
    const pool = familyCrafts(catalogue, family).map((craft) => atlasPlate(family, craft));
    return { ...withPlateLead(shelf, pool), more: shelf.more };
  });
}

export function ledSubFamilyShelves(shelves: readonly AtlasShelf[]): AtlasShelf[] {
  return shelves.map((shelf) => withPlateLead(shelf, [...shelf.plates, ...shelf.more]));
}
