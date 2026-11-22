import { expect, test } from "@playwright/test";

import { KNOWN_ANSWER_QUESTIONS, type KnownAnswerQuestion } from "./production/answers";
import { ANSWER_ROOT, drawnLanguage, languageProblems, proseScript, translatedProblems, type DrawnLanguage } from "./production/languageChecks";

function questionOf(label: string): KnownAnswerQuestion {
  const found = KNOWN_ANSWER_QUESTIONS.find((question) => question.label === label);
  if (!found) throw new Error(`no known-answer question is labelled ${label}`);
  return found;
}

const URDU = questionOf("Urdu");
const HINDI = questionOf("Hindi");
const ENGLISH = questionOf("English");
const NASTALIQ = "Noto Nastaliq Urdu";
const DRAWN: DrawnLanguage = { lang: "ur", dir: "rtl", direction: "rtl", prose: [{ script: "Aran", face: NASTALIQ }], loadedFaces: ["Inter", NASTALIQ] };

test("the Urdu known-answer question asks the mordant in Arabic script at Detailed depth", () => {
  expect([URDU.language, URDU.script, URDU.depth, URDU.check]).toEqual(["ur", "Arab", "DETAILED", "MORDANT"]);
  expect(proseScript(URDU)).toBe("Aran");
  expect(proseScript(HINDI)).toBe("Deva");
});

test("an Urdu answer passes when it reads right to left with its prose set in Nastaliq from a loaded face", () => {
  expect(languageProblems(DRAWN, URDU)).toEqual([]);
  expect(languageProblems(null, ENGLISH)).toEqual([]);
});

test("an Urdu answer that reads left to right, or sets its prose in another face, or never loads the face fails", () => {
  expect(languageProblems({ ...DRAWN, dir: null, direction: "ltr" }, URDU)).toEqual(["the answer reads ltr as lang ur dir none, not right to left in ur"]);
  expect(languageProblems({ ...DRAWN, prose: [{ script: "Arab", face: "Noto Sans Arabic" }, ...DRAWN.prose] }, URDU)).toEqual([
    "1 of 2 paragraphs in ur are not set in Noto Nastaliq Urdu (Arab, Noto Sans Arabic)"
  ]);
  expect(languageProblems({ ...DRAWN, loadedFaces: ["Inter"] }, URDU)).toEqual(["the Noto Nastaliq Urdu face never loaded"]);
  expect(languageProblems({ ...DRAWN, prose: [] }, URDU)).toEqual(['no paragraph of the answer is marked lang="ur"']);
  expect(languageProblems(null, URDU)).toEqual(["the page draws no answer to read its language from"]);
});

test("a Hindi answer needs Devanagari prose but no mirrored article", () => {
  const hindi: DrawnLanguage = { lang: null, dir: null, direction: "ltr", prose: [{ script: "Deva", face: "Noto Serif Devanagari" }], loadedFaces: [] };
  expect(languageProblems(hindi, HINDI)).toEqual([]);
  expect(languageProblems({ ...hindi, prose: [{ script: null, face: "Inter" }] }, HINDI)).toEqual(["1 of 1 paragraphs in hi are not set in Deva (no script, Inter)"]);
});

test("an answer in another script with no translated sentence fails", () => {
  const none = { scripts: { translated: 0, englishFallback: 4, other: 0 } };
  expect(translatedProblems(none, URDU)).toEqual(["no sentence arrived translated into the Arab script"]);
  expect(translatedProblems({ scripts: { ...none.scripts, translated: 2 } }, URDU)).toEqual([]);
  expect(translatedProblems(none, ENGLISH)).toEqual([]);
});

test("the page is read for its direction, its prose's script and face, and the faces it loaded", async ({ page }) => {
  await page.setContent(
    `<article data-testid="answer-view" lang="ur" dir="rtl"><p lang="ur" dir="rtl" data-script="Aran" style="font-family: 'Noto Nastaliq Urdu', serif">پھٹکری رنگ پکا کرتی ہے۔</p><p lang="en">Alum.</p></article>`
  );
  expect(await page.evaluate(drawnLanguage, { root: ANSWER_ROOT, lang: "ur" })).toEqual({
    lang: "ur",
    dir: "rtl",
    direction: "rtl",
    prose: [{ script: "Aran", face: NASTALIQ }],
    loadedFaces: []
  });
});
