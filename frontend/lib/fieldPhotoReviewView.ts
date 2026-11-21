import type { StatusTone } from "@/components/records/statusTone";
import { byCount, countNoun, formatDate } from "@/lib/format";
import {
  CROP_SIDE_MIN,
  NOTE_MIN,
  type DecisionBody,
  type FieldPhoto,
  type FieldPhotoQueue,
  type HideReason,
  type PhotoCrop,
  type PhotoDecision,
  type PhotoPerson,
  type PhotoRisk,
  type QueueCounts,
  type QueueState,
  type ScreenRun
} from "@/lib/fieldPhotoReviewContract";

export type Trims = { top: number; bottom: number; left: number; right: number };
export type PhotoDraft = { decision: PhotoDecision; reason: HideReason | null; note: string; trims: Trims; clearFlags: boolean };

export const TRIM_MAX = 45;
export const NO_TRIMS: Trims = { top: 0, bottom: 0, left: 0, right: 0 };
export const TRIM_SIDES: { key: keyof Trims; label: string }[] = [
  { key: "top", label: "Trim the top" },
  { key: "bottom", label: "Trim the bottom" },
  { key: "left", label: "Trim the left side" },
  { key: "right", label: "Trim the right side" }
];

export const STATE_LABELS: Record<QueueState, string> = { WAITING: "Waiting", SHOWN: "Shown", HIDDEN: "Hidden" };

export const DECISION_CHOICES: Record<PhotoDecision, string> = { SHOW: "Show", CROP: "Crop", HIDE: "Hide" };

export const REASON_LABELS: Record<HideReason, string> = {
  IDENTITY_DOCUMENT: "It shows an identity document",
  NOT_AGREED: "Someone in it has not agreed",
  PRIVATE_PLACE: "It shows a private place",
  POOR_QUALITY: "Its quality is too poor",
  NOT_THIS_CRAFT: "It is not this craft",
  OTHER: "Another reason, in the note"
};

export const RISK_COPY: Record<PhotoRisk, { label: string; tone: StatusTone }> = {
  IDENTITY: { label: "May show an identity document", tone: "error" },
  FACE: { label: "Shows a face", tone: "warning" },
  CHECK: { label: "Look closely", tone: "info" },
  CLEAR: { label: "The screens found nothing", tone: "success" }
};

const DONE_LABELS: Record<PhotoDecision, string> = { SHOW: "Shown", CROP: "Shown as a crop", HIDE: "Kept hidden" };
const ROLE_LABELS: Record<string, string> = { ADMIN: "Admin", MASTER_ADMIN: "Master Admin" };
const KIND_LABELS: Record<string, string> = { ARTISAN: "artisan", DESIGNER: "designer", RESEARCHER: "researcher" };

export function stateOptions(counts: QueueCounts): { value: QueueState; label: string }[] {
  const count: Record<QueueState, number> = { WAITING: counts.waiting, SHOWN: counts.shown, HIDDEN: counts.hidden };
  return (["WAITING", "SHOWN", "HIDDEN"] as const).map((value) => ({ value, label: `${STATE_LABELS[value]} ${count[value]}` }));
}

