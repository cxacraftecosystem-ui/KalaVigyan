import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  answerLanguagesOf,
  AUTO_LANGUAGE,
  detectedLanguage,
  ENGLISH,
  hasTranslation,
  headingView,
  languageOptions,
  paragraphAttributes,
  resolvedLanguage,
  scriptOf,
  sentenceView,
  type AnswerLanguage
} from "@/lib/answerLanguages";
import { answerSentenceShape, answerStatusShape } from "@/lib/answerShapes";
import { explainerShape } from "@/lib/explainerContract";
import { askingExplainer, reduceExplainer } from "@/lib/explainerState";
import { hasTranslatedText } from "@/lib/explainerView";
import { DEFAULT_PREFERENCES, normalizePreferences, PREFERENCES_KEY } from "@/lib/preferences";
import { parseShape } from "@/lib/shape";
import type { AnswerSection, AnswerSentence, Citation } from "@/lib/types";

const ROOT = join(__dirname, "..", "..");
const read = (...parts: string[]) => readFileSync(join(ROOT, ...parts), "utf8");

const language = (code: string, label: string, autonym: string, script: string, direction: "ltr" | "rtl" = "ltr"): AnswerLanguage => ({
  code,
  label,
  autonym,
  script,
  direction
});

const HINDI = language("hi", "Hindi", "हिन्दी", "Deva");
const MARATHI = language("mr", "Marathi", "मराठी", "Deva");
const BENGALI = language("bn", "Bengali", "বাংলা", "Beng");
const ASSAMESE = language("as", "Assamese", "অসমীয়া", "Beng");
const TAMIL = language("ta", "Tamil", "தமிழ்", "Taml");
const URDU = language("ur", "Urdu", "اردو", "Arab", "rtl");
const OFFERED = [ENGLISH, HINDI, BENGALI, TAMIL, MARATHI, ASSAMESE, URDU];

const citation: Citation = {
  id: "c1",
  claimId: "claim-1",
  sourceId: "s1",
  quote: "alum forms a lake with alizarin",
  locator: null,
  context: null,
  evidence: "QUOTED",
  level: "PROVISIONAL"
};

const sentence = (text: string, original?: string): AnswerSentence =>
  original === undefined
    ? { id: "s1.1", text, level: "PROVISIONAL", citations: [citation] }
    : { id: "s1.1", text, level: "PROVISIONAL", citations: [citation], translated: true, original };

const BACKEND_LANGUAGES = [...read("backend", "app", "research", "vocabulary.py").matchAll(/"([a-z]{2,3})": AnswerLanguageSpec\("([^"]+)", "([^"]+)", "([A-Za-z]{4})"\)/g)].map(
  ([, code, label, autonym, script]) => ({ code, label, autonym, script })
);

