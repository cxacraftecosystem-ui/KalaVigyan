import { apiFetch } from "@/lib/api";
import type { CatalogueConcept, CatalogueCraft, CraftCatalogue } from "@/lib/craftCatalogueContract";
import type { ConceptCraft } from "@/lib/explainerLearning";
import { TERM_KEY } from "@/lib/explainerBlockBase";
import { parseShape } from "@/lib/shape";
import { SHARED_CONCEPT_PATH, sharedConceptShape, type SharedConcept } from "@/lib/sharedScienceContract";

export const RESULT_ROWS_SHOWN = 4;
export const CONCEPT_GROUPS_SHOWN = 3;

export type MarkedPart = { text: string; mark: boolean };
export type ConceptRow = { craft: CatalogueCraft; cited: ConceptCraft | null };

export function isTermKey(key: string): boolean {
  try {
    TERM_KEY.parse(key, "key");
    return true;
  } catch {
    return false;
  }
}

export async function fetchSharedConcept(key: string): Promise<SharedConcept> {
  return parseShape(sharedConceptShape, await apiFetch<unknown>(SHARED_CONCEPT_PATH(key)));
}

function escaped(term: string): string {
  return term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/[\s-]+/g, "[\\s-]+");
}

export function markTerms(text: string, terms: readonly string[]): MarkedPart[] {
  const wanted = [...new Set(terms.map((term) => term.trim()).filter((term) => term.length >= 2))].sort((a, b) => b.length - a.length);
  if (!wanted.length) return [{ text, mark: false }];
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}])(${wanted.map(escaped).join("|")})`, "giu");
  const parts: MarkedPart[] = [];
  let from = 0;
  for (const found of text.matchAll(pattern)) {
    const at = found.index ?? 0;
    if (at > from) parts.push({ text: text.slice(from, at), mark: false });
    parts.push({ text: found[0], mark: true });
    from = at + found[0].length;
  }
  if (from < text.length) parts.push({ text: text.slice(from), mark: false });
  return parts;
}

export function conceptRows(crafts: readonly CatalogueCraft[], shared: SharedConcept | null): ConceptRow[] {
  const cited = new Map((shared?.node.crafts ?? []).map((entry) => [entry.craft.slug, entry]));
  return crafts
    .map((craft) => ({ craft, cited: cited.get(craft.slug) ?? null }))
    .sort((a, b) => Number(b.cited !== null) - Number(a.cited !== null));
}

export function conceptDek(rows: readonly ConceptRow[], named = 0): string {
  const cited = Math.max(named, rows.filter((row) => row.cited !== null).length);
  if (cited > 0) return `Named in the cited sentences of ${cited} ${cited === 1 ? "craft" : "crafts"}.`;
  return `Linked to ${rows.length} ${rows.length === 1 ? "craft" : "crafts"} on the craft list.`;
}

export function craftMeta(catalogue: CraftCatalogue, craft: CatalogueCraft): string {
  const family = catalogue.categories.find((category) => category.id === craft.categoryId);
  const state = craft.stateOfPractice[0] ?? craft.stateOfOrigin[0] ?? null;
  return [state, family ? (family.label ?? family.name) : craft.familyLabel].filter(Boolean).join(" · ");
}

export function conceptTerms(concept: CatalogueConcept): string[] {
  return [concept.label, ...concept.names];
}

export function searchStatus(query: string, concepts: number, crafts: number, firstConcept: string | null): string {
  if (!query.trim()) return "";
  if (firstConcept && concepts > 0) return `${firstConcept}: ${crafts} ${crafts === 1 ? "craft" : "crafts"}.`;
  if (crafts > 0) return `${crafts} ${crafts === 1 ? "craft matches" : "crafts match"}.`;
  return `Nothing matches “${query.trim()}”.`;
}
