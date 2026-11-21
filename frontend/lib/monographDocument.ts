import type { FieldCoverage } from "@/lib/fieldCoverage";

export const MONOGRAPH_DOCUMENT_PATH = (slug: string) => `/crafts/${encodeURIComponent(slug)}/monograph`;
export const MONOGRAPH_KIT_CSS = "/monographs/kit/monograph.css";
export const MONOGRAPH_KIT_JS = "/monographs/kit/monograph.js";
export const SUBJECT_KINDS = ["craft", "family", "category"] as const;
export const ENGLISH = "en";
export const LANGUAGE_TAG = /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/;

export type MonographMark = { m: string; c?: MonographNode[] } & Record<string, unknown>;
export type MonographNode = string | MonographMark;

export type MonographSource = {
  number: number;
  title: string;
  fullTitle: string | null;
  publisher: string | null;
  year: number | null;
  grade: string | null;
  url: string | null;
  extra: string | null;
  dossierSourceId: string | null;
};
export type MonographQuote = { source: string; locator: string | null; quote: string | null };
export type MonographUnit = { chapter: string; tag: string; field: string | null; nodes: MonographNode[]; claimIds: string[]; lang?: string };
export type DocumentTranslation = {
  sourceLanguage: "en";
  sourceVersion: number;
  script: string;
  direction: "ltr" | "rtl";
  passages: number;
  translated: number;
  held: number;
};
export type MonographComponent = {
  label: string;
  chapter: string;
  anchor: string;
  kind: string;
  title: string;
  description: string;
  field: string;
  fields: string[];
  subjects: string[];
};
export type MonographLayoutEntry = { chapter: string; kind: "unit" | "component"; ref: string; within: string | null };
export type MonographContent = {
  schemaVersion: 1;
  craftSlug: string;
  sources: Record<string, MonographSource>;
  citations: Record<string, MonographQuote[]>;
  citationClaims: Record<string, string[]>;
  data: Record<string, unknown>;
  units: Record<string, MonographUnit>;
  components: MonographComponent[];
  layout: MonographLayoutEntry[];
};
export type MonographDocument = {
  schemaVersion: 1;
  subjectKind: (typeof SUBJECT_KINDS)[number];
  subjectSlug: string;
  language: string;
  title: string;
  version: number;
  content: MonographContent;
  specs: Record<string, Record<string, unknown>>;
  fragments: Record<string, string>;
  shell: string | null;
  pageUrl: string;
  coverage?: FieldCoverage;
  translation?: DocumentTranslation;
};
