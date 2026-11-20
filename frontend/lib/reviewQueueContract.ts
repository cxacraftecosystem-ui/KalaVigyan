import { apiFetch } from "@/lib/api";
import { craftLinkShape, INSTANT, storedLevelShape, type CraftLink, type StoredLevel } from "@/lib/answerShapes";
import { imageContributionShape, type ImageContribution } from "@/lib/imageContributionContract";
import { boolean, dictionary, integer, list, nullable, number, object, oneOf, optional, parseShape, tagged, text, type Shape } from "@/lib/shape";
import {
  STRUCTURE_KINDS,
  structureCheckShape,
  structureEntryShape,
  type StructureCheck,
  type StructureEntry,
  type StructureKind
} from "@/lib/structureReviewContract";
import { reviewEntryShape, type ClosedReviewItem, type ReviewItem } from "@/lib/testimonyContract";

export const REVIEW_QUEUE_PATH = "/review-queue";
export const QUEUE_KINDS = ["FACTS", "TESTIMONY", "IMAGES", "COMPONENTS", "LAYOUTS", "STRUCTURE"] as const;
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
export type SourceQuote = { text: string; locator: string | null };
export type FactSource = { title: string; url: string | null; licence: string | null; reliability: string; quotes: SourceQuote[] };
export type RelatedFact = { id: string; text: string };
export type GateCheck = { gate: string; passed: boolean; reasons: string[]; model: string | null; related: RelatedFact[] };
export type FactConcept = { name: string; type: string };

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

type ItemBase = { id: string; origin: ReviewOrigin; submittedAt: string; craft: CraftLink | null; proposer: Proposer | null };

export type FactItem = ItemBase & { kind: "FACTS"; fact: FactReview };
export type TestimonyItem = ItemBase & { kind: "TESTIMONY"; testimony: ReviewItem | ClosedReviewItem };
export type PictureItem = ItemBase & { kind: "IMAGES"; picture: ImageContribution };
export type ComponentItem = ItemBase & { kind: "COMPONENTS"; component: ComponentReview };
export type LayoutItem = ItemBase & { kind: "LAYOUTS"; layout: LayoutReview };
export type StructureItem = ItemBase & { kind: "STRUCTURE"; structure: StructureReview };
export type QueueItem = FactItem | TestimonyItem | PictureItem | ComponentItem | LayoutItem | StructureItem;

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

const sourceShape: Shape<FactSource> = object<FactSource>({
  title: text,
  url: nullable(text),
  licence: nullable(text),
  reliability: text,
  quotes: list(object<SourceQuote>({ text, locator: nullable(text) }))
});

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
  gates: list(gateShape)
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
  closest: list(object<ClosestComponent>({ component: libraryShape, overlap: number, reasons: list(text) }))
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
  )
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

const base = { id: text, origin: originShape, submittedAt: INSTANT, craft: nullable(craftLinkShape), proposer: nullable(proposerShape) };

export const queueItemShape: Shape<QueueItem> = tagged<QueueItem>("kind", {
  FACTS: object<FactItem>({ ...base, kind: oneOf(["FACTS"] as const), fact: factShape }),
  TESTIMONY: object<TestimonyItem>({ ...base, kind: oneOf(["TESTIMONY"] as const), testimony: reviewEntryShape }),
  IMAGES: object<PictureItem>({ ...base, kind: oneOf(["IMAGES"] as const), picture: imageContributionShape }),
  COMPONENTS: object<ComponentItem>({ ...base, kind: oneOf(["COMPONENTS"] as const), component: componentShape }),
  LAYOUTS: object<LayoutItem>({ ...base, kind: oneOf(["LAYOUTS"] as const), layout: layoutShape }),
  STRUCTURE: object<StructureItem>({ ...base, kind: oneOf(["STRUCTURE"] as const), structure: structureShape })
});

export const reviewQueuePageShape: Shape<ReviewQueuePage> = object<ReviewQueuePage>({
  schemaVersion,
  kinds: list(kindShape),
  counts: dictionary(/^[A-Z]+$/, integer),
  total: integer,
  items: list(queueItemShape),
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

export function decisionBody(action: QueueAction, words: string): Record<string, string | null> {
  const trimmed = words.trim();
  if (action === "reject" || action === "retract") return { reason: trimmed };
  return { note: trimmed || null };
}

export async function fetchReviewQueue(filters: ReviewFilters, cursor: string | null): Promise<ReviewQueuePage> {
  return parseShape(reviewQueuePageShape, await apiFetch<unknown>(`${REVIEW_QUEUE_PATH}?${queueQuery(filters, cursor)}`));
}

export async function decideQueueItem(kind: QueueKind, id: string, action: QueueAction, words: string): Promise<QueueDecision> {
  const body = JSON.stringify(decisionBody(action, words));
  return parseShape(queueDecisionShape, await apiFetch<unknown>(DECISION_PATH(kind, id, action), { method: "POST", body }));
}