export function cropFromTrims(trims: Trims, width: number, height: number): PhotoCrop {
  const left = Math.round((width * trims.left) / 100);
  const top = Math.round((height * trims.top) / 100);
  const right = width - Math.round((width * trims.right) / 100);
  const bottom = height - Math.round((height * trims.bottom) / 100);
  return { left, top, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
}

export function cropProblem(crop: PhotoCrop, width: number, height: number): string | null {
  if (crop.width < CROP_SIDE_MIN || crop.height < CROP_SIDE_MIN) return `Keep at least ${CROP_SIDE_MIN} pixels on each side.`;
  if (crop.width * crop.height >= width * height) return "Trim at least one edge, or choose Show to show all of it.";
  return null;
}

export function needsMaster(photo: Pick<FieldPhoto, "masterOnly">, decision: PhotoDecision): boolean {
  return photo.masterOnly && decision !== "HIDE";
}

export function draftProblem(draft: PhotoDraft, photo: FieldPhoto, master: boolean): string | null {
  const noted = draft.note.trim().length >= NOTE_MIN;
  if (draft.decision !== "HIDE" && !photo.screen) return "The screens have not looked at it yet. Screen the waiting photographs first.";
  if (needsMaster(photo, draft.decision) && !master) return "Only a Master Admin can show this photograph. You can keep it hidden.";
  if (draft.decision === "HIDE" && !draft.reason) return "Choose why it stays hidden.";
  if (draft.decision === "HIDE" && draft.reason === "OTHER" && !noted) return "Say in the note why it stays hidden.";
  if (draft.decision === "SHOW" && photo.masterOnly && !draft.clearFlags) return "Clear the screen's flag, or show a crop that leaves the region out.";
  if (draft.decision === "SHOW" && draft.clearFlags && !noted) return "Say in the note why the screen's flag is wrong.";
  if (draft.decision === "CROP") return cropProblem(cropFromTrims(draft.trims, photo.width, photo.height), photo.width, photo.height);
  return null;
}

export function decisionBody(draft: PhotoDraft, photo: FieldPhoto): DecisionBody {
  const note = draft.note.trim();
  return {
    decision: draft.decision,
    seenSha256: photo.sha256,
    reason: draft.decision === "HIDE" ? draft.reason : null,
    note: note || null,
    crop: draft.decision === "CROP" ? cropFromTrims(draft.trims, photo.width, photo.height) : null,
    clearFlags: draft.decision === "SHOW" && draft.clearFlags
  };
}

export function firstDraft(photo: FieldPhoto): PhotoDraft {
  const decision: PhotoDecision = photo.state === "SHOWN" || photo.masterOnly ? "HIDE" : "SHOW";
  return { decision, reason: null, note: "", trims: NO_TRIMS, clearFlags: false };
}

export function peopleLine(people: PhotoPerson[]): string | null {
  const named = people.filter((person) => person.name).map((person) => (person.kind && KIND_LABELS[person.kind] ? `${person.name} (${KIND_LABELS[person.kind]})` : `${person.name}`));
  return named.length ? named.join(", ") : null;
}

export function decidedLine(entry: { decision: PhotoDecision; decidedBy: string | null; decidedAt: string }, role?: string): string {
  const who = entry.decidedBy ? ` by ${entry.decidedBy}${role ? ` (${ROLE_LABELS[role] ?? role})` : ""}` : "";
  return `${DONE_LABELS[entry.decision]}${who}, ${formatDate(entry.decidedAt)}`;
}

export function reasonLine(reason: string | null, note: string | null): string | null {
  const label = reason && reason in REASON_LABELS ? REASON_LABELS[reason as HideReason] : null;
  if (label && note) return `${label}: ${note}`;
  return label ?? note;
}

export function sizeLine(photo: Pick<FieldPhoto, "width" | "height" | "mime">): string {
  const kind = photo.mime === "image/png" ? "PNG" : "JPEG";
  return `${photo.width.toLocaleString("en-IN")} × ${photo.height.toLocaleString("en-IN")} px, ${kind}`;
}

export function keptRegion(trims: Trims): { x: number; y: number; width: number; height: number } {
  return { x: trims.left, y: trims.top, width: Math.max(0, 100 - trims.left - trims.right), height: Math.max(0, 100 - trims.top - trims.bottom) };
}

export function trimsOfCrop(crop: PhotoCrop, width: number, height: number): Trims {
  const percent = (part: number, whole: number) => Math.round((part * 1000) / whole) / 10;
  return {
    top: percent(crop.top, height),
    bottom: percent(height - crop.top - crop.height, height),
    left: percent(crop.left, width),
    right: percent(width - crop.left - crop.width, width)
  };
}

export function screenedLine(run: ScreenRun): string {
  const lost = run.missing.length;
  const missing = lost ? ` ${byCount(lost, "The stored copy", "The stored copies")} of ${countNoun(lost, "photograph")} ${byCount(lost, "is", "are")} missing.` : "";
  if (!run.screened) return `Every waiting photograph has been screened.${missing}`;
  return `Screened ${countNoun(run.screened, "photograph")}: ${run.flagged} flagged, ${run.unscreened} not looked at automatically.${missing}`;
}

const COUNT_KEYS: Record<QueueState, keyof QueueCounts> = { WAITING: "waiting", SHOWN: "shown", HIDDEN: "hidden" };

export function withMore(kept: FieldPhotoQueue, found: FieldPhotoQueue): FieldPhotoQueue {
  const seen = new Set(kept.items.map((photo) => photo.id));
  return { ...found, items: [...kept.items, ...found.items.filter((photo) => !seen.has(photo.id))] };
}

export function withDecided(queue: FieldPhotoQueue, photo: FieldPhoto): FieldPhotoQueue {
  const before = queue.items.find((each) => each.id === photo.id);
  const counts = { ...queue.counts };
  if (before && before.state !== photo.state) {
    counts[COUNT_KEYS[before.state]] = Math.max(0, counts[COUNT_KEYS[before.state]] - 1);
    counts[COUNT_KEYS[photo.state]] += 1;
  }
  return { ...queue, counts, items: queue.items.map((each) => (each.id === photo.id ? photo : each)) };
}
