import type { AskRequest } from "@/lib/answerStream";
import type { Discipline, ExplainerBlock } from "@/lib/explainerContract";
import { isFinalSection, reduceExplainer, type ExplainerRef, type ExplainerState, type SectionView } from "@/lib/explainerState";
import type { ExplainerEvent, SectionDone, SectionStarted } from "@/lib/explainerStream";
import type { BuildsOnEvent, ExplainerVersionDocument, VersionMark } from "@/lib/learningContract";

export const STALE_FOLLOW_UP = "This explainer changed since you opened it. Open the latest version and ask again.";

const IMAGES = "images";

export function explainerStateOf(document: ExplainerVersionDocument): ExplainerState {
  const { explainer, mark } = document;
  return {
    phase: "done",
    question: explainer.question,
    language: explainer.understood.language,
    answerId: explainer.answerId,
    understood: explainer.understood,
    lede: explainer.lede ?? null,
    status: null,
    trail: [],
    sections: explainer.sections.map((section) => ({ ...section, blocks: [...section.blocks] })),
    sources: [...explainer.sources],
    openQuestions: [],
    reactions: [],
    followUps: [...explainer.followUps],
    error: null,
    notice: null,
    mark,
    basedOn: null,
    quizAvailable: null
  };
}

export function explainerRef(state: ExplainerState): ExplainerRef | null {
  if (state.basedOn) return state.basedOn;
  if (state.mark) return { explainerId: state.mark.explainerId, version: state.mark.version };
  if (state.phase === "done" && state.answerId) return { explainerId: state.answerId, version: 1 };
  return null;
}

export function followingExplainer(base: ExplainerState, ref: ExplainerRef, question: string): ExplainerState {
  return {
    ...base,
    phase: "asking",
    question,
    answerId: null,
    lede: null,
    status: null,
    trail: [],
    followUps: [],
    error: null,
    notice: null,
    basedOn: ref,
    quizAvailable: null
  };
}

export function followUpRequest(ref: ExplainerRef, question: string, facets: readonly Discipline[] = []): AskRequest {
  return { question: question.trim(), depth: null, buildsOn: { explainerId: ref.explainerId, version: ref.version, facets: [...facets] } };
}

function reopened(sections: readonly SectionView[], started: SectionStarted): SectionView[] | null {
  if (!sections.some((section) => section.id === started.id)) return null;
  return sections.map((section) => (section.id === started.id ? { ...section, state: started.state } : section));
}

export function withDeepeningBlock(blocks: readonly ExplainerBlock[], block: ExplainerBlock): ExplainerBlock[] {
  if (blocks.some((held) => held.id === block.id)) return [...blocks];
  const pictures = blocks.findIndex((held) => held.kind === IMAGES);
  if (block.kind === IMAGES || pictures < 0) return [...blocks, block];
  return [...blocks.slice(0, pictures), block, ...blocks.slice(pictures)];
}

function deepened(sections: readonly SectionView[], sectionId: string, block: ExplainerBlock): SectionView[] {
  return sections.map((section) =>
    section.id === sectionId && !isFinalSection(section.state) ? { ...section, blocks: withDeepeningBlock(section.blocks, block) } : section
  );
}

function settledState(sections: readonly SectionView[], done: SectionDone): SectionDone["state"] {
  const held = sections.find((section) => section.id === done.sectionId);
  return done.state === "EMPTY" && held && held.blocks.length > 0 ? "READY" : done.state;
}

function markedAdded(sections: readonly SectionView[], id: string): SectionView[] {
  return sections.map((section) => (section.id === id ? { ...section, added: true } : section));
}

function settledSection(section: SectionView): SectionView {
  const stored = { ...section };
  delete stored.added;
  return stored;
}

export function storedSections(sections: readonly SectionView[]): SectionView[] {
  return sections.filter((section) => !section.added || section.blocks.length > 0).map(settledSection);
}

function sameBase(ref: ExplainerRef, event: BuildsOnEvent): boolean {
  return ref.explainerId === event.explainerId && ref.version === event.version;
}

function reduceFollowing(state: ExplainerState, ref: ExplainerRef, event: ExplainerEvent): ExplainerState {
  switch (event.type) {
    case "builds_on":
      return sameBase(ref, event.data) ? state : { ...state, phase: "failed", status: null, error: STALE_FOLLOW_UP };
    case "section_started": {
      const sections = reopened(state.sections, event.data);
      if (sections) return { ...state, phase: "streaming", sections };
      const opened = reduceExplainer(state, event);
      return { ...opened, sections: markedAdded(opened.sections, event.data.id) };
    }
    case "block":
      return { ...state, phase: "streaming", sections: deepened(state.sections, event.data.sectionId, event.data.block) };
    case "section_done":
      return reduceExplainer(state, { ...event, data: { ...event.data, state: settledState(state.sections, event.data) } });
    default:
      return reduceExplainer(state, event);
  }
}

export function reduceAnswerEvent(state: ExplainerState, event: ExplainerEvent): ExplainerState {
  if (event.type === "version") return { ...state, mark: event.data, basedOn: null, sections: storedSections(state.sections) };
  if (state.basedOn) return reduceFollowing(state, state.basedOn, event);
  return reduceExplainer(state, event);
}

export function versionChanges(mark: VersionMark, sections: readonly Pick<SectionView, "id" | "title">[]): string[] {
  const titles = new Map(sections.map((section) => [section.id, section.title]));
  return mark.changes.map((change) => `${change.change === "ADDED" ? "Added" : "Deepened"} ${titles.get(change.sectionId) ?? change.sectionId}`);
}

export type VersionOption = { value: string; label: string; hint: string };

export function knownVersions(listed: readonly VersionMark[], shown: VersionMark | null): VersionMark[] {
  const explainerId = listed[0]?.explainerId ?? shown?.explainerId;
  const byNumber = new Map(listed.map((mark) => [mark.version, mark]));
  if (shown && shown.explainerId === explainerId) byNumber.set(shown.version, shown);
  return [...byNumber.values()].sort((a, b) => a.version - b.version);
}

export function versionOptions(versions: readonly VersionMark[]): VersionOption[] {
  const latest = versions.at(-1)?.version ?? 0;
  return [...versions].reverse().map((mark) => ({
    value: String(mark.version),
    label: mark.version === latest ? `Version ${mark.version} · latest` : `Version ${mark.version}`,
    hint: mark.question
  }));
}
