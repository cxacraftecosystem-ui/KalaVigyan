import { apiFetch } from "@/lib/api";
import type { Discipline } from "@/lib/explainerBlockBase";
import { gateReportShape, type GateReport, type OpenTask } from "@/lib/ownProposalsContract";
import { boolean, list, nullable, object, oneOf, optional, parseShape, text, type Shape } from "@/lib/shape";

export const FACTS_PATH = "/knowledge/facts";
export const FACT_SUBJECT_KINDS = ["craft", "category"] as const;
export const PROPOSAL_OUTCOMES = ["PUBLISHED", "WAITING", "REFUSED"] as const;
export const STATEMENT_MIN = 20;
export const STATEMENT_MAX = 1000;
export const SOURCES_MAX = 5;
export const QUOTES_MAX = 6;
export const QUOTE_MIN = 20;
export const QUOTE_MAX = 300;
export const FIELDS_MAX = 3;
export const SOURCE_TITLE_MAX = 1000;
export const LICENCE_MAX = 200;
export const LOCATOR_MAX = 300;

export type FactSubjectKind = (typeof FACT_SUBJECT_KINDS)[number];
export type ProposalOutcome = (typeof PROPOSAL_OUTCOMES)[number];
export type QuoteDraft = { text: string; locator: string };
export type SourceDraft = { url: string; title: string; licence: string; quotes: QuoteDraft[] };
export type FactDraft = {
  subjectKind: FactSubjectKind;
  subjectSlug: string;
  subjectName: string;
  field: Discipline | "";
  fields: Discipline[];
  statement: string;
  sources: SourceDraft[];
};

export type ReaderPlace = {
  shown: boolean;
  reason: string | null;
  pageUrl: string | null;
  chapter: string | null;
  field: string | null;
  inProse: boolean;
  writeTask: string | null;
};

export type ProposalReply = {
  schemaVersion: 1;
  outcome: ProposalOutcome;
  claimId: string;
  status: string;
  level: string;
  approvedAtOnce: boolean;
  inReviewQueue: boolean;
  sourcesDiffer: boolean;
  differsFrom: string[];
  gates: GateReport[];
  message: string;
  readers?: ReaderPlace;
};

const readerPlaceShape: Shape<ReaderPlace> = object<ReaderPlace>({
  shown: boolean,
  reason: nullable(text),
  pageUrl: nullable(text),
  chapter: nullable(text),
  field: nullable(text),
  inProse: boolean,
  writeTask: nullable(text)
});

export const proposalReplyShape: Shape<ProposalReply> = object<ProposalReply>({
  schemaVersion: oneOf([1] as const),
  outcome: oneOf(PROPOSAL_OUTCOMES),
  claimId: text,
  status: text,
  level: text,
  approvedAtOnce: boolean,
  inReviewQueue: boolean,
  sourcesDiffer: boolean,
  differsFrom: list(text),
  gates: list(gateReportShape),
  message: text,
  readers: optional(readerPlaceShape)
});

export function emptyQuote(): QuoteDraft {
  return { text: "", locator: "" };
}

export function emptySource(): SourceDraft {
  return { url: "", title: "", licence: "", quotes: [emptyQuote()] };
}

export function emptyFact(): FactDraft {
  return { subjectKind: "craft", subjectSlug: "", subjectName: "", field: "", fields: [], statement: "", sources: [emptySource()] };
}

export function factFromTask(draft: FactDraft, task: OpenTask): FactDraft {
  const subject = task.subject;
  if (!subject || (subject.kind !== "craft" && subject.kind !== "category")) return draft;
  const field = task.field ?? draft.field;
  return { ...draft, subjectKind: subject.kind, subjectSlug: subject.slug, subjectName: subject.name, field, fields: draft.fields.filter((each) => each !== field) };
}

export function canAddSource(draft: FactDraft): boolean {
  return draft.sources.length < SOURCES_MAX;
}

export function canAddQuote(source: SourceDraft): boolean {
  return source.quotes.length < QUOTES_MAX;
}

export function replyHeadline(reply: ProposalReply): string {
  if (reply.outcome === "REFUSED") return "Not added";
  if (reply.outcome === "WAITING") return "Received: it waits for a reviewer";
  return reply.approvedAtOnce ? "Published and approved" : "Published, waiting for a reviewer's check";
}

export function factProblems(draft: FactDraft): string[] {
  const problems: string[] = [];
  if (!draft.subjectSlug) problems.push(draft.subjectKind === "craft" ? "Choose the craft the fact is about." : "Choose the category the fact is about.");
  if (!draft.field) problems.push("Choose the field the fact belongs to.");
  if (draft.fields.length > FIELDS_MAX || (draft.field && draft.fields.includes(draft.field))) {
    problems.push(`Choose at most ${FIELDS_MAX} further fields, leaving out the main one.`);
  }
  const statement = draft.statement.trim();
  if (statement.length < STATEMENT_MIN) problems.push(`Write the fact in at least ${STATEMENT_MIN} characters.`);
  if (statement.length > STATEMENT_MAX) problems.push("Keep the fact to 1,000 characters.");
  if (!draft.sources.length) problems.push("Add the source that states it.");
  if (draft.sources.length > SOURCES_MAX) problems.push(`Name at most ${SOURCES_MAX} sources.`);
  draft.sources.forEach((source, index) => problems.push(...sourceProblems(source, index + 1)));
  const urls = draft.sources.map((source) => source.url.trim()).filter(Boolean);
  if (new Set(urls).size !== urls.length) problems.push("Name each source once and give all its quotes under it.");
  return problems;
}

function sourceProblems(source: SourceDraft, number: number): string[] {
  const problems: string[] = [];
  if (!/^https:\/\/\S+$/.test(source.url.trim())) problems.push(`Source ${number}: give its https address.`);
  if (!source.title.trim()) problems.push(`Source ${number}: give its title.`);
  const quotes = source.quotes.map((quote) => quote.text.trim()).filter(Boolean);
  if (!quotes.length) problems.push(`Source ${number}: copy the words that state the fact.`);
  if (quotes.length > QUOTES_MAX) problems.push(`Source ${number}: give at most ${QUOTES_MAX} quotes.`);
  if (quotes.some((quote) => quote.length < QUOTE_MIN)) problems.push(`Source ${number}: each quote is at least ${QUOTE_MIN} characters.`);
  if (quotes.some((quote) => quote.length > QUOTE_MAX)) problems.push(`Source ${number}: each quote is at most ${QUOTE_MAX} characters.`);
  if (new Set(quotes).size !== quotes.length) problems.push(`Source ${number}: give each quote once.`);
  return problems;
}

export function factBody(draft: FactDraft): Record<string, unknown> {
  return {
    subject: { kind: draft.subjectKind, slug: draft.subjectSlug },
    field: draft.field,
    fields: draft.fields,
    statement: draft.statement.trim(),
    sources: draft.sources.map((source) => ({
      url: source.url.trim(),
      title: source.title.trim(),
      licence: source.licence.trim() || null,
      quotes: source.quotes
        .filter((quote) => quote.text.trim())
        .map((quote) => ({ text: quote.text.trim(), locator: quote.locator.trim() || null }))
    }))
  };
}

export async function proposeFact(draft: FactDraft): Promise<ProposalReply> {
  const body = await apiFetch<unknown>(FACTS_PATH, { method: "POST", body: JSON.stringify(factBody(draft)) });
  return parseShape(proposalReplyShape, body);
}
