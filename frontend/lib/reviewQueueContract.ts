import { apiFetch } from "@/lib/api";
import { craftLinkShape, INSTANT, storedLevelShape, type CraftLink, type StoredLevel } from "@/lib/answerShapes";
import { imageContributionShape, type ImageContribution } from "@/lib/imageContributionContract";
import { layerReviewShape, type LayerReview } from "@/lib/layerReviewContract";
import type { MonographDocument } from "@/lib/monographDocument";
import { monographDocumentShape } from "@/lib/monographDocumentShape";
import { boolean, dictionary, integer, knownOnly, list, nullable, number, object, oneOf, optional, parseShape, tagged, text, type Shape } from "@/lib/shape";
import {
  isKnownStructure,
  STRUCTURE_KINDS,
  structureCheckShape,
  structureEntryShape,
  type StructureCheck,
  type StructureEntry,
  type StructureKind
} from "@/lib/structureReviewContract";
import { readingShape, type ReadingReview } from "@/lib/readingReviewContract";
import { sourceShape, type FactSource, type SourceQuote, type SuppliedProvenance } from "@/lib/reviewSources";
import { reviewEntryShape, type ClosedReviewItem, type RejectReason, type ReviewItem } from "@/lib/testimonyContract";

export type { FactSource, ReadingReview, SourceQuote, SuppliedProvenance };

export const REVIEW_QUEUE_PATH = "/review-queue";
export const QUEUE_KINDS = ["FACTS", "TESTIMONY", "IMAGES", "COMPONENTS", "LAYOUTS", "STRUCTURE", "READINGS", "LAYERS", "STAGES"] as const;
export const REVIEW_ORIGINS = ["RESEARCH", "CONTRIBUTION", "AGENT", "TESTIMONY"] as const;
export const QUEUE_ACTIONS = ["approve", "raise", "reject", "retract"] as const;
export const LAYOUT_CHANGES = ["ADDED", "CHANGED", "REMOVED"] as const;
export const REASON_MIN = 3;
export const REASON_MAX = 500;
export const PAGE_SIZE = 25;

export type QueueKind = (typeof QUEUE_KINDS)[number];
export type ReviewOrigin = (typeof REVIEW_ORIGINS)[number];
export type QueueAction = (typeof QUEUE_ACTIONS)[number];
export type LayoutChangeKind = (typeof LAYOUT_CHANGES)[number];

export type Proposer = { name: string; role: string };
export type RelatedFact = { id: string; text: string };
export type GateCheck = { gate: string; passed: boolean; reasons: string[]; model: string | null; related: RelatedFact[] };
export type FactConcept = { name: string; type: string };
export type HeldWriteBack = { reason: string; suggestedCraft: string };
export type Placement = { processId: string; afterStageId: string | null };
export type Filing = { craft: string } | { family: string } | Placement;

export type FactReview = {
  statement: string;
  field: string | null;
  fields: string[];
  status: string;
  level: StoredLevel;
  sourcesDiffer: boolean;
  concept: FactConcept | null;
  sources: FactSource[];
  gates: GateCheck[];
  held?: HeldWriteBack | null;
};

export type LibrarySubject = { kind: string; key: string; name: string };
export type LibraryComponent = {
  label: string;
  title: string;
  description: string;
  kind: string;
  field: string;
  fields: string[];
  craftSlug: string | null;
  subjects: LibrarySubject[];
};
export type ClosestComponent = { component: LibraryComponent; overlap: number; reasons: string[] };
export type ProposedSubject = { kind: string; key: string };
export type DeliveredUnitReview = { unit: string; text: string; claimIds: string[] };
export type DeliveredFact = { id: string; text: string; level: StoredLevel | null; shown: boolean; sources: FactSource[] };
export type DeliveredReview = { drawing: MonographDocument | null; units: DeliveredUnitReview[]; facts: DeliveredFact[] };
export type PlacedDelivery = { label: string; title: string; kind: string; delivery: DeliveredReview };

export type ComponentReview = {
  label: string;
  title: string;
  description: string;
  kind: string;
  field: string;
  fields: string[];
  subjects: ProposedSubject[];
  consideredLabels: string[];
  extends: string | null;
  extension: string | null;
  taskKey: string | null;
  closest: ClosestComponent[];
  delivery?: DeliveredReview | null;
};

