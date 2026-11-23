import type { AnswerSection, Citation, SourceReliability, SourceRef } from "@/lib/types";

export function sourceNumbers(sections: readonly AnswerSection[]): Map<string, number> {
  const numbers = new Map<string, number>();
  const take = (citations: readonly Citation[]) => {
    for (const citation of citations) {
      if (!numbers.has(citation.sourceId)) numbers.set(citation.sourceId, numbers.size + 1);
    }
  };
  for (const section of sections) for (const sentence of section.sentences) take(sentence.citations);
  return numbers;
}

export function listedSourceNumbers(sources: readonly Pick<SourceRef, "id">[], numbered: ReadonlyMap<string, number> = new Map()): Map<string, number> {
  const numbers = new Map(numbered);
  let next = Math.max(0, ...numbers.values()) + 1;
  for (const source of sources) {
    if (numbers.has(source.id)) continue;
    numbers.set(source.id, next);
    next += 1;
  }
  return numbers;
}

export type SourceCitations = { sourceId: string; number: number | null; citations: Citation[] };

function passageKey(citation: Citation): string {
  return JSON.stringify([citation.sourceId, citation.evidence, citation.quote, citation.locator]);
}

function byNumber(a: SourceCitations, b: SourceCitations): number {
  if (a.number === b.number) return 0;
  if (a.number === null) return 1;
  if (b.number === null) return -1;
  return a.number - b.number;
}

export function citationsBySource(citations: readonly Citation[], numbers: ReadonlyMap<string, number>): SourceCitations[] {
  const groups = new Map<string, SourceCitations>();
  const passages = new Set<string>();
  for (const citation of citations) {
    const passage = passageKey(citation);
    if (passages.has(passage)) continue;
    passages.add(passage);
    const group = groups.get(citation.sourceId) ?? { sourceId: citation.sourceId, number: numbers.get(citation.sourceId) ?? null, citations: [] };
    group.citations.push(citation);
    groups.set(citation.sourceId, group);
  }
  return [...groups.values()].sort(byNumber);
}

const ALLOWED_PROTOCOLS = new Set(["https:"]);

export function safeOutboundUrl(value: string | null | undefined): string | null {
  const text = (value ?? "").trim();
  if (!text) return null;
  try {
    const url = new URL(text);
    return ALLOWED_PROTOCOLS.has(url.protocol) ? url.toString() : null;
  } catch {
    return null;
  }
}

export function doiUrl(doi: string | null | undefined): string | null {
  const text = (doi ?? "").trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "").replace(/^doi:\s*/i, "");
  if (!/^10\.\d{4,9}\/\S+$/.test(text)) return null;
  return `https://doi.org/${encodeURI(text)}`;
}

export function sourceHref(source: Pick<SourceRef, "url" | "doi">): string | null {
  return safeOutboundUrl(source.url) ?? doiUrl(source.doi);
}

export function sourceHost(href: string | null): string | null {
  if (!href) return null;
  try {
    return new URL(href).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

export function sourceByline(source: SourceRef): string {
  const authors = source.authors.filter(Boolean);
  const people = authors.length > 3 ? `${authors.slice(0, 3).join(", ")} et al.` : authors.join(", ");
  return [people, source.year ? String(source.year) : null, source.publisher].filter(Boolean).join(" · ");
}

export type HighlightPart = { text: string; mark: boolean };

function squash(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ");
}

export function highlightQuote(context: string | null | undefined, quote: string | null | undefined): HighlightPart[] {
  const body = squash(context ?? "").trim();
  const needle = squash(quote ?? "").trim();
  if (!body) return needle ? [{ text: needle, mark: true }] : [];
  if (!needle) return [{ text: body, mark: false }];
  const at = body.toLowerCase().indexOf(needle.toLowerCase());
  if (at < 0) return [{ text: needle, mark: true }];
  const parts: HighlightPart[] = [];
  if (at > 0) parts.push({ text: body.slice(0, at), mark: false });
  parts.push({ text: body.slice(at, at + needle.length), mark: true });
  if (at + needle.length < body.length) parts.push({ text: body.slice(at + needle.length), mark: false });
  return parts;
}

const SOURCE_KIND_LABEL: Record<string, string> = {
  PAPER: "Journal article",
  BOOK: "Book",
  BOOK_CHAPTER: "Book chapter",
  WEB_PAGE: "Web page",
  ENCYCLOPEDIA: "Encyclopedia",
  DATASET: "Dataset",
  GI_JOURNAL: "GI Journal",
  GOVERNMENT_REPORT: "Government report",
  COMPOUND_RECORD: "Compound record",
  FIELD_TESTIMONY: "Field testimony",
  MEDIA: "Media file",
  OTHER: "Other"
};

const RELIABILITY_LABEL: Record<SourceReliability, string> = {
  A: "A · peer-reviewed or official",
  B: "B · reputable reference",
  C: "C · general web",
  D: "D · unknown"
};

export function sourceKindLabel(kind: string): string {
  return SOURCE_KIND_LABEL[kind] ?? "Other";
}

export function sourceReliabilityLabel(reliability: SourceReliability): string {
  return RELIABILITY_LABEL[reliability];
}
