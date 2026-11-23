import type { ExplainerSentence, TermSpan } from "@/lib/explainerBlockBase";
import { componentSourceIds } from "@/lib/explainerComponent";
import type { BlockByKind, Discipline, ExplainerBlock, LadderStage, LedeBlock, TypedBlockKind, WorkingSectionState } from "@/lib/explainerContract";
import { reactionPlayerCitations } from "@/lib/explainerMatter";
import { signatureSentences, signatureSourceIds } from "@/lib/explainerSignature";
import type { SectionState, SectionView } from "@/lib/explainerState";
import { TRAIL_GROUPS, TRAIL_STAGES, type TrailEntry } from "@/lib/explainerStream";
import { byCount, formatDate } from "@/lib/format";
import { onceSaid } from "@/lib/sentenceGroups";
import type { AnswerReaction, AnswerSection, Citation } from "@/lib/types";

export type UnderstoodPart = "craft" | "depth" | "language";
export type TrailGroup = (typeof TRAIL_GROUPS)[number];
export type TrailStage = (typeof TRAIL_STAGES)[number];
export type TrailCount = { group: TrailGroup; count: number; noun: string };
export type TextRange = { from: number; to: number };
export type TextPart = { text: string; marked: boolean };
export type TextSegment = { text: string; term: TermSpan | null; parts: TextPart[] };
export type TypedBlock = BlockByKind[TypedBlockKind];

export const DISCIPLINE_LABEL: Record<Discipline, string> = {
  OVERVIEW: "Overview",
  PROCESS: "Process",
  CHEMISTRY: "Chemistry",
  PHYSICS: "Physics",
  MATERIALS: "Materials",
  GEOGRAPHY: "Geography and water",
  GEOLOGY: "Geology and soil",
  CLIMATE: "Climate",
  ECOLOGY: "Ecology",
  BOTANY: "Botany",
  HISTORY: "History",
  ECONOMICS: "Economics",
  DESIGN: "Design",
  HEALTH: "Health",
  SOCIETY: "Society",
  POLICY: "Policy"
};

export const WORKING_STATE_LABEL: Record<WorkingSectionState, string> = {
  RESEARCHING: "Researching",
  WRITING: "Writing",
  CHECKING: "Checking"
};

export function sectionAnchor(id: string): string {
  return `section-${id}`;
}

export function workingLabel(state: SectionState, streaming: boolean): string | null {
  if (!streaming || state === "READY" || state === "EMPTY") return null;
  return WORKING_STATE_LABEL[state];
}

export const TRAIL_STAGE_LABEL: Record<TrailStage, string> = { FOUND: "Found", READ: "Read", QUOTED: "Quoted" };

const TRAIL_NOUNS: Record<TrailGroup, readonly [string, string]> = {
  PAPERS: ["paper", "papers"],
  ENCYCLOPAEDIA: ["encyclopaedia article", "encyclopaedia articles"],
  DATASETS: ["dataset", "datasets"],
  WEB: ["web page", "web pages"],
  STORED: ["stored finding", "stored findings"]
};

export function stageCitations(stage: LadderStage): Citation[] {
  return [
    ...stage.sentences.flatMap((sentence) => sentence.citations),
    ...stage.materials.flatMap((material) => material.citations),
    ...stage.conditions.flatMap((condition) => condition.citations)
  ];
}

export function blockCitations(block: TypedBlock): Citation[] {
  if (block.kind === "process_ladder") return block.stages.flatMap(stageCitations);
  if (block.kind === "reaction_player") return reactionPlayerCitations(block);
  if (block.kind === "simulation") return block.values.flatMap((value) => value.citations);
  const cited = blockSentences(block).flatMap((sentence) => sentence.citations);
  if (block.kind !== "measure") return cited;
  return [...cited, ...block.rows.flatMap((row) => (row.conversion.citation ? [row.conversion.citation] : []))];
}

