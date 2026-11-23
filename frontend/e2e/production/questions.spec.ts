import { join } from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { explainerHref } from "@/lib/savedView";

import { KNOWN_ANSWER_QUESTIONS, savedLedeProblems, type AnswerRecord } from "./answers";
import { askKnownAnswer } from "./asking";
import { NetworkQuiet, captureScreen, readyForCapture, sightProblems, type Captured } from "./capture";
import { clip } from "./checks";
import { proveExports, type ExportProof } from "./exportProof";
import { answerLanguageProblems } from "./languageChecks";
import { proveLessonPack } from "./lessonProof";
import { ANSWER_WIDTHS, QUESTIONS_SCHEME, QUESTIONS_WIDTH, SCHEMES, contextOptions, runLabel } from "./matrix";
import { passPreviewProtection } from "./preview";
import type { AnswersReport } from "./report";
import { QUESTIONS_TIMEOUT_MS, SCREENSHOT_DIR, baseUrl, credentials, previewBypassToken, questionsRequested, runFileName, runId, runStartedAt, writeReport } from "./run";
import { essayOutcome } from "./screenChecks";
import { ScreenRun } from "./screenRun";
import { signIn } from "./signIn";
import { installStreamTap } from "./streamTap";

const REPORT_NAME = () => runFileName({ subject: "Known Answers", what: "Report", ext: "json" });
const ANSWER_VIEW_TIMEOUT_MS = 60_000;

function unaskedProblem(label: string, error: unknown): string {
  const message = error instanceof Error ? (error.message.split("\n")[0] ?? error.message) : String(error);
  return `${label}: could not ask the question: ${clip(message)}`;
}

async function capturedAnswer(page: Page, network: NetworkQuiet, label: string, index: number): Promise<Captured> {
  const subject = `${runLabel(QUESTIONS_WIDTH, QUESTIONS_SCHEME)} Question ${label}`;
  const shot = runFileName({ subject, what: "Snapshot", ext: "png", sequence: String(index + 1).padStart(2, "0") });
  const ready = await readyForCapture(page, network);
  const seen = await sightProblems(page, QUESTIONS_SCHEME);
  const captured = await captureScreen(page, join(SCREENSHOT_DIR, shot));
  return { problems: [...ready, ...seen, ...captured.problems], notes: captured.notes };
}

async function keepFirstAnswer(page: Page, records: readonly AnswerRecord[]): Promise<string[]> {
  const first = records.find((record) => record.answerId !== null);
  if (!first?.answerId) return [];
  try {
    await page.goto(explainerHref(first.answerId), { waitUntil: "domcontentloaded" });
    const save = page.getByTestId("save-answer");
    await expect(save).toBeEnabled({ timeout: ANSWER_VIEW_TIMEOUT_MS });
    if ((await save.getAttribute("aria-pressed")) !== "true") await save.click();
    await expect(save).toHaveAttribute("aria-pressed", "true", { timeout: ANSWER_VIEW_TIMEOUT_MS });
    return [];
  } catch (error) {
    return [`${first.label}: could not save the answer, so the screens runs have no essay to open: ${clip(String(error))}`];
  }
}

async function answerViews(browser: Browser, page: Page, records: readonly AnswerRecord[], role: string): Promise<string[]> {
  const answered = records.filter((record): record is AnswerRecord & { answerId: string } => record.answerId !== null);
  if (answered.length === 0) return [];
  const storageState = await page.context().storageState();
  const problems: string[] = [];
  for (const width of ANSWER_WIDTHS) {
    for (const scheme of SCHEMES) {
      const context = await browser.newContext({ ...contextOptions(width, scheme), baseURL: baseUrl(), storageState });
      try {
        const view = await context.newPage();
        const run = new ScreenRun(view, `${runLabel(width, scheme)} answers`, { scheme });
        await run.watch();
        run.markSignedIn(role);
        for (const record of answered) {
          await run.visit(`Question ${record.label}`, explainerHref(record.answerId), async () => {
            await expect(view.getByTestId("answer-view")).toBeVisible({ timeout: ANSWER_VIEW_TIMEOUT_MS });
            const essay = await essayOutcome(view);
            const lede = savedLedeProblems(record.lede, await view.getByTestId("answer-lede").getByTestId("answer-sentence").count());
            const asked = KNOWN_ANSWER_QUESTIONS.find((question) => question.label === record.label);
            return [...lede, ...essay, ...(asked ? await answerLanguageProblems(view, asked) : [])];
          });
        }
        run.write();
        problems.push(...run.problemLines());
      } finally {
        await context.close();
      }
    }
  }
  return problems;
}

test("seven known-answer questions: the mordant in English, Hindi and Urdu, Kachchh's water, the cloth's materials and its history at Detailed depth, and indigo's generated explainer at Expert depth", async ({ page, browser }) => {
  test.skip(!questionsRequested(), "Dispatch with questions=true to ask the known-answer questions.");
  test.setTimeout(QUESTIONS_TIMEOUT_MS);
  await passPreviewProtection(page.context(), baseUrl(), previewBypassToken());
  await installStreamTap(page);
  const network = new NetworkQuiet(page);
  const user = await signIn(page, credentials());
  const records: AnswerRecord[] = [];
  const unasked: string[] = [];
  let exports: ExportProof | null = null;
  const write = () => {
    const report: AnswersReport = {
      kind: "answers",
      baseUrl: baseUrl(),
      runId: runId(),
      startedAt: runStartedAt(),
      role: user.role,
      problemCount: records.reduce((sum, record) => sum + record.problems.length, 0) + unasked.length + (exports?.problems.length ?? 0),
      unasked,
      questions: records,
      exports
    };
    writeReport(REPORT_NAME(), report);
  };

  for (const [index, question] of KNOWN_ANSWER_QUESTIONS.entries()) {
    const record = await askKnownAnswer(page, question).catch((error: unknown) => {
      unasked.push(unaskedProblem(question.label, error));
      return null;
    });
    if (record) {
      records.push(record);
      const seen = await capturedAnswer(page, network, question.label, index).catch(
        (error: unknown): Captured => ({ problems: [`could not capture the answer: ${clip(String(error))}`], notes: [] })
      );
      record.problems.push(...seen.problems);
      record.notes.push(...seen.notes);
    }
    write();
  }
  exports = await proveExports(page, records);
  write();
  await proveLessonPack(browser, exports);
  write();
  const kept = await keepFirstAnswer(page, records);
  const viewed = await answerViews(browser, page, records, user.role);

  const exported = exports.problems.map((problem) => `Exports: ${problem}`);
  const problems = [...unasked, ...records.flatMap((record) => record.problems.map((problem) => `${record.label}: ${problem}`)), ...exported, ...kept, ...viewed];
  expect(problems.length, problems.join("\n")).toBe(0);
});
