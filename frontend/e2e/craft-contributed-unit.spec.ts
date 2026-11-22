import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { itemSentences } from "@/lib/craftChapterReads";
import type { ChapterItem, ChapterKey } from "@/lib/craftChapters";
import { contributedCredit, contributedPlacement, type ContributedPlate } from "@/lib/craftContributed";
import { chapterClaimIds, checkedCraftPage } from "@/lib/craftPageChecks";
import { craftPageShape, type CraftPage } from "@/lib/craftPageContract";
import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import { parseShape, ShapeError } from "@/lib/shape";

import { curatedPage, rawPage } from "./craftPageFixture";

const BACKEND = join(__dirname, "..", "..", "backend", "app", "research");
const TOOL = "Midjourney v6";
const PHOTO_CREDIT = "Contributed to KalaVigyan";
const AI_CREDIT = `Illustration, made with ${TOOL}`;

type Shelves = Partial<Record<ChapterKey, ContributedPlate[]>>;

const id = (n: number) => `5c0e0000-0000-4000-8000-${String(n).padStart(12, "0")}`;

function fact(): ExplainerSentence {
  const found = rawPage()
    .chapters.flatMap((chapter) => chapter.items.flatMap(itemSentences))
    .find((sentence) => sentence.level !== "HYPOTHESIS" && sentence.citations.length > 0);
  if (!found) throw new Error("the golden shows no cited fact");
  return found;
}

function firstStage(): string {
  return rawPage().process.stages[0].id;
}

function plate(n: number, changes: Partial<ContributedPlate> = {}): ContributedPlate {
  return {
    contributionId: id(n),
    url: `/api/crafts/contributed/${id(n)}`,
    mime: "image/jpeg",
    width: 1200,
    height: 800,
    origin: "PHOTOGRAPH",
    madeWith: null,
    caption: `Contributed picture number ${n}`,
    altText: `What contributed picture number ${n} shows`,
    credit: PHOTO_CREDIT,
    stageId: null,
    sentences: [],
    ...changes
  };
}

function illustration(n: number, changes: Partial<ContributedPlate> = {}): ContributedPlate {
  return plate(n, { origin: "AI_GENERATED", madeWith: TOOL, credit: AI_CREDIT, mime: "image/png", sentences: [fact()], ...changes });
}

function shelf(pictures: ContributedPlate[]): ChapterItem {
  return { block: null, part: { kind: "contributed", pictures }, figure: null, origin: null, pieceId: null };
}

function shelved(body: CraftPage, shelves: Shelves): void {
  for (const [key, pictures] of Object.entries(shelves)) {
    const chapter = body.chapters.find((entry) => entry.key === key);
    if (!chapter) throw new Error(`the golden has no ${key} chapter`);
    chapter.items.push(shelf(pictures));
  }
}

function page(shelves: Shelves): CraftPage {
  return curatedPage((body) => shelved(body, shelves));
}

function refused(shelves: Shelves): () => CraftPage {
  return () => {
    const body = rawPage();
    shelved(body, shelves);
    return checkedCraftPage(parseShape(craftPageShape, body));
  };
}

function backendString(file: string, name: string): string {
  const found = new RegExp(`^${name} = "([^"]+)"`, "m").exec(readFileSync(join(BACKEND, file), "utf8"));
  if (!found) throw new Error(`${name} is not a string in ${file}`);
  return found[1];
}

const SHELVES: Shelves = {
  glance: [plate(1)],
  made: [plate(2, { stageId: firstStage() }), plate(3, { origin: "DRAWING", stageId: id(99) })],
  why: [plate(4)],
  history: [illustration(5)]
};

test("a contributed picture is credited to KalaVigyan without a name, and an AI image always as an illustration made with its tool", () => {
  expect(contributedCredit("PHOTOGRAPH", null)).toBe(PHOTO_CREDIT);
  expect(contributedCredit("DRAWING", null)).toBe(PHOTO_CREDIT);
  expect(contributedCredit("AI_GENERATED", TOOL)).toBe(AI_CREDIT);
  expect(backendString("craft_contributed.py", "CONTRIBUTED_CREDIT")).toBe(PHOTO_CREDIT);
  expect(readFileSync(join(BACKEND, "image_contributions.py"), "utf8")).toContain('AI_GENERATED: "Illustration, made with {tool}"');
});

test("the client reads a contributed shelf in its chapter and lists the facts its plates show", () => {
  const shown = page(SHELVES);
  const history = shown.chapters.find((chapter) => chapter.key === "history");
  const part = history?.items.at(-1)?.part;
  expect(part?.kind).toBe("contributed");
  expect(part?.kind === "contributed" ? part.pictures.map((picture) => picture.credit) : []).toEqual([AI_CREDIT]);
  expect(chapterClaimIds(shown)).toContain(fact().citations[0].claimId);
});

test("the client refuses a picture credited to a person, an AI image shown as a photograph, and a shelf off its rules", () => {
  const cases: Shelves[] = [
    { glance: [plate(1, { credit: "Photo: Asha Patel" })] },
    { glance: [plate(1, { credit: "Photograph" })] },
    { glance: [plate(1, { madeWith: TOOL })] },
    { history: [illustration(5, { credit: PHOTO_CREDIT })] },
    { history: [illustration(5, { madeWith: null, credit: "Illustration, made with " })] },
    { history: [illustration(5, { origin: "PHOTOGRAPH", credit: AI_CREDIT })] },
    { glance: [plate(1, { url: `/api/crafts/contributed/${id(2)}` })] },
    { glance: [plate(1, { width: 0 })] },
    { glance: [plate(1, { sentences: [{ ...fact(), level: "HYPOTHESIS" }] })] },
    { glance: [plate(1), plate(1)] },
    { glance: Array.from({ length: 7 }, (_, n) => plate(n + 10)) }
  ];
  for (const shelves of cases) expect(refused(shelves)).toThrow(ShapeError);
  expect(refused({ glance: [plate(1, { mime: "image/gif" as ContributedPlate["mime"] })] })).toThrow(ShapeError);
  for (const mime of ["image/avif", "image/svg+xml"] as const) expect(refused({ glance: [plate(1, { mime })] })).not.toThrow();
  expect(refused({ glance: [{ ...plate(1), contributor: "Asha Patel" } as ContributedPlate] })).toThrow(/no such field/);
  expect(refused({ glance: [plate(1)], history: [plate(1)] })).toThrow(/each contributed picture shown once/);
  expect(refused({ glance: [] })).toThrow(ShapeError);
});

test("each plate goes to the view of its chapter: a stage's to its stage, the place's to the region, the rest to the overview", () => {
  const shown = page(SHELVES);
  const stages = new Set(shown.process.stages.map((stage) => stage.id));
  const placed = contributedPlacement(shown.chapters, ["overview", "process", "region", "sources"], stages);
  const ids = (plates: readonly ContributedPlate[] | undefined) => (plates ?? []).map((picture) => picture.contributionId);
  expect(ids(placed.stages.get(firstStage()))).toEqual([id(2)]);
  expect(ids(placed.tabs.process)).toEqual([id(3)]);
  expect(ids(placed.tabs.region)).toEqual([id(4)]);
  expect(ids(placed.tabs.overview)).toEqual([id(1), id(5)]);
  const unprocessed = contributedPlacement(shown.chapters, ["overview", "region"], stages);
  expect(ids(unprocessed.tabs.overview)).toEqual([id(1), id(2), id(3), id(5)]);
  expect(unprocessed.stages.size).toBe(0);
});