export function blockSourceIds(block: TypedBlock): string[] {
  const cited = blockCitations(block).map((citation) => citation.sourceId);
  if (block.kind === "indigo_vat") return [...cited, ...signatureSourceIds(block)];
  if (block.kind === "zoom_story") return [...cited, ...block.levels.flatMap((level) => (level.compound ? [level.compound.sourceId] : []))];
  if (block.kind === "component") return componentSourceIds(block);
  return block.kind === "molecule_3d" ? [...cited, block.sourceId] : cited;
}

export function ledeSentences(lede: LedeBlock): ExplainerSentence[] {
  return lede.figure ? [...lede.sentences, ...blockSentences(lede.figure)] : lede.sentences;
}

export function ledeSourceIds(lede: LedeBlock): string[] {
  const own = lede.sentences.flatMap((sentence) => sentence.citations.map((citation) => citation.sourceId));
  return lede.figure ? [...own, ...blockSourceIds(lede.figure)] : own;
}

export function explainerSourceNumbers(
  sections: readonly SectionView[],
  openQuestions: readonly AnswerSection[] = [],
  reactions: readonly AnswerReaction[] = [],
  lede: LedeBlock | null = null
): Map<string, number> {
  const numbers = new Map<string, number>();
  const number = (sourceIds: readonly string[]) => {
    for (const sourceId of sourceIds) if (!numbers.has(sourceId)) numbers.set(sourceId, numbers.size + 1);
  };
  const take = (citations: readonly Citation[]) => number(citations.map((citation) => citation.sourceId));
  if (lede) number(ledeSourceIds(lede));
  for (const section of sections) for (const block of section.blocks) number(blockSourceIds(block));
  for (const section of openQuestions) for (const sentence of section.sentences) take(sentence.citations);
  for (const reaction of reactions) take(reaction.citations);
  return numbers;
}

export function trailCounts(trail: readonly TrailEntry[]): TrailCount[] {
  return TRAIL_GROUPS.flatMap((group) => {
    const count = trail.filter((entry) => entry.group === group).length;
    return count > 0 ? [{ group, count, noun: byCount(count, ...TRAIL_NOUNS[group]) }] : [];
  });
}

export const COVERED_NOTE = "Already covered in this answer.";

export function withdrawnNote(count: number): string {
  const taken = count === 1 ? "one passage was taken out" : `${count} passages were taken out`;
  return `A field interview this section quoted is no longer shown, so ${taken}.`;
}

export function shownSections(sections: readonly SectionView[], streaming: boolean): SectionView[] {
  return sections.filter((section) => {
    if (section.blocks.length > 0) return true;
    if (section.state === "EMPTY") return section.searched !== COVERED_NOTE;
    return streaming && section.state !== "READY";
  });
}

export function termQuestion(label: string, craftName: string | null): string {
  return craftName ? `What is ${label} in ${craftName}?` : `What is ${label}?`;
}

export function reusedLabel(storedAt: string): string {
  return `From earlier research · ${formatDate(storedAt)}`;
}

export function showsEarlierResearch(sections: readonly SectionView[]): boolean {
  return sections.some((section) => section.blocks.some((block) => block.reuse !== null));
}

export function stagesSaidOnce(stages: readonly LadderStage[]): LadderStage[] {
  const say = onceSaid();
  return stages.map(({ why: stated, ...stage }) => {
    const sentences = stage.sentences.flatMap((sentence) => say(sentence) ?? []);
    const why = say(stated);
    return why ? { ...stage, sentences, why } : { ...stage, sentences };
  });
}

export function ladderReach(progress: number, count: number, reduce: boolean): number {
  if (count <= 0) return 0;
  if (reduce || count === 1) return count;
  const clamped = Math.min(1, Math.max(0, Number.isFinite(progress) ? progress : 0));
  return Math.floor(clamped * (count - 1) + 1e-9) + 1;
}

type TermRange = TextRange & { term: TermSpan };

