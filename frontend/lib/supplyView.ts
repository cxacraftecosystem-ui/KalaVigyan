import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import type { SupplyLink, SupplyMapBlock } from "@/lib/explainerPlace";
import { joinedBy, namesText, onceEach, sentenceKey, sentenceWords } from "@/lib/sentenceGroups";

export type LongitudeLatitudeBox = { minLongitude: number; maxLongitude: number; minLatitude: number; maxLatitude: number };
export type SupplyOrigin = { key: string; origin: string; wikidataId: string | null; pin: number | null };
export type SupplyGroup = { key: string; names: string[]; heading: string; origins: SupplyOrigin[]; sentences: ExplainerSentence[] };
export type SupplyPin = { key: string; origin: string; materials: string; latitude: number; longitude: number; pin: number; byDistrict: boolean };
export type SupplyLayout = { groups: SupplyGroup[]; pins: SupplyPin[] };

type PlacedLink = SupplyLink & { latitude: number; longitude: number };

export function wikidataUrl(id: string): string {
  return `https://www.wikidata.org/wiki/${encodeURIComponent(id)}`;
}

function materialKey(link: SupplyLink): string {
  return link.material.toLocaleLowerCase("en");
}

function originKey(link: SupplyLink): string {
  return link.origin.toLocaleLowerCase("en");
}

export function byDistrict(link: SupplyLink): boolean {
  return link.districtLgd !== undefined && link.districtLgd !== null;
}

function inBox(link: SupplyLink, box: LongitudeLatitudeBox): link is PlacedLink {
  const { latitude, longitude, wikidataId } = link;
  if (latitude === null || longitude === null || (wikidataId === null && !byDistrict(link))) return false;
  return longitude >= box.minLongitude && longitude <= box.maxLongitude && latitude >= box.minLatitude && latitude <= box.maxLatitude;
}

function firstOf(links: readonly SupplyLink[], keyOf: (link: SupplyLink) => string): SupplyLink[] {
  const kept = new Map<string, SupplyLink>();
  for (const link of links) if (!kept.has(keyOf(link))) kept.set(keyOf(link), link);
  return [...kept.values()];
}

export function materialRows(links: readonly SupplyLink[]): SupplyLink[][] {
  return joinedBy(links, (link) => [`material:${materialKey(link)}`, `sentence:${sentenceKey(link.sentence)}`]);
}

function placedPins(links: readonly SupplyLink[], box: LongitudeLatitudeBox, words: ReadonlySet<string>): SupplyPin[] {
  const placed = new Map<string, { link: PlacedLink; names: string[] }>();
  for (const link of links) {
    if (!inBox(link, box)) continue;
    const pin = placed.get(originKey(link)) ?? { link, names: [] };
    pin.names.push(link.material);
    placed.set(originKey(link), pin);
  }
  return [...placed.entries()].map(([key, { link, names }], index) => ({
    key,
    origin: link.origin,
    materials: namesText(names, words),
    latitude: link.latitude,
    longitude: link.longitude,
    pin: index + 1,
    byDistrict: byDistrict(link)
  }));
}

function supplyGroup(links: readonly SupplyLink[], pins: ReadonlyMap<string, number>, words: ReadonlySet<string>): SupplyGroup {
  const names = firstOf(links, materialKey).map((link) => link.material);
  const origins = firstOf(links, originKey).map((first) => {
    const key = originKey(first);
    const wikidataId = links.find((link) => originKey(link) === key && link.wikidataId !== null)?.wikidataId ?? null;
    return { key, origin: first.origin, wikidataId, pin: pins.get(key) ?? null };
  });
  const key = names.map((name) => name.toLocaleLowerCase("en")).join("+");
  return { key, names, heading: namesText(names, words), origins, sentences: onceEach(links.map((link) => link.sentence)) };
}

export function supplyLayout(block: SupplyMapBlock, box: LongitudeLatitudeBox): SupplyLayout {
  const words = sentenceWords(block.links.map((link) => link.sentence));
  const rows = materialRows(block.links);
  const pins = placedPins(rows.flat(), box, words);
  const numbers = new Map(pins.map((pin) => [pin.key, pin.pin]));
  return { groups: rows.map((links) => supplyGroup(links, numbers, words)), pins };
}
