import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { ENGLISH, type AnswerLanguage } from "@/lib/answerLanguages";
import { splitSseBuffer } from "@/lib/answerStream";
import { askDepthsOf, normaliseAskConfig } from "@/lib/askConfig";
import { ANY_CRAFT, ANY_CRAFT_VALUE, craftOffer, craftOptions, craftPickOf, craftValue, DETECT_CRAFT, namesLine, pickForQuestion, samePick, type CraftPick } from "@/lib/askCraft";
import { askedDepth, depthParam } from "@/lib/askDepth";
import { askable, askRequestOf, askSearch, plannedAsk, QUESTION_MAX, reasksOnChange, type AskSettings } from "@/lib/askRequest";
import type { CatalogueCraft } from "@/lib/craftCatalogueContract";
import type { Depth, Understood } from "@/lib/explainerContract";
import { askingExplainer, reduceExplainer, type ExplainerState } from "@/lib/explainerState";
import { explainerEventOf, type ExplainerEvent } from "@/lib/explainerStream";

const ROOT = join(__dirname, "..", "..");
const read = (...parts: string[]) => readFileSync(join(ROOT, ...parts), "utf8");

const AJRAKH = { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" };
const BAGRU = { slug: "Bagru-Hand-Block-Print", name: "Bagru Hand Block Print", path: "/crafts/Bagru-Hand-Block-Print" };
const BAGH = { slug: "Bagh-Print", name: "Bagh Print", path: "/crafts/Bagh-Print" };
const PICKED_AJRAKH: CraftPick = { craftSlug: "Kutch-Ajrakh", anyCraft: false };
const EVERY_DEPTH = [
  { depth: "BASIC", label: "Basic" },
  { depth: "DETAILED", label: "Detailed" },
  { depth: "EXPERT", label: "Expert" }
];
const PLAN_DEFAULTS: Record<string, Depth> = { STUDENT: "BASIC", ARTISAN: "BASIC", RESEARCHER: "DETAILED", PROFESSOR: "DETAILED", ADMIN: "EXPERT", MASTER_ADMIN: "EXPERT" };

function understood(crafts: Understood["crafts"], candidates: Understood["candidates"] = []): Understood {
  return { crafts, candidates, depth: "EXPERT", language: "en" };
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

function backendMapping(file: string, name: string): Record<string, string> {
  const text = read("backend", "app", ...file.split("/"));
  const block = new RegExp(`^${name}\\b[^\\n]*\\n?([\\s\\S]*?)^\\)`, "m").exec(text);
  if (!block) throw new Error(`${name} is not a mapping in backend/app/${file}`);
  return Object.fromEntries([...block[1].matchAll(/"?(\w+)"?: "(\w+)"/g)].map((found) => [found[1], found[2]]));
}

function goldenUnderstoodState(): ExplainerState {
  const { blocks } = splitSseBuffer(read("shared", "explainer.stream.golden.sse"));
  const events = blocks.map(explainerEventOf).filter((event): event is ExplainerEvent => event !== null);
  return events.reduce(reduceExplainer, askingExplainer("How is the red fixed in Ajrakh?", "en"));
}

test("the server sets each role's starting depth as the plan's table does, and the config carries it", () => {
  const roles = Object.fromEntries([...read("backend", "app", "core", "roles.py").matchAll(/^([A-Z_]+) = "([A-Z_]+)"$/gm)].map((found) => [found[1], found[2]]));
  const server = Object.entries(backendMapping("research/depth.py", "ROLE_DEFAULT_DEPTHS")).map(([name, depth]) => [roles[name], depth]);
  expect(Object.fromEntries(server)).toEqual(PLAN_DEFAULTS);
  expect(backendMapping("research/depth.py", "DEPTH_LABELS")).toEqual({ BASIC: "Basic", DETAILED: "Detailed", EXPERT: "Expert" });
  const route = read("backend", "app", "api", "routes", "knowledge.py");
  expect(route).toMatch(/"depths":\s*\[\s*\{"depth":\s*depth,\s*"label":\s*DEPTH_LABELS\[depth\]\}\s*for depth in depths\s*\]/);
  expect(route).toMatch(/"defaultDepth":\s*default_depth\(user\)/);
});

test("the screen starts at the role's depth from the config, and a depth the reader picks wins", () => {
  for (const [role, depth] of Object.entries(PLAN_DEFAULTS)) {
    const offered = normaliseAskConfig({ depths: EVERY_DEPTH, defaultDepth: depth });
    expect(askedDepth(null, offered), role).toBe(depth);
    expect(offered.depths.map((option) => option.label)).toEqual(["Basic", "Detailed", "Expert"]);
    expect(askedDepth("EXPERT", offered)).toBe("EXPERT");
  }
});

test("before the config arrives the server's default is asked for, and an address depth is kept", () => {
  const none = normaliseAskConfig({});
  expect(none).toMatchObject({ depths: [], defaultDepth: null });
  expect(askedDepth(null, none)).toBeNull();
  expect(askedDepth("BASIC", none)).toBe("BASIC");
  expect(askRequestOf("Why alum?", { pick: DETECT_CRAFT, depth: null, language: "en" })).toEqual({ question: "Why alum?", depth: null, craftSlug: null, language: "en" });
});

test("a depth list off the contract hides the choice and says why in the console", () => {
  const unknown = quietly(() => askDepthsOf([{ depth: "DEEP", label: "Deep" }], "DEEP"));
  expect(unknown.value).toEqual({ depths: [], defaultDepth: null });
  expect(String(unknown.logged[0])).toContain("answers/config depths");
  const unlisted = quietly(() => askDepthsOf(EVERY_DEPTH.slice(0, 2), "EXPERT"));
  expect(unlisted.value.depths).toEqual([]);
  expect(String(unlisted.logged[0])).toContain("one of the listed depths");
  expect(quietly(() => askDepthsOf([...EVERY_DEPTH, EVERY_DEPTH[0]], "BASIC")).value.depths).toEqual([]);
  expect(askDepthsOf([], null)).toEqual({ depths: [], defaultDepth: null });
});

test("a depth in the address is used only when it is one of the three", () => {
  expect(depthParam("EXPERT")).toBe("EXPERT");
  expect(depthParam("expert")).toBeNull();
  expect(depthParam("DEEP")).toBeNull();
  expect(depthParam(null)).toBeNull();
});

test("the craft is optional: before an answer the picker says Any craft and the ask names no craft", () => {
  expect(craftOffer(null, DETECT_CRAFT)).toEqual({ noneLabel: ANY_CRAFT, detected: [], candidates: [] });
  expect(craftValue(DETECT_CRAFT, craftOffer(null, DETECT_CRAFT))).toBe("");
  const request = askRequestOf("  Why does alum fix madder?  ", { pick: DETECT_CRAFT, depth: "BASIC", language: "en" });
  expect(request).toEqual({ question: "Why does alum fix madder?", depth: "BASIC", craftSlug: null, language: "en" });
  expect(request).not.toHaveProperty("mode");
  expect(request).not.toHaveProperty("anyCraft");
});

test("after the understood event the detected craft is named, Any craft is offered and the candidates are one tap away", () => {
  const state = goldenUnderstoodState();
  expect(state.understood).toEqual({ ...understood([AJRAKH], [BAGRU]), basis: "MODEL" });
  const offer = craftOffer(state.understood, DETECT_CRAFT);
  expect(offer.noneLabel).toBe("Kutch Ajrakh · detected");
  expect(offer.candidates).toEqual([BAGRU]);
  expect(craftValue(DETECT_CRAFT, offer)).toBe("");
  expect(craftOptions(null, DETECT_CRAFT, state.understood)).toEqual([{ value: ANY_CRAFT_VALUE, label: ANY_CRAFT }]);
});

test("choosing Any craft over a detected one asks without a craft; a new question detects again", () => {
  const any = craftPickOf(ANY_CRAFT_VALUE);
  expect(any).toEqual({ craftSlug: null, anyCraft: true });
  expect(askRequestOf("Why alum?", { pick: any, depth: "DETAILED", language: "en" })).toEqual({
    question: "Why alum?",
    depth: "DETAILED",
    craftSlug: null,
    language: "en",
    anyCraft: true
  });
  expect(pickForQuestion(any, "Why alum?", " Why alum? ")).toEqual(any);
  expect(pickForQuestion(any, "Why alum?", "Why iron?")).toEqual(DETECT_CRAFT);
  expect(pickForQuestion(PICKED_AJRAKH, "Why alum?", "Why iron?")).toEqual(PICKED_AJRAKH);
  expect(craftPickOf("")).toEqual(DETECT_CRAFT);
  expect(craftPickOf("Bagh-Print")).toEqual({ craftSlug: "Bagh-Print", anyCraft: false });
  expect(samePick(craftPickOf(""), DETECT_CRAFT)).toBe(true);
  expect(samePick(any, DETECT_CRAFT)).toBe(false);
});

test("a craft the reader picked is kept: no detected label, no candidates", () => {
  const offer = craftOffer(understood([AJRAKH], [BAGRU]), PICKED_AJRAKH);
  expect(offer).toEqual({ noneLabel: ANY_CRAFT, detected: [], candidates: [] });
  expect(craftValue(PICKED_AJRAKH, offer)).toBe("Kutch-Ajrakh");
});

test("nothing detected keeps Any craft and still offers the candidates; a comparison names every craft", () => {
  expect(craftOffer(understood([], [BAGRU, BAGH]), DETECT_CRAFT)).toEqual({ noneLabel: ANY_CRAFT, detected: [], candidates: [BAGRU, BAGH] });
  expect(craftOffer(understood([AJRAKH, BAGRU]), DETECT_CRAFT).noneLabel).toBe("Kutch Ajrakh and Bagru Hand Block Print · detected");
  expect(namesLine(["A", "B", "C"])).toBe("A, B and C");
  expect(namesLine(["A"])).toBe("A");
});

test("an understood event off the contract is refused loudly and changes nothing", () => {
  const parsed = quietly(() => explainerEventOf('event: understood\ndata: {"crafts":[],"candidates":[],"depth":"DEEP","language":"en"}'));
  expect(parsed.value).toBeNull();
  expect(String(parsed.logged[0])).toContain("understood.depth");
  const failed: ExplainerState = { ...askingExplainer("q", "en"), phase: "failed" };
  expect(reduceExplainer(failed, { type: "understood", data: understood([AJRAKH]) })).toBe(failed);
});

test("the picker lists the catalogue's crafts with their states, never a merged one, and keeps a picked craft it lacks", () => {
  const craft = (slug: string, name: string, states: string[], status?: "MERGED"): CatalogueCraft => ({
    id: slug,
    slug,
    name,
    displayName: name,
    localName: null,
    categoryId: null,
    subCategoryId: null,
    familyLabel: null,
    kindLabel: null,
    palette: null,
    sourceSerial: null,
    stateOfOrigin: [],
    stateOfPractice: states,
    giStatus: null,
    giYear: null,
    isCatchAll: false,
    craftCode: null,
    aliases: [],
    hero: null,
    depth: { coverage: null, claims: 0, stages: 0, pictures: 0, places: 0 },
    status
  });
  const catalogue = {
    crafts: [craft("Kutch-Ajrakh", "Kutch Ajrakh", ["Gujarat"]), craft("Old-Ajrakh", "Old Ajrakh", [], "MERGED"), craft("Bagh-Print", "Bagh Print", [])]
  };
  expect(craftOptions(catalogue, DETECT_CRAFT, null)).toEqual([
    { value: "Kutch-Ajrakh", label: "Kutch Ajrakh", hint: "Gujarat" },
    { value: "Bagh-Print", label: "Bagh Print" }
  ]);
  const bagru: CraftPick = { craftSlug: "Bagru-Hand-Block-Print", anyCraft: false };
  expect(craftOptions(catalogue, bagru, understood([AJRAKH], [BAGRU]))[0]).toEqual({ value: "Bagru-Hand-Block-Print", label: "Bagru Hand Block Print" });
  expect(craftOptions(null, { craftSlug: "Unknown-Craft", anyCraft: false }, null)).toEqual([{ value: "Unknown-Craft", label: "Unknown-Craft" }]);
});

test("a question is asked trimmed, between two and a thousand characters", () => {
  expect(askable(" a ")).toBe(false);
  expect(askable("ab")).toBe(true);
  expect(askRequestOf("x", { pick: DETECT_CRAFT, depth: "BASIC", language: "en" })).toBeNull();
  const long = askRequestOf("a".repeat(QUESTION_MAX + 5), { pick: PICKED_AJRAKH, depth: "EXPERT", language: "hi" });
  expect(long?.question).toHaveLength(1000);
  expect(long).toMatchObject({ craftSlug: "Kutch-Ajrakh", depth: "EXPERT", language: "hi" });
});

test("changing the craft, depth or language asks again only while the asked question is still in the box", () => {
  expect(reasksOnChange(true, "Why alum?", " Why alum? ")).toBe(true);
  expect(reasksOnChange(false, "Why alum?", "Why alum?")).toBe(false);
  expect(reasksOnChange(true, "Why alum?", "Why iron?")).toBe(false);
  expect(reasksOnChange(true, "", "")).toBe(false);
});

test("the address keeps the question, and the craft and depth only when chosen", () => {
  expect(askSearch("Why alum?", null, null)).toBe("q=Why+alum%3F");
  expect(askSearch("Why alum?", "Kutch-Ajrakh", "EXPERT")).toBe("q=Why+alum%3F&craft=Kutch-Ajrakh&depth=EXPERT");
});

const HINDI: AnswerLanguage = { code: "hi", label: "Hindi", autonym: "हिन्दी", script: "Deva", direction: "ltr" };
const SETTINGS: AskSettings = { pick: DETECT_CRAFT, depth: "DETAILED", pickedDepth: null, languageChoice: "auto", languages: [ENGLISH, HINDI] };

test("an ask carries the screen's choices, and a one-tap change replaces only what changed", () => {
  expect(plannedAsk("Why alum?", SETTINGS)).toEqual({
    request: { question: "Why alum?", depth: "DETAILED", craftSlug: null, language: "en" },
    search: "q=Why+alum%3F"
  });
  expect(plannedAsk("अजरख क्यों?", SETTINGS)?.request.language).toBe("hi");
  const candidate = plannedAsk("Why alum?", SETTINGS, { pick: { craftSlug: "Bagru-Hand-Block-Print", anyCraft: false } });
  expect(candidate?.request).toMatchObject({ craftSlug: "Bagru-Hand-Block-Print", depth: "DETAILED" });
  expect(candidate?.search).toBe("q=Why+alum%3F&craft=Bagru-Hand-Block-Print");
  expect(plannedAsk("Why alum?", { ...SETTINGS, pick: PICKED_AJRAKH }, { pick: DETECT_CRAFT })?.request.craftSlug).toBeNull();
  expect(plannedAsk("Why alum?", SETTINGS, { depth: "EXPERT" })?.search).toBe("q=Why+alum%3F&depth=EXPERT");
  expect(plannedAsk("Why alum?", SETTINGS, { languageChoice: "hi" })?.request.language).toBe("hi");
  expect(plannedAsk(" ", SETTINGS)).toBeNull();
});

test("research again asks the same question afresh, and only then", () => {
  expect(plannedAsk("Why alum?", SETTINGS, { fresh: true })?.request).toEqual({ question: "Why alum?", depth: "DETAILED", craftSlug: null, language: "en", fresh: true });
  expect(plannedAsk("Why alum?", SETTINGS)?.request).not.toHaveProperty("fresh");
});
