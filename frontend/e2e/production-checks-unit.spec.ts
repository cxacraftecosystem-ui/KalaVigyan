import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { splitSseBuffer } from "@/lib/answerStream";
import { explainerEventOf } from "@/lib/explainerStream";

import {
  KNOWN_ANSWER_QUESTIONS,
  NO_LEDE,
  answerProblems,
  answerRecord,
  knownAnswerOutcome,
  ledeProblems,
  parseTappedStream,
  savedLedeProblems,
  scriptProblems,
  type KnownAnswerQuestion
} from "./production/answers";
import { pageSentenceProblems } from "./production/pageSentences";
import { NetworkQuiet, captureScreen, judgeCapture, readyForCapture, sightProblems } from "./production/capture";
import { CITED_CONTENT, NAV_BY_ROLE, errorHeadline, gapCopyFindings, labelProblems } from "./production/checks";
import {
  ANSWER_SCOPE,
  BUSY_PATTERN,
  FULL_OPACITY,
  MIN_PICTURE_PX,
  REGION_MARKER,
  REGION_PANEL,
  busyProblems,
  clusterProblems,
  emptyPictureProblems,
  moleculeProblems,
  opacityProblems,
  regionProblems,
  repeatProblems,
  themeProblems,
  tileProblems,
  unpaintedNotes
} from "./production/gates";
import { SCHEMES, SCREEN_WIDTHS } from "./production/matrix";
import { GOOGLE_ORIGIN_REFUSED, PRODUCTION_ORIGIN, googleRefusesPreview, isPreview, previewConsoleNoise, roleSiteRefusal, siteRefusal } from "./production/preview";
import type { AnswersReport, ScreensReport } from "./production/report";
import { roleCredentials, runFileName } from "./production/run";
import { answerRepeats, busyText, citationClusters, emptyPictures, opacityAtCapture, regionRunPx } from "./production/sight";
import { scanTiles } from "./production/tiles";
import { base32Bytes, totpCode } from "./production/twoStep";
import type { TappedChunk, TappedStream } from "./production/streamTap";
import { summaryMarkdown } from "./production/summaryMarkdown";
import { FRAME_DOCUMENT_START, NO_CONCEPT_NOTE, type FrameSeen } from "./production/generatedExplainer";
import { RIVERS_NOT_LOADED_NOTE } from "./production/waterStory";
import { PHASE_C, phaseCBlock } from "./playFixture";

const SHARED = join(__dirname, "..", "..", "shared");
const GOLDEN = readFileSync(join(SHARED, "explainer.stream.golden.sse"), "utf8");
const LEDE_GOLDEN = readFileSync(join(SHARED, "explainer.lede.golden.sse"), "utf8");
const [ENGLISH, HINDI, WATER, INDIGO, MATERIALS, HISTORY] = KNOWN_ANSWER_QUESTIONS;
const PHASE_B = JSON.parse(readFileSync(join(SHARED, "explainer.phase-b.golden.json"), "utf8")) as {
  sections: { blocks: Record<string, unknown>[] }[];
  sources: Record<string, unknown>[];
};
const STORY = PHASE_B.sections.flatMap((section) => section.blocks).find((found) => found.id === "s1.b1") as Record<string, unknown>;
const CITATION = { id: "c1", claimId: "k1", sourceId: "s1", quote: "alum", locator: null, context: null, evidence: "QUOTED", level: "PROVISIONAL" };
const SOURCE = { id: "s1", kind: "PAPER", title: "Mordants", authors: [], year: 2020, doi: null, url: "https://example.org/m", publisher: null, licence: null, attribution: null, reliability: "B" };

function chunked(text: string, size: number, start = 1_000, step = 10): TappedChunk[] {
  const chunks: TappedChunk[] = [];
  for (let offset = 0; offset < text.length; offset += size) chunks.push({ at: start + step * chunks.length, text: text.slice(offset, offset + size) });
  return chunks;
}

function block(name: string, data: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}

function sentence(id: string, text: string, extra: Record<string, unknown> = {}, citations: unknown[] = [CITATION]): string {
  const prose = { id: `s1.${id}`, kind: "prose", version: 1, reuse: null, sentences: [{ id, text, level: "PROVISIONAL", citations, terms: [], ...extra }] };
  return block("block", { sectionId: "s1", block: prose });
}

function stream(text: string, language: string, depth = "DETAILED"): TappedStream {
  return {
    url: "/api/answers/stream",
    body: JSON.stringify({ question: "q", depth, craftSlug: "Kutch-Ajrakh", language }),
    requestedAt: 1_000,
    respondedAt: 1_100,
    status: 200,
    chunks: chunked(text, 64, 1_200),
    endedAt: 9_000,
    failure: null
  };
}

function recordOf(text: string, question: KnownAnswerQuestion, streamsOpened = 1) {
  return answerRecord({ question, stream: stream(text, question.language, question.depth), streamsOpened, clickedAt: 1_000, waited: null });
}

const HINDI_ANSWER = [
  block("source", SOURCE),
  block("section_started", { id: "s1", discipline: "CHEMISTRY", title: "रंगबंधक", original: "Mordants", order: 1, state: "WRITING" }),
  sentence("t1", "फिटकरी कपड़े पर लाल रंग को पक्का करती है।", { translated: true, original: "Alum fixes the red on the cloth." }),
  sentence("t2", "Alum forms a lake with alizarin at 60 °C."),
  block("done", { answerId: null })
].join("");

