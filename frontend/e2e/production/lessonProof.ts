import type { Browser, Page } from "@playwright/test";

import { canBuildLessons, ROLE_LABELS } from "@/lib/permissions";
import { explainerHref } from "@/lib/savedView";
import type { User } from "@/lib/types";

import { KNOWN_ANSWER_QUESTIONS, type KnownAnswerQuestion } from "./answers";
import { askKnownAnswer } from "./asking";
import { settle } from "./capture";
import { attempt, lessonFiles, PROOF_LABEL, type ExportProof } from "./exportProof";
import { QUESTIONS_SCHEME, QUESTIONS_WIDTH, contextOptions } from "./matrix";
import { roleSiteRefusal } from "./preview";
import { baseUrl, roleCredentials, type Credentials } from "./run";
import { signIn } from "./signIn";
import { installStreamTap } from "./streamTap";

export const PROFESSOR_SECRETS = "E2E_PROFESSOR_EMAIL, E2E_PROFESSOR_PASSWORD and E2E_PROFESSOR_TOTP_SECRET";

export type LessonStep = { kind: "prove"; account: Credentials } | { kind: "note"; text: string } | { kind: "problem"; text: string };

export function lessonStep(url: string, account: Credentials | null): LessonStep {
  const refusal = roleSiteRefusal(url);
  if (refusal !== null) return { kind: "note", text: `no lesson pack was built: ${refusal}` };
  if (account === null) {
    return { kind: "problem", text: `no lesson pack was built: set ${PROFESSOR_SECRETS}, since only a Professor builds one (docs/RUNBOOK.md, Professor and Admin E2E accounts)` };
  }
  return { kind: "prove", account };
}

export function professorProblems(user: User): string[] {
  return canBuildLessons(user) ? [] : [`the Professor E2E account signed in as a ${ROLE_LABELS[user.role]}, who may not build a lesson pack`];
}

function proofQuestion(): KnownAnswerQuestion {
  const question = KNOWN_ANSWER_QUESTIONS.find((entry) => entry.label === PROOF_LABEL);
  if (!question) throw new Error(`no ${PROOF_LABEL} known-answer question to build a lesson pack from`);
  return question;
}

async function professorLesson(page: Page, account: Credentials, proof: ExportProof): Promise<string[]> {
  const refused = professorProblems(await signIn(page, account));
  if (refused.length > 0) return refused;
  const record = await askKnownAnswer(page, proofQuestion());
  if (record.endedWith !== "done" || !record.answerId) {
    return [`the Professor's ${PROOF_LABEL} answer ended ${record.endedWith}, so no lesson pack was built`];
  }
  proof.lessonExplainerId = record.answerId;
  await page.goto(explainerHref(record.answerId), { waitUntil: "domcontentloaded" });
  await settle(page);
  await lessonFiles(page, proof, record.sources);
  return [];
}

export async function proveLessonPack(browser: Browser, proof: ExportProof): Promise<void> {
  const step = lessonStep(baseUrl(), roleCredentials("PROFESSOR"));
  if (step.kind === "note") {
    proof.notes.push(step.text);
    return;
  }
  if (step.kind === "problem") {
    proof.problems.push(step.text);
    return;
  }
  const context = await browser.newContext({ ...contextOptions(QUESTIONS_WIDTH, QUESTIONS_SCHEME), baseURL: baseUrl() });
  try {
    const page = await context.newPage();
    await installStreamTap(page);
    await attempt(proof, "the lesson pack", () => professorLesson(page, step.account, proof));
  } finally {
    await context.close();
  }
}
