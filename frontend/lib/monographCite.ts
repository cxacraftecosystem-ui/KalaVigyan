import type { MonographDocument } from "@/lib/monographDocument";

export const CITE_PUBLISHER = "IIT Kharagpur, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform";
export const CITE_STYLES = [
  { value: "text", label: "Text" },
  { value: "bibtex", label: "BibTeX" }
] as const;

export type CiteKind = "monograph" | "answer";
export type CiteStyle = (typeof CITE_STYLES)[number]["value"];
export type Citable = { kind: CiteKind; title: string; version: number; url: string; key: string };

const CITED_SUBJECT = "craft";
const KIND_WORDS: Readonly<Record<CiteKind, string>> = { monograph: "Monograph", answer: "Answer" };
const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric" });

export function versionedUrl(pageUrl: string, version: number): string {
  const url = new URL(pageUrl);
  return `${url.origin}${url.pathname.replace(/\/+$/, "").toLowerCase()}/v${version}`;
}

export function citeKey(slug: string, version: number): string {
  return `kalavigyan_${slug.toLowerCase().replace(/[^a-z0-9]+/g, "_")}_v${version}`;
}

export function documentCitation(document: MonographDocument): Citable | null {
  if (document.subjectKind !== CITED_SUBJECT) return null;
  return { kind: "monograph", title: document.title, version: document.version, url: versionedUrl(document.pageUrl, document.version), key: citeKey(document.subjectSlug, document.version) };
}

export function accessDay(day: Date): string {
  return DAY.format(day);
}

export function isoDay(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, "0");
  return `${day.getFullYear()}-${month}-${String(day.getDate()).padStart(2, "0")}`;
}

export function closedTitle(title: string): string {
  return /[.?!]$/.test(title) ? title : `${title}.`;
}

export function citationText(cite: Citable, accessed: Date | null): string {
  const text = `KalaVigyan. “${closedTitle(cite.title)}” ${KIND_WORDS[cite.kind]}, version ${cite.version}. ${CITE_PUBLISHER}. ${cite.url}.`;
  return accessed ? `${text} Accessed ${accessDay(accessed)}.` : text;
}

export function citationBibtex(cite: Citable, accessed: Date | null): string {
  const note = `${KIND_WORDS[cite.kind]}, version ${cite.version}`;
  return [
    `@misc{${cite.key},`,
    `  title = {${cite.title}},`,
    "  author = {{KalaVigyan}},",
    `  organization = {${CITE_PUBLISHER}},`,
    `  publisher = {${CITE_PUBLISHER}},`,
    `  version = {${cite.version}},`,
    `  url = {${cite.url}},`,
    ...(accessed ? [`  urldate = {${isoDay(accessed)}},`] : []),
    `  howpublished = {\\url{${cite.url}}},`,
    `  note = {${accessed ? `${note}. Accessed ${accessDay(accessed)}` : note}}`,
    "}"
  ].join("\n");
}

export function citation(cite: Citable, style: CiteStyle, accessed: Date | null): string {
  return style === "bibtex" ? citationBibtex(cite, accessed) : citationText(cite, accessed);
}
