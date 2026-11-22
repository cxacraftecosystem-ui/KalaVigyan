import { FINAL_SECTION_STATES, type ExplainerBlock, type FinalSectionState, type LedeBlock, type Understood, type WorkingSectionState } from "@/lib/explainerContract";
import { TRAIL_STAGES, type ExplainerEvent, type SectionStarted, type TrailEntry } from "@/lib/explainerStream";
import type { VersionMark } from "@/lib/learningContract";
import type { AnswerReaction, AnswerSection, AnswerSentence, AnswerStatus, SourceRef } from "@/lib/types";

export type ExplainerPhase = "idle" | "asking" | "streaming" | "done" | "empty" | "failed";

export type SectionState = WorkingSectionState | FinalSectionState;

export type SectionView = Omit<SectionStarted, "state"> & { state: SectionState; blocks: ExplainerBlock[]; searched: string | null; added?: true };

export type ExplainerRef = { explainerId: string; version: number };

export type ExplainerState = {
  phase: ExplainerPhase;
  question: string;
  language: string;
  answerId: string | null;
  understood: Understood | null;
  lede: LedeBlock | null;
  status: AnswerStatus | null;
  trail: TrailEntry[];
  sections: SectionView[];
  sources: SourceRef[];
  openQuestions: AnswerSection[];
  reactions: AnswerReaction[];
  followUps: string[];
  error: string | null;
  notice: string | null;
  mark: VersionMark | null;
  basedOn: ExplainerRef | null;
  quizAvailable: boolean | null;
};

const SETTLED: ReadonlySet<ExplainerPhase> = new Set(["empty", "failed"]);
const FINAL: ReadonlySet<SectionState> = new Set(FINAL_SECTION_STATES);

export function emptyExplainer(question = "", language = "en"): ExplainerState {
  return {
    phase: "idle",
    question,
    language,
    answerId: null,
    understood: null,
    lede: null,
    status: null,
    trail: [],
    sections: [],
    sources: [],
    openQuestions: [],
    reactions: [],
    followUps: [],
    error: null,
    notice: null,
    mark: null,
    basedOn: null,
    quizAvailable: null
  };
}

export function askingExplainer(question: string, language: string): ExplainerState {
  return { ...emptyExplainer(question, language), phase: "asking" };
}

export function isFinalSection(state: SectionState): state is FinalSectionState {
  return FINAL.has(state);
}

export function mergeTrail(trail: readonly TrailEntry[], entry: TrailEntry): TrailEntry[] {
  const index = trail.findIndex((existing) => existing.key === entry.key);
  if (index < 0) return [...trail, entry];
  if (TRAIL_STAGES.indexOf(entry.stage) <= TRAIL_STAGES.indexOf(trail[index].stage)) return [...trail];
  const next = [...trail];
  next[index] = entry;
  return next;
}

function startSection(sections: readonly SectionView[], started: SectionStarted): SectionView[] {
  if (sections.some((section) => section.id === started.id)) return [...sections];
  return [...sections, { ...started, blocks: [], searched: null }].sort((a, b) => a.order - b.order);
}

function updateSection(sections: readonly SectionView[], id: string, change: (section: SectionView) => SectionView): SectionView[] {
  return sections.map((section) => (section.id === id && !isFinalSection(section.state) ? change(section) : section));
}

function holdsBlock(sections: readonly SectionView[], blockId: string): boolean {
  return sections.some((section) => section.blocks.some((block) => block.id === blockId));
}

function addBlock(sections: readonly SectionView[], sectionId: string, block: ExplainerBlock): SectionView[] {
  if (holdsBlock(sections, block.id)) return [...sections];
  return updateSection(sections, sectionId, (section) => ({ ...section, blocks: [...section.blocks, block] }));
}

function appendOpenQuestion(sections: readonly AnswerSection[], sectionId: string, sentence: AnswerSentence, heading = ""): AnswerSection[] {
  if (sentence.citations.length === 0) return [...sections];
  const index = sections.findIndex((section) => section.id === sectionId);
  if (index < 0) return [...sections, { id: sectionId, heading, sentences: [sentence] }];
  const target = sections[index];
  if (target.sentences.some((existing) => existing.id === sentence.id)) return [...sections];
  const next = [...sections];
  next[index] = { ...target, sentences: [...target.sentences, sentence] };
  return next;
}

function withoutDuplicate<T extends { id: string }>(items: readonly T[], item: T): T[] {
  return items.some((existing) => existing.id === item.id) ? [...items] : [...items, item];
}

function streaming(state: ExplainerState): ExplainerPhase {
  return state.phase === "idle" || state.phase === "asking" ? "streaming" : state.phase;
}

function reduceSectionEvent(state: ExplainerState, event: ExplainerEvent): ExplainerState {
  switch (event.type) {
    case "section_started":
      return { ...state, phase: streaming(state), sections: startSection(state.sections, event.data) };
    case "section_state":
      return { ...state, sections: updateSection(state.sections, event.data.sectionId, (section) => ({ ...section, state: event.data.state })) };
    case "block":
      return { ...state, phase: streaming(state), sections: addBlock(state.sections, event.data.sectionId, event.data.block) };
    case "section_done": {
      const { sectionId, state: final, searched } = event.data;
      return { ...state, sections: updateSection(state.sections, sectionId, (section) => ({ ...section, state: final, searched })) };
    }
    case "section_heading": {
      const { sectionId, title, original } = event.data;
      return { ...state, sections: updateSection(state.sections, sectionId, (section) => ({ ...section, title, original })) };
    }
    default:
      return state;
  }
}

function reduceSettling(state: ExplainerState, event: ExplainerEvent): ExplainerState {
  switch (event.type) {
    case "not_enough_evidence":
      return { ...state, phase: "empty", status: null, notice: event.data.message };
    case "done":
      return { ...state, phase: SETTLED.has(state.phase) ? state.phase : "done", status: null, answerId: event.data.answerId ?? state.answerId, quizAvailable: event.data.quizAvailable ?? null };
    case "error":
      return { ...state, phase: "failed", status: null, error: event.data.message };
    default:
      return state;
  }
}

export function reduceExplainer(state: ExplainerState, event: ExplainerEvent): ExplainerState {
  switch (event.type) {
    case "understood":
      return SETTLED.has(state.phase) ? state : { ...state, phase: streaming(state), understood: event.data };
    case "status":
      return SETTLED.has(state.phase) ? state : { ...state, status: event.data };
    case "trail":
      return { ...state, trail: mergeTrail(state.trail, event.data) };
    case "source":
      return { ...state, sources: withoutDuplicate(state.sources, event.data) };
    case "open_question":
      return { ...state, openQuestions: appendOpenQuestion(state.openQuestions, event.data.sectionId, event.data.sentence, event.data.heading ?? "") };
    case "reaction":
      return { ...state, reactions: withoutDuplicate(state.reactions, event.data) };
    case "follow_ups":
      return { ...state, followUps: event.data.items };
    case "lede":
      return { ...state, phase: streaming(state), lede: event.data.block };
    case "section_started":
    case "section_state":
    case "block":
    case "section_done":
    case "section_heading":
      return reduceSectionEvent(state, event);
    default:
      return reduceSettling(state, event);
  }
}
