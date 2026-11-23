import { expect, test } from "@playwright/test";

import { askingExplainer, reduceExplainer } from "@/lib/explainerState";
import { parseExplainerStreamBlock } from "@/lib/explainerStream";

import { KNOWN_ANSWER_QUESTIONS, answerProblems, answerRecord, parseTappedStream } from "./production/answers";
import { STEPPED_BLOCK_KINDS, pageSentenceProblems } from "./production/pageSentences";
import type { TappedStream } from "./production/streamTap";
import { readRepo } from "./phaseBFixture";
import { PHASE_C } from "./playFixture";

type Fixture = { sections: { id: string; blocks: unknown[] }[]; sources: unknown[] };

const [ENGLISH, , , INDIGO] = KNOWN_ANSWER_QUESTIONS;
const QUANTITIES = JSON.parse(readRepo("shared", "explainer.quantities.golden.json")) as Fixture;
const PACED = { services: [{ service: "openalex", waitedSeconds: 1.25, waitedRequests: 3, refusals: 0, unsent: 0 }] };

function frame(name: string, data: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}

function streamed(frames: readonly string[], depth = "DETAILED"): TappedStream {
  return {
    url: "/api/answers/stream",
    body: JSON.stringify({ question: "q", depth, craftSlug: "Kutch-Ajrakh", language: "en" }),
    requestedAt: 1_000,
    respondedAt: 1_100,
    status: 200,
    chunks: frames.map((text, at) => ({ at: 1_200 + at * 10, text })),
    endedAt: 9_000,
    failure: null
  };
}

function sectionFrames(fixture: Fixture, sectionId: string): string[] {
  const section = fixture.sections.find((found) => found.id === sectionId);
  if (!section) throw new Error(`the fixture has a section ${sectionId}`);
  return [...fixture.sources.map((source) => frame("source", source)), ...section.blocks.map((block) => frame("block", { sectionId, block })), frame("done", { answerId: null })];
}

function recordOf(frames: readonly string[], shown: readonly string[]) {
  const record = answerRecord({ question: ENGLISH, stream: streamed(frames), streamsOpened: 1, clickedAt: 1_000, waited: null });
  return { ...record, pageSentences: shown.length, pageSentenceIds: [...shown], pageSentencesWithoutChip: 0 };
}

test("a quantities row said above is on the page where its sentence is said, and nowhere else", () => {
  const frames = sectionFrames(QUANTITIES, "s2");
  const record = recordOf(frames, ["s2.b1.1", "s2.b2.3", "s2.b2.4", "s2.b2.5"]);
  expect(record.sentences.filter((sentence) => sentence.shownIn !== null).map((sentence) => [sentence.id, sentence.shownIn])).toEqual([
    ["s2.b2.1", "s2.b1.1"],
    ["s2.b2.2", "s2.b1.1"]
  ]);
  expect(pageSentenceProblems(record)).toEqual([]);
  expect(pageSentenceProblems({ ...record, pageSentenceIds: ["s2.b2.3", "s2.b2.4", "s2.b2.5"] })).toEqual(["3 streamed sentences are not on the page: s2.b1.1, s2.b2.1, s2.b2.2"]);
});

test("a what-if shows one option's outcomes at a time, so it needs one of its sentences on the page", () => {
  const whatIf = PHASE_C.sections.flatMap((section) => section.blocks).find((block) => block.kind === "what_if");
  expect(whatIf?.id).toBe("s2.b1");
  expect(STEPPED_BLOCK_KINDS.has("what_if")).toBe(true);
  const frames = [...PHASE_C.sources.map((source) => frame("source", source)), frame("block", { sectionId: "s2", block: whatIf }), frame("done", { answerId: null })];
  const record = recordOf(frames, ["s2.b1.1", "s2.b1.2"]);
  expect(record.sentences.map((sentence) => sentence.id)).toEqual(["s2.b1.1", "s2.b1.2", "s2.b1.3", "s2.b1.4"]);
  expect(pageSentenceProblems(record)).toEqual([]);
  expect(pageSentenceProblems({ ...record, pageSentenceIds: [] })).toEqual(["the stepped block s2.b1 shows none of its 4 sentences"]);
});

test("the scholarly services' pace is an event of the stream: parsed, drawn as nothing and never refused", () => {
  const paced = frame("paced", PACED);
  expect(parseExplainerStreamBlock(paced.trim())).toEqual({ type: "paced", data: PACED });
  expect(() => parseExplainerStreamBlock(frame("paced", { services: [] }).trim())).toThrow();
  const asking = askingExplainer("How does indigo turn blue?", "en");
  expect(reduceExplainer(asking, { type: "paced", data: PACED })).toBe(asking);
  const parsed = parseTappedStream([{ at: 1_200, text: paced }], 1_000);
  expect([parsed.events.length, parsed.refused]).toEqual([1, []]);
  const record = answerRecord({ question: INDIGO, stream: streamed([paced, ...sectionFrames(QUANTITIES, "s2")], "EXPERT"), streamsOpened: 1, clickedAt: 1_000, waited: null });
  expect(record.refusedFrames).toBe(0);
});

test("a refused frame is named by its event, so the report says what broke the contract", () => {
  const unknown = frame("sentence", { sectionId: "s1", sentence: {} });
  const record = answerRecord({ question: ENGLISH, stream: streamed([unknown, unknown, ...sectionFrames(QUANTITIES, "s2")]), streamsOpened: 1, clickedAt: 1_000, waited: null });
  expect([record.refusedFrames, record.refusedEvents]).toEqual([2, ["sentence"]]);
  expect(answerProblems(record, ENGLISH)).toContain("2 stream frames broke the explainer contract: sentence");
});