export type LayoutCrop = { x: number; y: number; width: number; height: number };
export type LayoutEntry = {
  ref: string;
  chapter: string;
  order: number;
  role: string;
  crop?: LayoutCrop | null;
  size?: string | null;
  caption?: string | null;
};
export type LayoutChange = { ref: string; change: LayoutChangeKind; before: LayoutEntry | null; after: LayoutEntry | null };
export type LayoutSubject = { kind: string; slug: string };

export type LayoutReview = {
  subject: LayoutSubject;
  subjectName: string;
  pageUrl: string;
  baseVersion: number;
  currentVersion: number;
  stale: boolean;
  note: string | null;
  entryCount: number;
  changes: LayoutChange[];
  placed?: PlacedDelivery[];
};

export type StructureReview = {
  kind: StructureKind;
  subject: LayoutSubject;
  subjectName: string;
  pageUrl: string;
  target: string | null;
  current: string | null;
  item: StructureEntry;
  statement: string | null;
  field: string | null;
  note: string | null;
  taskKey: string | null;
  sources: FactSource[];
  checks: StructureCheck[];
  conflicting: RelatedFact[];
  stale: string | null;
};

export type ProcessStep = { id: string; ordinal: number; name: string };
export type StageProcess = { id: string; name: string; stages: ProcessStep[] };
export type StageFact = { id: string; text: string; sources: FactSource[] };
export type StagePlacing = { name: string; description: string | null; processes: StageProcess[]; facts: StageFact[] };

type ItemBase = { id: string; origin: ReviewOrigin; submittedAt: string; craft: CraftLink | null; proposer: Proposer | null };

export type FactItem = ItemBase & { kind: "FACTS"; fact: FactReview };
export type TestimonyItem = ItemBase & { kind: "TESTIMONY"; testimony: ReviewItem | ClosedReviewItem };
export type PictureItem = ItemBase & { kind: "IMAGES"; picture: ImageContribution };
export type ComponentItem = ItemBase & { kind: "COMPONENTS"; component: ComponentReview };
export type LayoutItem = ItemBase & { kind: "LAYOUTS"; layout: LayoutReview };
export type StructureItem = ItemBase & { kind: "STRUCTURE"; structure: StructureReview };
export type ReadingItem = ItemBase & { kind: "READINGS"; reading: ReadingReview };
export type LayerItem = ItemBase & { kind: "LAYERS"; layer: LayerReview };
export type StageItem = ItemBase & { kind: "STAGES"; stage: StagePlacing };
export type QueueItem =
  | FactItem
  | TestimonyItem
  | PictureItem
  | ComponentItem
  | LayoutItem
  | StructureItem
  | ReadingItem
  | LayerItem
  | StageItem;

export type ReviewQueuePage = {
  schemaVersion: 1;
  kinds: QueueKind[];
  counts: Record<string, number>;
  total: number;
  items: QueueItem[];
  nextCursor: string | null;
};

export type QueueDecision = {
  schemaVersion: 1;
  kind: QueueKind;
  id: string;
  status: string;
  level: StoredLevel | null;
  sourcesDiffer: boolean | null;
  message: string;
};

export type ReviewFilters = { kind: QueueKind | null; craft: string | null; origin: ReviewOrigin | null };

const schemaVersion = oneOf([1] as const);
const kindShape = oneOf(QUEUE_KINDS);
const originShape = oneOf(REVIEW_ORIGINS);
const proposerShape: Shape<Proposer> = object<Proposer>({ name: text, role: text });

const relatedShape: Shape<RelatedFact> = object<RelatedFact>({ id: text, text });

const gateShape: Shape<GateCheck> = object<GateCheck>({
  gate: text,
  passed: boolean,
  reasons: list(text),
  model: nullable(text),
  related: list(relatedShape)
});

const factShape: Shape<FactReview> = object<FactReview>({
  statement: text,
  field: nullable(text),
  fields: list(text),
  status: text,
  level: storedLevelShape,
  sourcesDiffer: boolean,
  concept: nullable(object<FactConcept>({ name: text, type: text })),
  sources: list(sourceShape),
  gates: list(gateShape),
  held: optional(nullable(object<HeldWriteBack>({ reason: text, suggestedCraft: text })))
});

