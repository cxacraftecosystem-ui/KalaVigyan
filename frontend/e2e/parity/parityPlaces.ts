import type { APIRequestContext } from "@playwright/test";

import { apiOrigin, readApi, type SubjectPage } from "./parityBorrowed";

export type PlaceBorrow = { path: string; slug: string; subject: SubjectPage["subject"]; label: string; district: number };
export type PlaceFacts = { located: ReadonlyMap<number, readonly string[]>; stateOf: ReadonlyMap<number, string>; practice: ReadonlyMap<string, readonly string[]>; members: ReadonlyMap<string, readonly string[]> };

type MapPoint = { key?: string; crafts?: { slug?: string }[] };
type RegionPlace = { districtLgd?: number | null; stateName?: string | null };
type CatalogueCraft = { slug?: string; stateOfPractice?: string[]; categoryId?: string; subCategoryId?: string; isCatchAll?: boolean };
type Catalogue = { crafts?: CatalogueCraft[]; categories?: { id?: string; slug?: string }[] };

const DISTRICT_SUBJECT = /^place:lgd:(\d+)$/;
const DISTRICT_KEY = /^district-(\d+)$/;
const ALL_INDIA = "All India";
const MAP_PATH = "/api/map/crafts";
const CATALOGUE_PATH = "/api/crafts/catalogue";

export function placeBorrows(pages: readonly SubjectPage[]): PlaceBorrow[] {
  return pages.flatMap((page) =>
    (page.authored ? [] : page.components)
      .filter((component) => !component.label.toLowerCase().startsWith(`${page.slug.toLowerCase()}/`))
      .flatMap((component) =>
        (component.subjects ?? []).flatMap((subject) => {
          const found = DISTRICT_SUBJECT.exec(subject);
          return found ? [{ path: page.path, slug: page.slug, subject: page.subject, label: component.label, district: Number(found[1]) }] : [];
        })
      )
  );
}

function practisedIn(states: readonly string[], state: string | undefined): boolean {
  const named = states.filter((name) => name !== ALL_INDIA);
  return named.length === 0 || (state !== undefined && named.includes(state));
}

export function strayBorrows(borrows: readonly PlaceBorrow[], facts: PlaceFacts): PlaceBorrow[] {
  return borrows.filter((borrow) => {
    const crafts = facts.members.get(borrow.path) ?? [borrow.slug];
    const located = facts.located.get(borrow.district) ?? [];
    return !crafts.some((craft) => located.includes(craft) && practisedIn(facts.practice.get(craft) ?? [], facts.stateOf.get(borrow.district)));
  });
}

export function pageMembers(page: Pick<PlaceBorrow, "slug" | "subject">, catalogue: Catalogue): string[] {
  const crafts = catalogue.crafts ?? [];
  if (page.subject === "category") {
    const category = (catalogue.categories ?? []).find((found) => found.slug === page.slug);
    return crafts.filter((craft) => category && craft.categoryId === category.id).flatMap((craft) => (craft.slug ? [craft.slug] : []));
  }
  const own = crafts.find((craft) => craft.slug === page.slug);
  if (page.subject !== "family" || !own?.subCategoryId) return [page.slug];
  return crafts.filter((craft) => craft.subCategoryId === own.subCategoryId).flatMap((craft) => (craft.slug ? [craft.slug] : []));
}

export function locatedCrafts(points: readonly MapPoint[]): Map<number, string[]> {
  const located = new Map<number, string[]>();
  for (const point of points) {
    const found = DISTRICT_KEY.exec(point.key ?? "");
    if (found) located.set(Number(found[1]), (point.crafts ?? []).flatMap((craft) => (craft.slug ? [craft.slug] : [])));
  }
  return located;
}

async function districtStates(request: APIRequestContext, origin: string, located: Map<number, string[]>, districts: readonly number[]): Promise<Map<number, string>> {
  const states = new Map<number, string>();
  for (const district of districts) {
    const craft = located.get(district)?.[0];
    if (!craft) continue;
    const region = ((await readApi(request, `${origin}/api/crafts/${encodeURIComponent(craft)}/region`)) ?? {}) as { places?: RegionPlace[] };
    const place = (region.places ?? []).find((found) => found.districtLgd === district);
    if (place?.stateName) states.set(district, place.stateName);
  }
  return states;
}

export async function placeFacts(request: APIRequestContext, site: string, borrows: readonly PlaceBorrow[]): Promise<PlaceFacts> {
  const origin = apiOrigin(site);
  const located = locatedCrafts(((await readApi(request, `${origin}${MAP_PATH}`)) ?? []) as MapPoint[]);
  const catalogue = ((await readApi(request, `${origin}${CATALOGUE_PATH}`)) ?? {}) as Catalogue;
  const practice = new Map((catalogue.crafts ?? []).flatMap((craft) => (craft.slug ? [[craft.slug, craft.stateOfPractice ?? []] as [string, string[]]] : [])));
  const members = new Map(borrows.map((borrow) => [borrow.path, pageMembers(borrow, catalogue)]));
  const stateOf = await districtStates(request, origin, located, [...new Set(borrows.map((borrow) => borrow.district))]);
  return { located, stateOf, practice, members };
}
