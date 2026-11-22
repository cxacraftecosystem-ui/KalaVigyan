import { readFile } from "node:fs/promises";

import { expect, type Locator, type Page } from "@playwright/test";

import { LESSON_FORMATS, LESSONS_PATH, type LessonFormat } from "@/lib/lessonContract";
import { CITATION_FORMAT_LABEL, CITATION_FORMAT_ORDER } from "@/lib/lessonView";
import { explainerHref } from "@/lib/savedView";

import type { AnswerRecord, SourceRecord } from "./answers";
import { settle } from "./capture";
import { clip } from "./checks";
import { citationFileProblems, htmlDeckProblems, pdfProblems, pptxProblems, type CitedSource } from "./exportFiles";

export const PROOF_LABEL = "English";
const FILE_WAIT_MS = 120_000;
const SCREEN_WAIT_MS = 60_000;

export type ExportProof = {
  label: string;
  explainerId: string | null;
  lessonExplainerId: string | null;
  files: string[];
  problems: string[];
  notes: string[];
};

type Saved = { name: string; body: Buffer };
type FileCheck = (where: string, file: Buffer, sources: readonly CitedSource[]) => string[];

const LESSON_FILE_CHECKS: Record<LessonFormat, { where: string; check: FileCheck }> = {
  html: { where: "the lesson deck", check: htmlDeckProblems },
  pptx: { where: "the lesson PPTX", check: pptxProblems },
  pdf: { where: "the lesson PDF", check: pdfProblems }
};

async function saved(page: Page, start: () => Promise<void>): Promise<Saved> {
  const [download] = await Promise.all([page.waitForEvent("download", { timeout: FILE_WAIT_MS }), start()]);
  const path = await download.path();
  return { name: download.suggestedFilename(), body: await readFile(path) };
}

export async function attempt(proof: ExportProof, what: string, work: () => Promise<string[]>): Promise<void> {
  try {
    proof.problems.push(...(await work()));
  } catch (error) {
    proof.problems.push(`${what}: ${clip(error instanceof Error ? (error.message.split("\n")[0] ?? error.message) : String(error))}`);
  }
}

async function fromMenu(page: Page, menu: Locator, item: string): Promise<Saved> {
  return saved(page, async () => {
    await menu.getByRole("button", { name: "Export", exact: true }).click();
    await page.getByTestId("explainer-export-items").getByRole("button", { name: item, exact: true }).click();
  });
}

async function explainerFiles(page: Page, proof: ExportProof, sources: readonly CitedSource[]): Promise<void> {
  const menu = page.getByTestId("explainer-export");
  await expect(menu).toBeVisible({ timeout: SCREEN_WAIT_MS });
  await attempt(proof, "the report PDF", async () => {
    const file = await fromMenu(page, menu, "Report as PDF");
    proof.files.push(file.name);
    return pdfProblems("the report PDF", file.body, sources);
  });
  for (const format of CITATION_FORMAT_ORDER) {
    await attempt(proof, `the ${format} citations`, async () => {
      const file = await fromMenu(page, menu, CITATION_FORMAT_LABEL[format]);
      proof.files.push(file.name);
      return citationFileProblems(format, file.body.toString("utf8"), sources);
    });
  }
}

async function builtLesson(page: Page): Promise<{ sources: SourceRecord[] }> {
  await page.getByTestId("make-lesson").click();
  await expect(page.getByTestId("lesson-builder")).toBeVisible({ timeout: SCREEN_WAIT_MS });
  const answered = page.waitForResponse(
    (response) => new URL(response.url()).pathname === `/api${LESSONS_PATH}` && response.request().method() === "POST",
    { timeout: FILE_WAIT_MS }
  );
  await page.getByTestId("lesson-build").click();
  const response = await answered;
  if (!response.ok()) throw new Error(`building the lesson answered ${response.status()}`);
  await expect(page.getByTestId("lesson-files")).toBeVisible({ timeout: SCREEN_WAIT_MS });
  return (await response.json()) as { sources: SourceRecord[] };
}

export function lessonSourceProblems(packSources: readonly SourceRecord[], explainerSources: readonly SourceRecord[]): string[] {
  const known = new Set(explainerSources.map((source) => source.id));
  const foreign = packSources.filter((source) => !known.has(source.id));
  return [
    ...(packSources.length === 0 ? ["the lesson pack cites no source"] : []),
    ...(foreign.length > 0 ? [`the lesson pack cites ${foreign.length} sources the explainer does not`] : [])
  ];
}

export async function lessonFiles(page: Page, proof: ExportProof, explainerSources: readonly SourceRecord[]): Promise<void> {
  const pack = await builtLesson(page);
  proof.problems.push(...lessonSourceProblems(pack.sources, explainerSources));
  for (const format of LESSON_FORMATS) {
    const { where, check } = LESSON_FILE_CHECKS[format];
    await attempt(proof, where, async () => {
      const file = await saved(page, () => page.getByTestId("lesson-files").locator(`[data-format="${format}"]`).click());
      proof.files.push(file.name);
      return check(where, file.body, pack.sources);
    });
  }
}

export async function proveExports(page: Page, records: readonly AnswerRecord[]): Promise<ExportProof> {
  const record = records.find((entry) => entry.label === PROOF_LABEL && entry.endedWith === "done" && entry.answerId);
  const proof: ExportProof = { label: PROOF_LABEL, explainerId: record?.answerId ?? null, lessonExplainerId: null, files: [], problems: [], notes: [] };
  if (!record?.answerId) {
    proof.problems.push(`the ${PROOF_LABEL} known answer did not finish, so nothing was exported`);
    return proof;
  }
  const explainerId = record.answerId;
  await attempt(proof, "the explainer's exports", async () => {
    await page.goto(explainerHref(explainerId), { waitUntil: "domcontentloaded" });
    await settle(page);
    await explainerFiles(page, proof, record.sources);
    return [];
  });
  return proof;
}
