import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { answerRecord, KNOWN_ANSWER_QUESTIONS, knownAnswerOutcome, NO_RIVER_STORY_NOTE, type KnownAnswerQuestion } from "./production/answers";
import { builtBlockNotes } from "./production/builtBlocks";
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

const PHASE_B = JSON.parse(readFileSync(join(SHARED, "explainer.phase-b.golden.json"), "utf8")) as { sections: { blocks: Record<string, unknown>[] }[] };
const CLIMATE = KNOWN_ANSWER_QUESTIONS.find((question) => question.check === "SEASONS") as KnownAnswerQuestion;
const GANGA = KNOWN_ANSWER_QUESTIONS.find((question) => question.check === "RIVER_TIME") as KnownAnswerQuestion;

function phaseB(id: string): Record<string, unknown> {
  return PHASE_B.sections.flatMap((section) => section.blocks).find((found) => found.id === id) as Record<string, unknown>;
}

function recordAt(chunks: { at: number; text: string }[], question: KnownAnswerQuestion) {
  const stream: TappedStream = { url: "/api/answers/stream", body: null, requestedAt: 1_000, respondedAt: 1_100, status: 200, chunks, endedAt: 9_000, failure: null };
  return answerRecord({ question, stream, streamsOpened: 1, clickedAt: 1_000, waited: null });
}

test("the climate question passes only with a seasons block, and each built block's time after its section's first block is noted", () => {
  expect(outcome(prose(), CLIMATE)).toEqual(["no seasons block arrived"]);
  const record = recordAt(
    [
      { at: 1_500, text: prose() },
      { at: 4_700, text: frame("block", { sectionId: "s1", block: { ...phaseB("s3.b1"), id: "s1.b2" } }) },
      { at: 6_000, text: frame("block", { sectionId: "s6", block: phaseB("s6.b1") }) }
    ],
    CLIMATE
  );
  expect(knownAnswerOutcome(record, CLIMATE).problems).toEqual([]);
  expect(builtBlockNotes(record.builtBlocks)).toEqual([
    "The seasons block of section s1 arrived 3.2 s after its section's first block: 1 row (1 timed), no rainfall.",
    "The supply map of section s6 arrived 0.0 s after its section's first block: 3 links, 0 origins pinned."
  ]);
});

test("the Ganga question asks for a Varanasi craft and only notes a missing river story, timing the one that arrives", () => {
  expect(GANGA.craft).toBe("Varanasi-Soft-Stone-Jali-Work");
  const missing = recordAt([{ at: 1_500, text: prose() }], GANGA);
  expect(knownAnswerOutcome(missing, GANGA)).toEqual({ problems: [], notes: [NO_RIVER_STORY_NOTE] });
  const story = recordAt([{ at: 1_500, text: prose() }, { at: 13_500, text: frame("block", { sectionId: "s1", block: { ...phaseB("s1.b1"), id: "s1.b2" } }) }], GANGA);
  expect(knownAnswerOutcome(story, GANGA)).toEqual({ problems: [], notes: [] });
  expect(builtBlockNotes(story.builtBlocks)).toEqual(["The region story of section s1 arrived 12.0 s after its section's first block: 4 steps, the Khari river over 8 reaches."]);
});
