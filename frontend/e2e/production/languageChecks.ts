import type { Page } from "@playwright/test";

import { LATIN, type AnswerRecord, type KnownAnswerQuestion } from "./answers";

export const RIGHT_TO_LEFT_SCRIPTS: ReadonlySet<string> = new Set(["Arab"]);
export const PROSE_SCRIPTS: Readonly<Record<string, string>> = { ur: "Aran" };
export const PROSE_FACES: Readonly<Record<string, string>> = { Aran: "Noto Nastaliq Urdu" };
export const ANSWER_ROOT = '[data-testid="answer-view"]';

export type DrawnProse = { script: string | null; face: string };
export type DrawnLanguage = { lang: string | null; dir: string | null; direction: string; prose: DrawnProse[]; loadedFaces: string[] };

export function drawnLanguage(options: { root: string; lang: string }): DrawnLanguage | null {
  const root = document.querySelector(options.root);
  if (!root) return null;
  const firstFace = (family: string) => (family.split(",")[0] ?? "").trim().replace(/^["']|["']$/g, "");
  const prose = Array.from(root.querySelectorAll(`p[lang="${options.lang}"]`)).map((node) => ({
    script: node.getAttribute("data-script"),
    face: firstFace(getComputedStyle(node).fontFamily)
  }));
  const loadedFaces = Array.from(document.fonts)
    .filter((face) => face.status === "loaded")
    .map((face) => face.family.replace(/^["']|["']$/g, ""));
  return { lang: root.getAttribute("lang"), dir: root.getAttribute("dir"), direction: getComputedStyle(root).direction, prose, loadedFaces: [...new Set(loadedFaces)] };
}

export function proseScript(question: Pick<KnownAnswerQuestion, "language" | "script">): string {
  return PROSE_SCRIPTS[question.language] ?? question.script;
}

export function translatedProblems(record: Pick<AnswerRecord, "scripts">, question: Pick<KnownAnswerQuestion, "script">): string[] {
  if (question.script === LATIN || record.scripts.translated > 0) return [];
  return [`no sentence arrived translated into the ${question.script} script`];
}

export function languageProblems(drawn: DrawnLanguage | null, question: Pick<KnownAnswerQuestion, "language" | "script">): string[] {
  if (question.script === LATIN) return [];
  if (!drawn) return ["the page draws no answer to read its language from"];
  const problems: string[] = [];
  if (RIGHT_TO_LEFT_SCRIPTS.has(question.script)) {
    if (drawn.lang !== question.language || drawn.dir !== "rtl" || drawn.direction !== "rtl") {
      problems.push(`the answer reads ${drawn.direction} as lang ${drawn.lang ?? "none"} dir ${drawn.dir ?? "none"}, not right to left in ${question.language}`);
    }
  }
  const script = proseScript(question);
  const face = PROSE_FACES[script];
  if (drawn.prose.length === 0) return [...problems, `no paragraph of the answer is marked lang="${question.language}"`];
  const misdrawn = drawn.prose.filter((paragraph) => paragraph.script !== script || (face !== undefined && paragraph.face !== face));
  if (misdrawn.length > 0) problems.push(`${misdrawn.length} of ${drawn.prose.length} paragraphs in ${question.language} are not set in ${face ?? script} (${misdrawn[0].script ?? "no script"}, ${misdrawn[0].face})`);
  if (face !== undefined && !drawn.loadedFaces.includes(face)) problems.push(`the ${face} face never loaded`);
  return problems;
}

export async function answerLanguageProblems(page: Page, question: KnownAnswerQuestion): Promise<string[]> {
  if (question.script === LATIN) return [];
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  return languageProblems(await page.evaluate(drawnLanguage, { root: ANSWER_ROOT, lang: question.language }), question);
}
