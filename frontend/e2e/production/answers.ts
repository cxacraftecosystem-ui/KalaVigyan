import { scriptOf } from "@/lib/answerLanguages";
import { splitSseBuffer } from "@/lib/answerStream";
import type { LedeBlock } from "@/lib/explainerContract";
import { explainerEventOf, type ExplainerEvent } from "@/lib/explainerStream";
import { blockSentences, ledeSentences } from "@/lib/explainerView";
import type { AnswerSentence } from "@/lib/types";

import { builtBlocks, type BuiltBlockSeen } from "./builtBlocks";
import { NO_EXPERT_PANEL, expertPanelNote, withExpertPanel } from "./expertPanel";
import { NO_GENERATED_EXPLAINER, generatedExplainerFound, generatedExplainerOutcome, withGeneratedExplainer, type GeneratedExplainerRecord } from "./generatedExplainer";
import type { TappedChunk, TappedStream } from "./streamTap";
import { NO_REGION_STORY, waterStoryFound, waterStoryOutcome, withRegionStory, type CheckOutcome, type RegionStoryRecord } from "./waterStory";

export const ANSWER_DEADLINE_MS = 10 * 60_000;
export const STALL_LIMIT_MS = 150_000;
export const DEPTH_LABELS = { DETAILED: "Detailed", EXPERT: "Expert" } as const;
export const KNOWN_ANSWER = /\balum\b|फिटकरी|फिटकिरी|फ़िटकरी|پھٹکری|پھٹکڑی/i;
export const LATIN = "Latn";

export type KnownAnswerCheck = "MORDANT" | "WATER_STORY" | "GENERATED_EXPLAINER" | "ZOOM_STORY" | "TIMELINE_MAP" | "SEASONS" | "RIVER_TIME";
export type AskedDepth = keyof typeof DEPTH_LABELS;
export type KnownAnswerQuestion = { label: string; language: string; script: string; depth: AskedDepth; question: string; check: KnownAnswerCheck; craft?: string };
export type KnownAnswerOptions = { riversLoaded: boolean };

export const RIVERS_NOT_LOADED: KnownAnswerOptions = { riversLoaded: false };
export const BUILT_KIND_CHECKS: Partial<Record<KnownAnswerCheck, string>> = { ZOOM_STORY: "zoom_story", TIMELINE_MAP: "timeline_map", SEASONS: "seasons" };
export const GANGA_CRAFT_SLUG = "Varanasi-Soft-Stone-Jali-Work";
export const KNOWN_ANSWER_QUESTIONS: readonly KnownAnswerQuestion[] = [
  { label: "English", language: "en", script: LATIN, depth: "DETAILED", check: "MORDANT", question: "Which mordant fixes the red in Kutch Ajrakh block printing?" },
  {
    label: "Hindi",
    language: "hi",
    script: "Deva",
    depth: "DETAILED",
    check: "MORDANT",
    question: "कच्छ की अजरख छपाई में लाल रंग पक्का करने के लिए कौन सा मॉर्डेंट इस्तेमाल होता है?"
  },
  { label: "Water", language: "en", script: LATIN, depth: "DETAILED", check: "WATER_STORY", question: "How does the water of Kachchh shape Kutch Ajrakh?" },
  { label: "Indigo", language: "en", script: LATIN, depth: "EXPERT", check: "GENERATED_EXPLAINER", question: "How does indigo turn blue on Kutch Ajrakh cloth?" },
  { label: "Materials", language: "en", script: LATIN, depth: "DETAILED", check: "ZOOM_STORY", question: "What is Kutch Ajrakh cloth made of, from the workshop down to the cotton fibre and the dye molecule?" },
  { label: "History", language: "en", script: LATIN, depth: "DETAILED", check: "TIMELINE_MAP", question: "How did Ajrakh printing come from Sindh to Kutch over the centuries?" },
  { label: "Climate", language: "en", script: LATIN, depth: "DETAILED", check: "SEASONS", question: "How do the seasons and rainfall of Kachchh shape when Kutch Ajrakh is printed and dyed?" },
  {
    label: "Ganga",
    language: "en",
    script: LATIN,
    depth: "DETAILED",
    check: "RIVER_TIME",
    craft: GANGA_CRAFT_SLUG,
    question: "How does the Ganga at Varanasi shape the land and water behind Varanasi soft stone jali work?"
  },
  { label: "Urdu", language: "ur", script: "Arab", depth: "DETAILED", check: "MORDANT", question: "کچھ اجرک کی چھپائی میں سرخ رنگ پکا کرنے کے لیے کون سا مارڈنٹ استعمال ہوتا ہے؟" }
];

