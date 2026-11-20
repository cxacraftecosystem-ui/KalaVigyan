import { citationsBySource, sourceReliabilityLabel } from "@/lib/citations";
import type { Citation, SourceReliability, SourceRef } from "@/lib/types";

export type ClusterEntry = { sourceId: string; number: number | null; source: SourceRef | null; citations: Citation[] };

export type CitationClusterView = { entries: ClusterEntry[]; label: string; name: string; description: string };

export type CitationSurface = "sheet" | "popover" | "margin";

export type ReliabilityFill = "filled" | "half" | "ring";

export const POPOVER_FROM_PX = 640;
export const MARGIN_FROM_PX = 1200;

const SHORT_TITLE_LIMIT = 72;
const NUMBER_LIST = new Intl.ListFormat("en-GB", { style: "long", type: "conjunction" });

export function clusterEntries(citations: readonly Citation[], numbers: ReadonlyMap<string, number>, sourcesById: ReadonlyMap<string, SourceRef>): ClusterEntry[] {
  return citationsBySource(citations, numbers).map((group) => ({ ...group, source: sourcesById.get(group.sourceId) ?? null }));
}

export function clusterLabel(entries: readonly Pick<ClusterEntry, "number">[]): string {
  return entries.map((entry) => (entry.number === null ? "·" : String(entry.number))).join(",");
}

export function clusterName(entries: readonly Pick<ClusterEntry, "number">[]): string {
  const numbered = entries.flatMap((entry) => (entry.number === null ? [] : [String(entry.number)]));
  const unnumbered = entries.length - numbered.length;
  if (numbered.length === 0) return unnumbered === 1 ? "Source" : `${unnumbered} sources`;
  const noun = numbered.length + unnumbered === 1 ? "Source" : "Sources";
  const more = unnumbered > 0 ? ` and ${unnumbered} more` : "";
  return `${noun} ${numbered.join(", ")}${more}`;
}

export function shownNumbers(label: string): Pick<ClusterEntry, "number">[] {
  return label.split(",").map((part) => (/^\d+$/.test(part.trim()) ? { number: Number(part.trim()) } : { number: null }));
}

export function shortTitle(title: string): string {
  const text = title.replace(/\s+/g, " ").trim();
  if (text.length <= SHORT_TITLE_LIMIT) return text;
  const cut = text.slice(0, SHORT_TITLE_LIMIT);
  const space = text[SHORT_TITLE_LIMIT] === " " ? SHORT_TITLE_LIMIT : cut.lastIndexOf(" ");
  return `${(space > 24 ? cut.slice(0, space) : cut).replace(/[\s,;:.]+$/, "")}…`;
}

export function clusterDescription(entries: readonly Pick<ClusterEntry, "source">[]): string {
  return entries.flatMap((entry) => (entry.source ? [shortTitle(entry.source.title)] : [])).join("; ");
}

export function citationCluster(citations: readonly Citation[], numbers: ReadonlyMap<string, number>, sourcesById: ReadonlyMap<string, SourceRef>): CitationClusterView {
  const entries = clusterEntries(citations, numbers, sourcesById);
  return { entries, label: clusterLabel(entries), name: clusterName(entries), description: clusterDescription(entries) };
}

export function citationSurface(viewportWidth: number, hasMargin: boolean): CitationSurface {
  if (viewportWidth < POPOVER_FROM_PX) return "sheet";
  if (hasMargin && viewportWidth >= MARGIN_FROM_PX) return "margin";
  return "popover";
}

export function sourceCountLine(count: number): string {
  return count === 1 ? "1 source for this sentence" : `${count} sources for this sentence`;
}

export function reliabilityFill(reliability: SourceReliability): ReliabilityFill {
  if (reliability === "A") return "filled";
  if (reliability === "B") return "half";
  return "ring";
}

export function reliabilityWords(reliability: SourceReliability): string {
  return `Reliability ${sourceReliabilityLabel(reliability)}`;
}

export function entryByline(source: SourceRef | null): string {
  if (!source) return "";
  const authors = source.authors.filter(Boolean);
  const people = authors.length > 2 ? `${authors[0]} and others` : NUMBER_LIST.format(authors);
  return [people || source.publisher, source.year ? String(source.year) : null].filter(Boolean).join(", ");
}

export function entryRights(source: Pick<SourceRef, "licence" | "attribution"> | null): string {
  if (!source) return "";
  const attribution = source.attribution?.trim() ?? "";
  const licence = source.licence?.trim() ?? "";
  const repeated = licence !== "" && attribution.toLowerCase().includes(licence.toLowerCase());
  return [attribution, repeated ? "" : licence].filter(Boolean).join(" · ");
}

export type EvidenceState = "verified" | "provisional" | "inferred" | "hypothesis" | "differ";

export const EVIDENCE_WORDS: Record<EvidenceState, string> = {
  verified: "Verified",
  provisional: "Provisional",
  inferred: "Inferred",
  hypothesis: "Hypothesis",
  differ: "Sources differ"
};

export function evidenceState(citation: Pick<Citation, "evidence" | "level">): EvidenceState {
  if (citation.evidence === "INFERRED") return "inferred";
  if (citation.level === "HYPOTHESIS") return "hypothesis";
  if (citation.level === "VERIFIED" || citation.level === "REVIEWED") return "verified";
  return "provisional";
}
