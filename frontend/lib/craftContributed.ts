import { UUID } from "@/lib/answerShapes";
import type { Chapter, ChapterKey } from "@/lib/craftChapters";
import type { CraftTab } from "@/lib/craftPageView";
import { explainerSentenceShape, type ExplainerSentence } from "@/lib/explainerBlockBase";
import { IMAGE_ORIGINS, type ImageOrigin } from "@/lib/imageContributionContract";
import { integer, list, matching, nullable, object, oneOf, ShapeError, text, type Shape } from "@/lib/shape";

export const CONTRIBUTED_CREDIT = "Contributed to KalaVigyan";
export const ILLUSTRATION_CREDIT = "Illustration, made with";
export const CONTRIBUTED_MIMES = ["image/png", "image/jpeg", "image/webp", "image/avif", "image/svg+xml"] as const;
export const CONTRIBUTED_PER_CHAPTER_MAX = 6;
export const CONTRIBUTED_PATH = /^\/api\/crafts\/contributed\/[0-9a-f-]{36}$/;
export const CONTRIBUTED_RULE = `at most ${CONTRIBUTED_PER_CHAPTER_MAX} contributed pictures, each once, credited to KalaVigyan without a name, an AI image as an illustration made with its tool, showing facts only`;
export const CONTRIBUTED_TABS: Record<ChapterKey, ContributedTab> = {
  glance: "overview",
  made: "process",
  chem: "overview",
  why: "region",
  history: "overview",
  market: "overview",
  whatif: "overview",
  people: "region",
  kin: "overview",
  sources: "overview"
};

export type ContributedTab = Extract<CraftTab, "overview" | "process" | "region">;
export type ContributedPlate = {
  contributionId: string;
  url: string;
  mime: (typeof CONTRIBUTED_MIMES)[number];
  width: number;
  height: number;
  origin: ImageOrigin;
  madeWith: string | null;
  caption: string;
  altText: string;
  credit: string;
  stageId: string | null;
  sentences: ExplainerSentence[];
};
export type ContributedPlacement = { stages: ReadonlyMap<string, readonly ContributedPlate[]>; tabs: Readonly<Record<ContributedTab, readonly ContributedPlate[]>> };

export const NO_PLATES: readonly ContributedPlate[] = [];
export const NO_CONTRIBUTIONS: ContributedPlacement = { stages: new Map(), tabs: { overview: NO_PLATES, process: NO_PLATES, region: NO_PLATES } };

export const contributedPlateShape: Shape<ContributedPlate> = object<ContributedPlate>({
  contributionId: UUID,
  url: matching(CONTRIBUTED_PATH, "the contributed picture's own address"),
  mime: oneOf(CONTRIBUTED_MIMES),
  width: integer,
  height: integer,
  origin: oneOf(IMAGE_ORIGINS),
  madeWith: nullable(text),
  caption: text,
  altText: text,
  credit: text,
  stageId: nullable(UUID),
  sentences: list(explainerSentenceShape)
});

export function contributedCredit(origin: ImageOrigin, madeWith: string | null): string {
  return origin === "AI_GENERATED" ? `${ILLUSTRATION_CREDIT} ${madeWith ?? ""}` : CONTRIBUTED_CREDIT;
}

export function contributedPath(contributionId: string): string {
  return `/api/crafts/contributed/${contributionId}`;
}

export function creditedRightly(plate: ContributedPlate): boolean {
  const ai = plate.origin === "AI_GENERATED";
  return plate.url === contributedPath(plate.contributionId) && ai === (plate.madeWith !== null) && plate.credit === contributedCredit(plate.origin, plate.madeWith);
}

export function shownRightly(plate: ContributedPlate): boolean {
  return creditedRightly(plate) && plate.width >= 1 && plate.height >= 1 && plate.sentences.every((sentence) => sentence.level !== "HYPOTHESIS");
}

export function shelvedRightly(pictures: readonly ContributedPlate[]): boolean {
  const ids = pictures.map((plate) => plate.contributionId);
  return pictures.length <= CONTRIBUTED_PER_CHAPTER_MAX && new Set(ids).size === ids.length && pictures.every(shownRightly);
}

export function plateClaimIds(plate: ContributedPlate): string[] {
  return [...new Set(plate.sentences.flatMap((sentence) => sentence.citations.map((citation) => citation.claimId)))];
}

export function chapterContributions(chapter: Chapter): ContributedPlate[] {
  return chapter.items.flatMap((item) => (item.part?.kind === "contributed" ? item.part.pictures : []));
}

export function checkContributed(chapters: readonly Chapter[]): void {
  const ids = chapters.flatMap(chapterContributions).map((plate) => plate.contributionId);
  if (new Set(ids).size !== ids.length) throw new ShapeError("chapters", "each contributed picture shown once");
}

export function contributedPlacement(chapters: readonly Chapter[], offered: readonly CraftTab[], stageIds: ReadonlySet<string>): ContributedPlacement {
  const stages = new Map<string, ContributedPlate[]>();
  const tabs: Record<ContributedTab, ContributedPlate[]> = { overview: [], process: [], region: [] };
  for (const chapter of chapters) {
    const wanted = CONTRIBUTED_TABS[chapter.key];
    const tab = offered.includes(wanted) ? wanted : "overview";
    for (const plate of chapterContributions(chapter)) {
      if (tab === "process" && plate.stageId !== null && stageIds.has(plate.stageId)) stages.set(plate.stageId, [...(stages.get(plate.stageId) ?? []), plate]);
      else tabs[tab].push(plate);
    }
  }
  return { stages, tabs };
}