export type WaitOutcome = "stalled" | "timeout" | "never-started";
export type AnswerEnd = "done" | "error" | "closed" | WaitOutcome;

export type TimedEvent = { at: number; event: ExplainerEvent };
export type ParsedStream = { events: TimedEvent[]; heartbeats: number; longestSilenceMs: number; unparsed: number };

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
};

export type SourceRecord = { id: string; kind: string; title: string; publisher: string | null; year: number | null; doi: string | null; url: string | null };

export type LedeRecord = { sentences: number; cited: number; shown: number | null; shownCited: number | null };

export const NO_LEDE: LedeRecord = { sentences: 0, cited: 0, shown: null, shownCited: null };

export type AnswerRecord = {
  label: string;
  question: string;
  expectedLanguage: string;
  request: { depth: string | null; language: string | null; craftSlug: string | null };
  httpStatus: number | null;
  streamsOpened: number;
  endedWith: AnswerEnd;
  answerId: string | null;
  craft: string | null;
  error: string | null;
  notEnoughEvidence: string | null;
  timing: { firstByteMs: number | null; firstSentenceMs: number | null; doneMs: number | null; totalMs: number | null; heartbeats: number; longestSilenceMs: number };
  statusSteps: { step: string; message: string; atMs: number }[];
  sentenceCount: number;
  citedSentenceCount: number;
  uncitedSentenceCount: number;
  refusedFrames: number;
  openQuestionCount: number;
  citationCount: number;
  sources: SourceRecord[];
  sentences: SentenceRecord[];
  followUps: string[];
  scripts: { translated: number; englishFallback: number; other: number };
  knownAnswerFound: boolean;
  regionStory: RegionStoryRecord;
  builtBlocks: BuiltBlockSeen[];
  generatedExplainer: GeneratedExplainerRecord;
  lede: LedeRecord;
  pageSentences: number | null;
  pageSentenceIds: string[] | null;
  pageSentencesWithoutChip: number | null;
  problems: string[];
  notes: string[];
};

function isComment(block: string): boolean {
  const lines = block.split("\n").filter((line) => line.trim() !== "");
  return lines.length > 0 && lines.every((line) => line.startsWith(":"));
}

export function parseTappedStream(chunks: readonly TappedChunk[], startedAt: number): ParsedStream {
  const parsed: ParsedStream = { events: [], heartbeats: 0, longestSilenceMs: 0, unparsed: 0 };
  let buffer = "";
  let last = startedAt;
  const take = (block: string, at: number) => {
    if (!block.trim()) return;
    if (isComment(block)) {
      parsed.heartbeats += 1;
      return;
    }
    const event = explainerEventOf(block);
    if (event) parsed.events.push({ at, event });
    else parsed.unparsed += 1;
  };
  for (const chunk of chunks) {
    parsed.longestSilenceMs = Math.max(parsed.longestSilenceMs, chunk.at - last);
    last = chunk.at;
    buffer += chunk.text;
    const { blocks, rest } = splitSseBuffer(buffer);
    buffer = rest;
    for (const block of blocks) take(block, chunk.at);
  }
  take(buffer.replace(/\r\n/g, "\n"), last);
  return parsed;
}

function sentenceRecord(kind: SentenceRecord["kind"], sectionId: string, sentence: AnswerSentence, block: { id: string; kind: string } | null = null): SentenceRecord {
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
    sourceIds: [...new Set(sentence.citations.map((citation) => citation.sourceId))]
  };
}

function ledeRecords(lede: LedeBlock): { record: LedeRecord; sentences: SentenceRecord[] } {
  const opening = ledeSentences(lede);
  const record = { ...NO_LEDE, sentences: opening.length, cited: opening.filter((sentence) => sentence.citations.length > 0).length };
  return { record, sentences: opening.map((sentence) => sentenceRecord("sentence", lede.id, sentence, lede)) };
}