test("a tapped stream parses the same in any chunking, counting heartbeats and silence", () => {
  const whole = splitSseBuffer(GOLDEN).blocks.map(explainerEventOf).filter((event) => event !== null);
  for (const size of [1, 7, 64, GOLDEN.length]) {
    const parsed = parseTappedStream(chunked(GOLDEN, size), 1_000);
    expect(parsed.events.map(({ event }) => event)).toEqual(whole);
    expect(parsed.heartbeats).toBe(1);
    expect(parsed.refused).toEqual([]);
  }
  const silent = parseTappedStream([{ at: 1_500, text: ": keep-alive\n\n" }, { at: 61_500, text: block("done", { answerId: null }) }], 1_000);
  expect(silent.longestSilenceMs).toBe(60_000);
  expect(silent.heartbeats).toBe(1);
});

test("the golden English answer records its sentences, citations and sources and passes", () => {
  const record = recordOf(GOLDEN, ENGLISH);
  expect(record.endedWith).toBe("done");
  expect(record.sentenceCount).toBe(record.sentences.length);
  expect(record.citedSentenceCount).toBeGreaterThan(0);
  expect(record.uncitedSentenceCount).toBe(0);
  expect(record.sources.length).toBeGreaterThan(0);
  expect(record.knownAnswerFound).toBe(true);
  expect(record.timing.heartbeats).toBe(1);
  expect(record.timing.firstByteMs).toBe(200);
  expect(answerProblems(record, ENGLISH)).toEqual([]);
});

test("a Hindi answer passes with Devanagari translations and English fallbacks", () => {
  const record = recordOf(HINDI_ANSWER, HINDI);
  expect(record.scripts).toEqual({ translated: 1, englishFallback: 1, other: 0 });
  expect(answerProblems(record, HINDI)).toEqual([]);
});

test("the Hindi rule refuses a translated sentence in Latin, a missing original and a mixed fallback", () => {
  const latin = recordOf(sentence("x1", "Alum fixes the red.", { translated: true, original: "Alum fixes the red." }), HINDI);
  expect(scriptProblems(latin.sentences, "Deva")).toEqual(["sentence x1 is marked translated but is written in Latn"]);
  const bare = recordOf(sentence("x2", "फिटकरी रंग पक्का करती है।", { translated: true }), HINDI);
  expect(scriptProblems(bare.sentences, "Deva")).toEqual(["sentence x2 is translated but carries no English original"]);
  const untranslated = recordOf(sentence("x3", "फिटकरी रंग पक्का करती है।"), HINDI);
  expect(scriptProblems(untranslated.sentences, "Deva")).toEqual(["sentence x3 is neither in Deva nor an English fallback"]);
});

test("an answer without done, with an uncited sentence or opened twice fails", () => {
  const cut = recordOf([block("source", SOURCE), sentence("e1", "Alum is the mordant.")].join(""), ENGLISH);
  expect(answerProblems(cut, ENGLISH)).toContain("the stream ended with closed, not done");
  const uncited = recordOf([sentence("e2", "Alum is the mordant.", {}, []), block("done", { answerId: null })].join(""), ENGLISH);
  expect(answerProblems(uncited, ENGLISH)).toEqual(expect.arrayContaining(["no cited sentence arrived", "1 stream frames broke the explainer contract: block"]));
  const retired = recordOf([block("source", SOURCE), block("sentence", { sectionId: "a", sentence: {} }), sentence("e6", "Alum is the mordant."), block("done", { answerId: null })].join(""), ENGLISH);
  expect(answerProblems(retired, ENGLISH)).toEqual(["1 stream frames broke the explainer contract: sentence"]);
  const twice = recordOf([block("source", SOURCE), sentence("e3", "Alum is the mordant."), block("done", { answerId: null })].join(""), ENGLISH, 2);
  expect(answerProblems(twice, ENGLISH)).toEqual(["the question opened 2 answer streams, not 1"]);
  const orphan = recordOf([sentence("e4", "Alum is the mordant."), block("done", { answerId: null })].join(""), ENGLISH);
  expect(answerProblems(orphan, ENGLISH)).toEqual(["1 cited sources never arrived as source events"]);
  const wrong = recordOf([block("source", SOURCE), sentence("e5", "Iron darkens the black."), block("done", { answerId: null })].join(""), ENGLISH);
  expect(answerProblems(wrong, ENGLISH)).toEqual(["no sentence names alum, the known mordant"]);
});

function waterAnswer(...frames: string[]): string {
  return [block("source", SOURCE), ...PHASE_B.sources.map((source) => block("source", source)), ...frames, block("done", { answerId: null })].join("");
}

test("the water question passes only when a region story with a river path and cited steps arrives", () => {
  const story = recordOf(waterAnswer(block("block", { sectionId: "s1", block: STORY })), WATER);
  expect(story.regionStory).toEqual({ blocks: 1, withRiver: 1, steps: 4, citedSteps: 4 });
  expect(story.knownAnswerFound).toBe(true);
  expect(answerProblems(story, WATER, { riversLoaded: true })).toEqual([]);
  const riverless = recordOf(waterAnswer(block("block", { sectionId: "s1", block: { ...STORY, river: null } })), WATER);
  expect(riverless.knownAnswerFound).toBe(false);
  expect(answerProblems(riverless, WATER)).toEqual(["1 region stories arrived without a river path"]);
});