function termRanges(text: string, terms: readonly TermSpan[]): TermRange[] {
  const found = terms
    .map((term) => ({ from: term.text ? text.indexOf(term.text) : -1, term }))
    .filter((range) => range.from >= 0)
    .map((range) => ({ from: range.from, to: range.from + range.term.text.length, term: range.term }))
    .sort((a, b) => a.from - b.from);
  const kept: TermRange[] = [];
  for (const range of found) {
    const last = kept.at(-1);
    if (!last || range.from >= last.to) kept.push(range);
  }
  return kept;
}

function markedParts(text: string, offset: number, mark: TextRange | null): TextPart[] {
  if (!mark || mark.to <= offset || mark.from >= offset + text.length) return [{ text, marked: false }];
  const from = Math.max(mark.from - offset, 0);
  const to = Math.min(mark.to - offset, text.length);
  const parts = [
    { text: text.slice(0, from), marked: false },
    { text: text.slice(from, to), marked: true },
    { text: text.slice(to), marked: false }
  ];
  return parts.filter((part) => part.text !== "");
}

export function sentenceSegments(text: string, terms: readonly TermSpan[], mark: TextRange | null = null): TextSegment[] {
  const segments: TextSegment[] = [];
  let at = 0;
  const cut = (to: number, term: TermSpan | null) => {
    if (to > at) segments.push({ text: text.slice(at, to), term, parts: markedParts(text.slice(at, to), at, mark) });
    at = to;
  };
  for (const range of termRanges(text, terms)) {
    cut(range.from, null);
    cut(range.to, range.term);
  }
  cut(text.length, null);
  return segments;
}

function anyTranslated(sentences: readonly ExplainerSentence[]): boolean {
  return sentences.some((sentence) => sentence.translated === true);
}

export function hasTranslatedText(sections: readonly SectionView[], lede: LedeBlock | null = null): boolean {
  if (lede && anyTranslated(ledeSentences(lede))) return true;
  return sections.some((section) => section.original !== undefined || section.blocks.some((block) => anyTranslated(blockSentences(block))));
}

export function blockSentences(block: TypedBlock): ExplainerSentence[] {
  if (block.kind === "prose") return block.sentences;
  if (block.kind === "process_ladder") return block.stages.flatMap((stage) => stage.sentences);
  if (block.kind === "region_story") return block.steps.map((step) => step.sentence);
  if (block.kind === "reaction_player") return (block.notes ?? []).map((note) => note.sentence);
  if (block.kind === "seasons") return block.rows.map((row) => row.sentence);
  if (block.kind === "supply_map") return block.links.map((link) => link.sentence);
  if (block.kind === "material_card") return [...block.facts, ...block.handling];
  if (block.kind === "expert_view") return [...block.take, ...block.differs.flatMap((difference) => [difference.thisView, difference.otherView])];
  if (block.kind === "what_if") return block.options.flatMap((option) => option.outcomes.map((outcome) => outcome.sentence));
  if (block.kind === "zoom_story") return block.levels.map((level) => level.sentence);
  if (block.kind === "timeline_map") return [...block.points.map((point) => point.sentence), ...block.routes.map((route) => route.sentence)];
  if (block.kind === "indigo_vat" || block.kind === "mordant_bath" || block.kind === "lost_wax" || block.kind === "firing") return signatureSentences(block);
  return learningSentences(block);
}

function learningSentences(block: TypedBlock): ExplainerSentence[] {
  if (block.kind === "quiz") return block.questions.flatMap((question) => question.options.map((option) => option.sentence));
  if (block.kind === "compare") return block.rows.flatMap((row) => row.cells.flatMap((cell) => (cell ? [cell.sentence] : [])));
  if (block.kind === "concept_graph") return block.nodes.flatMap((node) => node.crafts.map((entry) => entry.sentence));
  if (block.kind === "measure") return block.rows.map((row) => row.sentence);
  if (block.kind === "market_gi") return [...(block.gi?.sentences ?? []), ...block.imitation, ...block.prices.map((price) => price.sentence)];
  if (block.kind === "climate_risk") return block.meaning;
  return [];
}