function requestOf(body: string | null): AnswerRecord["request"] {
  try {
    const parsed = JSON.parse(body ?? "") as Record<string, unknown>;
    const text = (key: string) => (typeof parsed[key] === "string" ? (parsed[key] as string) : null);
    return { depth: text("depth"), language: text("language"), craftSlug: text("craftSlug") };
  } catch {
    return { depth: null, language: null, craftSlug: null };
  }
}

function since(at: number | undefined | null, start: number): number | null {
  return at === undefined || at === null ? null : at - start;
}

function endOf(parsed: ParsedStream, waited: WaitOutcome | null): AnswerEnd {
  if (waited) return waited;
  if (parsed.events.some(({ event }) => event.type === "done")) return "done";
  if (parsed.events.some(({ event }) => event.type === "error")) return "error";
  return "closed";
}

function scriptCounts(sentences: readonly SentenceRecord[], script: string): AnswerRecord["scripts"] {
  return {
    translated: sentences.filter((sentence) => sentence.translated && sentence.script === script).length,
    englishFallback: sentences.filter((sentence) => !sentence.translated && sentence.script === LATIN).length,
    other: sentences.filter((sentence) => !(sentence.translated ? sentence.script === script : sentence.script === LATIN)).length
  };
}

export type AnswerInput = {
  question: KnownAnswerQuestion;
  stream: TappedStream | null;
  streamsOpened: number;
  clickedAt: number;
  waited: WaitOutcome | null;
};

export function answerRecord(input: AnswerInput): AnswerRecord {
  const { question, stream, clickedAt } = input;
  const parsed = parseTappedStream(stream?.chunks ?? [], stream?.requestedAt ?? clickedAt);
  const sentences: SentenceRecord[] = [];
  const sources: SourceRecord[] = [];
  const statusSteps: AnswerRecord["statusSteps"] = [];
  let followUps: string[] = [];
  let answerId: string | null = null;
  let craft: string | null = null;
  let error: string | null = null;
  let notEnoughEvidence: string | null = null;
  let regionStory = NO_REGION_STORY;
  let generatedExplainer = NO_GENERATED_EXPLAINER;
  let expertPanel = NO_EXPERT_PANEL;
  let lede = NO_LEDE;
  const kinds = new Set<string>();
  for (const { at, event } of parsed.events) {
    if (event.type === "lede") {
      const opening = ledeRecords(event.data.block);
      sentences.push(...opening.sentences);
      lede = opening.record;
    } else if (event.type === "block") {
      sentences.push(...blockSentences(event.data.block).map((sentence) => sentenceRecord("sentence", event.data.sectionId, sentence, event.data.block)));
      kinds.add(event.data.block.kind);
      regionStory = withRegionStory(regionStory, event.data.block);
      generatedExplainer = withGeneratedExplainer(generatedExplainer, event.data.block);
      expertPanel = withExpertPanel(expertPanel, event.data.block);
    } else if (event.type === "open_question") sentences.push(sentenceRecord("open_question", event.data.sectionId, event.data.sentence));
    else if (event.type === "source") {
      const { id, kind, title, publisher, year, doi, url } = event.data;
      sources.push({ id, kind, title, publisher, year, doi, url });
    } else if (event.type === "status") statusSteps.push({ step: event.data.step, message: event.data.message, atMs: at - clickedAt });
    else if (event.type === "follow_ups") followUps = event.data.items;
    else if (event.type === "done") answerId = event.data.answerId;
    else if (event.type === "understood") craft = event.data.crafts[0]?.slug ?? null;
    else if (event.type === "error") error = event.data.message;
    else if (event.type === "not_enough_evidence") notEnoughEvidence = event.data.message;
  }
  const atOf = (type: ExplainerEvent["type"]) => parsed.events.find(({ event }) => event.type === type)?.at;
  const firstSentenceAt = parsed.events.find(({ event }) => event.type === "lede" || (event.type === "block" && blockSentences(event.data.block).length > 0))?.at;
  const body = sentences.filter((sentence) => sentence.kind === "sentence");
  return {
    label: question.label,
    question: question.question,
    expectedLanguage: question.language,
    request: requestOf(stream?.body ?? null),
    httpStatus: stream?.status ?? null,
    streamsOpened: input.streamsOpened,
    endedWith: endOf(parsed, input.waited),
    answerId,
    craft,
    error,
    notEnoughEvidence,
    timing: {
      firstByteMs: since(stream?.chunks[0]?.at, clickedAt),
      firstSentenceMs: since(firstSentenceAt, clickedAt),
      doneMs: since(atOf("done"), clickedAt),
      totalMs: since(stream?.endedAt, clickedAt),
      heartbeats: parsed.heartbeats,
      longestSilenceMs: parsed.longestSilenceMs
    },
    statusSteps,
    sentenceCount: sentences.length,
    citedSentenceCount: body.filter((sentence) => sentence.citations > 0).length,
    uncitedSentenceCount: sentences.filter((sentence) => sentence.citations === 0).length,
    refusedFrames: parsed.unparsed,
    openQuestionCount: sentences.length - body.length,
    citationCount: sentences.reduce((sum, sentence) => sum + sentence.citations, 0),
    sources,
    sentences,
    followUps,
    scripts: scriptCounts(sentences, question.script),
    knownAnswerFound: knownAnswerFound(question, sentences, regionStory, generatedExplainer, kinds),
    regionStory,
    builtBlocks: builtBlocks(parsed.events),
    generatedExplainer,
    lede,
    pageSentences: null,
    pageSentenceIds: null,
    pageSentencesWithoutChip: null,
    problems: [],
    notes: question.depth === "EXPERT" ? [expertPanelNote(expertPanel)] : []
  };
}

