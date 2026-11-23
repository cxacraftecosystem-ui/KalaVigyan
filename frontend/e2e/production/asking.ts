import { expect, type Page } from "@playwright/test";

import {
  ANSWER_DEADLINE_MS,
  DEPTH_LABELS,
  STALL_LIMIT_MS,
  answerProblems,
  answerRecord,
  knownAnswerOutcome,
  type AnswerRecord,
  type AskedDepth,
  type KnownAnswerQuestion,
  type WaitOutcome
} from "./answers";
import { settle } from "./capture";
import { answerLanguageProblems, translatedProblems } from "./languageChecks";
import { CRAFT_SLUG, riversLoaded } from "./run";
import { readSandboxFrames, watchSandboxFrames, type SandboxWatch } from "./sandboxWatch";
import { glanceAtTaps, pageNow, readTaps } from "./streamTap";

const POLL_MS = 2_000;
const LAST_STREAM_GRACE_MS = 1_500;
const UI_SETTLE_MS = 30_000;
const AUTO_LANGUAGE = /^Auto\b/;

async function chooseAutoLanguage(page: Page): Promise<void> {
  const picker = page.getByRole("button", { name: "Answer language", exact: true });
  if ((await picker.count()) === 0 || AUTO_LANGUAGE.test((await picker.innerText()).trim())) return;
  await picker.click();
  await page.getByRole("option", { name: AUTO_LANGUAGE }).click();
  await expect(picker).toHaveText(AUTO_LANGUAGE);
}

async function chooseDepth(page: Page, asked: AskedDepth): Promise<void> {
  const depth = page.getByRole("group", { name: "Depth" }).getByRole("button", { name: DEPTH_LABELS[asked], exact: true });
  if ((await depth.getAttribute("aria-pressed")) !== "true") await depth.click();
  await expect(depth).toHaveAttribute("aria-pressed", "true");
}

async function waitForStreamEnd(page: Page, clickedAt: number): Promise<WaitOutcome | null> {
  for (;;) {
    await page.waitForTimeout(POLL_MS);
    const glance = await glanceAtTaps(page, clickedAt);
    if (glance.endedAt !== null) {
      await page.waitForTimeout(LAST_STREAM_GRACE_MS);
      const again = await glanceAtTaps(page, clickedAt);
      if (again.streams === glance.streams && again.endedAt !== null) return null;
      continue;
    }
    if (glance.now - clickedAt > ANSWER_DEADLINE_MS) return "timeout";
    if (glance.lastActivity === null && glance.now - clickedAt > STALL_LIMIT_MS) return "never-started";
    if (glance.lastActivity !== null && glance.now - glance.lastActivity > STALL_LIMIT_MS) return "stalled";
  }
}

async function readPageSentences(page: Page, record: AnswerRecord): Promise<void> {
  const settled = await expect(page.getByTestId("answer-progress"))
    .toHaveCount(0, { timeout: UI_SETTLE_MS })
    .then(() => true)
    .catch(() => false);
  if (!settled) record.problems.push("the page still shows progress after the stream ended");
  const shown = await page
    .getByTestId("answer-view")
    .getByTestId("answer-sentence")
    .evaluateAll((nodes) =>
      nodes.map((node) => ({
        id: node.getAttribute("data-sentence-id"),
        chips: node.querySelectorAll('[data-testid="citation-chip"]').length,
        lede: node.closest('[data-testid="answer-lede"]') !== null
      }))
    );
  const lede = shown.filter((entry) => entry.lede);
  record.pageSentences = shown.length;
  record.pageSentenceIds = shown.every((entry) => entry.id !== null) ? shown.map((entry) => entry.id as string) : null;
  record.pageSentencesWithoutChip = shown.filter((entry) => entry.chips === 0).length;
  record.lede = { ...record.lede, shown: lede.length, shownCited: lede.filter((entry) => entry.chips > 0).length };
}

async function generatedFrames(page: Page, record: AnswerRecord, watch: SandboxWatch, ended: boolean): Promise<void> {
  const frames = ended ? await readSandboxFrames(page) : null;
  record.generatedExplainer = { ...record.generatedExplainer, frames, frameRequests: [...watch.requests], frameRefusals: [...watch.refusals] };
}

async function asked(page: Page, question: KnownAnswerQuestion, watch: SandboxWatch | null): Promise<AnswerRecord> {
  const clickedAt = await pageNow(page);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const waited = await waitForStreamEnd(page, clickedAt);
  const streams = await readTaps(page, clickedAt);
  const record = answerRecord({ question, stream: streams.at(-1) ?? null, streamsOpened: streams.length, clickedAt, waited });
  if (!waited) await readPageSentences(page, record);
  if (watch) await generatedFrames(page, record, watch, waited === null);
  return record;
}

export async function askKnownAnswer(page: Page, question: KnownAnswerQuestion): Promise<AnswerRecord> {
  await page.goto(`/ask?craft=${encodeURIComponent(CRAFT_SLUG)}`, { waitUntil: "domcontentloaded" });
  await settle(page);
  await chooseDepth(page, question.depth);
  await chooseAutoLanguage(page);
  await page.getByLabel("Your question").fill(question.question);
  const watch = question.check === "GENERATED_EXPLAINER" ? await watchSandboxFrames(page) : null;
  try {
    const record = await asked(page, question, watch);
    const options = { riversLoaded: riversLoaded() };
    record.problems.push(...answerProblems(record, question, options), ...translatedProblems(record, question));
    if (record.endedWith === "done") record.problems.push(...(await answerLanguageProblems(page, question)));
    record.notes.push(...knownAnswerOutcome(record, question, options).notes);
    return record;
  } finally {
    await watch?.stop();
  }
}
