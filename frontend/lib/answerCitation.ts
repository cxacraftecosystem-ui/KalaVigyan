import { explainerHref } from "@/lib/savedView";

export type CitationStyle = "text" | "bibtex";

export type AnswerCitation = {
  explainerId: string;
  version: number;
  question: string;
  answeredAt: string | null;
  sources: number;
  origin: string;
  path: string | null;
  accessedAt: Date;
};

export const KALAVIGYAN_PUBLISHER = "IIT Kharagpur, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform";

export const CITATION_STYLES: { value: CitationStyle; label: string }[] = [
  { value: "text", label: "Text" },
  { value: "bibtex", label: "BibTeX" }
];

const LONG_DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

function longDate(value: Date): string {
  return LONG_DATE.format(value);
}

function isoDay(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export function answerAddress(citation: Pick<AnswerCitation, "explainerId" | "version" | "origin" | "path">): string {
  return `${citation.origin.replace(/\/+$/, "")}${citation.path ?? explainerHref(citation.explainerId, citation.version)}`;
}

function answered(citation: AnswerCitation): Date | null {
  if (!citation.answeredAt) return null;
  const when = new Date(citation.answeredAt);
  return Number.isNaN(when.getTime()) ? null : when;
}

export function answerCitationText(citation: AnswerCitation): string {
  const when = answered(citation);
  const edition = [`Answer, version ${citation.version}`, when ? `answered ${longDate(when)}` : null].filter(Boolean).join(", ");
  const title = /[.?!]$/.test(citation.question) ? citation.question : `${citation.question}.`;
  return `KalaVigyan. “${title}” ${edition}. ${KALAVIGYAN_PUBLISHER}. ${answerAddress(citation)}. Accessed ${longDate(citation.accessedAt)}.`;
}

function bibtexEscape(value: string): string {
  return value.replace(/([{}\\])/g, "\\$1").replace(/([&%$#_])/g, "\\$1");
}

export function answerCitationKey(citation: Pick<AnswerCitation, "explainerId" | "version">): string {
  return `kalavigyan_answer_${citation.explainerId.slice(0, 8)}_v${citation.version}`;
}

export function answerBibtex(citation: AnswerCitation): string {
  const when = answered(citation) ?? citation.accessedAt;
  const url = answerAddress(citation);
  const sources = citation.sources === 1 ? "1 source" : `${citation.sources} sources`;
  const fields = [
    ["title", bibtexEscape(citation.question)],
    ["author", "{KalaVigyan}"],
    ["organization", KALAVIGYAN_PUBLISHER],
    ["publisher", KALAVIGYAN_PUBLISHER],
    ["version", String(citation.version)],
    ["date", isoDay(when)],
    ["year", String(when.getUTCFullYear())],
    ["howpublished", `\\url{${url}}`],
    ["url", url],
    ["urldate", isoDay(citation.accessedAt)],
    ["note", `Answer, drawn from ${sources}. Accessed ${longDate(citation.accessedAt)}`]
  ];
  return `@misc{${answerCitationKey(citation)},\n${fields.map(([name, value]) => `  ${name} = {${value}}`).join(",\n")}\n}`;
}

export function answerCitationIn(style: CitationStyle, citation: AnswerCitation): string {
  return style === "bibtex" ? answerBibtex(citation) : answerCitationText(citation);
}