function knownAnswerFound(question: KnownAnswerQuestion, sentences: readonly SentenceRecord[], story: RegionStoryRecord, generated: GeneratedExplainerRecord, kinds: ReadonlySet<string>): boolean {
  const kind = BUILT_KIND_CHECKS[question.check];
  if (kind) return kinds.has(kind);
  if (question.check === "WATER_STORY" || question.check === "RIVER_TIME") return waterStoryFound(story);
  if (question.check === "GENERATED_EXPLAINER") return generatedExplainerFound(generated);
  return sentences.some((sentence) => KNOWN_ANSWER.test(`${sentence.text} ${sentence.original ?? ""}`));
}

export function scriptProblems(sentences: readonly SentenceRecord[], script: string): string[] {
  if (script === LATIN) return [];
  return sentences.flatMap((sentence) => {
    if (sentence.translated) {
      if (sentence.script !== script) return [`sentence ${sentence.id} is marked translated but is written in ${sentence.script ?? "no script"}`];
      return sentence.original ? [] : [`sentence ${sentence.id} is translated but carries no English original`];
    }
    return sentence.script === LATIN ? [] : [`sentence ${sentence.id} is neither in ${script} nor an English fallback`];
  });
}

export function knownAnswerOutcome(record: AnswerRecord, question: KnownAnswerQuestion, options: KnownAnswerOptions = RIVERS_NOT_LOADED): CheckOutcome {
  if (question.check === "WATER_STORY") return waterStoryOutcome(record.regionStory, options.riversLoaded);
  if (question.check === "RIVER_TIME") return { problems: [], notes: record.knownAnswerFound ? [] : [NO_RIVER_STORY_NOTE] };
  if (question.check === "GENERATED_EXPLAINER") return generatedExplainerOutcome(record.generatedExplainer);
  const kind = BUILT_KIND_CHECKS[question.check];
  if (kind) return { problems: record.knownAnswerFound ? [] : [`no ${kind} block arrived`], notes: [] };
  return { problems: record.knownAnswerFound ? [] : ["no sentence names alum, the known mordant"], notes: [] };
}

export const NO_RIVER_STORY_NOTE = "No region story with a river arrived, so the trace through a large basin is not timed in this run.";

export const STEPPED_BLOCK_KINDS: ReadonlySet<string> = new Set(["zoom_story", "concept_graph"]);

const NAMED_IDS_MAX = 8;

function named(ids: readonly string[]): string {
  return ids.length > NAMED_IDS_MAX ? `${ids.slice(0, NAMED_IDS_MAX).join(", ")} and ${ids.length - NAMED_IDS_MAX} more` : ids.join(", ");
}

