import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { chapterForTab, figureNumbers, itemCitations, itemKind, itemSourceIds } from "@/lib/craftChapterReads";
import { CHAPTER_KEYS, PAGE_BLOCK_KINDS, type Chapter, type ChapterItem, type ChapterKey, type ItemOrigin, type PageAiMedia, type PageBlock, type PagePart } from "@/lib/craftChapters";
import { originLabel } from "@/lib/craftOrigins";
import { checkedCraftPage } from "@/lib/craftPageChecks";
import { CRAFT_PAGE_PATH, craftEdition, craftPageShape, type CraftPage, type EvidenceEntry } from "@/lib/craftPageContract";
import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import { BLOCK_SHAPES, type LadderStage } from "@/lib/explainerContract";
import type { ExpertViewBlock } from "@/lib/explainerExperts";
import { parseShape, ShapeError } from "@/lib/shape";

import { CRAFT_PAGE_GOLDEN, curatedPage, rawPage, REGISTER_PAGE_GOLDEN, registerPage } from "./craftPageFixture";

const TITLES: Record<string, string> = {
  glance: "At a glance",
  made: "How it is made",
  chem: "The chemistry",
  why: "Why Kachchh",
  history: "History and trade",
  market: "Market and GI",
  whatif: "What if",
  people: "People and voices",
  kin: "Kin crafts and shared science",
  sources: "Sources"
};
const HOME_CHAPTERS: Record<string, string> = {
  key_facts: "glance",
  register_facts: "glance",
  start_research: "glance",
  process_ladder: "made",
  reaction_player: "chem",
  molecule_3d: "chem",
  material_card: "chem",
  zoom_story: "chem",
  region_story: "why",
  climate_risk: "why",
  seasons: "why",
  supply_map: "why",
  places: "why",
  timeline_map: "history",
  market_gi: "market",
  what_if: "whatif",
  communities: "people",
  artisan_voice: "people",
  field_photos: "people",
  concept_graph: "kin",
  relatives: "kin",
  source_list: "sources",
  open_questions: "sources",
  searched: "sources"
};
const PERSONAL_KEYS = /"(userId|answerId|createdFromAnswerId|requestedById|askedBy|email)":/;
const OUTSIDE = "00000000-0000-4000-8000-000000000001";

function refused(edit: (body: CraftPage) => void): () => CraftPage {
  return () => {
    const body = rawPage();
    edit(body);
    return checkedCraftPage(parseShape(craftPageShape, body));
  };
}

function chapter(page: CraftPage, key: string): Chapter {
  const found = page.chapters.find((entry) => entry.key === key);
  if (!found) throw new Error(`the page has no ${key} chapter`);
  return found;
}

function itemOf(page: CraftPage, kind: string): ChapterItem {
  const found = page.chapters.flatMap((entry) => entry.items).find((item) => itemKind(item) === kind);
  if (!found) throw new Error(`the page shows no ${kind}`);
  return found;
}

function ladderStage(page: CraftPage): LadderStage {
  const block = itemOf(page, "process_ladder").block;
  if (block?.kind !== "process_ladder") throw new Error("no ladder");
  return block.stages[0];
}

const origin = (extra: Partial<ItemOrigin>): ItemOrigin => ({ basis: "STORED", generated: null, model: null, generatedOn: null, fromQuestion: null, ...extra });

test("the Kutch Ajrakh monograph keeps the contract's chapter order and titles, each chapter with an item", () => {
  const page = curatedPage();
  const keys = page.chapters.map((entry) => entry.key);
  expect(keys).toEqual(CHAPTER_KEYS.filter((key) => keys.includes(key)));
  for (const entry of page.chapters) {
    expect(entry.title).toBe(TITLES[entry.key]);
    expect(entry.items.length).toBeGreaterThan(0);
  }
});

test("the Kutch Ajrakh golden holds every chapter the builders make; What if waits on its builder (decision 0098)", () => {
  expect(curatedPage().chapters.map((entry) => entry.key)).toEqual(CHAPTER_KEYS.filter((key) => key !== "whatif"));
});

