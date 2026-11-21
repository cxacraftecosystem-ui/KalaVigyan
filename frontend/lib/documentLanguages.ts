import { ENGLISH, type MonographUnit } from "@/lib/monographDocument";
import { boolean, integer, list, matching, object, oneOf, parseShape, text, type Shape } from "@/lib/shape";

export const DOCUMENT_LANGUAGE_CODES = ["hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "or", "pa", "as", "ur"] as const;
export const PAGE_KINDS = ["craft", "family", "category"] as const;
export const DEFAULT_ALTERNATE = "x-default";

export type DocumentLanguageCode = (typeof DOCUMENT_LANGUAGE_CODES)[number];
export type PageKind = (typeof PAGE_KINDS)[number];
export type TextDirection = "ltr" | "rtl";

export const TEXT_SCRIPTS: Record<DocumentLanguageCode, string> = {
  hi: "Deva",
  bn: "Beng",
  ta: "Taml",
  te: "Telu",
  mr: "Deva",
  gu: "Gujr",
  kn: "Knda",
  ml: "Mlym",
  or: "Orya",
  pa: "Guru",
  as: "Beng",
  ur: "Aran"
};
export const RIGHT_TO_LEFT: readonly DocumentLanguageCode[] = ["ur"];
export const LANGUAGE_NAMES: Record<DocumentLanguageCode, { label: string; autonym: string }> = {
  hi: { label: "Hindi", autonym: "हिन्दी" },
  bn: { label: "Bengali", autonym: "বাংলা" },
  ta: { label: "Tamil", autonym: "தமிழ்" },
  te: { label: "Telugu", autonym: "తెలుగు" },
  mr: { label: "Marathi", autonym: "मराठी" },
  gu: { label: "Gujarati", autonym: "ગુજરાતી" },
  kn: { label: "Kannada", autonym: "ಕನ್ನಡ" },
  ml: { label: "Malayalam", autonym: "മലയാളം" },
  or: { label: "Odia", autonym: "ଓଡ଼ିଆ" },
  pa: { label: "Punjabi", autonym: "ਪੰਜਾਬੀ" },
  as: { label: "Assamese", autonym: "অসমীয়া" },
  ur: { label: "Urdu", autonym: "اردو" }
};

export type PageLanguage = {
  code: DocumentLanguageCode;
  label: string;
  autonym: string;
  script: string;
  direction: TextDirection;
  passages: number;
  translated: number;
  offered: boolean;
};
export type PageLanguages = { schemaVersion: 1; subject: { kind: PageKind; slug: string }; languages: PageLanguage[] };
export type AlternateLanguages = Partial<Record<typeof ENGLISH | DocumentLanguageCode | typeof DEFAULT_ALTERNATE, string>>;
export type UnitLanguage = { lang?: string; dir?: TextDirection; "data-fallback"?: string; "data-script"?: string };

export const pageLanguageShape: Shape<PageLanguage> = object<PageLanguage>({
  code: oneOf(DOCUMENT_LANGUAGE_CODES),
  label: text,
  autonym: text,
  script: matching(/^[A-Z][a-z]{3}$/, "a script code"),
  direction: oneOf(["ltr", "rtl"] as const),
  passages: integer,
  translated: integer,
  offered: boolean
});

const pageLanguagesShape: Shape<PageLanguages> = object<PageLanguages>({
  schemaVersion: oneOf([1] as const),
  subject: object<{ kind: PageKind; slug: string }>({ kind: oneOf(PAGE_KINDS), slug: text }),
  languages: list(pageLanguageShape)
});

export function parsePageLanguages(raw: unknown): PageLanguages {
  return parseShape(pageLanguagesShape, raw);
}

export function documentLanguagesPath(kind: PageKind, slug: string): string {
  return `/pages/${kind}/${encodeURIComponent(slug)}/languages`;
}

export function isDocumentLanguage(segment: string): segment is DocumentLanguageCode {
  return (DOCUMENT_LANGUAGE_CODES as readonly string[]).includes(segment);
}

export function pagePath(kind: PageKind, slug: string): string {
  return kind === "category" ? `/categories/${slug}` : `/crafts/${slug}`;
}

export function documentLanguagePath(kind: PageKind, slug: string, code: string): string {
  return code === ENGLISH ? pagePath(kind, slug) : `${pagePath(kind, slug)}/${code}`;
}

export function readLanguages(languages: readonly PageLanguage[]): PageLanguage[] {
  return languages.filter((language) => language.translated > 0);
}

export function languageAlternates(kind: PageKind, slug: string, languages: readonly PageLanguage[]): AlternateLanguages {
  const read = readLanguages(languages);
  if (!read.length) return {};
  const english = pagePath(kind, slug);
  const translated = read.map((language): [string, string] => [language.code, documentLanguagePath(kind, slug, language.code)]);
  const entries: [string, string][] = [[ENGLISH, english], ...translated, [DEFAULT_ALTERNATE, english]];
  return Object.fromEntries(entries) as AlternateLanguages;
}

export function textDirection(code: string): TextDirection {
  return (RIGHT_TO_LEFT as readonly string[]).includes(code) ? "rtl" : "ltr";
}

export function unitLanguage(unit: MonographUnit): UnitLanguage {
  if (!unit.lang) return {};
  if (unit.lang === ENGLISH) return { lang: ENGLISH, dir: "ltr", "data-fallback": ENGLISH };
  if (!isDocumentLanguage(unit.lang)) return { lang: unit.lang };
  return { lang: unit.lang, dir: textDirection(unit.lang), "data-script": TEXT_SCRIPTS[unit.lang] };
}