const libraryShape: Shape<LibraryComponent> = object<LibraryComponent>({
  label: text,
  title: text,
  description: text,
  kind: text,
  field: text,
  fields: list(text),
  craftSlug: nullable(text),
  subjects: list(object<LibrarySubject>({ kind: text, key: text, name: text }))
});

const deliveryShape: Shape<DeliveredReview> = object<DeliveredReview>({
  drawing: nullable(monographDocumentShape),
  units: list(object<DeliveredUnitReview>({ unit: text, text, claimIds: list(text) })),
  facts: list(
    object<DeliveredFact>({ id: text, text, level: nullable(storedLevelShape), shown: boolean, sources: list(sourceShape) })
  )
});

const placedShape: Shape<PlacedDelivery> = object<PlacedDelivery>({ label: text, title: text, kind: text, delivery: deliveryShape });

const componentShape: Shape<ComponentReview> = object<ComponentReview>({
  label: text,
  title: text,
  description: text,
  kind: text,
  field: text,
  fields: list(text),
  subjects: list(object<ProposedSubject>({ kind: text, key: text })),
  consideredLabels: list(text),
  extends: nullable(text),
  extension: nullable(text),
  taskKey: nullable(text),
  closest: list(object<ClosestComponent>({ component: libraryShape, overlap: number, reasons: list(text) })),
  delivery: optional(nullable(deliveryShape))
});

const cropShape: Shape<LayoutCrop> = object<LayoutCrop>({ x: number, y: number, width: number, height: number });

const layoutEntryShape: Shape<LayoutEntry> = object<LayoutEntry>({
  ref: text,
  chapter: text,
  order: integer,
  role: text,
  crop: optional(nullable(cropShape)),
  size: optional(nullable(text)),
  caption: optional(nullable(text))
});

const layoutShape: Shape<LayoutReview> = object<LayoutReview>({
  subject: object<LayoutSubject>({ kind: text, slug: text }),
  subjectName: text,
  pageUrl: text,
  baseVersion: integer,
  currentVersion: integer,
  stale: boolean,
  note: nullable(text),
  entryCount: integer,
  changes: list(
    object<LayoutChange>({ ref: text, change: oneOf(LAYOUT_CHANGES), before: nullable(layoutEntryShape), after: nullable(layoutEntryShape) })
  ),
  placed: optional(list(placedShape))
});

const structureShape: Shape<StructureReview> = object<StructureReview>({
  kind: oneOf(STRUCTURE_KINDS),
  subject: object<LayoutSubject>({ kind: text, slug: text }),
  subjectName: text,
  pageUrl: text,
  target: nullable(text),
  current: nullable(text),
  item: structureEntryShape,
  statement: nullable(text),
  field: nullable(text),
  note: nullable(text),
  taskKey: nullable(text),
  sources: list(sourceShape),
  checks: list(structureCheckShape),
  conflicting: list(relatedShape),
  stale: nullable(text)
});

const placingShape: Shape<StagePlacing> = object<StagePlacing>({
  name: text,
  description: nullable(text),
  processes: list(
    object<StageProcess>({ id: text, name: text, stages: list(object<ProcessStep>({ id: text, ordinal: integer, name: text })) })
  ),
  facts: list(object<StageFact>({ id: text, text, sources: list(sourceShape) }))
});

const base = { id: text, origin: originShape, submittedAt: INSTANT, craft: nullable(craftLinkShape), proposer: nullable(proposerShape) };

export const queueItemShape: Shape<QueueItem> = tagged<QueueItem>("kind", {
  FACTS: object<FactItem>({ ...base, kind: oneOf(["FACTS"] as const), fact: factShape }),
  TESTIMONY: object<TestimonyItem>({ ...base, kind: oneOf(["TESTIMONY"] as const), testimony: reviewEntryShape }),
  IMAGES: object<PictureItem>({ ...base, kind: oneOf(["IMAGES"] as const), picture: imageContributionShape }),
  COMPONENTS: object<ComponentItem>({ ...base, kind: oneOf(["COMPONENTS"] as const), component: componentShape }),
  LAYOUTS: object<LayoutItem>({ ...base, kind: oneOf(["LAYOUTS"] as const), layout: layoutShape }),
  STRUCTURE: object<StructureItem>({ ...base, kind: oneOf(["STRUCTURE"] as const), structure: structureShape }),
  READINGS: object<ReadingItem>({ ...base, kind: oneOf(["READINGS"] as const), reading: readingShape }),
  LAYERS: object<LayerItem>({ ...base, kind: oneOf(["LAYERS"] as const), layer: layerReviewShape }),
  STAGES: object<StageItem>({ ...base, kind: oneOf(["STAGES"] as const), stage: placingShape })
});