test("without a region story the water question fails once rivers are loaded, and before that only records the absence", () => {
  const absent = recordOf(waterAnswer(sentence("w1", "Alum is the mordant.")), WATER);
  expect(absent.regionStory.blocks).toBe(0);
  expect(answerProblems(absent, WATER)).toEqual([]);
  expect(knownAnswerOutcome(absent, WATER).notes).toEqual([RIVERS_NOT_LOADED_NOTE]);
  expect(answerProblems(absent, WATER, { riversLoaded: true })).toEqual(["no region story arrived although the river lines are loaded"]);
  expect(knownAnswerOutcome(absent, WATER, { riversLoaded: true }).notes).toEqual([]);
  expect(answerProblems(recordOf(waterAnswer(sentence("w1", "Alum is the mordant.")), ENGLISH), ENGLISH)).toEqual([]);
});

test("the page must show every streamed sentence with a citation chip", () => {
  const record = recordOf([block("source", SOURCE), sentence("p1", "Alum is the mordant."), block("done", { answerId: null })].join(""), ENGLISH);
  record.pageSentences = 2;
  record.pageSentencesWithoutChip = 1;
  expect(answerProblems(record, ENGLISH)).toEqual(["1 sentences on the page show no citation", "the page shows 2 sentences; the stream sent 1"]);
  record.pageSentences = 1;
  record.pageSentenceIds = ["p9"];
  record.pageSentencesWithoutChip = 0;
  expect(answerProblems(record, ENGLISH)).toEqual(["1 streamed sentences are not on the page: p1", "1 sentences on the page never arrived in the stream: p9"]);
  record.pageSentenceIds = ["p1"];
  expect(answerProblems(record, ENGLISH)).toEqual([]);
});

test("a known answer opens with its lede: the stream's lede sentences are recorded first and the page must show one of them cited", () => {
  const record = recordOf(LEDE_GOLDEN, ENGLISH);
  expect(record.lede).toEqual({ sentences: 3, cited: 3, shown: null, shownCited: null });
  expect(record.sentences.slice(0, 3).map((entry) => [entry.id, entry.blockKind, entry.citations])).toEqual([
    ["lede.1", "lede", 1],
    ["lede.2", "lede", 3],
    ["lede.3", "lede", 1]
  ]);
  expect(record.timing.firstSentenceMs).not.toBeNull();
  expect(ledeProblems(record)).toEqual([]);
  record.pageSentences = record.sentences.length;
  record.pageSentenceIds = record.sentences.map((entry) => entry.id);
  record.pageSentencesWithoutChip = 0;
  record.lede = { ...record.lede, shown: 3, shownCited: 3 };
  expect(answerProblems(record, ENGLISH)).toEqual([]);
  expect(ledeProblems({ ...record, lede: { ...record.lede, shown: 0, shownCited: 0 } })).toEqual(["the page shows no lede"]);
  expect(ledeProblems({ ...record, lede: { ...record.lede, shown: 3, shownCited: 0 } })).toEqual(["no lede sentence on the page shows a citation"]);
  record.pageSentenceIds = record.sentences.slice(3).map((entry) => entry.id);
  expect(pageSentenceProblems(record)).toEqual(["3 streamed sentences are not on the page: lede.1, lede.2, lede.3"]);
});

test("an answer streamed without a lede fails once its page is read, and the saved explainer must show every lede sentence", () => {
  const unled = recordOf(GOLDEN, ENGLISH);
  expect(unled.lede).toEqual(NO_LEDE);
  expect(ledeProblems(unled)).toEqual([]);
  expect(ledeProblems({ ...unled, lede: { ...unled.lede, shown: 0, shownCited: 0 } })).toEqual(["the answer opened without a lede"]);
  const led = recordOf(LEDE_GOLDEN, ENGLISH).lede;
  expect(savedLedeProblems(led, 3)).toEqual([]);
  expect(savedLedeProblems(led, 0)).toEqual(["the saved explainer shows 0 of the lede's 3 sentences"]);
  expect(savedLedeProblems(NO_LEDE, 0)).toEqual([]);
});

test("a sentence a block repeats word for word counts as shown once its twin is on the page", () => {
  const twins = ["t1", "t2"].map((id) => ({ id, text: "Indigo came from Sindh.", level: "PROVISIONAL", citations: [CITATION], terms: [] }));
  const prose = block("block", { sectionId: "s1", block: { id: "s1.b1", kind: "prose", version: 1, reuse: null, sentences: twins } });
  const record = recordOf([block("source", SOURCE), prose, block("done", { answerId: null })].join(""), ENGLISH);
  record.pageSentences = 1;
  record.pageSentencesWithoutChip = 0;
  record.pageSentenceIds = ["t1"];
  expect(pageSentenceProblems(record)).toEqual([]);
  record.pageSentenceIds = [];
  expect(pageSentenceProblems(record)).toEqual(["2 streamed sentences are not on the page: t1, t2"]);
});

test("a stepped block needs only the sentence of the level it shows on the page", () => {
  const story = { ...phaseCBlock("zoom_story", "s3.b1"), id: "s1.zoom" };
  const levels = story.levels.map((level) => level.sentence.id);
  const record = recordOf([block("source", SOURCE), sentence("p1", "Alum is the mordant."), block("block", { sectionId: "s1", block: story }), block("done", { answerId: null })].join(""), ENGLISH);
  expect(levels.length).toBeGreaterThan(1);
  expect(record.sentences.filter((entry) => entry.blockKind === "zoom_story").map((entry) => entry.blockId)).toEqual(levels.map(() => "s1.zoom"));
  record.pageSentences = 2;
  record.pageSentencesWithoutChip = 0;
  record.pageSentenceIds = ["p1", levels[1]];
  expect(pageSentenceProblems(record)).toEqual([]);
  record.pageSentenceIds = ["p1"];
  expect(pageSentenceProblems(record)).toEqual([`the stepped block s1.zoom shows none of its ${levels.length} sentences`]);
});

