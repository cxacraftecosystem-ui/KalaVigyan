import type { CraftPage, EvidenceEntry, EvidenceGroup, PageClaim, PageCraft, PagePicture, PageSentence, PageTerm, Provenance, SubjectKind } from "@/lib/craftPageContract";
import type { PageProcess, PageStage, StageTiming } from "@/lib/craftPageProcess";
import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import { sourceReliabilityLabel } from "@/lib/citations";
import { ShapeError } from "@/lib/shape";
import type { Citation, SourceReliability, SourceRef } from "@/lib/types";

export const CRAFT_TABS = ["overview", "process", "region", "science", "sources", "evidence"] as const;
export type CraftTab = (typeof CRAFT_TABS)[number];

export const CRAFT_TAB_LABEL: Record<CraftTab, string> = {
  overview: "Overview",
  process: "Process",
  region: "Region",
  science: "Shared science",
  sources: "Sources",
  evidence: "All evidence"
};

export const PROVENANCE_LABEL: Record<Provenance, string> = {
  CURATED: "Curated",
  SEED: "Seed",
  FROM_ANSWERS: "From answers",
  RESEARCHER: "Researcher"
};

export const SUBJECT_KIND_LABEL: Record<SubjectKind, string> = {
  CRAFT: "Craft",
  STAGE: "Stage",
  MATERIAL: "Material",
  TOOL: "Tool",
  PLACE: "Place",
  COMMUNITY: "People",
  TERM: "Term",
  CONCEPT: "Topic"
};

export const TIMING_LABEL: Record<StageTiming["kind"], string> = { DURATION: "Duration", SEASON: "Season" };

export const UNRATED_SOURCES = "Not rated";

export type ClaimIndex = ReadonlyMap<string, PageClaim>;
export type RegisterFact = { label: string; value: string };
export type SourceGroup = { reliability: SourceReliability | null; label: string; sources: SourceRef[] };

export function isCraftTab(value: string | null | undefined): value is CraftTab {
  return CRAFT_TABS.includes(value as CraftTab);
}

export type CraftTabOffers = { sources: boolean; evidence: boolean; science: boolean };

export function craftTabs(page: CraftPage, offers: CraftTabOffers): CraftTab[] {
  const process = page.process.stages.length + page.process.reactions.length > 0;
  return CRAFT_TABS.filter((tab) => {
    if (tab === "process") return process;
    if (tab === "science") return offers.science;
    if (tab === "sources") return offers.sources;
    if (tab === "evidence") return offers.evidence && page.evidence !== null && page.claims.length > 0;
    return true;
  });
}

export function shownTab(requested: string | null, tabs: readonly CraftTab[]): CraftTab {
  return isCraftTab(requested) && tabs.includes(requested) ? requested : "overview";
}

export function claimIndex(page: CraftPage): ClaimIndex {
  return new Map(page.claims.map((claim) => [claim.id, claim]));
}

export function claimsOf(index: ClaimIndex, ids: readonly string[]): PageClaim[] {
  return [...new Set(ids)].map((id) => {
    const claim = index.get(id);
    if (!claim) throw new ShapeError(`claim ${id}`, "a claim the page lists");
    return claim;
  });
}

export function citationsOf(index: ClaimIndex, ids: readonly string[]): Citation[] {
  return claimsOf(index, ids).flatMap((claim) => claim.citations);
}

export function shownSentence(index: ClaimIndex, sentence: PageSentence): ExplainerSentence {
  return { id: sentence.id, text: sentence.text, level: sentence.level, citations: citationsOf(index, sentence.claimIds), terms: sentence.terms };
}

export function overviewPictures(pictures: readonly PagePicture[]): PagePicture[] {
  return pictures.filter((picture) => picture.stageId === null);
}

export function stagePictures(pictures: readonly PagePicture[], stageId: string): PagePicture[] {
  return pictures.filter((picture) => picture.stageId === stageId);
}

export function stageGroups(stages: readonly PageStage[]): { numbered: PageStage[]; unnumbered: PageStage[] } {
  const numbered = stages.filter((stage) => stage.order !== null).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  return { numbered, unnumbered: stages.filter((stage) => stage.order === null) };
}

export function pageStageNames(process: PageProcess): Map<string, string> {
  return new Map(process.stages.map((stage) => [stage.id, stage.name] as const));
}