export function pageSentenceProblems(record: AnswerRecord): string[] {
  if (record.pageSentences === null) return [];
  const cited = record.sentences.filter((sentence) => sentence.kind === "sentence" && sentence.citations > 0);
  if (record.pageSentenceIds === null) {
    const shown = new Set(cited.map((sentence) => `${sentence.sectionId}:${sentence.id}`)).size;
    return record.pageSentences === shown ? [] : [`the page shows ${record.pageSentences} sentences; the stream sent ${shown}`];
  }
  const onPage = new Set(record.pageSentenceIds);
  const shownTexts = new Set(cited.filter((sentence) => onPage.has(sentence.id)).map((sentence) => `${sentence.blockId}\u0000${sentence.text}`));
  const problems: string[] = [];
  const missing = [
    ...new Set(
      cited
        .filter((sentence) => !STEPPED_BLOCK_KINDS.has(sentence.blockKind ?? "") && !onPage.has(sentence.id) && !shownTexts.has(`${sentence.blockId}\u0000${sentence.text}`))
        .map((sentence) => sentence.id)
    )
  ];
  if (missing.length > 0) problems.push(`${missing.length} streamed sentences are not on the page: ${named(missing)}`);
  const stepped = new Map<string, string[]>();
  for (const sentence of cited) {
    if (sentence.blockId !== null && STEPPED_BLOCK_KINDS.has(sentence.blockKind ?? "")) stepped.set(sentence.blockId, [...(stepped.get(sentence.blockId) ?? []), sentence.id]);
  }
  for (const [blockId, ids] of stepped) {
    if (!ids.some((id) => onPage.has(id))) problems.push(`the stepped block ${blockId} shows none of its ${ids.length} sentences`);
  }
  const sent = new Set(cited.map((sentence) => sentence.id));
  const unsent = [...new Set(record.pageSentenceIds.filter((id) => !sent.has(id)))];
  if (unsent.length > 0) problems.push(`${unsent.length} sentences on the page never arrived in the stream: ${named(unsent)}`);
  return problems;
}

export function ledeProblems(record: AnswerRecord): string[] {
  const { lede } = record;
  if (lede.shown === null) return [];
  if (lede.sentences === 0) return ["the answer opened without a lede"];
  if (lede.shown === 0) return ["the page shows no lede"];
  return lede.shownCited ? [] : ["no lede sentence on the page shows a citation"];
}

export function savedLedeProblems(lede: LedeRecord, shown: number): string[] {
  if (lede.sentences === 0 || shown === lede.sentences) return [];
  return [`the saved explainer shows ${shown} of the lede's ${lede.sentences} sentences`];
}

export function answerProblems(record: AnswerRecord, question: KnownAnswerQuestion, options: KnownAnswerOptions = RIVERS_NOT_LOADED): string[] {
  const problems: string[] = [];
  const sent = new Set(record.sources.map((source) => source.id));
  if (record.httpStatus !== 200) problems.push(`the stream answered ${record.httpStatus ?? "nothing"}`);
  if (record.streamsOpened !== 1) problems.push(`the question opened ${record.streamsOpened} answer streams, not 1`);
  if (record.endedWith !== "done") problems.push(`the stream ended with ${record.endedWith}, not done`);
  if (record.error) problems.push(`the stream sent an error: ${record.error}`);
  if (record.request.depth !== question.depth) problems.push(`the request asked at ${record.request.depth ?? "no depth"}, not ${question.depth}`);
  if (record.request.language !== question.language) problems.push(`the request asked for ${record.request.language ?? "no language"}, not ${question.language}`);
  if (record.citedSentenceCount < 1) problems.push("no cited sentence arrived");
  if (record.uncitedSentenceCount > 0) problems.push(`${record.uncitedSentenceCount} sentences arrived without a citation`);
  if (record.refusedFrames > 0) problems.push(`${record.refusedFrames} stream frames broke the explainer contract`);
  const orphans = record.sentences.flatMap((sentence) => sentence.sourceIds).filter((id) => !sent.has(id));
  if (orphans.length > 0) problems.push(`${new Set(orphans).size} cited sources never arrived as source events`);
  if (record.pageSentencesWithoutChip) problems.push(`${record.pageSentencesWithoutChip} sentences on the page show no citation`);
  return [
    ...problems,
    ...pageSentenceProblems(record),
    ...ledeProblems(record),
    ...knownAnswerOutcome(record, question, options).problems,
    ...scriptProblems(record.sentences, question.script)
  ];
}
