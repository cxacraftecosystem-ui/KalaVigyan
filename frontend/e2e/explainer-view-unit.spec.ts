import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { splitSseBuffer } from "@/lib/answerStream";
import { explainerShape, type Explainer } from "@/lib/explainerContract";
import { askingExplainer, reduceExplainer, type ExplainerState } from "@/lib/explainerState";
import { explainerEventOf, type ExplainerEvent, type TrailEntry } from "@/lib/explainerStream";
import {
  blockSentences,
  COVERED_NOTE,
  explainerSourceNumbers,
  hasTranslatedText,
  ladderReach,
  reusedLabel,
  showsEarlierResearch,
  sentenceSegments,
  shownSections,
  termQuestion,
  trailCounts,
  workingLabel
} from "@/lib/explainerView";
import { activeWordIndex, checkedScript, elapsedOf, listenLanguagesOf, listenMark, nextRate, scriptDuration, wordRanges } from "@/lib/listen";
import { parseShape, ShapeError } from "@/lib/shape";
import { termPath } from "@/lib/termSummary";

const ROOT = join(__dirname, "..", "..");
const read = (...parts: string[]) => readFileSync(join(ROOT, ...parts), "utf8");
const QUESTION = "How is Kutch Ajrakh made, and why does its water matter?";

function document(name = "explainer.document.golden.json"): Explainer {
  return parseShape(explainerShape, JSON.parse(read("shared", name)));
}

function streamed(name = "explainer.stream.golden.sse"): ExplainerEvent[] {
  const { blocks } = splitSseBuffer(read("shared", name));
  return blocks.map(explainerEventOf).filter((event): event is ExplainerEvent => event !== null);
}

function reduced(events: readonly ExplainerEvent[], from: ExplainerState = askingExplainer(QUESTION, "en")): ExplainerState {
  return events.reduce(reduceExplainer, from);
}

