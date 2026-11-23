import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { answerRecord, KNOWN_ANSWER_QUESTIONS, knownAnswerOutcome, type KnownAnswerQuestion } from "./production/answers";
import type { TappedStream } from "./production/streamTap";

const SHARED = join(__dirname, "..", "..", "shared");
const PHASE_C = JSON.parse(readFileSync(join(SHARED, "explainer.phase-c.golden.json"), "utf8")) as { sections: { blocks: Record<string, unknown>[] }[] };
const CITATION = { id: "c1", claimId: "k1", sourceId: "s1", quote: "alum", locator: null, context: null, evidence: "QUOTED", level: "PROVISIONAL" };
const MATERIALS = KNOWN_ANSWER_QUESTIONS.find((question) => question.check === "ZOOM_STORY") as KnownAnswerQuestion;
const HISTORY = KNOWN_ANSWER_QUESTIONS.find((question) => question.check === "TIMELINE_MAP") as KnownAnswerQuestion;

function frame(name: string, data: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}

function golden(id: string): Record<string, unknown> {
  return PHASE_C.sections.flatMap((section) => section.blocks).find((found) => found.id === id) as Record<string, unknown>;
}

function prose(): string {
  const sentence = { id: "s1.b1.1", text: "Alum is the mordant.", level: "PROVISIONAL", citations: [CITATION], terms: [] };
  return frame("block", { sectionId: "s1", block: { id: "s1.b1", kind: "prose", version: 1, reuse: null, sentences: [sentence] } });
}

function outcome(text: string, question: KnownAnswerQuestion): string[] {
  const stream: TappedStream = { url: "/api/answers/stream", body: null, requestedAt: 1_000, respondedAt: 1_100, status: 200, chunks: [{ at: 1_500, text }], endedAt: 2_000, failure: null };
  const record = answerRecord({ question, stream, streamsOpened: 1, clickedAt: 1_000, waited: null });
  return knownAnswerOutcome(record, question).problems;
}

test("the materials question passes only when a zoom story arrives, the history question only with a timeline", () => {
  expect(outcome(prose(), MATERIALS)).toEqual(["no zoom_story block arrived"]);
  expect(outcome(prose(), HISTORY)).toEqual(["no timeline_map block arrived"]);
  expect(outcome(prose() + frame("block", { sectionId: "s3", block: golden("s3.b1") }), MATERIALS)).toEqual([]);
  expect(outcome(prose() + frame("block", { sectionId: "s4", block: golden("s4.b1") }), HISTORY)).toEqual([]);
  expect([MATERIALS.depth, HISTORY.depth, MATERIALS.language, HISTORY.language]).toEqual(["DETAILED", "DETAILED", "en", "en"]);
});
