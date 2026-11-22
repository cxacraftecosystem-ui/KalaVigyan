import { expect, test } from "@playwright/test";

import { BLOCK_SHAPES, BUILT_BLOCK_KINDS, explainerBlockShape, type TypedBlockKind } from "@/lib/explainerContract";
import { SANDBOX_ATTRIBUTE, SANDBOX_CSP, SANDBOX_DATA_ELEMENT_ID, SANDBOX_MAX_BYTES, type SimulationBlock, type TimelineMapBlock } from "@/lib/explainerPlay";
import { parseExplainerStreamBlock } from "@/lib/explainerStream";
import { checkedFilmScore, filmOfferShape, filmScorePath, SCORE_LABEL, scoreMaking } from "@/lib/filmScore";
import { parseShape, ShapeError } from "@/lib/shape";

import { readRepo } from "./phaseBFixture";

type Fixture = {
  sandbox: { attribute: string; csp: string; dataElementId: string; maxBytes: number };
  sections: { id: string; blocks: Record<string, unknown>[] }[];
  sources: { id: string }[];
};

const FIXTURE = JSON.parse(readRepo("shared", "explainer.phase-c.golden.json")) as Fixture;
const SCORE = JSON.parse(readRepo("shared", "film.score.golden.json")) as Record<string, unknown>;
const PHASE_C_KINDS = ["simulation", "timeline_map", "what_if", "zoom_story"];
const PLANNED_POLICY = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:";

function fixtureBlocks(): Record<string, unknown>[] {
  return FIXTURE.sections.flatMap((section) => section.blocks);
}

function fixtureBlock(id: string): Record<string, unknown> {
  const found = fixtureBlocks().find((block) => block.id === id);
  if (!found) throw new Error(`the phase C fixture has block ${id}`);
  return structuredClone(found);
}

function parsed<K extends TypedBlockKind>(kind: K, value: unknown) {
  return parseShape(BLOCK_SHAPES[kind], value);
}

test("every phase C fixture block parses with its kind's shape, exactly as the backend writes it", () => {
  const kinds = fixtureBlocks().map((block) => block.kind as TypedBlockKind);
  expect([...new Set(kinds)].sort()).toEqual(PHASE_C_KINDS);
  for (const block of fixtureBlocks()) expect(parsed(block.kind as TypedBlockKind, block)).toEqual(block);
});

test("every phase C kind is built: the parser and the stream take each fixture block", () => {
  const built: readonly string[] = BUILT_BLOCK_KINDS;
  const frame = (sectionId: string, block: unknown) => `event: block\ndata: ${JSON.stringify({ sectionId, block })}`;
  for (const block of fixtureBlocks()) {
    expect(built).toContain(String(block.kind));
    expect(parseShape(explainerBlockShape, block)).toEqual(block);
    expect(parseExplainerStreamBlock(frame(String(block.id).split(".")[0], block))?.type).toBe("block");
  }
});

test("the sandbox frame is the server's and the plan's", () => {
  expect(FIXTURE.sandbox).toEqual({
    attribute: SANDBOX_ATTRIBUTE,
    csp: SANDBOX_CSP,
    dataElementId: SANDBOX_DATA_ELEMENT_ID,
    maxBytes: SANDBOX_MAX_BYTES
  });
  const plan = readRepo("docs", "plans", "answer-experience.md").split(/\s+/).join(" ");
  expect(SANDBOX_CSP).toBe(`${PLANNED_POLICY}; webrtc 'block'`);
  expect(plan).toContain(PLANNED_POLICY);
  expect(plan).toContain(`sandbox="${SANDBOX_ATTRIBUTE}"`);
  const server = readRepo("backend", "app", "research", "sandbox.py");
  expect(server.split(/\s+/).join(" ")).toContain(`SANDBOX_CSP = ( "${SANDBOX_CSP}" )`);
  expect(server).toContain(`SANDBOX_DATA_ELEMENT_ID = "${SANDBOX_DATA_ELEMENT_ID}"`);
});

test("a generated explainer's HTML is bounded and its values carry their evidence", () => {
  const simulation = parsed("simulation", fixtureBlock("s1.b1")) as SimulationBlock;
  expect(simulation.html).toContain(`getElementById("${SANDBOX_DATA_ELEMENT_ID}")`);
  expect(simulation.values.map((value) => [value.key, value.value])).toEqual([
    ["fallLowFeet", 10],
    ["fallHighFeet", 15]
  ]);
  const block = fixtureBlock("s1.b1");
  expect(() => parsed("simulation", { ...block, html: "" })).toThrow(ShapeError);
  expect(() => parsed("simulation", { ...block, html: "é".repeat(SANDBOX_MAX_BYTES / 2 + 1) })).toThrow(ShapeError);
  expect(() => parsed("simulation", { ...block, hidden: "no" })).toThrow(ShapeError);
  const values = block.values as Record<string, unknown>[];
  expect(() => parsed("simulation", { ...block, values: [{ ...values[0], key: "Fall low" }] })).toThrow(ShapeError);
});

