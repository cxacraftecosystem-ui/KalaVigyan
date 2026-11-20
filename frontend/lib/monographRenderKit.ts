import type { MonographContent, MonographDocument } from "@/lib/monographDocument";
import { citedSourceKeys } from "@/lib/monographRender";
import { specStrings, type ComponentBundle } from "@/lib/monographRenderLayout";

export const KIT_CITES_ID = "kv-cites";
export const KIT_HIDDEN_SCOPES = ["chem", "pt", "mb", "rm"] as const;
export const KIT_SCOPE_CONTROLS = ["theme-toggle", "contrast-toggle", "text-toggle", "motion-toggle", "pop", "scrim"] as const;
export const KIT_DATA_SCOPES: Readonly<Record<string, (typeof KIT_HIDDEN_SCOPES)[number]>> = {
  "mol-data": "chem",
  "rs-data": "pt",
  "kv-data": "rm",
  "film-subs": "rm"
};
export const GRADE_ORDER = ["A", "B", "C", "D"] as const;

export function scriptJson(value: unknown): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

export function kitCites(content: MonographContent): { s: Record<string, unknown[]>; c: Record<string, unknown[][]> } {
  const s = Object.fromEntries(
    Object.entries(content.sources).map(([key, source]) => [key, [source.number, source.title, source.fullTitle, source.publisher, source.year, source.grade, source.url, source.extra]])
  );
  const c = Object.fromEntries(Object.entries(content.citations).map(([key, quotes]) => [key, quotes.map((quote) => [quote.source, quote.locator, quote.quote])]));
  return { s, c };
}

export function dataByScope(content: MonographContent): { scoped: Record<string, string[]>; loose: string[] } {
  const scoped: Record<string, string[]> = Object.fromEntries(KIT_HIDDEN_SCOPES.map((scope) => [scope, []]));
  const loose: string[] = [];
  for (const key of Object.keys(content.data)) {
    const scope = KIT_DATA_SCOPES[key];
    if (scope) scoped[scope].push(key);
    else loose.push(key);
  }
  return { scoped, loose };
}

export type KitDataBlock = { id: string; value: unknown; scope: string | null };

export function kitDataBlocks(content: MonographContent): KitDataBlock[] {
  const { scoped, loose } = dataByScope(content);
  const inScopes = KIT_HIDDEN_SCOPES.flatMap((scope) => scoped[scope].map((id) => ({ id, value: content.data[id], scope })));
  return [...inScopes, ...loose.map((id) => ({ id, value: content.data[id], scope: null })), { id: KIT_CITES_ID, value: kitCites(content), scope: null }];
}

export type GradeTally = { total: number; grades: { grade: string; count: number }[] };

export function gradeTally(document: MonographDocument, keys: readonly string[]): GradeTally {
  const sources = document.content.sources;
  const grades = GRADE_ORDER.map((grade) => ({ grade, count: keys.filter((key) => sources[key]?.grade === grade).length })).filter((tally) => tally.count > 0);
  return { total: keys.length, grades };
}

export function sentenceCounts(document: MonographDocument): Map<string, number> {
  const counts = new Map<string, number>();
  for (const unit of Object.values(document.content.units)) for (const key of citedSourceKeys(unit.nodes)) counts.set(key, (counts.get(key) ?? 0) + 1);
  return counts;
}

export function bundleSources(document: MonographDocument, bundles: Readonly<Record<string, ComponentBundle>>): MonographContent["sources"] {
  const sources = document.content.sources;
  const keys = new Set<string>();
  for (const bundle of Object.values(bundles)) {
    for (const unit of Object.values(bundle.units)) citedSourceKeys(unit.nodes).forEach((key) => keys.add(key));
    for (const value of specStrings(bundle.spec)) if (Object.hasOwn(sources, value)) keys.add(value);
  }
  return Object.fromEntries([...keys].sort().map((key) => [key, sources[key]]));
}