test("each piece sits in the chapter of its kind, as an answer block or a page part", () => {
  for (const page of [curatedPage(), registerPage()]) {
    for (const entry of page.chapters) {
      for (const item of entry.items) {
        expect((item.block === null) !== (item.part === null)).toBe(true);
        const home = HOME_CHAPTERS[itemKind(item)];
        if (home) expect([itemKind(item), entry.key]).toEqual([itemKind(item), home]);
      }
    }
  }
});

test("figures and tables are numbered through the page, titled from the item's own values", () => {
  const page = curatedPage();
  const numbers = figureNumbers(page.chapters);
  const ladder = itemOf(page, "process_ladder");
  const facts = itemOf(page, "key_facts");
  expect(facts.figure).toEqual({ kind: "TABLE", title: "Key facts", borrowed: [] });
  expect(numbers.get(facts)).toBe("Table 1");
  const stages = ladder.block?.kind === "process_ladder" ? ladder.block.stages.length : 0;
  expect(ladder.figure?.title).toBe(`How Kutch Ajrakh is made, in ${stages} stages`);
  expect(numbers.get(ladder)).toBe("Fig. 1");
  const shown = [...numbers.values()];
  const figures = shown.filter((label) => label.startsWith("Fig."));
  expect(figures).toEqual(figures.map((_, index) => `Fig. ${index + 1}`));
});

test("an item's provenance reads as the contract words it, the asker never named", () => {
  expect(originLabel(null)).toEqual({ basis: null, question: null, generated: null, madeBy: null });
  expect(originLabel(origin({ basis: "CURATED" })).basis).toBeNull();
  expect(originLabel(origin({ basis: "STORED" })).basis).toBe("From earlier research");
  const asked = originLabel(origin({ basis: "READERS", fromQuestion: { text: "Why is the cloth boiled in madder?", askedIn: "2026-11" } }));
  expect([asked.basis, asked.question]).toEqual(["From a reader's question, November 2026", "Why is the cloth boiled in madder?"]);
  expect(originLabel(origin({ basis: "READERS", fromQuestion: { text: null, askedIn: "2026-11" } }))).toEqual({ basis: "From a reader's question", question: null, generated: null, madeBy: null });
  const built = originLabel(origin({ basis: "READERS", generated: "MODEL", model: "expert-explainer", generatedOn: "2026-11-18" }));
  expect([built.generated, built.madeBy]).toEqual(["Model-built from cited claims", "expert-explainer, 18 November 2026"]);
  expect(originLabel(origin({ basis: "READERS", generated: "AI_IMAGE", model: "image-model", generatedOn: "2026-11-02" })).generated).toBe("AI illustration");
  expect(originLabel(origin({ basis: "READERS", generated: "AI_VIDEO", model: "video-model", generatedOn: "2026-11-02" })).generated).toBe("AI video");
});