test("gap copy is found with its context and ordinary copy is not", () => {
  expect(gapCopyFindings("Voice calls are coming soon to every craft.")).toEqual(["Voice calls are coming soon to every craft."]);
  expect(gapCopyFindings("Region data isn't available yet for this place")).toHaveLength(1);
  expect(gapCopyFindings("This screen is not built")).toHaveLength(1);
  expect(gapCopyFindings("Ask about any Indian craft. Sign in. No source found.")).toEqual([]);
});

test("nav labels must match the role exactly and in order", () => {
  expect(labelProblems("the menu", ["Ask", "Map"], [" Ask ", "Map"])).toEqual([]);
  expect(labelProblems("the menu", ["Ask", "Map"], ["Map", "Ask"])).toEqual(["the menu shows [Map, Ask]; this role should see [Ask, Map]"]);
  expect(NAV_BY_ROLE.STUDENT).toEqual({
    bar: ["Ask", "Crafts", "Map", "Saved"],
    account: ["Connect your AI", "Settings"],
    menu: ["Ask", "Crafts", "Map", "Saved", "Connect your AI", "Settings"],
    depths: ["Basic", "Detailed", "Expert"]
  });
  expect(NAV_BY_ROLE.RESEARCHER).toEqual({
    bar: ["Ask", "Crafts", "Map", "Saved"],
    account: ["Give a picture", "Propose knowledge", "Connect your AI", "Settings"],
    menu: ["Ask", "Crafts", "Map", "Saved", "Give a picture", "Propose knowledge", "Connect your AI", "Settings"],
    depths: ["Basic", "Detailed", "Expert"]
  });
  expect(NAV_BY_ROLE.PROFESSOR).toBeUndefined();
});

test("run files follow the naming golden rows", () => {
  const rows = JSON.parse(readFileSync(join(SHARED, "naming-golden.json"), "utf8")).evalRunFiles as {
    startedAt: string;
    subject: string;
    what: string;
    ext: string;
    sequence?: string;
    fileName: string;
  }[];
  const before = process.env.E2E_RUN_STARTED_AT;
  try {
    for (const row of rows) {
      process.env.E2E_RUN_STARTED_AT = row.startedAt;
      expect(runFileName(row)).toBe(row.fileName);
    }
  } finally {
    if (before === undefined) delete process.env.E2E_RUN_STARTED_AT;
    else process.env.E2E_RUN_STARTED_AT = before;
  }
});

test("the step summary orders widths from widest and escapes table cells", () => {
  const screens = (width: string, px: number, problems: string[]): ScreensReport => ({
    kind: "screens",
    width,
    viewport: { width: px, height: 800 },
    baseUrl: "https://example.org",
    runId: "7",
    startedAt: "2026-11-17T09:00:00Z",
    role: "RESEARCHER",
    problemCount: problems.length,
    screens: [{ name: "Ask", path: "/ask", screenshot: null, durationMs: 1, problems, notes: [] }]
  });
  const answers: AnswersReport = {
    kind: "answers",
    baseUrl: "https://example.org",
    runId: "7",
    startedAt: "2026-11-17T09:00:00Z",
    role: "RESEARCHER",
    problemCount: 0,
    unasked: [],
    questions: [recordOf(LEDE_GOLDEN, ENGLISH), recordOf(HINDI_ANSWER, HINDI), { ...recordOf(waterAnswer(sentence("w2", "Alum is the mordant.")), WATER), notes: [RIVERS_NOT_LOADED_NOTE] }],
    exports: null
  };
  const markdown = summaryMarkdown([screens("Phone", 390, ["a | b"]), screens("Desktop", 1440, [])], {
    runId: "7",
    baseUrl: "https://example.org",
    startedAt: "2026-11-17T09:00:00Z",
    questionsRequested: true
  });
  expect(markdown).toContain("| Screen | Desktop | Phone |");
  expect(markdown).toContain("| Ask | Pass | Fail (1) |");
  expect(markdown).toContain("- Phone · Ask: a \\| b");
  const withAnswers = summaryMarkdown([screens("Desktop", 1440, []), answers], { runId: null, baseUrl: null, startedAt: "x", questionsRequested: true });
  expect(withAnswers).toContain("| Question | Ended | Lede | Sentences | Cited | Citations | Sources | Known answer | Script | Done in | Result |");
  expect(withAnswers).toContain("| English | done | 3 cited | 9 | 9 | 13 | 2 | Yes | English |");
  expect(withAnswers).toContain("| Hindi | done | None | 2 | 2 | 2 | 1 | Yes | 1 translated, 1 English, 0 other |");
  expect(withAnswers).toContain(`#### Answer notes\n\n- Water: ${RIVERS_NOT_LOADED_NOTE}`);
});

function indigoAnswer(...frames: string[]): string {
  return [block("source", SOURCE), ...PHASE_C.sources.map((source) => block("source", source)), sentence("i1", "Indigo turns blue as it meets the air."), ...frames, block("done", { answerId: null })].join("");
}

const DRAWN_FRAME: FrameSeen = { sandbox: "allow-scripts", policyFirst: true, drawn: true, peerless: true };

