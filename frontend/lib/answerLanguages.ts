import { interfaceWordsShape, type InterfaceWord } from "@/lib/interfaceWords";
import { list, matching, object, oneOf, optional, parseShape, ShapeError, text, type Shape } from "@/lib/shape";
import type { AnswerSection, AnswerSentence } from "@/lib/types";

export type TextDirection = "ltr" | "rtl";

export type LanguageOption = { value: string; label: string; hint?: string };

export type AnswerLanguage = {
  code: string;
  label: string;
  autonym: string;
  script: string;
  direction: TextDirection;
  words?: InterfaceWord[];
};

export type TextAttributes = { lang?: string; dir: TextDirection | "auto" };

export type ShownText = TextAttributes & { text: string };

export const AUTO_LANGUAGE = "auto";

export const ENGLISH: AnswerLanguage = { code: "en", label: "English", autonym: "English", script: "Latn", direction: "ltr" };

const ENGLISH_TEXT: TextAttributes = { lang: ENGLISH.code, dir: ENGLISH.direction };

const SCRIPT_LETTERS: ReadonlyArray<readonly [string, RegExp]> = [
  ["Latn", /\p{Script=Latin}/u],
  ["Deva", /\p{Script=Devanagari}/u],
  ["Beng", /\p{Script=Bengali}/u],
  ["Taml", /\p{Script=Tamil}/u],
  ["Telu", /\p{Script=Telugu}/u],
  ["Gujr", /\p{Script=Gujarati}/u],
  ["Knda", /\p{Script=Kannada}/u],
  ["Mlym", /\p{Script=Malayalam}/u],
  ["Orya", /\p{Script=Oriya}/u],
  ["Guru", /\p{Script=Gurmukhi}/u],
  ["Arab", /\p{Script=Arabic}/u]
];

const LETTER = /\p{L}/u;
const ASSAMESE_LETTERS = /[ৰৱ]/u;
const ASSAMESE = "as";

export const languageCodeShape: Shape<string> = matching(/^[a-z]{2,3}$/, "a language code");

export const answerLanguageShape: Shape<AnswerLanguage> = object<AnswerLanguage>({
  code: languageCodeShape,
  label: text,
  autonym: text,
  script: matching(/^[A-Z][a-z]{3}$/, "a script code"),
  direction: oneOf(["ltr", "rtl"] as const),
  words: optional(interfaceWordsShape)
});

export function answerLanguagesOf(raw: unknown): AnswerLanguage[] {
  if (raw === undefined || raw === null) return [ENGLISH];
  try {
    const languages = parseShape(list(answerLanguageShape, 1), raw);
    return languages.some((language) => language.code === ENGLISH.code) ? languages : [ENGLISH, ...languages];
  } catch (error) {
    if (!(error instanceof ShapeError)) throw error;
    console.error(new ShapeError(`answers/config languages.${error.path}`, error.expected));
    return [ENGLISH];
  }
}

export function scriptOf(value: string): string | null {
  const counts = new Map<string, number>();
  for (const char of value) {
    if (!LETTER.test(char)) continue;
    const found = SCRIPT_LETTERS.find(([, pattern]) => pattern.test(char));
    if (found) counts.set(found[0], (counts.get(found[0]) ?? 0) + 1);
  }
  let best: string | null = null;
  for (const [script] of SCRIPT_LETTERS) {
    const count = counts.get(script) ?? 0;
    if (count > 0 && (best === null || count > (counts.get(best) ?? 0))) best = script;
  }
  return best;
}

export function detectedLanguage(question: string, languages: AnswerLanguage[]): AnswerLanguage | null {
  const script = scriptOf(question);
  if (!script) return null;
  const candidates = languages.filter((language) => language.script === script);
  if (script === "Beng" && ASSAMESE_LETTERS.test(question)) {
    return candidates.find((language) => language.code === ASSAMESE) ?? candidates[0] ?? null;
  }
  return candidates[0] ?? null;
}

export function englishOf(languages: AnswerLanguage[]): AnswerLanguage {
  return languages.find((language) => language.code === ENGLISH.code) ?? ENGLISH;
}

export function languageFor(code: string, languages: AnswerLanguage[]): AnswerLanguage {
  return languages.find((language) => language.code === code) ?? englishOf(languages);
}

export function resolvedLanguage(choice: string, question: string, languages: AnswerLanguage[]): AnswerLanguage {
  if (choice !== AUTO_LANGUAGE) return languageFor(choice, languages);
  return detectedLanguage(question, languages) ?? englishOf(languages);
}

export function languageOptions(languages: AnswerLanguage[], detected: AnswerLanguage): LanguageOption[] {
  return [
    { value: AUTO_LANGUAGE, label: `Auto · ${detected.autonym}` },
    ...languages.map((language) =>
      language.autonym === language.label ? { value: language.code, label: language.label } : { value: language.code, label: language.autonym, hint: language.label }
    )
  ];
}

export function textAttributes(language: AnswerLanguage): TextAttributes {
  return { lang: language.code, dir: language.direction };
}

export function attributesForText(value: string, language: AnswerLanguage | null): TextAttributes {
  if (language && scriptOf(value) === language.script) return textAttributes(language);
  return scriptOf(value) === "Latn" ? ENGLISH_TEXT : { dir: "auto" };
}

export function sentenceView(sentence: AnswerSentence, language: AnswerLanguage | null, original: boolean): ShownText {
  if (!sentence.translated || sentence.original === undefined) return { text: sentence.text, ...ENGLISH_TEXT };
  if (original) return { text: sentence.original, ...ENGLISH_TEXT };
  return { text: sentence.text, ...(language ? textAttributes(language) : { dir: "auto" }) };
}

export function headingView(section: AnswerSection, language: AnswerLanguage | null, original: boolean): ShownText {
  if (section.original === undefined) return { text: section.heading, ...ENGLISH_TEXT };
  if (original) return { text: section.original, ...ENGLISH_TEXT };
  return { text: section.heading, ...(language ? textAttributes(language) : { dir: "auto" }) };
}

export function paragraphAttributes(section: AnswerSection, language: AnswerLanguage | null, original: boolean): TextAttributes {
  const translated = section.sentences.some((sentence) => sentence.translated);
  if (original || !translated) return ENGLISH_TEXT;
  return language ? textAttributes(language) : { dir: "auto" };
}

export function hasTranslation(sections: AnswerSection[]): boolean {
  return sections.some((section) => section.original !== undefined || section.sentences.some((sentence) => sentence.translated));
}
