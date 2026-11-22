import {
  KIN_ITEM_KINDS,
  TAB_CHAPTERS,
  type Chapter,
  type ChapterItem,
  type ChapterKey,
  type PageBlock,
  type PagePart,
  type PagePlate
} from "@/lib/craftChapters";
import type { ExplainerSentence, MediaRef } from "@/lib/explainerBlockBase";
import type { DifferReading, LadderStage } from "@/lib/explainerContract";
import { blockCitations, blockSentences, blockSourceIds } from "@/lib/explainerView";
import type { Citation } from "@/lib/types";

export function itemKind(item: ChapterItem): string {
  return item.block?.kind ?? item.part?.kind ?? "";
}

export function isKinItem(item: ChapterItem): boolean {
  return (KIN_ITEM_KINDS as readonly string[]).includes(itemKind(item));
}

function stageExtras(block: PageBlock): ExplainerSentence[] {
  if (block.kind !== "process_ladder") return [];
  return block.stages.flatMap((stage) => [...(stage.why ? [stage.why] : []), ...(stage.differs ?? []).flatMap(readingSentences)]);
}

function stageCitations(stage: LadderStage): Citation[] {
  const sentences = [...stage.sentences, ...(stage.why ? [stage.why] : []), ...(stage.differs ?? []).flatMap(readingSentences)];
  return [
    ...sentences.flatMap((sentence) => sentence.citations),
    ...stage.materials.flatMap((material) => material.citations),
    ...stage.conditions.flatMap((condition) => condition.citations),
    ...(stage.tools ?? []).flatMap((tool) => tool.citations),
    ...(stage.after?.citations ?? [])
  ];
}

export function readingSentences(reading: DifferReading): ExplainerSentence[] {
  return reading.readings.flatMap((read) => (read.sentence ? [read.sentence] : []));
}

export function plateSentences(plate: PagePlate | null): ExplainerSentence[] {
  return plate ? plate.sentences : [];
}

export function partSentences(part: PagePart): ExplainerSentence[] {
  switch (part.kind) {
    case "plate":
      return part.plate.sentences;
    case "record":
      return part.entries.flatMap((entry) => [...entry.sentences, ...plateSentences(entry.plate)]);
    case "sources_differ":
      return readingSentences(part.reading);
    case "places":
      return part.places.flatMap((place) => place.sentences);
    case "communities":
      return part.communities.flatMap((community) => community.sentences);
    case "open_questions":
      return part.questions.flatMap((question) => question.sentences);
    case "ai_media":
      return part.media.flatMap((item) => item.sentences);
    case "contributed":
      return part.pictures.flatMap((plate) => plate.sentences);
    default:
      return [];
  }
}

export function partCitations(part: PagePart): Citation[] {
  if (part.kind === "key_facts") return part.facts.flatMap((fact) => fact.citations);
  if (part.kind === "relatives") return part.crafts.flatMap((relative) => relative.lede?.citations ?? []);
  return partSentences(part).flatMap((sentence) => sentence.citations);
}

export function itemSentences(item: ChapterItem): ExplainerSentence[] {
  if (item.part) return partSentences(item.part);
  return item.block ? [...blockSentences(item.block), ...stageExtras(item.block)] : [];
}

export function itemCitations(item: ChapterItem): Citation[] {
  if (item.part) return partCitations(item.part);
  if (!item.block) return [];
  return item.block.kind === "process_ladder" ? item.block.stages.flatMap(stageCitations) : blockCitations(item.block);
}

export function itemSourceIds(item: ChapterItem): string[] {
  const cited = itemCitations(item).map((citation) => citation.sourceId);
  if (!item.block) return cited;
  const formulas = item.block.kind === "reaction_player" ? item.block.steps.flatMap((step) => step.formulaSources ?? []) : [];
  return [...cited, ...blockSourceIds(item.block), ...formulas];
}

export function itemMedia(item: ChapterItem): MediaRef[] {
  const part = item.part;
  if (part?.kind === "plate") return [part.plate.media];
  if (part?.kind === "record") return part.entries.flatMap((entry) => (entry.plate ? [entry.plate.media] : []));
  if (part?.kind === "relatives") return part.crafts.flatMap((relative) => (relative.hero ? [relative.hero.media] : []));
  const block = item.block;
  if (block?.kind === "images") return block.items.map((entry) => entry.media);
  if (block?.kind === "zoom_story") return block.levels.flatMap((level) => (level.media ? [level.media] : []));
  return [];
}

export function chapterCitations(chapter: Chapter, { kin }: { kin: boolean }): Citation[] {
  const items = chapter.items.filter((item) => kin || !isKinItem(item));
  return [...plateSentences(chapter.opener).flatMap((sentence) => sentence.citations), ...items.flatMap(itemCitations)];
}

export function chapterSourceIds(chapter: Chapter): string[] {
  return [...plateSentences(chapter.opener).flatMap((sentence) => sentence.citations.map((citation) => citation.sourceId)), ...chapter.items.flatMap(itemSourceIds)];
}

export function chapterMedia(chapter: Chapter): MediaRef[] {
  return [...(chapter.opener ? [chapter.opener.media] : []), ...chapter.items.flatMap(itemMedia)];
}

export function chapterSentences(chapter: Chapter): ExplainerSentence[] {
  return [...plateSentences(chapter.opener), ...chapter.items.flatMap(itemSentences)];
}

export function figureNumbers(chapters: readonly Chapter[]): Map<ChapterItem, string> {
  const counts = { FIGURE: 0, TABLE: 0 };
  const numbers = new Map<ChapterItem, string>();
  for (const item of chapters.flatMap((chapter) => chapter.items)) {
    if (!item.figure) continue;
    counts[item.figure.kind] += 1;
    numbers.set(item, `${item.figure.kind === "TABLE" ? "Table" : "Fig."} ${counts[item.figure.kind]}`);
  }
  return numbers;
}

export function chapterForTab(tab: string | null | undefined): ChapterKey | null {
  return tab && tab in TAB_CHAPTERS ? TAB_CHAPTERS[tab as keyof typeof TAB_CHAPTERS] : null;
}
