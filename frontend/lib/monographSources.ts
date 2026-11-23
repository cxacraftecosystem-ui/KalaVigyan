import { sourceReliabilityLabel } from "@/lib/citations";
import type { MonographDocument, MonographSource } from "@/lib/monographDocument";
import { citedSourceKeys } from "@/lib/monographRender";
import { GRADE_ORDER } from "@/lib/monographRenderKit";
import { componentUnits, pageSources, specStrings } from "@/lib/monographRenderLayout";
import type { SourceReliability } from "@/lib/types";

export const KIN_KIND = "related_crafts";
export const KIN_SOURCES_ID = "kv-src-kin";
export const UNGRADED_GROUP = "Other sources";

export type SourceGroup = { title: string; keys: string[] };
export type SourceSplit = { own: string[]; kin: string[] };

export const KIND_GROUPS = ["Government records", "Scholarship", "Museums and references", "Community and press", "Compound records"] as const;
export type KindGroup = (typeof KIND_GROUPS)[number];

const RECORDS = new Map<string, KindGroup>([
  ["COMPOUND_RECORD", "Compound records"],
  ["GI_JOURNAL", "Government records"],
  ["GOVERNMENT_REPORT", "Government records"]
]);
const WRITINGS = new Map<string, KindGroup>([
  ["PAPER", "Scholarship"],
  ["BOOK", "Scholarship"],
  ["BOOK_CHAPTER", "Scholarship"],
  ["DATASET", "Scholarship"],
  ["ENCYCLOPEDIA", "Museums and references"]
]);
const MUSEUM_WORDS = /\b(museum|archives?|gallery)\b/i;
const SCHOLARLY_WORDS = /\b(university|institute)\b/i;

function kinLabels(document: MonographDocument): Set<string> {
  return new Set(document.content.components.filter((component) => component.kind === KIN_KIND).map((component) => component.label));
}

export function sourceSplit(document: MonographDocument): SourceSplit {
  const labels = kinLabels(document);
  const held = new Set([...labels].flatMap((label) => componentUnits(document, label)));
  const kin = new Set<string>();
  const elsewhere = new Set<string>();
  for (const [ref, unit] of Object.entries(document.content.units)) citedSourceKeys(unit.nodes).forEach((key) => (held.has(ref) ? kin : elsewhere).add(key));
  for (const [label, spec] of Object.entries(document.specs)) if (!labels.has(label)) specStrings(spec).forEach((value) => elsewhere.add(value));
  const keys = pageSources(document);
  const apart = new Set(keys.filter((key) => kin.has(key) && !elsewhere.has(key)));
  return { own: keys.filter((key) => !apart.has(key)), kin: keys.filter((key) => apart.has(key)) };
}

export function kindGroup(source: MonographSource): KindGroup {
  const kind = source.kind ?? "";
  const publisher = source.publisher ?? "";
  const record = RECORDS.get(kind);
  if (record) return record;
  if (MUSEUM_WORDS.test(publisher)) return "Museums and references";
  return WRITINGS.get(kind) ?? (SCHOLARLY_WORDS.test(publisher) ? "Scholarship" : "Community and press");
}

function gradeOf(source: MonographSource): SourceReliability | null {
  return (GRADE_ORDER as readonly string[]).includes(source.grade ?? "") ? (source.grade as SourceReliability) : null;
}

function gradeTitle(grade: SourceReliability): string {
  const words = sourceReliabilityLabel(grade).split(" · ")[1] ?? grade;
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function gradeGroups(sources: MonographDocument["content"]["sources"], keys: readonly string[]): SourceGroup[] {
  const graded = GRADE_ORDER.map((grade) => ({ title: gradeTitle(grade), keys: keys.filter((key) => gradeOf(sources[key]) === grade) }));
  return [...graded, { title: UNGRADED_GROUP, keys: keys.filter((key) => gradeOf(sources[key]) === null) }];
}

export function sourceGroups(document: MonographDocument, keys: readonly string[]): SourceGroup[] {
  const sources = document.content.sources;
  const kinded = keys.length > 0 && keys.every((key) => Boolean(sources[key].kind));
  const groups: SourceGroup[] = kinded ? KIND_GROUPS.map((title) => ({ title, keys: keys.filter((key) => kindGroup(sources[key]) === title) })) : gradeGroups(sources, keys);
  return groups.filter((group) => group.keys.length > 0);
}
