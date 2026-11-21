import { apiFetch, buildQuery } from "@/lib/api";
import { boolean, integer, list, nullable, object, oneOf, parseShape, text, type Shape } from "@/lib/shape";

export const FIELD_PHOTO_QUEUE_PATH = "/field-photos/review";
export const FIELD_PHOTO_SCREEN_PATH = "/field-photos/screen";
export const FIELD_PHOTO_DECISION_PATH = (id: string) => `/field-photos/${encodeURIComponent(id)}/decision`;
export const FIELD_PHOTO_SWITCH_PATH = "/field-voices/held-images/visibility";

export const PHOTO_DECISIONS = ["SHOW", "CROP", "HIDE"] as const;
export const HIDE_REASONS = ["IDENTITY_DOCUMENT", "NOT_AGREED", "PRIVATE_PLACE", "POOR_QUALITY", "NOT_THIS_CRAFT", "OTHER"] as const;
export const QUEUE_STATES = ["WAITING", "SHOWN", "HIDDEN"] as const;
export const PHOTO_RISKS = ["IDENTITY", "FACE", "CHECK", "CLEAR"] as const;
export const SWITCH_STATES = ["HIDDEN", "SHOWN"] as const;
export const PHOTO_ORIGINS = ["DESIGNER", "FIELD_REPOSITORY"] as const;
export const SCREEN_VERDICTS = ["CLEAR", "FLAGGED", "UNSCREENED"] as const;
export const NOTE_MIN = 3;
export const NOTE_MAX = 500;
export const CROP_SIDE_MIN = 64;

export type PhotoDecision = (typeof PHOTO_DECISIONS)[number];
export type HideReason = (typeof HIDE_REASONS)[number];
export type QueueState = (typeof QUEUE_STATES)[number];
export type PhotoRisk = (typeof PHOTO_RISKS)[number];
export type SwitchState = (typeof SWITCH_STATES)[number];

export type PhotoCrop = { left: number; top: number; width: number; height: number };
export type PhotoPerson = { name: string | null; kind: string | null };
export type PhotoScreen = { verdict: (typeof SCREEN_VERDICTS)[number]; flags: string[]; reasons: string[]; nearestDistance: number | null; model: string | null; screenedAt: string };
export type PhotoDecisionView = {
  decision: PhotoDecision;
  reason: HideReason | null;
  note: string | null;
  clearedFlags: string[];
  crop: PhotoCrop | null;
  cropUrl: string | null;
  decidedAt: string;
  decidedBy: string | null;
  decidedRole: string;
  current: boolean;
};
export type PhotoHistoryEntry = { decision: PhotoDecision; reason: string | null; note: string | null; decidedAt: string; decidedBy: string | null };

export type FieldPhoto = {
  id: string;
  itemId: string;
  origin: (typeof PHOTO_ORIGINS)[number];
  publisher: string;
  sha256: string;
  caption: string | null;
  alt: string;
  takenOn: string | null;
  crafts: string[];
  placements: string[];
  people: PhotoPerson[];
  credit: string;
  workshop: string | null;
  statement: string;
  rightsHolder: string;
  licence: string | null;
  width: number;
  height: number;
  mime: string;
  fileUrl: string | null;
  state: QueueState;
  risk: PhotoRisk;
  masterOnly: boolean;
  screen: PhotoScreen | null;
  decision: PhotoDecisionView | null;
  history: PhotoHistoryEntry[];
};

export type QueueCounts = Record<"waiting" | "shown" | "hidden", number>;
export type FieldPhotoQueue = {
  schemaVersion: 1;
  state: QueueState;
  visibility: SwitchState;
  counts: QueueCounts;
  cursor: string | null;
  nextCursor: string | null;
  items: FieldPhoto[];
};
export type ScreenRun = { ok: boolean; screened: number; flagged: number; unscreened: number; missing: string[] };

export type DecisionBody = {
  decision: PhotoDecision;
  seenSha256: string;
  reason: HideReason | null;
  note: string | null;
  crop: PhotoCrop | null;
  clearFlags: boolean;
};

