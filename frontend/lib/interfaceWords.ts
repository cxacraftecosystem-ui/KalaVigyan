import type { AnswerLanguage, TextDirection } from "@/lib/answerLanguages";
import { formatDate } from "@/lib/format";
import { list, object, text, type Shape } from "@/lib/shape";
import { cn } from "@/lib/utils";

export type InterfaceWord = { key: string; english: string; text: string };
export type Worded<K extends string> = { words: Record<K, string>; language: AnswerLanguage | null };
export type WordAttributes = { lang?: string; dir?: TextDirection; "data-script"?: string; className?: string };

export const PROVENANCE_KEY = "essay.provenance";
export const PROVENANCE_ENGLISH = { answer: "Answer", oneSource: "Drawn from {count} source", sources: "Drawn from {count} sources", answered: "Answered {date}" } as const;
export const ACTIONS_KEY = "essay.actions";
export const ACTIONS_ENGLISH = { save: "Save", saved: "Saved", saving: "Saving", removing: "Removing", cite: "Cite this answer" } as const;
export type ProvenanceWord = keyof typeof PROVENANCE_ENGLISH;
export type ProvenanceWords = Record<ProvenanceWord, string>;
export type ActionWord = keyof typeof ACTIONS_ENGLISH;
export const ENGLISH_PROVENANCE: Worded<ProvenanceWord> = { words: PROVENANCE_ENGLISH, language: null };
export const ESSAY_WORD_GROUPS: ReadonlyArray<{ key: string; english: Readonly<Record<string, string>> }> = [
  { key: PROVENANCE_KEY, english: PROVENANCE_ENGLISH },
  { key: ACTIONS_KEY, english: ACTIONS_ENGLISH }
];

const PLACEHOLDER = /\{([a-z]+)\}/g;
const UI_FACE = "ui";

export const interfaceWordShape: Shape<InterfaceWord> = object<InterfaceWord>({ key: text, english: text, text });
export const interfaceWordsShape: Shape<InterfaceWord[]> = list(interfaceWordShape);

export function wordedIn<K extends string>(language: AnswerLanguage | null, key: string, english: Readonly<Record<K, string>>): Worded<K> {
  const reviewed = language?.words ?? [];
  const shown = Object.entries<string>(english).map(([name, said]) => [name, reviewed.find((word) => word.key === key && word.english === said)?.text] as const);
  if (!language || shown.some(([, found]) => found === undefined)) return { words: { ...english }, language: null };
  return { words: Object.fromEntries(shown) as Record<K, string>, language };
}

export function filled(template: string, values: Readonly<Record<string, string | number>>): string {
  return template.replace(PLACEHOLDER, (whole, name: string) => (name in values ? String(values[name]) : whole));
}

export function wordedDate(value: string, language: AnswerLanguage | null): string {
  if (!language) return formatDate(value);
  return new Intl.DateTimeFormat(`${language.code}-IN-u-nu-latn`, { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
}

export function wordAttributes(language: AnswerLanguage | null, className?: string): WordAttributes {
  if (!language) return className ? { className } : {};
  return { lang: language.code, dir: language.direction, "data-script": language.script, className: cn(UI_FACE, className) };
}
