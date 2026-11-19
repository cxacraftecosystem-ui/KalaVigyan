import type { AnswerLanguage, TextDirection } from "@/lib/answerLanguages";
import type { ExplainerSentence, MediaRef } from "@/lib/explainerBlockBase";
import type { LadderStage } from "@/lib/explainerContract";
import type { SectionView } from "@/lib/explainerState";
import { blockSentences, blockSourceIds, type TypedBlock } from "@/lib/explainerView";
import { countNoun, formatDate, listText } from "@/lib/format";
import { marginNotes, type CitingSentence, type MarginNote } from "@/lib/marginNotes";
import type { AnswerSentence, SourceReliability, SourceRef } from "@/lib/types";

export type GradeCount = { grade: SourceReliability; count: number };
export type AnswerProvenance = { sources: string; grades: GradeCount[]; spoken: string };
export type SentenceMark = "hypothesis" | "inferred" | null;
export type ShownQuestion = { shown: string; full: string | null };

export const QUESTION_SHOWN_MAX = 96;
export const QUESTION_CUT_AT = 80;

const GRADES: readonly SourceReliability[] = ["A", "B", "C", "D"];

export function answerProvenance(sources: readonly Pick<SourceRef, "reliability">[]): AnswerProvenance {
  const grades = GRADES.map((grade) => ({ grade, count: sources.filter((source) => source.reliability === grade).length })).filter((grade) => grade.count > 0);
  const graded = grades.map((grade) => `${grade.count} graded ${grade.grade}`);
  const named = countNoun(sources.length, "source");
  return { sources: `Drawn from ${named}`, grades, spoken: graded.length > 0 ? `Reliability of the ${named}: ${listText(graded)}` : "" };
}

export function answeredOn(createdAt: string | null | undefined): string | null {
  return createdAt ? `Answered ${formatDate(createdAt)}` : null;
}

export function sentenceMark(sentence: Pick<AnswerSentence, "level" | "citations">): SentenceMark {
  if (sentence.level === "HYPOTHESIS") return "hypothesis";
  if (sentence.citations.length > 0 && sentence.citations.every((citation) => citation.evidence === "INFERRED")) return "inferred";
  return null;
}

export function shownQuestion(question: string): ShownQuestion {
  const text = question.replace(/\s+/g, " ").trim();
  if (text.length <= QUESTION_SHOWN_MAX) return { shown: text, full: null };
  const cut = text.slice(0, QUESTION_CUT_AT);
  const space = cut.lastIndexOf(" ");
  return { shown: `${(space > 24 ? cut.slice(0, space) : cut).replace(/[\s,;:.]+$/, "")}…`, full: text };
}

export function essayDirection(language: Pick<AnswerLanguage, "direction">, original: boolean): TextDirection {
  return !original && language.direction === "rtl" ? "rtl" : "ltr";
}

const NASTALIQ_LANGUAGES: ReadonlySet<string> = new Set(["ur", "ks"]);
const DISPLAY_LEADING: Readonly<Record<string, string>> = { Aran: "leading-[1.7]", Arab: "leading-[1.45]" };
const PROSE_LEADING: Readonly<Record<string, string>> = { Aran: "leading-[2.2]", Arab: "leading-[1.9]" };

export function essayScript(language: Pick<AnswerLanguage, "code" | "script">): string | null {
  if (language.script === "Latn") return null;
  return language.script === "Arab" && NASTALIQ_LANGUAGES.has(language.code) ? "Aran" : language.script;
}

export function textScript(lang: string | undefined, language: Pick<AnswerLanguage, "code" | "script">): string | null {
  return lang && lang === language.code ? essayScript(language) : null;
}

export function scriptLeading(script: string | null, role: "display" | "prose"): string | null {
  if (!script) return null;
  if (role === "display") return DISPLAY_LEADING[script] ?? "leading-[1.3]";
  return PROSE_LEADING[script] ?? "leading-[1.8]";
}

export function essaySections(sections: readonly SectionView[], streaming: boolean): SectionView[] {
  return sections.filter((section) => section.blocks.length > 0 || (streaming && section.state !== "READY" && section.state !== "EMPTY"));
}

export type CreditParts = { holder: string } | { author: string | null; licence: string | null; site: string };

export function creditParts(media: Pick<MediaRef, "author" | "licence" | "site" | "credit">): CreditParts {
  if (media.credit && !media.author) return { holder: media.credit };
  return { author: media.author, licence: media.licence, site: media.site };
}

export function marginPicture(blocks: readonly TypedBlock[]): { blockId: string; media: MediaRef } | null {
  const images = blocks.find((block) => block.kind === "images");
  if (!images || images.kind !== "images" || images.items.length !== 1) return null;
  return { blockId: images.id, media: images.items[0].media };
}

export function sentenceAnchor(sentenceId: string): string {
  return `say-${sentenceId}`;
}

export function blockAnchor(blockId: string): string {
  return `block-${blockId}`;
}

export function citingSentences(sentences: readonly ExplainerSentence[]): CitingSentence[] {
  return sentences.map((sentence) => ({ anchorId: sentenceAnchor(sentence.id), sourceIds: sentence.citations.map((citation) => citation.sourceId) }));
}

function stageExtras(stage: LadderStage): ExplainerSentence[] {
  return [...(stage.why ? [stage.why] : []), ...(stage.differs ?? []).flatMap((differ) => differ.readings.flatMap((reading) => (reading.sentence ? [reading.sentence] : [])))];
}

export function ladderExtraSourceIds(block: TypedBlock): string[] {
  if (block.kind !== "process_ladder") return [];
  return block.stages.flatMap((stage) => [
    ...stageExtras(stage).flatMap((sentence) => sentence.citations),
    ...(stage.tools ?? []).flatMap((tool) => tool.citations),
    ...(stage.after?.citations ?? [])
  ]).map((citation) => citation.sourceId);
}

export function essaySourceNumbers(numbered: ReadonlyMap<string, number>, sections: readonly SectionView[]): Map<string, number> {
  const numbers = new Map(numbered);
  for (const section of sections) for (const block of section.blocks) for (const id of ladderExtraSourceIds(block)) if (!numbers.has(id)) numbers.set(id, numbers.size + 1);
  return numbers;
}

export function blockCiting(block: TypedBlock): CitingSentence[] {
  const sentences = citingSentences(blockSentences(block));
  const said = new Set(sentences.flatMap((sentence) => sentence.sourceIds));
  const rest = [...new Set([...blockSourceIds(block), ...ladderExtraSourceIds(block)])].filter((id) => !said.has(id));
  return rest.length > 0 ? [...sentences, { anchorId: blockAnchor(block.id), sourceIds: rest }] : sentences;
}

export function sectionNotes(blocks: readonly TypedBlock[], numbers: ReadonlyMap<string, number>, sourcesById: ReadonlyMap<string, SourceRef>): MarginNote[] {
  return marginNotes(blocks.flatMap(blockCiting), numbers, sourcesById);
}

export function ledeNotes(sentences: readonly ExplainerSentence[], numbers: ReadonlyMap<string, number>, sourcesById: ReadonlyMap<string, SourceRef>): MarginNote[] {
  return marginNotes(citingSentences(sentences), numbers, sourcesById);
}
