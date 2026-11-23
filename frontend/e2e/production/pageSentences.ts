import { scriptOf } from "@/lib/answerLanguages";
import { blockSentences, type TypedBlock } from "@/lib/explainerView";
import type { AnswerSentence } from "@/lib/types";

export type SentenceRecord = {
  kind: "sentence" | "open_question";
  id: string;
  sectionId: string;
  blockId: string | null;
  blockKind: string | null;
  text: string;
  original: string | null;
  translated: boolean;
  level: string;
  script: string | null;
  citations: number;
  sourceIds: string[];
  shownIn: string | null;
};

export type PageRead = { sentences: readonly SentenceRecord[]; pageSentences: number | null; pageSentenceIds: readonly string[] | null };

type BlockMark = { id: string; kind: string };

export const STEPPED_BLOCK_KINDS: ReadonlySet<string> = new Set(["zoom_story", "concept_graph", "what_if"]);

const NAMED_IDS_MAX = 8;

export function sentenceRecord(kind: SentenceRecord["kind"], sectionId: string, sentence: AnswerSentence, block: BlockMark | null = null, shownIn: string | null = null): SentenceRecord {
  return {
    kind,
    id: sentence.id,
    sectionId,
    blockId: block?.id ?? null,
    blockKind: block?.kind ?? null,
    text: sentence.text,
    original: sentence.original ?? null,
    translated: sentence.translated === true,
    level: sentence.level,
    script: scriptOf(sentence.text),
    citations: sentence.citations.length,
    sourceIds: [...new Set(sentence.citations.map((citation) => citation.sourceId))],
    shownIn
  };
}

function saidAbove(block: TypedBlock): Map<string, string> {
  if (block.kind !== "quantities") return new Map();
  return new Map(block.rows.flatMap((row) => (row.shownIn ? [[row.sentence.id, row.shownIn] as const] : [])));
}

export function blockSentenceRecords(sectionId: string, block: TypedBlock): SentenceRecord[] {
  const said = saidAbove(block);
  return blockSentences(block).map((sentence) => sentenceRecord("sentence", sectionId, sentence, block, said.get(sentence.id) ?? null));
}

function named(ids: readonly string[]): string {
  return ids.length > NAMED_IDS_MAX ? `${ids.slice(0, NAMED_IDS_MAX).join(", ")} and ${ids.length - NAMED_IDS_MAX} more` : ids.join(", ");
}

function steppedProblems(cited: readonly SentenceRecord[], onPage: ReadonlySet<string>): string[] {
  const stepped = new Map<string, string[]>();
  for (const sentence of cited) {
    if (sentence.blockId !== null && STEPPED_BLOCK_KINDS.has(sentence.blockKind ?? "")) stepped.set(sentence.blockId, [...(stepped.get(sentence.blockId) ?? []), sentence.id]);
  }
  return [...stepped].flatMap(([blockId, ids]) => (ids.some((id) => onPage.has(id)) ? [] : [`the stepped block ${blockId} shows none of its ${ids.length} sentences`]));
}

export function pageSentenceProblems(record: PageRead): string[] {
  if (record.pageSentences === null) return [];
  const cited = record.sentences.filter((sentence) => sentence.kind === "sentence" && sentence.citations > 0);
  if (record.pageSentenceIds === null) {
    const shown = new Set(cited.map((sentence) => `${sentence.sectionId}:${sentence.id}`)).size;
    return record.pageSentences === shown ? [] : [`the page shows ${record.pageSentences} sentences; the stream sent ${shown}`];
  }
  const onPage = new Set(record.pageSentenceIds);
  const shownTexts = new Set(cited.filter((sentence) => onPage.has(sentence.id)).map((sentence) => `${sentence.blockId}\u0000${sentence.text}`));
  const shown = (sentence: SentenceRecord) =>
    onPage.has(sentence.id) || (sentence.shownIn !== null && onPage.has(sentence.shownIn)) || shownTexts.has(`${sentence.blockId}\u0000${sentence.text}`);
  const missing = [...new Set(cited.filter((sentence) => !STEPPED_BLOCK_KINDS.has(sentence.blockKind ?? "") && !shown(sentence)).map((sentence) => sentence.id))];
  const problems = missing.length > 0 ? [`${missing.length} streamed sentences are not on the page: ${named(missing)}`] : [];
  const sent = new Set(cited.map((sentence) => sentence.id));
  const unsent = [...new Set(record.pageSentenceIds.filter((id) => !sent.has(id)))];
  return [
    ...problems,
    ...steppedProblems(cited, onPage),
    ...(unsent.length > 0 ? [`${unsent.length} sentences on the page never arrived in the stream: ${named(unsent)}`] : [])
  ];
}