function stageClaimIds(stage: PageStage, pictures: readonly PagePicture[]): string[] {
  return [
    ...stage.claimIds,
    ...[...stage.materials, ...stage.tools].flatMap((item) => item.claimIds),
    ...stage.timing.map((timing) => timing.claimId),
    ...stage.reactions.flatMap((reaction) => reaction.claimIds),
    ...stagePictures(pictures, stage.id).flatMap((picture) => picture.claimIds)
  ];
}

export function readingOrderClaimIds(page: CraftPage): string[] {
  const { overview, process } = page;
  const { numbered, unnumbered } = stageGroups(process.stages);
  return [
    ...overview.lede.flatMap((sentence) => sentence.claimIds),
    ...overview.keyFacts.flatMap((fact) => fact.claimIds),
    ...overviewPictures(page.pictures).flatMap((picture) => picture.claimIds),
    ...overview.sections.flatMap((section) => section.sentences.flatMap((sentence) => sentence.claimIds)),
    ...[...page.sourcesDiffer, ...page.openQuestions, ...page.glossary].flatMap((row) => row.claimIds),
    ...[...numbered, ...unnumbered].flatMap((stage) => stageClaimIds(stage, page.pictures)),
    ...process.reactions.flatMap((reaction) => reaction.claimIds),
    ...[...page.places, ...page.communities].flatMap((row) => row.claimIds),
    ...page.claims.map((claim) => claim.id)
  ];
}

export function pageSourceNumbers(page: CraftPage, regionSources: readonly SourceRef[]): Map<string, number> {
  const index = claimIndex(page);
  const numbers = new Map<string, number>();
  const take = (sourceId: string) => {
    if (!numbers.has(sourceId)) numbers.set(sourceId, numbers.size + 1);
  };
  for (const id of readingOrderClaimIds(page)) for (const citation of index.get(id)?.citations ?? []) take(citation.sourceId);
  for (const source of [...page.sources, ...regionSources]) take(source.id);
  return numbers;
}

export function pageSourcesById(page: CraftPage, regionSources: readonly SourceRef[]): Map<string, SourceRef> {
  const byId = new Map(regionSources.map((source) => [source.id, source]));
  for (const source of page.sources) byId.set(source.id, source);
  return byId;
}

const RELIABILITY_ORDER: readonly (SourceReliability | null)[] = ["A", "B", "C", "D", null];

export function sourceGroups(sources: Iterable<SourceRef>, numbers: ReadonlyMap<string, number>): SourceGroup[] {
  const listed = [...sources].sort((a, b) => (numbers.get(a.id) ?? Infinity) - (numbers.get(b.id) ?? Infinity));
  return RELIABILITY_ORDER.map((reliability) => ({
    reliability,
    label: reliability ? sourceReliabilityLabel(reliability) : UNRATED_SOURCES,
    sources: listed.filter((source) => source.reliability === reliability)
  })).filter((group) => group.sources.length > 0);
}

export function entryCount(entries: readonly EvidenceEntry[]): number {
  return entries.reduce((sum, entry) => sum + 1 + entry.foldedIds.length, 0);
}

export function groupCount(group: EvidenceGroup): number {
  return group.subjects.reduce((sum, subject) => sum + entryCount(subject.entries), 0);
}

export function glossaryMeaning(term: PageTerm): string | null {
  return term.meaning && term.claimIds.length > 0 ? term.meaning : null;
}

export function termAliases(term: PageTerm): string[] {
  const label = term.label.toLocaleLowerCase();
  return [...new Set(term.names)].filter((name) => name.toLocaleLowerCase() !== label);
}

export function overviewHasContent(page: CraftPage): boolean {
  const { overview } = page;
  const rows = [overview.lede, overview.keyFacts, overview.sections, overviewPictures(page.pictures), page.sourcesDiffer, page.openQuestions, page.glossary];
  return rows.some((row) => row.length > 0);
}

export function registerFacts(craft: PageCraft): RegisterFact[] {
  const facts: [string, string | null][] = [
    ["Category", craft.categoryName],
    ["Kind", craft.subCategoryName],
    ["GI status", craft.giStatus === "GI" ? "Registered geographical indication" : craft.giStatus === "NON_GI" ? "Not registered" : null],
    ["Practised in", craft.stateOfPractice.join(", ") || null],
    ["Origin", craft.stateOfOrigin.join(", ") || null]
  ];
  return facts.flatMap(([label, value]) => (value ? [{ label, value }] : []));
}

export function craftSubtitle(craft: PageCraft): string | undefined {
  const path = [craft.categoryName, craft.subCategoryName].filter(Boolean).join(" › ");
  return [craft.localName && craft.localName !== craft.name ? craft.localName : null, path].filter(Boolean).join(" · ") || undefined;
}
