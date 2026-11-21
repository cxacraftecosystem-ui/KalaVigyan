import { apiFetch, buildQuery } from "@/lib/api";
import { DOCUMENT_LANGUAGE_CODES, PAGE_KINDS, type DocumentLanguageCode, type PageKind } from "@/lib/documentLanguages";
import { boolean, integer, list, nullable, object, oneOf, optional, parseShape, text, type Shape } from "@/lib/shape";

export const PASSAGE_STATES = ["TO_TRANSLATE", "HELD", "WAITING", "TRANSLATED"] as const;
export const PART_OUTCOMES = ["ACCEPTED", "REFUSED", "SHOWN", "LISTED"] as const;
export const REVIEW_PATH = "/knowledge/translations/review";
export const READER_LANGUAGES_PATH = "/knowledge/translations/languages";
export const PAGE_BUNDLE_PATH = "/knowledge/pages";
export const PAGE_PREVIEW_PATH = "/knowledge/pages/preview";
export const PASSAGES_SHOWN = 10;

export type PassageState = (typeof PASSAGE_STATES)[number];
export type TaskPassage = { key: string; sourceHash: string; english: string; texts: string[]; fixed: number[]; cited: number[] };
export type PassageView = TaskPassage & { chapter: string; tag: string; state: PassageState; translation?: string[]; previous?: string[] };
export type LanguageOffer = { code: DocumentLanguageCode; label: string; autonym: string; script: string; direction: "ltr" | "rtl" };
export type TranslationView = {
  schemaVersion: 1;
  subject: { kind: PageKind; slug: string };
  title: string;
  language: LanguageOffer;
  englishVersion: number;
  passagesTotal: number;
  translated: number;
  held: number;
  waiting: number;
  toTranslate: number;
  offered: boolean;
  passages: PassageView[];
  nextOffset: number | null;
  pageUrl: string;
};
export type PartReport = { part: string; index: number; outcome: (typeof PART_OUTCOMES)[number]; status: string | null; id: string | null; message: string };
export type BundleReply = { parts: PartReport[]; message: string; previewUrl: string | null };
export type ReviewItem = {
  id: string;
  subject: { kind: PageKind; slug: string };
  language: DocumentLanguageCode;
  key: string;
  status: string;
  english: string;
  texts: string[];
  current: boolean;
  note: string | null;
  createdAt: string;
  pageUrl: string;
};
export type ReviewList = { languages: DocumentLanguageCode[]; total: number; items: ReviewItem[] };
export type TranslatedPassage = { key: string; sourceHash: string; texts: string[] };

const taskPassageFields = { key: text, sourceHash: text, english: text, texts: list(text), fixed: list(integer), cited: list(integer) };
export const taskPassageShape: Shape<TaskPassage> = object<TaskPassage>(taskPassageFields);

const passageShape: Shape<PassageView> = object<PassageView>({
  ...taskPassageFields,
  chapter: text,
  tag: text,
  state: oneOf(PASSAGE_STATES),
  translation: optional(list(text)),
  previous: optional(list(text))
});

const offerShape: Shape<LanguageOffer> = object<LanguageOffer>({
  code: oneOf(DOCUMENT_LANGUAGE_CODES),
  label: text,
  autonym: text,
  script: text,
  direction: oneOf(["ltr", "rtl"] as const)
});

const subjectShape = object<{ kind: PageKind; slug: string }>({ kind: oneOf(PAGE_KINDS), slug: text });

const viewShape: Shape<TranslationView> = object<TranslationView>({
  schemaVersion: oneOf([1] as const),
  subject: subjectShape,
  title: text,
  language: offerShape,
  englishVersion: integer,
  passagesTotal: integer,
  translated: integer,
  held: integer,
  waiting: integer,
  toTranslate: integer,
  offered: boolean,
  passages: list(passageShape),
  nextOffset: nullable(integer),
  pageUrl: text
});

const reportFields = object<PartReport>({ part: text, index: integer, outcome: oneOf(PART_OUTCOMES), status: nullable(text), id: nullable(text), message: text });

const reportShape: Shape<PartReport> = {
  expected: "a part report",
  parse(value, path) {
    const raw = (value ?? {}) as Record<string, unknown>;
    return reportFields.parse({ part: raw.part, index: raw.index, outcome: raw.outcome, status: raw.status ?? null, id: raw.id ?? null, message: raw.message }, path);
  }
};

const reviewFields = object<ReviewItem>({
  id: text,
  subject: subjectShape,
  language: oneOf(DOCUMENT_LANGUAGE_CODES),
  key: text,
  status: text,
  english: text,
  texts: list(text),
  current: boolean,
  note: nullable(text),
  createdAt: text,
  pageUrl: text
});