test("a what-if offers at least two options and an option with no outcome is unknown", () => {
  const block = fixtureBlock("s2.b1");
  const options = block.options as Record<string, unknown>[];
  expect(options.map((option) => (option.outcomes as unknown[]).length)).toEqual([2, 2, 0]);
  expect(() => parsed("what_if", { ...block, options: options.slice(0, 1) })).toThrow(ShapeError);
  expect(() => parsed("what_if", { ...block, options: [{ ...options[2], outcome: null }, options[0]] })).toThrow(ShapeError);
});

test("zoom levels are the five scales and a timeline cites its boundary row", () => {
  const zoom = fixtureBlock("s3.b1");
  const levels = zoom.levels as Record<string, unknown>[];
  expect(levels.map((level) => level.level)).toEqual(["DISTRICT", "WORKSHOP", "MOLECULE"]);
  expect(() => parsed("zoom_story", { ...zoom, levels: [{ ...levels[0], level: "STREET" }, levels[1]] })).toThrow(ShapeError);
  const timeline = parsed("timeline_map", fixtureBlock("s4.b1")) as TimelineMapBlock;
  expect(timeline.places.filter((place) => place.latitude !== null).map((place) => place.wikidataId)).toEqual(["Q839456"]);
  const raw = fixtureBlock("s4.b1");
  expect(() => parsed("timeline_map", { ...raw, datasets: [] })).toThrow(ShapeError);
  expect(() => parsed("timeline_map", { ...raw, geometry: [[31.2, 30.0]] })).toThrow(ShapeError);
});

test("every citation in the fixture names a listed source", () => {
  const listed = new Set(FIXTURE.sources.map((source) => source.id));
  const cited = JSON.stringify(FIXTURE.sections).match(/"sourceId":"[0-9a-f-]{36}"/g) ?? [];
  expect(cited.length).toBeGreaterThan(0);
  for (const entry of cited) expect(listed.has(entry.slice(12, -1))).toBe(true);
});

test("the film score is read only for the answer and language asked", () => {
  const answerId = String(SCORE.answerId);
  const score = checkedFilmScore(structuredClone(SCORE), answerId, "en");
  expect(score.label.text).toBe(SCORE_LABEL);
  expect(score.cues.map((cue) => cue.blockId)).toEqual(["s1.b1"]);
  expect(filmScorePath(answerId, "hi")).toBe(`/answers/${answerId}/film-score?language=hi`);
  expect(() => checkedFilmScore(structuredClone(SCORE), answerId, "hi")).toThrow(ShapeError);
  expect(() => checkedFilmScore(structuredClone(SCORE), "00000000-0000-4000-8000-000000000000", "en")).toThrow(ShapeError);
  const cues = SCORE.cues as Record<string, unknown>[];
  expect(() => checkedFilmScore({ ...SCORE, cues: [cues[0], cues[0]] }, answerId, "en")).toThrow(ShapeError);
  expect(() => checkedFilmScore({ ...SCORE, music: null, cues: [] }, answerId, "en")).toThrow(ShapeError);
  const music = SCORE.music as Record<string, unknown>;
  expect(() => checkedFilmScore({ ...SCORE, music: { ...music, audioUrl: "http://example.org/a.mp3" } }, answerId, "en")).toThrow(ShapeError);
  const making = { answerId, language: "en", pollAfterSeconds: 5 };
  expect(scoreMaking(making, answerId, "en")).toEqual(making);
  expect(scoreMaking(structuredClone(SCORE), answerId, "en")).toBeNull();
  expect(() => scoreMaking({ ...making, language: "hi" }, answerId, "en")).toThrow(ShapeError);
  expect(() => scoreMaking({ ...making, pollAfterSeconds: 0 }, answerId, "en")).toThrow(ShapeError);
  expect(() => scoreMaking({ ...making, pollAfterSeconds: 2.5 }, answerId, "en")).toThrow(ShapeError);
  expect(parseShape(filmOfferShape, { score: false })).toEqual({ score: false });
  expect(() => parseShape(filmOfferShape, { score: "yes" })).toThrow(ShapeError);
});