test("the nine known-answer questions ask the mordant in three languages, the water, materials, history, climate and the Ganga at Detailed depth and indigo at Expert", () => {
  expect(KNOWN_ANSWER_QUESTIONS.map((question) => [question.label, question.depth, question.check])).toEqual([
    ["English", "DETAILED", "MORDANT"],
    ["Hindi", "DETAILED", "MORDANT"],
    ["Water", "DETAILED", "WATER_STORY"],
    ["Indigo", "EXPERT", "GENERATED_EXPLAINER"],
    ["Materials", "DETAILED", "ZOOM_STORY"],
    ["History", "DETAILED", "TIMELINE_MAP"],
    ["Climate", "DETAILED", "SEASONS"],
    ["Ganga", "DETAILED", "RIVER_TIME"],
    ["Urdu", "DETAILED", "MORDANT"]
  ]);
  expect(KNOWN_ANSWER_QUESTIONS.filter((question) => question.craft).map((question) => question.craft)).toEqual(["Varanasi-Soft-Stone-Jali-Work"]);
  expect(INDIGO.question).toBe("How does indigo turn blue on Kutch Ajrakh cloth?");
  expect(FRAME_DOCUMENT_START).toContain("webrtc 'block'");
  const detailed = answerRecord({ question: INDIGO, stream: stream(indigoAnswer(), "en"), streamsOpened: 1, clickedAt: 1_000, waited: null });
  expect(answerProblems(detailed, INDIGO)).toContain("the request asked at DETAILED, not EXPERT");
});

test("indigo passes when its generated explainer draws in the sandbox and its frame reaches nothing", () => {
  const generated = block("block", { sectionId: "s1", block: phaseCBlock("simulation", "s1.b1") });
  const record = recordOf(indigoAnswer(generated), INDIGO);
  expect(record.generatedExplainer).toMatchObject({ blocks: 1, values: 2, valuesWithoutBasis: 0 });
  expect(record.knownAnswerFound).toBe(true);
  expect(answerProblems({ ...record, generatedExplainer: { ...record.generatedExplainer, frames: [DRAWN_FRAME] } }, INDIGO)).toEqual([]);
  const leaking = { ...record.generatedExplainer, frames: [DRAWN_FRAME], frameRequests: ["https://example.org/leak"], frameRefusals: ["Refused to connect to 'https://example.org/'"] };
  expect(answerProblems({ ...record, generatedExplainer: leaking }, INDIGO)).toEqual([
    "a generated explainer frame attempted 1 network requests: https://example.org/leak",
    "a generated explainer frame attempted 1 loads its policy refused: Refused to connect to 'https://example.org/'"
  ]);
  const broken = { ...record.generatedExplainer, frames: [{ sandbox: "allow-scripts allow-same-origin", policyFirst: false, drawn: false, peerless: false }, DRAWN_FRAME] };
  expect(answerProblems({ ...record, generatedExplainer: broken }, INDIGO)).toEqual([
    "the stream sent 1 generated explainers; the page draws 2 sandboxed frames",
    '1 generated explainer frames lack sandbox="allow-scripts" or the policy as their first head element',
    "1 generated explainer frames drew nothing",
    "1 generated explainer frames still offer a peer connection"
  ]);
});

test("without a generated explainer the indigo question records that the builder chose no concept and does not fail", () => {
  const record = recordOf(indigoAnswer(), INDIGO);
  expect(record.generatedExplainer.blocks).toBe(0);
  expect(record.knownAnswerFound).toBe(false);
  expect(answerProblems({ ...record, generatedExplainer: { ...record.generatedExplainer, frames: [] } }, INDIGO)).toEqual([]);
  expect(knownAnswerOutcome(record, INDIGO).notes).toEqual([NO_CONCEPT_NOTE]);
});

const CHIP = (number: number) => `<button type="button" data-testid="citation-chip"><span>${number}</span></button>`;
const CITED = (text: string, numbers: number[]) => `<span data-testid="answer-sentence"><span lang="en">${text}</span><span>${numbers.map(CHIP).join(" ")}</span> </span>`;
const THUMB = (width: number) => `https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Ajrakh_cloth.jpg/${width}px-Ajrakh_cloth.jpg`;
const REGION = { panel: REGION_PANEL, marker: REGION_MARKER };

test("a half-built headline and a faded largest element fail the opacity gate, and a steady page passes", async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 600 });
  const faded = "A long faded paragraph that fills most of the first screen. ".repeat(6);
  await page.setContent(
    `<h1><span>Ask</span> <span>how</span> <span style="opacity:0.4">crafts</span> <span style="opacity:0">work</span></h1><p style="font-size:40px;opacity:0.5">${faded}</p><p>Small.</p>`
  );
  const found = await page.evaluate(opacityAtCapture, FULL_OPACITY);
  expect(found.headline).toEqual([
    { word: "crafts", opacity: 0.4 },
    { word: "work", opacity: 0 }
  ]);
  expect(found.largest?.opacity).toBe(0.5);
  expect(found.largest?.name.startsWith('<p> "A long faded paragraph')).toBe(true);
  expect(opacityProblems(found)).toEqual([
    'the headline is half drawn at capture: "crafts" at 40%, "work" at 0%',
    `the largest element on screen is at 50% opacity at capture: ${found.largest?.name}`
  ]);
  await page.setContent(
    '<h1><span>Ask</span> <span>how</span> crafts work</h1><p style="font-size:40px">A steady paragraph.</p><div aria-hidden="true" style="opacity:0.1;font-size:90px">Decoration</div>'
  );
  expect(opacityProblems(await page.evaluate(opacityAtCapture, FULL_OPACITY))).toEqual([]);
});

test("a citation cluster reading 1 4 1 4 fails, and clusters of distinct numbers pass", async ({ page }) => {
  const unnumbered = '<span data-testid="answer-sentence"><span lang="en">Alum.</span><button data-testid="citation-chip">·</button> <button data-testid="citation-chip">·</button></span>';
  await page.setContent(`<p>${CITED("Ajrakh is printed in Kachchh.", [1, 4, 1, 4])}${CITED("It is dyed with indigo.", [1, 4])}${CITED("Madder gives the red.", [5, 6])}${unnumbered}</p>`);
  const clusters = await page.evaluate(citationClusters);
  expect(clusters).toEqual([{ numbers: ["1", "4", "1", "4"], context: "Ajrakh is printed in Kachchh." }]);
  expect(clusterProblems(clusters)).toEqual(['a citation cluster repeats a source number (1 4 1 4) after "Ajrakh is printed in Kachchh."']);
});