function upTo(events: readonly ExplainerEvent[], matches: (event: ExplainerEvent) => boolean): ExplainerEvent[] {
  return events.slice(0, events.findIndex(matches) + 1);
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

test("the stream golden reduces to the explainer document, section for section", () => {
  const expected = document();
  const state = reduced(streamed());
  expect(state.phase).toBe("done");
  expect(state.status).toBeNull();
  expect(state.answerId).toBe(expected.answerId);
  expect(state.understood).toEqual(expected.understood);
  expect(state.followUps).toEqual(expected.followUps);
  expect(state.sections).toEqual(expected.sections);
  expect(new Set(state.sources.map((source) => source.id))).toEqual(new Set(expected.sources.map((source) => source.id)));
});

test("sources are numbered in the document's order of first citation, walking sections in reading order", () => {
  const state = reduced(streamed());
  expect([...explainerSourceNumbers(state.sections).keys()]).toEqual(document().sources.map((source) => source.id));
  expect(explainerSourceNumbers(state.sections).get("907e2c52-14e7-5e41-9b27-9c10f70906a9")).toBe(4);
});

test("a reused piece streams first and shows as earlier research with its date", () => {
  const events = streamed();
  const state = reduced(upTo(events, (event) => event.type === "section_done"));
  expect(state.phase).toBe("streaming");
  expect(state.sections.map((section) => [section.id, section.state])).toEqual([["s2", "READY"]]);
  const reuse = state.sections[0].blocks[0].reuse;
  expect(reuse).toEqual({ pieceId: "7d4e2c10-5a6b-4c7d-9e8f-0a1b2c3d4e5f", storedAt: "2026-11-12T08:15:00Z" });
  expect(reusedLabel("2026-11-12T08:15:00Z")).toBe("From earlier research · 12 Nov 2026");
  expect(state.trail.map((entry) => [entry.key, entry.storedAt])).toEqual([["piece:7d4e2c10-5a6b-4c7d-9e8f-0a1b2c3d4e5f", "2026-11-12T08:15:00Z"]]);
  expect(showsEarlierResearch(state.sections)).toBe(true);
  expect(showsEarlierResearch(state.sections.map((section) => ({ ...section, blocks: section.blocks.map((block) => ({ ...block, reuse: null })) })))).toBe(false);
});

test("a partial stream orders sections by their order and shows each one's working state", () => {
  const events = streamed();
  const started = reduced(upTo(events, (event) => event.type === "section_started" && event.data.id === "s3"));
  expect(started.sections.map((section) => [section.id, section.state, section.blocks.length])).toEqual([
    ["s1", "RESEARCHING", 0],
    ["s2", "READY", 1],
    ["s3", "RESEARCHING", 0]
  ]);
  expect(shownSections(started.sections, true).map((section) => section.id)).toEqual(["s1", "s2", "s3"]);
  expect(shownSections(started.sections, false).map((section) => section.id)).toEqual(["s2"]);
  const checking = reduced(upTo(events, (event) => event.type === "section_state" && event.data.state === "CHECKING"));
  expect(checking.sections.map((section) => [section.id, section.state])).toEqual([
    ["s1", "CHECKING"],
    ["s2", "READY"],
    ["s3", "WRITING"]
  ]);
  expect(workingLabel("CHECKING", true)).toBe("Checking");
  expect(workingLabel("CHECKING", false)).toBeNull();
  expect(workingLabel("READY", true)).toBeNull();
  const ladder = reduced(upTo(events, (event) => event.type === "block" && event.data.block.kind === "process_ladder"));
  expect(ladder.sections[0].blocks.map((block) => block.kind)).toEqual(["process_ladder"]);
  expect(ladder.sections[0].state).toBe("CHECKING");
});

test("a trail entry only moves forward and keeps the place it was first found", () => {
  const state = reduced(streamed());
  expect(state.trail.map((entry) => [entry.key.split(":")[0], entry.stage])).toEqual([
    ["piece", "FOUND"],
    ["source", "QUOTED"],
    ["source", "QUOTED"],
    ["source", "QUOTED"],
    ["source", "QUOTED"]
  ]);
  const quoted = state.trail[1];
  const found: TrailEntry = { ...quoted, stage: "FOUND" };
  expect(reduceExplainer(state, { type: "trail", data: found }).trail[1].stage).toBe("QUOTED");
  expect(trailCounts(state.trail)).toEqual([{ group: "STORED", count: 5, noun: "stored findings" }]);
  const paper: TrailEntry = { ...found, key: "openalex:W1", group: "PAPERS", storedAt: null, sourceId: null };
  expect(trailCounts([paper])).toEqual([{ group: "PAPERS", count: 1, noun: "paper" }]);
});

test("a dropped block leaves its section's note of what was searched, and late blocks are not drawn", () => {
  const state = reduced(streamed());
  const prose = state.sections[2].blocks[0];
  const events: ExplainerEvent[] = [
    { type: "section_started", data: { id: "s4", discipline: "PHYSICS", title: "Heat in the dye bath", order: 4, state: "RESEARCHING" } },
    { type: "section_done", data: { sectionId: "s4", state: "EMPTY", searched: "Searched 12 stored claims and 3 papers; none was cited closely enough." } },
    { type: "block", data: { sectionId: "s4", block: { ...prose, id: "s4.b1" } } },
    { type: "block", data: { sectionId: "s9", block: { ...prose, id: "s9.b1" } } },
    { type: "section_started", data: { id: "s5", discipline: "HISTORY", title: "Where it came from", order: 5, state: "WRITING" } },
    { type: "section_done", data: { sectionId: "s5", state: "READY", searched: null } }
  ];
  const settled = reduced(events, state);
  const empty = settled.sections.find((section) => section.id === "s4");
  expect(empty).toMatchObject({ state: "EMPTY", blocks: [], searched: "Searched 12 stored claims and 3 papers; none was cited closely enough." });
  expect(shownSections(settled.sections, false).map((section) => section.id)).toEqual(["s1", "s2", "s3", "s4"]);
  const refused = quietly(() => explainerEventOf(`event: block\ndata: ${JSON.stringify({ sectionId: "s3", block: { ...prose, id: "s3.b2", kind: "artisan_voice" } })}`));
  expect(refused.value).toBeNull();
  expect(String(refused.logged[0])).toContain("block.block.kind");
});

test("a section the answer already covered is not drawn, and the note matches the backend's", () => {
  const backend = /^COVERED_NOTE = "([^"]+)"$/m.exec(read("backend", "app", "services", "claim_ledger.py"));
  expect(backend?.[1]).toBe(COVERED_NOTE);
  const state = reduced(streamed());
  const events: ExplainerEvent[] = [
    { type: "section_started", data: { id: "s4", discipline: "BOTANY", title: "Botany", order: 4, state: "WRITING" } },
    { type: "section_done", data: { sectionId: "s4", state: "EMPTY", searched: COVERED_NOTE } }
  ];
  const started = reduced(events.slice(0, 1), state);
  expect(shownSections(started.sections, true).map((section) => section.id)).toContain("s4");
  const settled = reduced(events, state);
  expect(shownSections(settled.sections, true).map((section) => section.id)).not.toContain("s4");
  expect(shownSections(settled.sections, false).map((section) => section.id)).toEqual(["s1", "s2", "s3"]);
});

