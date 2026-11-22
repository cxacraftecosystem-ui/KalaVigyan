import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { splitSseBuffer } from "@/lib/answerStream";
import { askingExplainer, reduceExplainer, type ExplainerState } from "@/lib/explainerState";
import { explainerEventOf, type ExplainerEvent } from "@/lib/explainerStream";

const SHARED = join(__dirname, "..", "..", "shared");

function blocksOf(name: string): string[] {
  const { blocks, rest } = splitSseBuffer(readFileSync(join(SHARED, name), "utf8"));
  expect(rest).toBe("");
  return blocks;
}

function eventsOf(name: string): ExplainerEvent[] {
  return blocksOf(name)
    .map(explainerEventOf)
    .filter((event): event is ExplainerEvent => event !== null);
}

function reduced(name: string): ExplainerState {
  return eventsOf(name).reduce(reduceExplainer, askingExplainer("Why alum?", "en"));
}

function quietly<T>(run: () => T): { value: T; logged: unknown[] } {
  const logged: unknown[] = [];
  const original = console.error;
  console.error = (...args: unknown[]) => void logged.push(...args);
  try {
    return { value: run(), logged };
  } finally {
    console.error = original;
  }
}

test("the buffer splitter keeps an unfinished block for the next chunk", () => {
  const { blocks, rest } = splitSseBuffer('event: done\r\ndata: {"answerId":"x"}\r\n\r\nevent: sec');
  expect(blocks).toEqual(['event: done\ndata: {"answerId":"x"}']);
  expect(rest).toBe("event: sec");
});

test("multi-line data is joined, and comments and unknown events are skipped", () => {
  expect(explainerEventOf('event: follow_ups\ndata: {"items":\ndata: ["Why?"]}')).toEqual({ type: "follow_ups", data: { items: ["Why?"] } });
  expect(explainerEventOf(": keep-alive")).toBeNull();
  expect(explainerEventOf("event: ping\ndata: {}")).toBeNull();
  expect(explainerEventOf('event: section\ndata: {"id":"a","heading":"Mordant"}')).toBeNull();
  const broken = quietly(() => explainerEventOf("event: follow_ups\ndata: {not json"));
  expect(broken.value).toBeNull();
  expect(String(broken.logged[0])).toContain("follow_ups");
});

test("the backend's researched stream parses every event and settles with its answer id", () => {
  const skipped = blocksOf("answer-stream.research.golden.sse").filter((block) => explainerEventOf(block) === null);
  expect(skipped).toEqual([]);
  const events = eventsOf("answer-stream.research.golden.sse");
  expect(events[0]).toEqual({
    type: "understood",
    data: { crafts: [{ slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" }], candidates: [], depth: "DETAILED", language: "en", basis: "MODEL" }
  });
  const steps = events.flatMap((event) => (event.type === "status" ? [event.data.step] : []));
  expect(steps).toEqual(["PLANNING", "SEARCHING_STORED", "RESEARCHING", "READING", "COMPOSING", "WRITING_BACK"]);
  const state = reduced("answer-stream.research.golden.sse");
  expect(state.phase).toBe("done");
  expect(state.status).toBeNull();
  expect(state.answerId).toBe("0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9");
  expect(state.sources.map((source) => source.kind)).toEqual(["BOOK", "PAPER", "WEB_PAGE"]);
  expect(state.openQuestions[0].sentences[0].citations[0].evidence).toBe("INFERRED");
  expect(state.followUps).toEqual(["How is the alum bath prepared for Kutch Ajrakh?"]);
  for (const section of state.sections) expect(section.state === "READY" || section.state === "EMPTY").toBe(true);
  expect(state.sections.map((section) => [section.id, section.discipline, section.state])).toEqual([["s1", "CHEMISTRY", "READY"]]);
  expect(state.sections[0].blocks.map((block) => [block.id, block.kind])).toEqual([
    ["s1.b1", "prose"],
    ["s1.b2", "images"]
  ]);
  const [prose, images] = state.sections[0].blocks;
  if (prose.kind !== "prose" || images.kind !== "images") throw new Error("the section streams its prose, then its pictures");
  expect(prose.sentences.map((sentence) => sentence.terms.map((span) => span.termKey))).toEqual([["alum", "alizarin", "cotton"], ["alum"], []]);
  expect(images.items.map((item) => item.media.display)).toEqual(["INLINE"]);
  const cited = new Set(prose.sentences.flatMap((sentence) => sentence.citations.map((citation) => citation.claimId)));
  for (const item of images.items) for (const claimId of item.claimIds) expect(cited.has(claimId)).toBe(true);
  expect(state.trail.map((entry) => [entry.key, entry.stage])).toEqual([
    ["crossref:10.1000/lake", "QUOTED"],
    ["searxng:https://crafts.example.org/ajrakh", "QUOTED"],
    ["searxng:https://crafts.example.org/workshops", "READ"],
    ["openalex:W9", "FOUND"],
    ["source:1a2b3c4d-0000-4000-8000-000000000001", "QUOTED"]
  ]);
});

test("the backend's not-enough-evidence stream settles on the empty state with what was searched", () => {
  const state = reduced("answer-stream.not-enough.golden.sse");
  expect(state.phase).toBe("empty");
  expect(state.error).toBeNull();
  expect(state.status).toBeNull();
  expect(state.notice).toContain('T3 "Kutch Ajrakh alum mordant"');
  expect(state.sections.map((section) => [section.id, section.state, section.blocks.length])).toEqual([["s1", "EMPTY", 0]]);
  expect(state.sections[0].searched).toContain('T3 "Kutch Ajrakh alum mordant"');
  expect(state.answerId).toBe("0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9");
});
