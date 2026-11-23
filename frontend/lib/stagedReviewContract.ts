import { apiFetch } from "@/lib/api";
import { INSTANT, UUID } from "@/lib/answerShapes";
import { REASON_MAX } from "@/lib/reviewQueueContract";
import { count, integer, knownOnly, list, nullable, object, oneOf, optional, parseShape, text, type Shape } from "@/lib/shape";

export const STAGED_PATH = "/review-queue/staged";
export const STAGED_KINDS = ["FACTS", "COMPONENTS", "LAYOUTS", "STRUCTURE", "READINGS", "LAYERS", "STAGES", "SOURCES", "SOURCES_DIFFER"] as const;
export const STAGED_ACTIONS = ["approve", "reject", "raise", "retract", "correct", "clear"] as const;
export const SOURCE_KINDS = [
  "PAPER",
  "BOOK",
  "BOOK_CHAPTER",
  "WEB_PAGE",
  "ENCYCLOPEDIA",
  "DATASET",
  "GI_JOURNAL",
  "GOVERNMENT_REPORT",
  "COMPOUND_RECORD",
  "FIELD_TESTIMONY",
  "OTHER",
  "MEDIA"
] as const;
export const BATCH_STATUSES = ["OPEN", "CONFIRMED", "DISCARDED", "EXPIRED"] as const;
export const ITEM_STATES = ["STAGED", "APPLIED", "REFUSED", "SKIPPED"] as const;
export const STAGED_REASON_MIN = 12;
export const STAGED_REASON_MAX = REASON_MAX;
export const CONFIRM_MAX = 20;
export const SOURCE_YEAR_MIN = 1000;
export const SOURCE_YEAR_MAX = 2100;
export const SOURCE_TITLE_MAX = 500;
export const SOURCE_CONTAINER_MAX = 300;
export const SOURCE_AUTHORS_MAX = 30;
export const SOURCE_AUTHOR_MAX = 200;

export type StagedKind = (typeof STAGED_KINDS)[number];
export type StagedAction = (typeof STAGED_ACTIONS)[number];
export type SourceKind = (typeof SOURCE_KINDS)[number];
export type BatchStatus = (typeof BATCH_STATUSES)[number];
export type ItemState = (typeof ITEM_STATES)[number];

export type SourceFix = {
  title?: string | null;
  authors?: string[] | null;
  year?: number | null;
  containerTitle?: string | null;
  kind?: SourceKind | null;
};

export type StagedChoice = {
  action: StagedAction;
  reason: string;
  craft: string | null;
  family: string | null;
  source: SourceFix | null;
};

export type StagedDecision = StagedChoice & { kind: StagedKind; id: string };
export type ConfirmedItem = StagedChoice & { id: string };
export type StagedConfirmation = { items: ConfirmedItem[] };

export type StagedItemView = {
  id: string;
  position: number;
  label: string;
  decision: StagedDecision;
  state: ItemState;
  applied: StagedDecision | null;
  outcome: string | null;
};

export type StagedBatchView = {
  id: string;
  status: BatchStatus;
  clientName: string;
  proposedBy: string | null;
  createdAt: string;
  expiresAt: string;
  decidedBy: string | null;
  decidedAt: string | null;
  refresh: string | null;
  items: StagedItemView[];
};

export type StagedBatchList = { schemaVersion: 1; batches: StagedBatchView[] };

const sourceFixShape: Shape<SourceFix> = object<SourceFix>({
  title: optional(nullable(text)),
  authors: optional(nullable(list(text))),
  year: optional(nullable(integer)),
  containerTitle: optional(nullable(text)),
  kind: optional(nullable(oneOf(SOURCE_KINDS)))
});

const decisionShape: Shape<StagedDecision> = object<StagedDecision>({
  kind: oneOf(STAGED_KINDS),
  id: UUID,
  action: oneOf(STAGED_ACTIONS),
  reason: text,
  craft: nullable(text),
  family: nullable(text),
  source: nullable(sourceFixShape)
});

const itemShape: Shape<StagedItemView> = object<StagedItemView>({
  id: UUID,
  position: count,
  label: text,
  decision: decisionShape,
  state: oneOf(ITEM_STATES),
  applied: nullable(decisionShape),
  outcome: nullable(text)
});

function includes(values: readonly string[], value: unknown): boolean {
  return typeof value === "string" && values.includes(value);
}

function isKnownDecision(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return true;
  const decision = value as { kind?: unknown; action?: unknown; source?: unknown };
  const source = typeof decision.source === "object" && decision.source !== null ? (decision.source as { kind?: unknown }) : null;
  const sourceKnown = source === null || source.kind === undefined || source.kind === null || includes(SOURCE_KINDS, source.kind);
  return includes(STAGED_KINDS, decision.kind) && includes(STAGED_ACTIONS, decision.action) && sourceKnown;
}

export function isKnownStagedItem(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return true;
  const item = value as { decision?: unknown; applied?: unknown };
  return isKnownDecision(item.decision) && (item.applied === null || item.applied === undefined || isKnownDecision(item.applied));
}

export const stagedBatchShape: Shape<StagedBatchView> = object<StagedBatchView>({
  id: UUID,
  status: oneOf(BATCH_STATUSES),
  clientName: text,
  proposedBy: nullable(text),
  createdAt: INSTANT,
  expiresAt: INSTANT,
  decidedBy: nullable(text),
  decidedAt: nullable(INSTANT),
  refresh: nullable(text),
  items: knownOnly(itemShape, isKnownStagedItem)
});

export const stagedBatchListShape: Shape<StagedBatchList> = object<StagedBatchList>({
  schemaVersion: oneOf([1] as const),
  batches: list(stagedBatchShape)
});

export function parseStagedBatchList(raw: unknown): StagedBatchList {
  return parseShape(stagedBatchListShape, raw);
}

export function parseStagedBatch(raw: unknown): StagedBatchView {
  return parseShape(stagedBatchShape, raw);
}

export function stagedBatchPath(batchId: string, step: "confirm" | "discard"): string {
  return `${STAGED_PATH}/${encodeURIComponent(batchId)}/${step}`;
}

export async function fetchStagedBatches(): Promise<StagedBatchList> {
  return parseStagedBatchList(await apiFetch<unknown>(STAGED_PATH));
}

export async function confirmStagedBatch(batchId: string, body: StagedConfirmation): Promise<StagedBatchView> {
  return parseStagedBatch(await apiFetch<unknown>(stagedBatchPath(batchId, "confirm"), { method: "POST", body: JSON.stringify(body) }));
}

export async function discardStagedBatch(batchId: string): Promise<StagedBatchView> {
  return parseStagedBatch(await apiFetch<unknown>(stagedBatchPath(batchId, "discard"), { method: "POST" }));
}