test("a settled answer ignores late understanding and status, and an error clears the progress line", () => {
  const empty = reduced([{ type: "not_enough_evidence", data: { message: "Not enough cited evidence yet." } }]);
  const late = reduced([{ type: "status", data: { step: "COMPOSING", message: "late" } }, { type: "done", data: { answerId: null } }], empty);
  expect(late).toMatchObject({ phase: "empty", status: null, notice: "Not enough cited evidence yet." });
  const failed = reduced([{ type: "status", data: { step: "READING", message: "Reading" } }, { type: "error", data: { message: "Research failed." } }]);
  expect(failed).toMatchObject({ phase: "failed", status: null, error: "Research failed." });
  expect(reduced([{ type: "understood", data: document().understood }], failed)).toBe(failed);
});

test("the ladder rests complete and fills only with a film's scene, never with the scroll", () => {
  expect([0, 0.2, 0.5, 1].map((progress) => ladderReach(progress, 4, true))).toEqual([4, 4, 4, 4]);
  expect([0, 0.3, 1 / 3, 0.5, 0.99, 1].map((progress) => ladderReach(progress, 4, false))).toEqual([1, 1, 2, 2, 3, 4]);
  expect(ladderReach(Number.NaN, 4, false)).toBe(1);
  expect(ladderReach(0, 1, false)).toBe(1);
  expect(ladderReach(1, 0, false)).toBe(0);
  const ladder = read("frontend", "components", "answer", "ProcessLadder.tsx");
  expect(ladder).toContain("const shown = reduce || !film ? count : ladderReach(film.progress, count, false);");
  expect(ladder).not.toContain("useScroll");
});

test("a sentence underlines each marked term once, at its first occurrence", () => {
  const ladder = document().sections[0].blocks[0];
  if (ladder.kind !== "process_ladder") throw new Error("the fixture's first block is the ladder");
  const sentence = ladder.stages[1].sentences[0];
  expect(sentenceSegments(sentence.text, sentence.terms).map((segment) => [segment.text, segment.term?.termKey ?? null])).toEqual([
    ["Areas where black is required are printed with ", null],
    ["kut", "kut"],
    [" paste, usually an infill (", null],
    ["datla", "datla"],
    [") between ", null],
    ["khariyanu", "khariyanu"],
    [" outlines.", null]
  ]);
  const twice = sentenceSegments("alum and alum", [{ text: "alum", termKey: "alum" }]);
  expect(twice.map((segment) => [segment.text, segment.term?.termKey ?? null])).toEqual([
    ["alum", "alum"],
    [" and alum", null]
  ]);
  const overlapping = sentenceSegments("iron acetate", [{ text: "iron acetate", termKey: "iron-acetate" }, { text: "acetate", termKey: "acetate" }]);
  expect(overlapping.map((segment) => segment.term?.termKey ?? null)).toEqual(["iron-acetate"]);
  expect(sentenceSegments("Alum is the mordant.", [{ text: "फिटकरी", termKey: "alum" }]).map((segment) => segment.term)).toEqual([null]);
});

test("the word being read is marked inside or across a term without changing the text", () => {
  const segments = sentenceSegments("Kut paste turns black.", [{ text: "Kut paste", termKey: "kut" }], { from: 4, to: 9 });
  expect(segments.map((segment) => [segment.term?.termKey ?? null, segment.parts])).toEqual([
    [
      "kut",
      [
        { text: "Kut ", marked: false },
        { text: "paste", marked: true }
      ]
    ],
    [null, [{ text: " turns black.", marked: false }]]
  ]);
  expect(segments.map((segment) => segment.text).join("")).toBe("Kut paste turns black.");
});

test("a term opens its summary in the answer's language, and Ask about it names the craft", () => {
  expect(termPath("iron-acetate", "hi")).toBe("/terms/iron-acetate?language=hi");
  expect(termQuestion("Kut", "Kutch Ajrakh")).toBe("What is Kut in Kutch Ajrakh?");
  expect(termQuestion("Kut", null)).toBe("What is Kut?");
});