const reviewItemShape: Shape<ReviewItem> = {
  expected: "a translation waiting for review",
  parse(value, path) {
    const raw = (value ?? {}) as Record<string, unknown>;
    const picked = { id: raw.id, subject: raw.subject, language: raw.language, key: raw.key, status: raw.status, english: raw.english, texts: raw.texts, current: raw.current, note: raw.note ?? null, createdAt: raw.createdAt, pageUrl: raw.pageUrl };
    return reviewFields.parse(picked, path);
  }
};

export function translationPath(kind: PageKind, slug: string, language: DocumentLanguageCode, state: PassageState | null, offset = 0): string {
  const query = buildQuery({ state, offset: offset || null, limit: PASSAGES_SHOWN });
  return `/pages/${kind}/${encodeURIComponent(slug)}/translations/${language}${query}`;
}

export async function fetchTranslationView(kind: PageKind, slug: string, language: DocumentLanguageCode, state: PassageState | null): Promise<TranslationView> {
  return parseShape(viewShape, await apiFetch<unknown>(translationPath(kind, slug, language, state)));
}

export function translationBundle(view: TranslationView, passages: TranslatedPassage[], taskKey: string | null): Record<string, unknown> {
  const translation = { language: view.language.code, passages, ...(taskKey ? { taskKey } : {}) };
  return { subject: view.subject, translation };
}

function bundleReply(raw: unknown): BundleReply {
  const body = (raw ?? {}) as Record<string, unknown>;
  const parts = parseShape(list(reportShape), body.parts ?? []);
  return { parts, message: typeof body.message === "string" ? body.message : "", previewUrl: typeof body.previewUrl === "string" ? body.previewUrl : null };
}

export async function sendTranslation(bundle: Record<string, unknown>, preview: boolean): Promise<BundleReply> {
  const path = preview ? PAGE_PREVIEW_PATH : PAGE_BUNDLE_PATH;
  return bundleReply(await apiFetch<unknown>(path, { method: "POST", body: JSON.stringify(bundle) }));
}

export async function fetchReviewList(): Promise<ReviewList> {
  const raw = (await apiFetch<unknown>(REVIEW_PATH)) as Record<string, unknown>;
  return {
    languages: parseShape(list(oneOf(DOCUMENT_LANGUAGE_CODES)), raw.languages),
    total: parseShape(integer, raw.total),
    items: parseShape(list(reviewItemShape), raw.items)
  };
}

export async function decideTranslation(id: string, approve: boolean, note: string | null): Promise<void> {
  const path = `/knowledge/translations/${encodeURIComponent(id)}/${approve ? "approve" : "reject"}`;
  await apiFetch<unknown>(path, { method: "POST", body: JSON.stringify({ note }) });
}

export async function fetchReaderLanguages(): Promise<DocumentLanguageCode[]> {
  const raw = (await apiFetch<unknown>(READER_LANGUAGES_PATH)) as Record<string, unknown>;
  return parseShape(list(oneOf(DOCUMENT_LANGUAGE_CODES)), raw.languages);
}

export async function saveReaderLanguages(languages: DocumentLanguageCode[]): Promise<DocumentLanguageCode[]> {
  const raw = (await apiFetch<unknown>(READER_LANGUAGES_PATH, { method: "PUT", body: JSON.stringify({ languages }) })) as Record<string, unknown>;
  return parseShape(list(oneOf(DOCUMENT_LANGUAGE_CODES)), raw.languages);
}

export function translatedTexts(passage: TaskPassage, given: Record<number, string>): string[] {
  return passage.texts.map((english, at) => (passage.fixed.includes(at) ? english : (given[at] ?? "")));
}

export type TaskPage = { kind: PageKind; slug: string; language: DocumentLanguageCode };

export function taskPage(key: string): TaskPage | null {
  const [kind, subject, slug, language] = key.split(":");
  if (kind !== "TRANSLATE" || !slug || !language) return null;
  if (!(PAGE_KINDS as readonly string[]).includes(subject) || !(DOCUMENT_LANGUAGE_CODES as readonly string[]).includes(language)) return null;
  return { kind: subject as PageKind, slug, language: language as DocumentLanguageCode };
}

export function filledPassages(passages: readonly PassageView[], drafts: Record<string, Record<number, string>>): TranslatedPassage[] {
  return passages
    .filter((passage) => drafts[passage.key] && Object.values(drafts[passage.key]).some((value) => value.trim()))
    .map((passage) => ({ key: passage.key, sourceHash: passage.sourceHash, texts: translatedTexts(passage, drafts[passage.key]) }));
}
