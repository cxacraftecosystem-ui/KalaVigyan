import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AnswerProvenance } from "@/components/answer/AnswerProvenance";
import { answeredOn, answerProvenance } from "@/lib/answerEssay";
import { answerLanguagesOf, type AnswerLanguage } from "@/lib/answerLanguages";
import { ACTIONS_ENGLISH, ACTIONS_KEY, ESSAY_WORD_GROUPS, PROVENANCE_ENGLISH, PROVENANCE_KEY, filled, wordedDate, wordedIn, type InterfaceWord } from "@/lib/interfaceWords";

const WORDS_DIR = join(__dirname, "..", "..", "backend", "app", "data", "interface_words");
const URDU_PROVENANCE: InterfaceWord[] = [
  { key: PROVENANCE_KEY, english: "Answer", text: "جواب" },
  { key: PROVENANCE_KEY, english: "Drawn from {count} source", text: "{count} ماخذ سے" },
  { key: PROVENANCE_KEY, english: "Drawn from {count} sources", text: "{count} ماخذوں سے" },
  { key: PROVENANCE_KEY, english: "Answered {date}", text: "جواب دیا گیا {date}" }
];
const URDU: AnswerLanguage = { code: "ur", label: "Urdu", autonym: "اردو", script: "Arab", direction: "rtl", words: URDU_PROVENANCE };
const SEVEN = Array.from({ length: 7 }, () => ({ reliability: null }));

type WordsFile = { language: string; words: { key: string; english: string; review: unknown }[] };

function wordsFiles(): WordsFile[] {
  return readdirSync(WORDS_DIR)
    .filter((name) => name.endsWith(".json"))
    .map((name) => JSON.parse(readFileSync(join(WORDS_DIR, name), "utf8")) as WordsFile);
}

test("a group of interface words is shown in a language only when every word of it is reviewed", () => {
  const shown = wordedIn(URDU, PROVENANCE_KEY, PROVENANCE_ENGLISH);
  expect(shown.language).toBe(URDU);
  expect(shown.words).toEqual({ answer: "جواب", oneSource: "{count} ماخذ سے", sources: "{count} ماخذوں سے", answered: "جواب دیا گیا {date}" });
  const partial = { ...URDU, words: URDU_PROVENANCE.slice(1) };
  expect(wordedIn(partial, PROVENANCE_KEY, PROVENANCE_ENGLISH)).toEqual({ words: PROVENANCE_ENGLISH, language: null });
  expect(wordedIn(URDU, ACTIONS_KEY, ACTIONS_ENGLISH)).toEqual({ words: ACTIONS_ENGLISH, language: null });
  expect(wordedIn(null, PROVENANCE_KEY, PROVENANCE_ENGLISH).language).toBeNull();
});

test("a word whose english changed since its review is not shown", () => {
  const stale = { ...URDU, words: URDU_PROVENANCE.map((word) => (word.english === "Answer" ? { ...word, english: "The answer" } : word)) };
  expect(wordedIn(stale, PROVENANCE_KEY, PROVENANCE_ENGLISH).language).toBeNull();
});

test("placeholders are filled by name and the date keeps western digits", () => {
  expect(filled("{count} ماخذوں سے", { count: 7 })).toBe("7 ماخذوں سے");
  expect(filled("Answered {date}", {})).toBe("Answered {date}");
  const urdu = wordedDate("2026-11-18T06:00:00Z", URDU);
  expect(urdu).toContain("18");
  expect(urdu).toContain("2026");
  expect(urdu).toContain("نومبر");
  expect(wordedDate("2026-11-18T06:00:00Z", null)).toBe("18 Nov 2026");
});

test("the provenance says its sources and its day in the reviewed words of the answer's language", () => {
  const worded = wordedIn(URDU, PROVENANCE_KEY, PROVENANCE_ENGLISH);
  expect(answerProvenance(SEVEN, worded.words).sources).toBe("7 ماخذوں سے");
  expect(answerProvenance(SEVEN).sources).toBe("Drawn from 7 sources");
  expect(answeredOn("2026-11-18T06:00:00Z", worded)).toMatch(/^جواب دیا گیا 18 /);
  expect(answeredOn("2026-11-18T06:00:00Z")).toBe("Answered 18 Nov 2026");
});

test("the provenance rail marks its words with their language, script and the interface face", () => {
  const facts = { sources: [], craft: null, answeredAt: "2026-11-18T06:00:00Z" };
  const urdu = renderToStaticMarkup(createElement(AnswerProvenance, { facts: { ...facts, language: URDU } }));
  expect(urdu).toContain('<span lang="ur" dir="rtl" data-script="Arab" class="ui kicker text-ink-1">جواب</span>');
  const english = renderToStaticMarkup(createElement(AnswerProvenance, { facts: { ...facts, language: null } }));
  expect(english).toContain('<span class="kicker text-ink-1">Answer</span>');
  expect(english).not.toContain("data-script");
});

test("the config's languages carry their reviewed words, and a language without them still parses", () => {
  const [english, urdu] = answerLanguagesOf([{ code: "en", label: "English", autonym: "English", script: "Latn", direction: "ltr" }, URDU]);
  expect(english.words).toBeUndefined();
  expect(urdu.words).toEqual(URDU_PROVENANCE);
});

test("every essay word the backend keeps translates an english word this web shows", () => {
  const shown = new Set(ESSAY_WORD_GROUPS.flatMap((group) => Object.values(group.english).map((english) => `${group.key}\u0000${english}`)));
  const files = wordsFiles();
  expect(files.length).toBeGreaterThan(0);
  for (const file of files) {
    for (const word of file.words.filter((entry) => entry.key.startsWith("essay."))) {
      expect(shown.has(`${word.key}\u0000${word.english}`), `${file.language}: ${word.key} ${word.english}`).toBe(true);
    }
  }
});