export function isQueueKind(value: unknown): value is QueueKind {
  return QUEUE_KINDS.includes(value as QueueKind);
}

function isKnownItem(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return true;
  const item = value as { kind?: unknown; structure?: unknown };
  return isQueueKind(item.kind) && (item.kind !== "STRUCTURE" || isKnownStructure(item.structure));
}

export const reviewQueuePageShape: Shape<ReviewQueuePage> = object<ReviewQueuePage>({
  schemaVersion,
  kinds: knownOnly(kindShape, isQueueKind),
  counts: dictionary(/^[A-Z_]+$/, integer),
  total: integer,
  items: knownOnly(queueItemShape, isKnownItem),
  nextCursor: nullable(text)
});

export const queueDecisionShape: Shape<QueueDecision> = object<QueueDecision>({
  schemaVersion,
  kind: kindShape,
  id: text,
  status: text,
  level: nullable(storedLevelShape),
  sourcesDiffer: nullable(boolean),
  message: text
});

export const DECISION_PATH = (kind: QueueKind, id: string, action: QueueAction) =>
  `${REVIEW_QUEUE_PATH}/${kind}/${encodeURIComponent(id)}/${action}`;

export function queueQuery(filters: ReviewFilters, cursor: string | null, limit: number = PAGE_SIZE): string {
  const query = new URLSearchParams();
  if (filters.kind) query.set("kind", filters.kind);
  if (filters.craft) query.set("craft", filters.craft);
  if (filters.origin) query.set("origin", filters.origin);
  if (cursor) query.set("cursor", cursor);
  query.set("limit", String(limit));
  return query.toString();
}

export function decisionBody(action: QueueAction, words: string, filing: Filing | null = null): Record<string, string | null> {
  const trimmed = words.trim();
  if (action === "reject" || action === "retract") return { reason: trimmed };
  if (action === "approve" && filing) return { note: trimmed || null, ...filing };
  return { note: trimmed || null };
}

export async function fetchReviewQueue(filters: ReviewFilters, cursor: string | null): Promise<ReviewQueuePage> {
  return parseShape(reviewQueuePageShape, await apiFetch<unknown>(`${REVIEW_QUEUE_PATH}?${queueQuery(filters, cursor)}`));
}

export type TestimonyDecision = { action: "approve"; englishChecked: boolean } | { action: "reject"; reason: RejectReason; note: string };

export function testimonyDecisionBody(item: Pick<ReviewItem, "version">, decision: TestimonyDecision): Record<string, unknown> {
  if (decision.action === "approve") return { version: item.version, englishChecked: decision.englishChecked };
  return { version: item.version, testimonyReason: decision.reason, reason: decision.note.trim() || null };
}

export function testimonyNoteReady(reason: RejectReason | "", note: string): boolean {
  const words = note.trim();
  if (!reason || (reason === "OTHER" && !words)) return false;
  return words.length === 0 || (words.length >= REASON_MIN && words.length <= REASON_MAX);
}

async function decided(kind: QueueKind, id: string, action: QueueAction, body: Record<string, unknown>): Promise<QueueDecision> {
  return parseShape(queueDecisionShape, await apiFetch<unknown>(DECISION_PATH(kind, id, action), { method: "POST", body: JSON.stringify(body) }));
}

export async function decideQueueItem(kind: QueueKind, id: string, action: QueueAction, words: string, filing: Filing | null = null): Promise<QueueDecision> {
  return decided(kind, id, action, decisionBody(action, words, filing));
}

export async function decideTestimony(item: ReviewItem, decision: TestimonyDecision): Promise<QueueDecision> {
  return decided("TESTIMONY", item.id, decision.action, testimonyDecisionBody(item, decision));
}
