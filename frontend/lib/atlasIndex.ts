import { isMonograph, plateOrder, readerCrafts } from "@/lib/atlasCollection";
import type { CatalogueConcept, CatalogueCraft, CraftCatalogue } from "@/lib/craftCatalogueContract";

export const ALL_INDIA = "All India";
export const PLACES_SHOWN = 12;
export const IDEAS_SHOWN = 9;
export const NEIGHBOURS_SHOWN = 4;

const NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

export type StateCount = { name: string; count: number };
export type StateCounts = { states: StateCount[]; allIndia: number };
export type StateCraftList = { name: string; crafts: CatalogueCraft[] };
export type StateCrafts = { states: StateCraftList[]; allIndia: CatalogueCraft[] };
export type ConceptNeighbour = { concept: CatalogueConcept; shared: number };

export function numberWord(value: number): string {
  return NUMBER_WORDS[value] ?? value.toLocaleString("en-IN");
}

function isAllIndia(state: string): boolean {
  return state.trim().toLowerCase() === ALL_INDIA.toLowerCase();
}

export function stateCrafts(catalogue: CraftCatalogue): StateCrafts {
  const lists = new Map<string, CatalogueCraft[]>();
  const allIndia: CatalogueCraft[] = [];
  for (const craft of readerCrafts(catalogue)) {
    const states = new Set(craft.stateOfPractice.map((state) => state.trim()).filter(Boolean));
    if ([...states].some(isAllIndia)) allIndia.push(craft);
    for (const state of states) if (!isAllIndia(state)) lists.set(state, [...(lists.get(state) ?? []), craft]);
  }
  const states = [...lists]
    .map(([name, crafts]) => ({ name, crafts: [...crafts].sort(plateOrder) }))
    .sort((a, b) => b.crafts.length - a.crafts.length || a.name.localeCompare(b.name, "en"));
  return { states, allIndia: allIndia.sort(plateOrder) };
}

export function listCounts(lists: StateCrafts): StateCounts {
  return { states: lists.states.map((state) => ({ name: state.name, count: state.crafts.length })), allIndia: lists.allIndia.length };
}

export function stateCounts(catalogue: CraftCatalogue): StateCounts {
  return listCounts(stateCrafts(catalogue));
}

export function monographCount(catalogue: CraftCatalogue): number {
  return readerCrafts(catalogue).filter(isMonograph).length;
}

export function familyCount(catalogue: CraftCatalogue): number {
  return catalogue.categories.filter((category) => category.readerCount > 0).length;
}

export function atlasDek(catalogue: CraftCatalogue): string {
  const crafts = catalogue.summary.crafts;
  const families = familyCount(catalogue);
  const states = catalogue.summary.states;
  const monographs = monographCount(catalogue);
  const head = `${crafts.toLocaleString("en-IN")} ${crafts === 1 ? "craft" : "crafts"} in ${numberWord(families)} ${families === 1 ? "family" : "families"}, from ${states} ${states === 1 ? "state or union territory" : "states and union territories"}.`;
  if (monographs === 0) return head;
  return `${head} ${monographs} ${monographs === 1 ? "is a monograph" : "are monographs"}, read in full.`;
}

export const SEARCH_ANCHOR = "atlas-search";

export function searchHref(query: string): string {
  return `/crafts?q=${encodeURIComponent(query)}#${SEARCH_ANCHOR}`;
}

export function allPlacesLabel(counts: StateCounts): string {
  const head = `Show all ${counts.states.length}`;
  return counts.allIndia > 0 ? `${head}, and ${counts.allIndia} ${counts.allIndia === 1 ? "craft" : "crafts"} of all India` : head;
}

export function conceptNeighbours(catalogue: CraftCatalogue, concept: CatalogueConcept, limit = NEIGHBOURS_SHOWN): ConceptNeighbour[] {
  const own = new Set(concept.craftSlugs);
  return catalogue.concepts
    .filter((other) => other.key !== concept.key)
    .map((other) => ({ concept: other, shared: other.craftSlugs.filter((slug) => own.has(slug)).length }))
    .filter((found) => found.shared > 0)
    .sort((a, b) => b.shared - a.shared || a.concept.label.localeCompare(b.concept.label, "en"))
    .slice(0, limit);
}

export function shownIdeas(catalogue: CraftCatalogue, limit = IDEAS_SHOWN): CatalogueConcept[] {
  return catalogue.concepts.slice(0, limit);
}

function conceptFamily(catalogue: CraftCatalogue, concept: CatalogueConcept): string | null {
  const first = catalogue.crafts.find((craft) => concept.craftSlugs.includes(craft.slug));
  return first?.categoryId ?? null;
}

export function tryQueries(catalogue: CraftCatalogue, limit = NEIGHBOURS_SHOWN): string[] {
  const families = new Set<string | null>();
  const picked: CatalogueConcept[] = [];
  for (const concept of catalogue.concepts) {
    const family = conceptFamily(catalogue, concept);
    if (families.has(family)) continue;
    families.add(family);
    picked.push(concept);
    if (picked.length === limit) break;
  }
  for (const concept of catalogue.concepts) {
    if (picked.length >= limit) break;
    if (!picked.includes(concept)) picked.push(concept);
  }
  return picked.map((concept) => concept.label.toLowerCase());
}
