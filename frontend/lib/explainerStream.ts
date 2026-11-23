import { answerSentenceShape, answerStatusShape, HTTPS_URL, INSTANT, sourceRefShape, UUID } from "@/lib/answerShapes";
import { ANSWER_STREAM_PATH, openEventStream, readSseBlocks, sseFields, type AskRequest } from "@/lib/answerStream";
import {
  DISCIPLINES,
  explainerBlockShape,
  FINAL_SECTION_STATES,
  ledeBlockShape,
  SECTION_ID,
  understoodShape,
  WORKING_SECTION_STATES,
  type Discipline,
  type ExplainerBlock,
  type FinalSectionState,
  type LedeBlock,
  type Understood,
  type WorkingSectionState
} from "@/lib/explainerContract";
import { buildsOnEventShape, versionMarkShape, type BuildsOnEvent, type VersionMark } from "@/lib/learningContract";
import { boolean, integer, list, matching, nullable, number, object, oneOf, optional, ShapeError, text, type Shape } from "@/lib/shape";
import type { AnswerSentence, AnswerStatus, SourceRef } from "@/lib/types";

export const TRAIL_STAGES = ["FOUND", "READ", "QUOTED"] as const;
export const TRAIL_GROUPS = ["PAPERS", "ENCYCLOPAEDIA", "DATASETS", "WEB", "STORED"] as const;

export type SectionStarted = { id: string; discipline: Discipline; title: string; original?: string; order: number; state: WorkingSectionState };
export type SectionStateChange = { sectionId: string; state: WorkingSectionState };
export type BlockArrived = { sectionId: string; block: ExplainerBlock };
export type SectionDone = { sectionId: string; state: FinalSectionState; searched: string | null };
export type SectionHeading = { sectionId: string; title: string; original?: string };
export type LedeArrived = { block: LedeBlock };
export type TrailEntry = {
  key: string;
  stage: (typeof TRAIL_STAGES)[number];
  group: (typeof TRAIL_GROUPS)[number];
  title: string;
  url: string | null;
  publisher: string | null;
  year: number | null;
  sourceId: string | null;
  storedAt: string | null;
};

export type StreamDone = { answerId: string | null; quizAvailable?: boolean };
export type ServiceWait = { service: string; waitedSeconds: number; waitedRequests: number; refusals: number; unsent: number };
export type PacedServices = { services: ServiceWait[] };

export type ExplainerEvent =
  | { type: "understood"; data: Understood }
  | { type: "builds_on"; data: BuildsOnEvent }
  | { type: "version"; data: VersionMark }
  | { type: "section_started"; data: SectionStarted }
  | { type: "section_state"; data: SectionStateChange }
  | { type: "block"; data: BlockArrived }
  | { type: "section_done"; data: SectionDone }
  | { type: "section_heading"; data: SectionHeading }
  | { type: "lede"; data: LedeArrived }
  | { type: "trail"; data: TrailEntry }
  | { type: "paced"; data: PacedServices }
  | { type: "status"; data: AnswerStatus }
  | { type: "source"; data: SourceRef }
  | { type: "open_question"; data: { sectionId: string; heading?: string; sentence: AnswerSentence } }
  | { type: "follow_ups"; data: { items: string[] } }
  | { type: "not_enough_evidence"; data: { message: string } }
  | { type: "done"; data: StreamDone }
  | { type: "error"; data: { message: string } };

const EVENTS: { [K in ExplainerEvent["type"]]: Shape<Extract<ExplainerEvent, { type: K }>["data"]> } = {
  understood: understoodShape,
  builds_on: buildsOnEventShape,
  version: versionMarkShape,
  section_started: object<SectionStarted>({
    id: SECTION_ID,
    discipline: oneOf(DISCIPLINES),
    title: text,
    original: optional(text),
    order: integer,
    state: oneOf(WORKING_SECTION_STATES)
  }),
  section_state: object<SectionStateChange>({ sectionId: SECTION_ID, state: oneOf(WORKING_SECTION_STATES) }),
  block: object<BlockArrived>({ sectionId: SECTION_ID, block: explainerBlockShape }),
  section_done: object<SectionDone>({ sectionId: SECTION_ID, state: oneOf(FINAL_SECTION_STATES), searched: nullable(text) }),
  section_heading: object<SectionHeading>({ sectionId: SECTION_ID, title: text, original: optional(text) }),
  lede: object<LedeArrived>({ block: ledeBlockShape }),
  trail: object<TrailEntry>({
    key: matching(/^[a-z][a-z0-9_]{1,39}:\S+$/, "a trail key"),
    stage: oneOf(TRAIL_STAGES),
    group: oneOf(TRAIL_GROUPS),
    title: text,
    url: nullable(HTTPS_URL),
    publisher: nullable(text),
    year: nullable(integer),
    sourceId: nullable(text),
    storedAt: nullable(INSTANT)
  }),
  paced: object<PacedServices>({
    services: list(object<ServiceWait>({ service: text, waitedSeconds: number, waitedRequests: integer, refusals: integer, unsent: integer }), 1)
  }),
  status: answerStatusShape,
  source: sourceRefShape,
  open_question: object<{ sectionId: string; heading?: string; sentence: AnswerSentence }>({
    sectionId: text,
    heading: optional(text),
    sentence: answerSentenceShape
  }),
  follow_ups: object<{ items: string[] }>({ items: list(text) }),
  not_enough_evidence: object<{ message: string }>({ message: text }),
  done: object<StreamDone>({ answerId: nullable(UUID), quizAvailable: optional(boolean) }),
  error: object<{ message: string }>({ message: text })
};

function isExplainerEvent(name: string): name is ExplainerEvent["type"] {
  return Object.hasOwn(EVENTS, name);
}

export function parseExplainerStreamBlock(block: string): ExplainerEvent | null {
  const { name, data } = sseFields(block);
  if (!isExplainerEvent(name) || data === null) return null;
  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    throw new ShapeError(name, "a JSON payload");
  }
  return { type: name, data: EVENTS[name].parse(payload, name) } as ExplainerEvent;
}

export function explainerEventOf(block: string): ExplainerEvent | null {
  try {
    return parseExplainerStreamBlock(block);
  } catch (error) {
    if (!(error instanceof ShapeError)) throw error;
    console.error(error);
    return null;
  }
}

export async function streamExplainer(request: AskRequest, onEvent: (event: ExplainerEvent) => void, signal?: AbortSignal): Promise<void> {
  const stream = await openEventStream(ANSWER_STREAM_PATH, { body: JSON.stringify(request), json: true, signal, fallback: "Couldn't answer that. Try again." });
  await readSseBlocks(stream, (block) => {
    const event = explainerEventOf(block);
    if (event) onEvent(event);
  });
}