test("an answer that repeats a sentence or a picture fails, hidden twins and text outside the answer do not count, and unloaded pictures show as empty frames", async ({ page }) => {
  await page.route("https://upload.wikimedia.org/**", (route) => route.abort());
  await page.setContent(
    `<article data-testid="answer-view"><p>${CITED("Indigo came from Sindh.", [1])}${CITED("Indigo came from Sindh.", [2])}${CITED("Alum fixes the red.", [3])}</p>` +
      `<p style="display:none">${CITED("Alum fixes the red.", [3])}</p>` +
      `<img alt="Ajrakh" width="120" height="90" src="${THUMB(320)}"><img alt="Ajrakh again" width="120" height="90" src="${THUMB(640)}"></article>` +
      `<section>${CITED("Indigo came from Sindh.", [1])}</section>`
  );
  const repeats = await page.evaluate(answerRepeats, ANSWER_SCOPE);
  expect(repeats).toEqual({
    sentences: [{ what: "Indigo came from Sindh.", count: 2 }],
    pictures: [{ what: "upload.wikimedia.org/wikipedia/commons/a/ab/Ajrakh_cloth.jpg", count: 2 }]
  });
  expect(repeatProblems(repeats)).toEqual([
    'the answer shows 1 repeated sentences, such as "Indigo came from Sindh." 2 times',
    "the answer shows 1 repeated pictures: upload.wikimedia.org/wikipedia/commons/a/ab/Ajrakh_cloth.jpg 2 times"
  ]);
  expect(emptyPictureProblems(await page.evaluate(emptyPictures, MIN_PICTURE_PX))).toEqual(['2 pictures show an empty frame: "Ajrakh", "Ajrakh again"']);
});

test("a screen-high tile of one flat colour fails, a tile with anything drawn passes, and a short last tile is not judged", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 300 });
  const band = (body: string) => `<div style="height:300px;overflow:hidden">${body}</div>`;
  const drawn = band('<p style="margin:0;font-size:24px">Ajrakh</p><div style="width:200px;height:120px;background:#2a4385"></div>');
  await page.setContent(`<body style="margin:0;background:#f7f6fb">${drawn}${band("")}${drawn}<div style="height:100px"></div></body>`);
  const ratio = await page.evaluate(() => window.devicePixelRatio);
  const scan = await scanTiles(await page.screenshot({ fullPage: true }), 300 * ratio);
  expect({ judged: scan.judged, flat: scan.flat, height: scan.height }).toEqual({ judged: 3, flat: [1], height: 1000 * ratio });
  expect(tileProblems(scan)).toEqual(["1 of 3 screen-high tiles are one flat colour: 2"]);
  await page.setContent(`<body style="margin:0;background:#110f19">${drawn}${drawn}</body>`);
  expect(tileProblems(await scanTiles(await page.screenshot({ fullPage: true }), 300 * ratio))).toEqual([]);
  await expect(scanTiles(Buffer.from("not a png"), 300)).rejects.toThrow("the screenshot is not a PNG");
});

test("tiles are judged from what was painted: a tile blank only in the full-page screenshot is a note, a blank band past eight screens keeps its number", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 100 });
  const band = (drawn: boolean) =>
    `<div style="height:100px;overflow:hidden">${drawn ? '<p style="margin:0;font-size:24px">Ajrakh</p><div style="width:200px;height:40px;background:#2a4385"></div>' : ""}</div>`;
  const sheet = (blank: (index: number) => boolean) =>
    `<body style="margin:0;background:#f7f6fb">${Array.from({ length: 20 }, (_, index) => band(!blank(index))).join("")}</body>`;
  const twoBlank = (index: number) => index === 9 || index === 17;
  const blankTiles = "2 of 20 screen-high tiles are one flat colour: 10, 18";
  await page.setContent(sheet(twoBlank));
  expect(await judgeCapture(page, await page.screenshot({ fullPage: true }))).toEqual({ problems: [blankTiles], notes: [] });
  await page.setContent(sheet((index) => index >= 2));
  const unpainted = await page.screenshot({ fullPage: true });
  await page.setContent(sheet(twoBlank));
  expect(await judgeCapture(page, unpainted)).toEqual({
    problems: [blankTiles],
    notes: ["the full-page screenshot stops painting near 200 px, so 16 of its tiles look blank; each was judged from its own capture"]
  });
  await page.setContent(sheet(() => false));
  expect(await judgeCapture(page, unpainted)).toEqual({
    problems: [],
    notes: ["the full-page screenshot stops painting near 200 px, so 18 of its tiles look blank; each was judged from its own capture"]
  });
  expect(unpaintedNotes([4, 5], [4, 5], 844)).toEqual([]);
});

test("Loading, Searching and Checking left on screen fail, and the same words in prose, cited text or hidden text do not", async ({ page }) => {
  await page.setContent(
    '<p role="status">Loading…</p><p><span>Searching sources</span></p><p>Checking the vat every morning keeps the indigo alive, as the dyers of Dhamadka and Ajrakhpur say.</p>' +
      '<span data-level="PROVISIONAL">Loading the cloth</span><p style="display:none">Checking your admin view…</p>'
  );
  const busy = await page.evaluate(busyText, { citedSelector: CITED_CONTENT, pattern: BUSY_PATTERN });
  expect(busy).toEqual(["Loading…", "Searching sources"]);
  expect(busyProblems(busy)).toEqual(['"Loading…", "Searching sources" is still on screen once the page settled']);
  expect(busyProblems([])).toEqual([]);
});