test("the backend offers English and twelve Indian languages", () => {
  expect(BACKEND_LANGUAGES.map((entry) => entry.code)).toEqual(["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "or", "pa", "as", "ur"]);
});

test("every offered language's own name is detected as its script", () => {
  for (const entry of BACKEND_LANGUAGES) expect(scriptOf(entry.autonym), entry.code).toBe(entry.script);
});

test("every non-Latin script of the offered languages has a local Noto Sans face and a reading face", () => {
  const fonts = read("frontend", "app", "scriptFonts.ts");
  const reading = read("frontend", "app", "readingScriptFonts.ts");
  const readingFiles: Record<string, string> = {
    Deva: "noto-serif-devanagari-var.woff2",
    Beng: "noto-serif-bengali-var.woff2",
    Taml: "noto-serif-tamil-var.woff2",
    Telu: "noto-serif-telugu-var.woff2",
    Gujr: "noto-serif-gujarati-var.woff2",
    Knda: "noto-serif-kannada-var.woff2",
    Mlym: "noto-serif-malayalam-var.woff2",
    Orya: "noto-serif-oriya-var.woff2",
    Guru: "noto-serif-gurmukhi-var.woff2",
    Arab: "noto-nastaliq-urdu-var.woff2"
  };
  const files: Record<string, string> = {
    Deva: "noto-sans-devanagari-var.woff2",
    Beng: "noto-sans-bengali-var.woff2",
    Taml: "noto-sans-tamil-var.woff2",
    Telu: "noto-sans-telugu-var.woff2",
    Gujr: "noto-sans-gujarati-var.woff2",
    Knda: "noto-sans-kannada-var.woff2",
    Mlym: "noto-sans-malayalam-var.woff2",
    Orya: "noto-sans-oriya-var.woff2",
    Guru: "noto-sans-gurmukhi-var.woff2",
    Arab: "noto-sans-arabic-var.woff2"
  };
  for (const script of new Set(BACKEND_LANGUAGES.map((entry) => entry.script).filter((script) => script !== "Latn"))) {
    expect(fonts, script).toContain(`src: "../fonts/${files[script]}"`);
    expect(reading, script).toContain(`src: "../fonts/${readingFiles[script]}"`);
    for (const file of [files[script], readingFiles[script]]) expect(readFileSync(join(ROOT, "frontend", "fonts", file)).subarray(0, 4).toString("latin1"), file).toBe("wOF2");
  }
  for (const faces of [fonts, reading]) expect(faces.match(/preload: false/g)).toHaveLength(faces.match(/localFont\(/g)?.length ?? -1);
  expect(read("frontend", "app", "layout.tsx")).toContain("${SCRIPT_FONT_VARIABLES} ${READING_SCRIPT_FONT_VARIABLES}");
});

test("the question's script picks the answer language", () => {
  expect(detectedLanguage("अजरख को फिटकरी लाल क्यों रखती है?", OFFERED)).toEqual(HINDI);
  expect(detectedLanguage("আজরখে ফিটকিরি কেন লাগে?", OFFERED)).toEqual(BENGALI);
  expect(detectedLanguage("অজৰখত ফিটকিৰি কিয় লাগে?", OFFERED)).toEqual(ASSAMESE);
  expect(detectedLanguage("அஜ்ரக் ஏன் சிவப்பு?", OFFERED)).toEqual(TAMIL);
  expect(detectedLanguage("اجرک میں پھٹکری کیوں؟", OFFERED)).toEqual(URDU);
  expect(detectedLanguage("Why does alum keep Ajrakh red?", OFFERED)).toEqual(ENGLISH);
  expect(detectedLanguage("1200 / 60?", OFFERED)).toBeNull();
  expect(detectedLanguage("Ajrakh को फिटकरी क्यों?", OFFERED)).toEqual(HINDI);
});

test("a chosen language wins over the question's script, and auto follows it", () => {
  expect(resolvedLanguage("ta", "Why alum?", OFFERED)).toEqual(TAMIL);
  expect(resolvedLanguage(AUTO_LANGUAGE, "अजरख क्यों?", OFFERED)).toEqual(HINDI);
  expect(resolvedLanguage(AUTO_LANGUAGE, "Why alum?", OFFERED)).toEqual(ENGLISH);
  expect(resolvedLanguage("fr", "Why alum?", OFFERED)).toEqual(ENGLISH);
});

test("the picker lists auto first, then each language by its own name", () => {
  expect(languageOptions([ENGLISH, HINDI, URDU], HINDI)).toEqual([
    { value: "auto", label: "Auto · हिन्दी" },
    { value: "en", label: "English" },
    { value: "hi", label: "हिन्दी", hint: "Hindi" },
    { value: "ur", label: "اردو", hint: "Urdu" }
  ]);
});

test("the choice is remembered in the existing preferences key", () => {
  expect(PREFERENCES_KEY).toBe("kalavigyan_preferences");
  expect(DEFAULT_PREFERENCES.answerLanguage).toBe("auto");
  expect(normalizePreferences({ theme: "dark", answerLanguage: "ta" }).answerLanguage).toBe("ta");
  expect(normalizePreferences({ answerLanguage: "Hindi" }).answerLanguage).toBe("auto");
  expect(normalizePreferences({}).answerLanguage).toBe("auto");
  expect(read("frontend", "components", "ask", "useAskScreen.ts")).toContain("update({ answerLanguage: next })");
});

test("the config's languages are checked, and English is always offered", () => {
  expect(answerLanguagesOf([URDU])).toEqual([ENGLISH, URDU]);
  expect(answerLanguagesOf(undefined)).toEqual([ENGLISH]);
  const errors: unknown[] = [];
  const original = console.error;
  console.error = (error: unknown) => errors.push(error);
  try {
    expect(answerLanguagesOf([{ code: "hi", label: "Hindi" }])).toEqual([ENGLISH]);
  } finally {
    console.error = original;
  }
  expect(errors).toHaveLength(1);
});

test("an Urdu sentence renders right to left in Urdu, and its original left to right in English", () => {
  const urdu = sentence("اسے ۶۰ °C تک گرم کیا گیا۔", "It was heated to 60 °C.");
  expect(sentenceView(urdu, URDU, false)).toEqual({ text: "اسے ۶۰ °C تک گرم کیا گیا۔", lang: "ur", dir: "rtl" });
  expect(sentenceView(urdu, URDU, true)).toEqual({ text: "It was heated to 60 °C.", lang: "en", dir: "ltr" });
  expect(sentenceView(sentence("The lake withstood 20 washes."), URDU, false)).toEqual({ text: "The lake withstood 20 washes.", lang: "en", dir: "ltr" });
  const section: AnswerSection = { id: "s1", heading: "رنگ", original: "Colour", sentences: [urdu] };
  expect(headingView(section, URDU, false)).toEqual({ text: "رنگ", lang: "ur", dir: "rtl" });
  expect(headingView(section, URDU, true)).toEqual({ text: "Colour", lang: "en", dir: "ltr" });
  expect(paragraphAttributes(section, URDU, false)).toEqual({ lang: "ur", dir: "rtl" });
  expect(paragraphAttributes({ ...section, sentences: [sentence("Plain.")] }, URDU, false)).toEqual({ lang: "en", dir: "ltr" });
  expect(hasTranslation([section])).toBe(true);
  expect(hasTranslation([{ id: "s2", heading: "Colour", sentences: [sentence("Plain.")] }])).toBe(false);
});

test("the answer renders every sentence and heading with its own lang and dir", () => {
  const block = read("frontend", "components", "answer", "AnswerSectionBlock.tsx");
  expect(block).toContain("<span lang={shown.lang} dir={shown.dir}>");
  expect(block).toContain("lang={heading.lang} dir={heading.dir}");
  expect(block).toContain("lang={paragraph.lang} dir={paragraph.dir}");
  expect(read("frontend", "components", "answer", "ExplainerSentence.tsx")).toContain("<span lang={shown.lang} dir={shown.dir}>");
  expect(read("frontend", "components", "answer", "ExplainerSectionView.tsx")).toContain("lang={heading.lang} dir={heading.dir}");
  expect(read("frontend", "components", "answer", "ProseBlockView.tsx")).toContain("lang={paragraph.lang} dir={paragraph.dir}");
  const header = read("frontend", "components", "answer", "ExplainerHeader.tsx");
  expect(header).toContain('label="Answer text"');
  expect(header).toContain("{ value: ORIGINAL_TEXT, label: ENGLISH.label }");
});

test("translated sentences and headings keep their originals through the stream", () => {
  let state = askingExplainer("अजरख क्यों?", "hi");
  expect(state.language).toBe("hi");
  state = reduceExplainer(state, { type: "section_started", data: { id: "s1", discipline: "MATERIALS", title: "सामग्री", original: "Materials and tools", order: 1, state: "WRITING" } });
  const translated = { ...sentence("फिटकरी मॉर्डेंट है।", "Alum is the mordant."), terms: [] };
  state = reduceExplainer(state, { type: "block", data: { sectionId: "s1", block: { id: "s1.b1", kind: "prose", version: 1, reuse: null, sentences: [translated] } } });
  expect(state.sections[0].original).toBe("Materials and tools");
  const block = state.sections[0].blocks[0];
  expect(block.kind === "prose" ? block.sentences[0].original : null).toBe("Alum is the mordant.");
  expect(hasTranslatedText(state.sections)).toBe(true);
  expect(parseShape(answerSentenceShape, sentence("फिटकरी मॉर्डेंट है।", "Alum is the mordant.")).original).toBe("Alum is the mordant.");
  expect(parseShape(answerStatusShape, { step: "TRANSLATING", message: "Translating the answer into Hindi" }).step).toBe("TRANSLATING");
});

test("the translated golden answer parses with each translated sentence's English and its section's English heading", () => {
  const explainer = parseShape(explainerShape, JSON.parse(read("shared", "explainer.translated.golden.json")));
  const [section] = explainer.sections;
  expect([explainer.understood.language, section.original]).toEqual(["hi", "Why the water matters"]);
  const [prose] = section.blocks;
  const sentences = prose.kind === "prose" ? prose.sentences : [];
  expect(sentences.map((said) => said.translated)).toEqual([true, true, false]);
  expect(sentenceView(sentences[0], HINDI, false)).toMatchObject({ text: sentences[0].text, lang: "hi" });
  expect(sentenceView(sentences[0], HINDI, true).text).toBe("Presence of iron in the water supply dulls and darkens the final result; alum, tin or chrome deposits help brighten colours.");
  expect(sentenceView(sentences[2], HINDI, false).text).toBe(sentences[2].text);
});