test("the client refuses an item that is both or neither, a block a page never shows, and an origin off its rules", () => {
  expect(refused((body) => (body.chapters[0].items[0].part = { kind: "start_research", questions: ["a", "b", "c"] }))).toThrow(/never both/);
  expect(refused((body) => (body.chapters[0].items[0] = { ...body.chapters[0].items[0], block: null, part: null }))).toThrow(/never both/);
  expect(refused((body) => (chapter(body, "glance").items[0].block = { id: "quiz", kind: "quiz", version: 1, reuse: null, questions: [] } as never))).toThrow(ShapeError);
  expect(refused((body) => (body.chapters[0].items[0].origin = origin({ generated: "MODEL" })))).toThrow(/model and day/);
  expect(refused((body) => (body.chapters[0].items[0].origin = origin({ basis: "CURATED", fromQuestion: { text: null, askedIn: "2026-11" } })))).toThrow(/reader's piece/);
  expect(refused((body) => (body.chapters[0].items[0].origin = origin({ basis: "READERS", fromQuestion: { text: "x".repeat(161), askedIn: "2026-11" } })))).toThrow(ShapeError);
  expect(refused((body) => ((body.chapters[0].items[0] as unknown as Record<string, unknown>).askedBy = "someone"))).toThrow(/no such field/);
});

test("the client refuses chapters out of order or twice, an empty chapter, a plate that is a link card, and a picture shown twice", () => {
  expect(refused((body) => body.chapters.reverse())).toThrow(/order/);
  expect(refused((body) => body.chapters.push(body.chapters[0]))).toThrow(ShapeError);
  expect(refused((body) => (body.chapters[0].items = []))).toThrow(ShapeError);
  expect(
    refused((body) => {
      const plate = body.chapters.flatMap((entry) => entry.items).find((item) => item.part?.kind === "plate");
      if (plate?.part?.kind === "plate") plate.part.plate.media.display = "LINK_CARD";
    })
  ).toThrow(/inline/);
  expect(
    refused((body) => {
      const plate = body.chapters.flatMap((entry) => entry.items).find((item) => item.part?.kind === "plate");
      if (plate) chapter(body, "sources").items.push(plate);
    })
  ).toThrow(/once/);
});

test("the client refuses a chapter that cites a claim or a source the page does not list", () => {
  const cite = (body: CraftPage) => {
    const prose = chapter(body, "glance").items.find((item) => item.block?.kind === "prose");
    if (prose?.block?.kind !== "prose") throw new Error("no prose at a glance");
    return prose.block.sentences[0].citations[0];
  };
  expect(refused((body) => (cite(body).claimId = OUTSIDE))).toThrow(/claim/);
  expect(refused((body) => (cite(body).sourceId = OUTSIDE))).toThrow(/source/);
});

test("the page's block fields parse beside the answer's: a ladder stage's added parts, a step's formula basis, a climate series", () => {
  const page = curatedPage();
  const stage = ladderStage(page);
  const citation = stage.sentences[0].citations[0];
  const added: LadderStage = {
    ...stage,
    localName: "saaj",
    unnumbered: true,
    after: { text: "red cloth", colours: ["RED"], citations: [citation] },
    why: stage.sentences[0],
    tools: [{ toolId: OUTSIDE, name: "Block", localNames: ["bibu"], citations: [citation] }],
    differs: [{ key: "d1", about: "Days", weight: 3, readings: [{ sentence: stage.sentences[0], shownIn: null }, { sentence: null, shownIn: stage.sentences[0].id }] }],
    pictures: []
  };
  const ladder = itemOf(page, "process_ladder").block;
  const parsed = BLOCK_SHAPES.process_ladder.parse({ ...ladder, stages: [{ ...added, pictures: undefined }] }, "ladder");
  expect(parsed.stages[0].after?.colours).toEqual(["RED"]);
  expect(() => BLOCK_SHAPES.process_ladder.parse({ ...ladder, stages: [{ ...added, pictures: undefined, after: { ...added.after, colours: ["TEAL"] } }] }, "ladder")).toThrow(ShapeError);
  const player = itemOf(page, "reaction_player").block;
  if (player?.kind !== "reaction_player") throw new Error("no reaction player");
  const step = { ...player.steps[0], formulaBasis: "COMPOUND_RECORD", formulaSources: [OUTSIDE] };
  expect(BLOCK_SHAPES.reaction_player.parse({ ...player, steps: [step] }, "player").steps[0].formulaBasis).toBe("COMPOUND_RECORD");
  expect(() => BLOCK_SHAPES.reaction_player.parse({ ...player, steps: [{ ...step, formulaBasis: "GUESSED" }] }, "player")).toThrow(ShapeError);
  const climate = itemOf(page, "climate_risk").block;
  if (climate?.kind !== "climate_risk") throw new Error("no climate block");
  const trend = climate.trends[0];
  const series = { district: trend.district, variable: trend.variable, datasetCode: trend.datasetCode, unit: "mm/year", firstYear: 1981, values: [512.5, null, 430] };
  expect(BLOCK_SHAPES.climate_risk.parse({ ...climate, series: [series] }, "climate").series?.[0].values).toEqual([512.5, null, 430]);
  expect(() => BLOCK_SHAPES.climate_risk.parse({ ...climate, series: [{ ...series, values: ["dry"] }] }, "climate")).toThrow(ShapeError);
});

test("the page shows every answer block kind it may hold and none it may not", () => {
  expect([...PAGE_BLOCK_KINDS].sort()).not.toContain("quiz");
  expect(PAGE_BLOCK_KINDS).not.toContain("compare");
  expect(PAGE_BLOCK_KINDS).not.toContain("map_layer");
  expect(PAGE_BLOCK_KINDS).toEqual(expect.arrayContaining(["prose", "process_ladder", "reaction_player", "simulation", "what_if", "indigo_vat", "firing", "artisan_voice"]));
});

test("version 2 tabs open the chapter that carries them", () => {
  expect(["overview", "process", "science", "region", "sharedScience", "sources", "evidence"].map(chapterForTab)).toEqual(["glance", "made", "chem", "why", "kin", "sources", "sources"]);
  expect(chapterForTab("profile")).toBeNull();
  expect(chapterForTab(null)).toBeNull();
});

const ASKED_IN = "2026-11";
const READER_QUESTION = "Why is the cloth boiled in madder?";
const AI_ASSET = "00000000-0000-4000-8000-0000000000a1";

function readerItem(block: PageBlock | null, part: PagePart | null, from: ItemOrigin): ChapterItem {
  return { block, part, figure: null, origin: from, pieceId: null };
}

function placed(page: CraftPage, key: ChapterKey, item: ChapterItem): void {
  const found = page.chapters.find((entry) => entry.key === key);
  if (found) found.items.push(item);
  else page.chapters.push({ key, title: TITLES[key], opener: null, items: [item] });
  page.chapters.sort((a, b) => CHAPTER_KEYS.indexOf(a.key) - CHAPTER_KEYS.indexOf(b.key));
}

function withReaderAnswer(body: CraftPage): void {
  const claim = body.claims.find((entry) => entry.level !== "HYPOTHESIS" && entry.citations.length > 0);
  if (!claim) throw new Error("the golden lists no cited fact");
  const asked = origin({ basis: "READERS", fromQuestion: { text: READER_QUESTION, askedIn: ASKED_IN } });
  const sentence = (id: string): ExplainerSentence => ({ id, text: claim.text, level: claim.level, citations: [claim.citations[0]], translated: false, terms: [] });
  const view: ExpertViewBlock = { id: "history.reader-1", kind: "expert_view", version: 1, reuse: null, seat: "HISTORIAN", take: [sentence("history.reader-1.1")], agreesWith: [], differs: [] };
  const picture: PageAiMedia = {
    assetId: AI_ASSET,
    kind: "IMAGE",
    url: `/api/crafts/media/${AI_ASSET}`,
    mime: "image/webp",
    width: 1600,
    height: 1000,
    durationSeconds: null,
    altText: "An AI illustration of printed cloth in a madder bath",
    sentences: [sentence("history.reader-2.1")],
    stageId: null,
    origin: { ...asked, generated: "AI_IMAGE", model: "image-model", generatedOn: "2026-11-18" }
  };
  placed(body, "history", readerItem(view, null, asked));
  placed(body, "history", readerItem(null, { kind: "ai_media", media: [picture] }, asked));
  body.masthead.provenance.updatedOn = "2026-11-18";
}

function withRecordedAnswer(body: CraftPage): void {
  const curated = rawPage();
  const prose = chapter(curated, "history").items.find((item) => item.block?.kind === "prose");
  if (!prose?.block) throw new Error("the golden has no history prose");
  const item = readerItem(prose.block, null, origin({ basis: "READERS", fromQuestion: { text: null, askedIn: ASKED_IN } }));
  const cited = new Set(itemCitations(item).map((citation) => citation.claimId));
  const filed = (entry: EvidenceEntry) => [entry.claimId, ...entry.foldedIds].some((id) => cited.has(id));
  const groups = curated.evidence.groups
    .map((group) => ({ ...group, subjects: group.subjects.map((subject) => ({ ...subject, entries: subject.entries.filter(filed) })).filter((subject) => subject.entries.length > 0) }))
    .filter((group) => group.subjects.length > 0);
  const hypotheses = curated.evidence.hypotheses.filter(filed);
  const kept = new Set([...groups.flatMap((group) => group.subjects.flatMap((subject) => subject.entries)), ...hypotheses].flatMap((entry) => [entry.claimId, ...entry.foldedIds]));
  const claims = curated.claims.filter((claim) => kept.has(claim.id));
  const sourceIds = new Set([...claims.flatMap((claim) => claim.citations.map((citation) => citation.sourceId)), ...itemSourceIds(item)]);
  const listed = new Set(body.sources.map((source) => source.id));
  body.evidence = { groups: [...body.evidence.groups, ...groups], hypotheses: [...body.evidence.hypotheses, ...hypotheses] };
  body.claims.push(...claims);
  body.sources.push(...curated.sources.filter((source) => sourceIds.has(source.id) && !listed.has(source.id)));
  placed(body, "history", item);
}

test("a reader's Expert answer joins Kutch Ajrakh with its question shown, its expert seat and its AI picture", () => {
  const page = curatedPage(withReaderAnswer);
  const items = page.chapters.flatMap((entry) => entry.items);
  const readers = items.filter((item) => item.origin?.basis === "READERS");
  expect(readers.length).toBeGreaterThan(0);
  expect(readers.some((item) => item.origin?.fromQuestion?.text)).toBe(true);
  expect(items.some((item) => item.block?.kind === "expert_view")).toBe(true);
  const media = items.flatMap((item) => (item.part?.kind === "ai_media" ? item.part.media : []));
  expect(media.map((entry) => [entry.kind, entry.origin.generated])).toEqual([["IMAGE", "AI_IMAGE"]]);
  expect(page.masthead.provenance.updatedOn).not.toBeNull();
});

test("a craft without a dossier shows only the chapters its rows support, each from the one recorded answer", () => {
  const page = registerPage(withRecordedAnswer);
  expect(page.curated).toBe(false);
  expect(chapter(page, "glance").items.some((item) => item.part?.kind === "register_facts")).toBe(true);
  const answered = page.chapters.filter((found) => !["glance", "sources", "kin"].includes(found.key));
  expect(answered.length).toBeGreaterThan(0);
  for (const entry of answered) {
    expect(entry.items.some((item) => item.origin?.basis === "READERS" && item.origin.fromQuestion?.text === null)).toBe(true);
  }
});

test("no golden carries a user or an answer id", () => {
  for (const golden of [CRAFT_PAGE_GOLDEN, REGISTER_PAGE_GOLDEN]) expect(readFileSync(golden, "utf8")).not.toMatch(PERSONAL_KEYS);
});

test("a versioned address reads the page of its curation version", () => {
  expect([craftEdition("v2"), craftEdition("v0"), craftEdition("2"), craftEdition("v2x")]).toEqual([2, null, null, null]);
  expect(CRAFT_PAGE_PATH("Kutch-Ajrakh", 2)).toBe("/crafts/Kutch-Ajrakh/page?version=2");
  expect(CRAFT_PAGE_PATH("Kutch-Ajrakh")).toBe("/crafts/Kutch-Ajrakh/page");
  const page = curatedPage();
  const edition = page.cite?.url.split("/").pop() ?? "";
  expect(craftEdition(edition)).toBe(page.curation?.version);
  expect(page.cite?.text.endsWith(page.cite.url)).toBe(true);
});
