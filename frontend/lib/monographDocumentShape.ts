import {
  LANGUAGE_TAG,
  MONOGRAPH_DOCUMENT_PATH,
  SUBJECT_KINDS,
  type DocumentTranslation,
  type MonographChapterName,
  type MonographComponent,
  type MonographContent,
  type MonographDocument,
  type MonographLayoutEntry,
  type MonographMark,
  type MonographNode,
  type MonographQuote,
  type MonographSource,
  type MonographUnit
} from "@/lib/monographDocument";
import { fieldCoverageShape } from "@/lib/fieldCoverage";
import { dictionary, integer, list, matching, nullable, object, oneOf, optional, parseShape, ShapeError, text, type Shape } from "@/lib/shape";

export const CATEGORY_MONOGRAPH_DOCUMENT_PATH = (slug: string) => `/categories/${encodeURIComponent(slug)}/monograph`;
export const MONOGRAPH_PREVIEW_SUBJECTS = ["craft", "category"] as const;
export type MonographPreviewSubject = (typeof MONOGRAPH_PREVIEW_SUBJECTS)[number];

const ANY_KEY = /^.+$/;
const SUBJECT_SLUG = matching(/^[A-Za-z0-9-]+$/, "a subject slug");

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const anything: Shape<unknown> = { expected: "any value", parse: (value) => value };

const record: Shape<Record<string, unknown>> = {
  expected: "an object",
  parse(value, path) {
    if (!isRecord(value)) throw new ShapeError(path, "an object");
    return value;
  }
};

const positive = (inner: Shape<number>): Shape<number> => ({
  expected: `${inner.expected} of 1 or more`,
  parse(value, path) {
    const parsed = inner.parse(value, path);
    if (parsed < 1) throw new ShapeError(path, "1 or more");
    return parsed;
  }
});

export const monographNodeShape: Shape<MonographNode> = {
  expected: "text or an inline mark",
  parse(value, path) {
    if (typeof value === "string") return value;
    if (!isRecord(value) || typeof value.m !== "string") throw new ShapeError(path, "text or a mark with m");
    if (value.c === undefined) return value as MonographMark;
    return { ...value, c: list(monographNodeShape).parse(value.c, `${path}.c`) } as MonographMark;
  }
};

const sourceShape: Shape<MonographSource> = object<MonographSource>({
  number: positive(integer),
  title: text,
  fullTitle: nullable(text),
  publisher: nullable(text),
  year: nullable(integer),
  grade: nullable(text),
  url: nullable(text),
  extra: nullable(text),
  dossierSourceId: nullable(text),
  kind: optional(text)
});

const quoteShape: Shape<MonographQuote> = object<MonographQuote>({ source: text, locator: nullable(text), quote: nullable(text) });

const unitShape: Shape<MonographUnit> = object<MonographUnit>({
  chapter: text,
  tag: text,
  field: nullable(text),
  nodes: list(monographNodeShape),
  claimIds: list(text),
  lang: optional(matching(LANGUAGE_TAG, "a language tag"))
});

const translationShape: Shape<DocumentTranslation> = object<DocumentTranslation>({
  sourceLanguage: oneOf(["en"] as const),
  sourceVersion: positive(integer),
  script: matching(/^[A-Z][a-z]{3}$/, "a script code"),
  direction: oneOf(["ltr", "rtl"] as const),
  passages: integer,
  translated: integer,
  held: integer
});

const componentShape: Shape<MonographComponent> = object<MonographComponent>({
  label: text,
  chapter: text,
  anchor: text,
  kind: text,
  title: text,
  description: text,
  field: text,
  fields: list(text),
  subjects: list(text)
});

const layoutShape: Shape<MonographLayoutEntry> = object<MonographLayoutEntry>({
  chapter: text,
  kind: oneOf(["unit", "component"] as const),
  ref: text,
  within: nullable(text)
});

const chapterNameShape: Shape<MonographChapterName> = object<MonographChapterName>({ key: text, title: text, rail: text });

const contentShape: Shape<MonographContent> = object<MonographContent>({
  schemaVersion: oneOf([1] as const),
  craftSlug: text,
  sources: dictionary(ANY_KEY, sourceShape),
  citations: dictionary(ANY_KEY, list(quoteShape)),
  citationClaims: dictionary(ANY_KEY, list(text)),
  data: dictionary(ANY_KEY, anything),
  units: dictionary(ANY_KEY, unitShape),
  components: list(componentShape),
  layout: list(layoutShape),
  chapters: optional(list(chapterNameShape))
});

export const monographDocumentShape: Shape<MonographDocument> = object<MonographDocument>({
  schemaVersion: oneOf([1] as const),
  subjectKind: oneOf(SUBJECT_KINDS),
  subjectSlug: SUBJECT_SLUG,
  language: matching(LANGUAGE_TAG, "a language tag"),
  title: text,
  version: positive(integer),
  content: contentShape,
  specs: dictionary(ANY_KEY, record),
  fragments: dictionary(ANY_KEY, text),
  shell: nullable(text),
  pageUrl: text,
  coverage: optional(fieldCoverageShape),
  translation: optional(translationShape)
});

export function checkedMonographDocument(document: MonographDocument): MonographDocument {
  const labels = new Set(document.content.components.map((component) => component.label));
  const drawn = [...Object.keys(document.specs), ...Object.keys(document.fragments)];
  const unknown = drawn.filter((label) => !labels.has(label));
  if (unknown.length) throw new ShapeError(`specs and fragments.${unknown[0]}`, "a component the content lists");
  const both = Object.keys(document.specs).filter((label) => Object.hasOwn(document.fragments, label));
  if (both.length) throw new ShapeError(`specs.${both[0]}`, "a spec or a fragment, not both");
  return document;
}

export function parseMonographDocument(raw: unknown): MonographDocument {
  return checkedMonographDocument(parseShape(monographDocumentShape, raw));
}

export function versionedDocumentPath(path: string, version: number | null): string {
  return version === null ? path : `${path}?version=${version}`;
}

export function monographDocumentPath(subject: MonographPreviewSubject, slug: string): string {
  return subject === "craft" ? MONOGRAPH_DOCUMENT_PATH(slug) : CATEGORY_MONOGRAPH_DOCUMENT_PATH(slug);
}
