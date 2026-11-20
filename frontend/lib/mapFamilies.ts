import { isMonograph } from "@/lib/atlasCollection";
import type { CraftCatalogue, FamilyPalette } from "@/lib/craftCatalogueContract";
import type { CraftMapPoint } from "@/lib/types";

export const COLOURED_FAMILIES = 3;
export const OTHER_FAMILY = "other";

const FAMILY_TOKEN: Record<FamilyPalette, string> = {
  indigo: "textiles",
  bronze: "metal",
  teak: "wood",
  paper: "paper",
  terracotta: "clay",
  sandstone: "stone",
  hide: "leather",
  cane: "fibre",
  lac: OTHER_FAMILY
};

export type MapFamily = { id: string; name: string; token: string; colour: string };
export type PlaceCraft = { slug: string; name: string; monograph: boolean };
export type PlaceMarker = { key: string; name: string; longitude: number; latitude: number; total: number; family: MapFamily | null; href: string; crafts: PlaceCraft[] };

export function familyColour(token: string): string {
  return `var(--fam-${token})`;
}

function familyOfSlug(catalogue: CraftCatalogue): Map<string, MapFamily> {
  const families = new Map(
    catalogue.categories.map((category) => {
      const token = category.palette ? FAMILY_TOKEN[category.palette] : OTHER_FAMILY;
      return [category.id, { id: category.id, name: category.label ?? category.name, token, colour: familyColour(token) }] as const;
    })
  );
  const bySlug = new Map<string, MapFamily>();
  for (const craft of catalogue.crafts) {
    const family = craft.categoryId ? families.get(craft.categoryId) : undefined;
    if (family) bySlug.set(craft.slug, family);
  }
  return bySlug;
}

function pointFamily(point: CraftMapPoint, bySlug: Map<string, MapFamily>): MapFamily | null {
  const found = new Set(point.crafts.map((craft) => bySlug.get(craft.slug)?.id ?? null));
  if (found.size !== 1) return null;
  return bySlug.get(point.crafts[0].slug) ?? null;
}

export function placeHref(point: CraftMapPoint): string {
  return point.crafts.length === 1 ? `/crafts/${encodeURIComponent(point.crafts[0].slug)}` : `/crafts?q=${encodeURIComponent(point.name)}`;
}

function monographSlugs(catalogue: CraftCatalogue | null): Set<string> {
  return new Set((catalogue?.crafts ?? []).filter(isMonograph).map((craft) => craft.slug));
}

export function placeMarkers(points: readonly CraftMapPoint[], catalogue: CraftCatalogue | null): PlaceMarker[] {
  const bySlug = catalogue ? familyOfSlug(catalogue) : new Map<string, MapFamily>();
  const documented = monographSlugs(catalogue);
  const located = points.filter((point) => !point.key.startsWith("state-"));
  const tally = new Map<string, number>();
  for (const point of located) {
    const family = pointFamily(point, bySlug);
    if (family && family.token !== OTHER_FAMILY) tally.set(family.id, (tally.get(family.id) ?? 0) + 1);
  }
  const coloured = new Set([...tally].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, COLOURED_FAMILIES).map(([id]) => id));
  return located.map((point) => {
    const family = pointFamily(point, bySlug);
    return {
      key: point.key,
      name: point.name,
      longitude: point.longitude,
      latitude: point.latitude,
      total: point.total,
      family: family && coloured.has(family.id) ? family : null,
      href: placeHref(point),
      crafts: point.crafts.map((craft) => ({ slug: craft.slug, name: craft.name, monograph: documented.has(craft.slug) }))
    };
  });
}

export function markerFamilies(markers: readonly PlaceMarker[]): MapFamily[] {
  const seen = new Map<string, MapFamily>();
  for (const marker of markers) if (marker.family && !seen.has(marker.family.id)) seen.set(marker.family.id, marker.family);
  return [...seen.values()];
}