test("the Listen golden reads the document's sentences word by word, in reading order", () => {
  const explainer = document();
  const raw = JSON.parse(read("shared", "listen.script.golden.json"));
  const script = checkedScript(raw, explainer.answerId, "en");
  const blocks = new Map(explainer.sections.flatMap((section) => section.blocks).map((block) => [block.id, block]));
  for (const track of script.tracks) {
    const block = blocks.get(track.blockId);
    if (!block) throw new Error(`the Listen golden reads ${track.blockId}, which the document does not hold`);
    for (const sentence of blockSentences(block)) {
      const words = track.words.filter((word) => word.sentenceId === sentence.id);
      expect(words.length, sentence.id).toBeGreaterThan(0);
      expect(wordRanges(sentence.text, words).every((range) => range !== null), sentence.id).toBe(true);
    }
  }
  expect(listenMark(script, { track: 0, time: 0.5 })).toMatchObject({ sentenceId: "s2.b1.1", wordIndex: 1 });
  expect(listenMark(script, { track: 0, time: -1 })).toBeNull();
  expect(scriptDuration(script)).toBe(14.7);
  expect(elapsedOf(script, { track: 0, time: 3 })).toBe(3);
  expect(() => checkedScript(raw, "7d4e2c10-5a6b-4c7d-9e8f-0a1b2c3d4e5f", "en")).toThrow(ShapeError);
  expect(() => checkedScript(raw, explainer.answerId, "hi")).toThrow(ShapeError);
  const [first, second, ...rest] = raw.tracks[0].words;
  const backwards = { ...raw, tracks: [{ ...raw.tracks[0], words: [second, first, ...rest] }] };
  expect(() => checkedScript(backwards, explainer.answerId, "en")).toThrow(ShapeError);
});

test("a word is found from where the last one ended, and Listen is offered only in listed languages", () => {
  expect(wordRanges("alum and alum again", [{ text: "alum" }, { text: "alum" }, { text: "iron" }])).toEqual([{ from: 0, to: 4 }, { from: 9, to: 13 }, null]);
  expect(activeWordIndex([{ sentenceId: "a", text: "x", start: 0.2, end: 0.4 }], 0.1)).toBe(-1);
  expect(listenLanguagesOf(undefined)).toEqual([]);
  expect(listenLanguagesOf({ languages: ["en", "hi"] })).toEqual(["en", "hi"]);
  const refused = quietly(() => listenLanguagesOf({ languages: "en" }));
  expect(refused.value).toEqual([]);
  expect(String(refused.logged[0])).toContain("answers/config listen.languages");
  expect([1, 1.25, 1.5].map(nextRate)).toEqual([1.25, 1.5, 1]);
});

test("the lede stream reduces to the lede document: the lede first, then sections under their own headings", () => {
  const expected = document("explainer.lede.golden.json");
  const events = streamed("explainer.lede.golden.sse");
  const state = reduced(events, askingExplainer(expected.question, "en"));
  expect(state.phase).toBe("done");
  expect(state.lede).toEqual(expected.lede);
  expect(state.sections).toEqual(expected.sections);
  expect(state.followUps).toEqual(expected.followUps);
  expect([...explainerSourceNumbers(state.sections, [], [], state.lede).keys()]).toEqual(expected.sources.map((source) => source.id));
  const opened = reduced(upTo(events, (event) => event.type === "lede"), askingExplainer(expected.question, "en"));
  expect(opened.lede?.headline).toBe(expected.question);
  expect(opened.sections.map((section) => [section.id, section.title, section.blocks.length])).toEqual([
    ["s1", "The chemistry behind Kutch Ajrakh", 0],
    ["s2", "What Kutch Ajrakh is made from", 0],
    ["s3", "How Kutch Ajrakh is made", 0]
  ]);
  const headed = reduced(upTo(events, (event) => event.type === "section_heading"), opened);
  expect(headed.sections[0].title).toBe("Alum holds the red, iron the black");
  expect(blockSentences(state.sections[0].blocks[0]).length).toBe(2);
});

test("a translated lede offers the English original even when no section is translated", () => {
  const { lede } = document("explainer.lede.golden.json");
  if (!lede) throw new Error("the lede golden holds a lede");
  const [first, ...rest] = lede.sentences;
  const translated = { ...lede, sentences: [{ ...first, text: "फिटकरी लाल रंग को पक्का करती है।", original: first.text, translated: true }, ...rest] };
  expect(hasTranslatedText([], lede)).toBe(false);
  expect(hasTranslatedText([], translated)).toBe(true);
  expect(hasTranslatedText([])).toBe(false);
});