test("the Region tab may run three screens before All measurements, and no further", async ({ page }) => {
  const panel = (markerAt: number | null) =>
    `<section data-testid="craft-panel-region"><div style="height:${markerAt ?? 3000}px"></div>${markerAt === null ? "" : `<button>${REGION_MARKER}</button><div style="height:4000px"></div>`}</section>`;
  await page.setContent(panel(null));
  const tall = await page.evaluate(regionRunPx, REGION);
  expect(tall).toBe(3000);
  expect(regionProblems(tall, 844)).toEqual([`the Region tab runs 3.6 screens before "${REGION_MARKER}"; it must fit in 3`]);
  await page.setContent(panel(2000));
  expect(regionProblems(await page.evaluate(regionRunPx, REGION), 844)).toEqual([]);
  await page.setContent("<main></main>");
  expect(await page.evaluate(regionRunPx, REGION)).toBeNull();
});

test("gap admissions on the busiest routes are caught", () => {
  expect(gapCopyFindings("Not enough cited evidence yet. Research it live.")).toEqual(["Not enough cited evidence yet. Research it live."]);
  expect(gapCopyFindings("This craft is not curated.")).toHaveLength(1);
  expect(gapCopyFindings("Its process is yet to be researched.")).toHaveLength(1);
  expect(gapCopyFindings("Enough cited evidence for every stage.")).toEqual([]);
});

test("a dark run must draw the dark theme, and molecules must report ready", () => {
  expect(themeProblems("light", "dark")).toEqual(["the page is drawn light; this run asks for dark"]);
  expect(themeProblems("dark", "dark")).toEqual([]);
  expect(themeProblems(null, null)).toEqual([]);
  expect(moleculeProblems(["ready", "failed", "loading", "waiting", "hidden"])).toEqual(["1 3D molecules did not load", "2 3D molecules never reported ready"]);
  expect(moleculeProblems(["ready", "hidden"])).toEqual([]);
});

test("the matrix runs 360, 390, 834, 1440 and 1920 in light and dark", () => {
  expect(SCREEN_WIDTHS.map((width) => width.viewport.width).sort((a, b) => a - b)).toEqual([360, 390, 834, 1440, 1920]);
  expect(SCHEMES).toEqual(["light", "dark"]);
});

test("only production and this project's Vercel previews may be driven", () => {
  const preview = "https://kalavigyan-ab12cd34e-cxacraftecosystem-8028s-projects.vercel.app";
  expect(siteRefusal(PRODUCTION_ORIGIN)).toBeNull();
  expect(siteRefusal(`${PRODUCTION_ORIGIN}/`)).toBeNull();
  expect(isPreview(preview)).toBe(true);
  expect(siteRefusal(preview)).toBeNull();
  const refused = [
    "https://evil.vercel.app",
    "https://kalavigyan-ab12cd34e-someone-else.vercel.app",
    `${preview}.evil.example`,
    preview.replace("https:", "http:"),
    `https://user:pass@${new URL(preview).host}`,
    "https://kalavigyan-git-main-cxacraftecosystem-8028s-projects.vercel.app",
    "not a url"
  ];
  for (const url of refused) {
    expect(isPreview(url), url).toBe(false);
    expect(siteRefusal(url), url).not.toBeNull();
  }
});

test("the Professor and Admin accounts sign in only on production, never on a preview", () => {
  const preview = "https://kalavigyan-ab12cd34e-cxacraftecosystem-8028s-projects.vercel.app";
  expect(roleSiteRefusal(PRODUCTION_ORIGIN)).toBeNull();
  expect(roleSiteRefusal(`${PRODUCTION_ORIGIN}/admin`)).toBeNull();
  for (const url of [preview, "http://kalavigyan.vercel.app", "https://kalavigyan.vercel.app.evil.example", "https://localhost:3000", "not a url"]) {
    expect(roleSiteRefusal(url), url).not.toBeNull();
  }
  const names = ["E2E_BASE_URL", "E2E_ADMIN_EMAIL", "E2E_ADMIN_PASSWORD", "E2E_ADMIN_TOTP_SECRET"] as const;
  const before = names.map((name) => process.env[name]);
  try {
    process.env.E2E_ADMIN_EMAIL = "e2e-admin@kalavigyan.example";
    process.env.E2E_ADMIN_PASSWORD = "unit-passphrase-only";
    process.env.E2E_ADMIN_TOTP_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ";
    process.env.E2E_BASE_URL = preview;
    expect(roleCredentials("ADMIN")).toBeNull();
    process.env.E2E_BASE_URL = PRODUCTION_ORIGIN;
    expect(roleCredentials("ADMIN")?.email).toBe("e2e-admin@kalavigyan.example");
  } finally {
    names.forEach((name, index) => {
      const value = before[index];
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    });
  }
});