const cropShape: Shape<PhotoCrop> = object<PhotoCrop>({ left: integer, top: integer, width: integer, height: integer });
const personShape: Shape<PhotoPerson> = object<PhotoPerson>({ name: nullable(text), kind: nullable(text) });
const screenShape: Shape<PhotoScreen> = object<PhotoScreen>({
  verdict: oneOf(SCREEN_VERDICTS),
  flags: list(text),
  reasons: list(text),
  nearestDistance: nullable(integer),
  model: nullable(text),
  screenedAt: text
});
const decisionShape: Shape<PhotoDecisionView> = object<PhotoDecisionView>({
  decision: oneOf(PHOTO_DECISIONS),
  reason: nullable(oneOf(HIDE_REASONS)),
  note: nullable(text),
  clearedFlags: list(text),
  crop: nullable(cropShape),
  cropUrl: nullable(text),
  decidedAt: text,
  decidedBy: nullable(text),
  decidedRole: text,
  current: boolean
});
const historyShape: Shape<PhotoHistoryEntry> = object<PhotoHistoryEntry>({
  decision: oneOf(PHOTO_DECISIONS),
  reason: nullable(text),
  note: nullable(text),
  decidedAt: text,
  decidedBy: nullable(text)
});

export const fieldPhotoShape: Shape<FieldPhoto> = object<FieldPhoto>({
  id: text,
  itemId: text,
  origin: oneOf(PHOTO_ORIGINS),
  publisher: text,
  sha256: text,
  caption: nullable(text),
  alt: text,
  takenOn: nullable(text),
  crafts: list(text),
  placements: list(text),
  people: list(personShape),
  credit: text,
  workshop: nullable(text),
  statement: text,
  rightsHolder: text,
  licence: nullable(text),
  width: integer,
  height: integer,
  mime: text,
  fileUrl: nullable(text),
  state: oneOf(QUEUE_STATES),
  risk: oneOf(PHOTO_RISKS),
  masterOnly: boolean,
  screen: nullable(screenShape),
  decision: nullable(decisionShape),
  history: list(historyShape)
});

export const fieldPhotoQueueShape: Shape<FieldPhotoQueue> = object<FieldPhotoQueue>({
  schemaVersion: oneOf([1] as const),
  state: oneOf(QUEUE_STATES),
  visibility: oneOf(SWITCH_STATES),
  counts: object<QueueCounts>({ waiting: integer, shown: integer, hidden: integer }),
  cursor: nullable(text),
  nextCursor: nullable(text),
  items: list(fieldPhotoShape)
});

const screenRunShape: Shape<ScreenRun> = object<ScreenRun>({ ok: boolean, screened: integer, flagged: integer, unscreened: integer, missing: list(text) });
const switchShape: Shape<{ visibility: SwitchState }> = object<{ visibility: SwitchState }>({ visibility: oneOf(SWITCH_STATES) });

export async function fetchFieldPhotos(state: QueueState, cursor: string | null = null): Promise<FieldPhotoQueue> {
  const body = await apiFetch<unknown>(`${FIELD_PHOTO_QUEUE_PATH}${buildQuery({ state, cursor })}`);
  return parseShape(fieldPhotoQueueShape, body);
}

export async function decideFieldPhoto(id: string, decision: DecisionBody): Promise<FieldPhoto> {
  const body = await apiFetch<unknown>(FIELD_PHOTO_DECISION_PATH(id), { method: "POST", body: JSON.stringify(decision) });
  return parseShape(fieldPhotoShape, body);
}

export async function screenFieldPhotos(): Promise<ScreenRun> {
  return parseShape(screenRunShape, await apiFetch<unknown>(FIELD_PHOTO_SCREEN_PATH, { method: "POST" }));
}

export async function setFieldPhotoSwitch(visibility: SwitchState): Promise<SwitchState> {
  const body = await apiFetch<unknown>(FIELD_PHOTO_SWITCH_PATH, { method: "PUT", body: JSON.stringify({ visibility }) });
  return parseShape(switchShape, body).visibility;
}