test("Google refusing a preview origin is told apart from every other console error", () => {
  const forbidden = "Failed to load resource: the server responded with a status of 403 ()";
  expect(googleRefusesPreview(GOOGLE_ORIGIN_REFUSED, "https://accounts.google.com/gsi/client")).toBe(true);
  expect(googleRefusesPreview(forbidden, "https://accounts.google.com/gsi/button?theme=outline&client_id=1")).toBe(true);
  expect(googleRefusesPreview(forbidden, "https://kalavigyan-ab12cd34e-cxacraftecosystem-8028s-projects.vercel.app/api/crafts")).toBe(false);
  expect(googleRefusesPreview(forbidden, "https://accounts.google.com.evil.example/gsi/button")).toBe(false);
  expect(googleRefusesPreview("[GSI_LOGGER]: Provided button width is invalid: 1000", "https://accounts.google.com/gsi/client")).toBe(false);
  expect(googleRefusesPreview("TypeError: x is undefined", "https://accounts.google.com/gsi/client")).toBe(false);
});

test("on a preview, only Google's refusal and the blocked Vercel toolbar frame are noise", () => {
  const toolbar = "Framing 'https://vercel.live/' violates the following Content Security Policy directive: \"frame-src https://accounts.google.com/gsi/\". The request has been blocked.";
  expect(previewConsoleNoise(toolbar, "https://kalavigyan-ab12cd34e-cxacraftecosystem-8028s-projects.vercel.app/crafts")).toBe(true);
  expect(previewConsoleNoise(GOOGLE_ORIGIN_REFUSED, "https://accounts.google.com/gsi/client")).toBe(true);
  expect(previewConsoleNoise("Refused to load https://vercel.live/_next-live/feedback/feedback.html?dpl=dpl_1 because it does not appear in the frame-src directive of the Content Security Policy.", "")).toBe(true);
  expect(previewConsoleNoise("Framing 'https://evil.example/' violates the following Content Security Policy directive: \"frame-src 'none'\".", "")).toBe(false);
  expect(previewConsoleNoise("TypeError: Cannot read properties of null (reading 'textContent')", "")).toBe(false);
});

test("two-step codes match the RFC 6238 SHA-1 vectors", () => {
  const secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ";
  expect(base32Bytes(secret).toString("latin1")).toBe("12345678901234567890");
  expect(totpCode(secret, 59_000)).toBe("287082");
  expect(totpCode(secret, 1_111_111_109_000)).toBe("081804");
  expect(totpCode(secret, 1_234_567_890_000)).toBe("005924");
  expect(totpCode(secret, 20_000_000_000_000)).toBe("353130");
  expect(() => base32Bytes("not base32!")).toThrow("the two-step secret is not base32");
});

test("a page is captured only once it has scrolled to the end, its molecules report ready and it is back at the top", async ({ page }, testInfo) => {
  const network = new NetworkQuiet(page);
  await page.setViewportSize({ width: 400, height: 300 });
  await page.setContent(
    '<body style="margin:0"><h1>Ajrakh</h1><div style="height:1500px;background:linear-gradient(#f7f6fb,#2a4385)"></div>' +
      '<figure data-testid="molecule-3d" data-status="waiting" style="height:120px;margin:0;background:#ae2e27">Indigo</figure>' +
      "<script>new IntersectionObserver((seen) => { if (seen.some((entry) => entry.isIntersecting)) document.querySelector('figure').dataset.status = 'ready'; }).observe(document.querySelector('figure'));</script></body>"
  );
  expect(await readyForCapture(page, network)).toEqual([]);
  expect(await page.evaluate(() => [window.scrollY, document.querySelector("figure")?.getAttribute("data-status")])).toEqual([0, "ready"]);
  expect(await sightProblems(page, null)).toEqual([]);
  expect(await captureScreen(page, testInfo.outputPath("captured.png"))).toEqual({ problems: [], notes: [] });
});

test("a failed step is reported by its first line and Playwright's Error line, without terminal colours", () => {
  const escape = String.fromCharCode(27);
  const expectFailure = new Error(
    [
      `${escape}[2mexpect(${escape}[22m${escape}[31mlocator${escape}[39m${escape}[2m).${escape}[22mtoContainText${escape}[2m(${escape}[22m${escape}[32mexpected${escape}[39m${escape}[2m)${escape}[22m failed`,
      "",
      "Locator: getByRole('alert')",
      "Expected substring: \"This craft could not be found.\"",
      "Error: strict mode violation: getByRole('alert') resolved to 2 elements:",
      "    1) <section role=\"alert\">…</section>"
    ].join("\n")
  );
  expect(errorHeadline(expectFailure)).toBe(
    "expect(locator).toContainText(expected) failed Error: strict mode violation: getByRole('alert') resolved to 2 elements:"
  );
  expect(errorHeadline(new Error("Timeout 30000ms exceeded."))).toBe("Timeout 30000ms exceeded.");
  expect(errorHeadline("plain words")).toBe("plain words");
  expect(errorHeadline(new Error(""))).toBe("");
});

test("the unknown craft's alert is found by its text, not confused with the route announcer in its shadow root", async ({ page }) => {
  const text = "This craft could not be found. It may have been deleted.";
  await page.setContent(
    `<main><section role="alert">${text}</section></main><div id="announcer-host"></div><script>document.getElementById("announcer-host").attachShadow({ mode: "open" }).innerHTML = '<div role="alert" aria-live="assertive">Craft · KalaVigyan</div>';</script>`
  );
  expect(await page.getByRole("alert").count()).toBe(2);
  await expect(page.getByRole("alert").filter({ hasText: text })).toBeVisible();
  expect(await page.getByRole("main").getByRole("alert").count()).toBe(1);
  const screens = readFileSync(join(__dirname, "production", "screens.spec.ts"), "utf8");
  expect(screens).not.toMatch(/getByRole\("alert"\)\)/);
  const screenChecks = readFileSync(join(__dirname, "production", "screenChecks.ts"), "utf8");
  expect(screenChecks).not.toMatch(/\.or\(page\.getByRole\("alert"\)\)/);
});
