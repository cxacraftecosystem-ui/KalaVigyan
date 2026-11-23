import { ACTION_LABELS, FILE_UNDER_CRAFT, FILE_UNDER_FAMILY, filingOf, KIND_NOUNS } from "@/lib/reviewQueueView";
import {
  CONFIRM_MAX,
  SOURCE_AUTHOR_MAX,
  SOURCE_AUTHORS_MAX,
  SOURCE_KINDS,
  SOURCE_YEAR_MAX,
  SOURCE_YEAR_MIN,
  STAGED_REASON_MAX,
  STAGED_REASON_MIN,
  type BatchStatus,
  type ConfirmedItem,
  type ItemState,
  type SourceFix,
  type SourceKind,
  type StagedAction,
  type StagedBatchView,
  type StagedConfirmation,
  type StagedDecision,
  type StagedItemView,
  type StagedKind
} from "@/lib/stagedReviewContract";

export type SourceDraft = { title: string; authors: string; year: string; containerTitle: string; kind: string };

export type StagedDraft = {
  id: string;
  kind: StagedKind;
  selected: boolean;
  action: StagedAction;
  reason: string;
  fileUnder: string;
  source: SourceDraft | null;
};

export type DraftProblems = { reason: string | null; source: string | null };

const QUEUE_PAIR: readonly StagedAction[] = ["approve", "reject"];

export const STAGED_KIND_ACTIONS: Record<StagedKind, readonly StagedAction[]> = {
  FACTS: ["approve", "raise", "reject", "retract"],
  COMPONENTS: QUEUE_PAIR,
  LAYOUTS: QUEUE_PAIR,
  STRUCTURE: QUEUE_PAIR,
  READINGS: QUEUE_PAIR,
  LAYERS: QUEUE_PAIR,
  STAGES: QUEUE_PAIR,
  SOURCES: ["correct"],
  SOURCES_DIFFER: ["clear"]
};

export const STAGED_KIND_LABELS: Record<StagedKind, string> = {
  FACTS: KIND_NOUNS.FACTS,
  COMPONENTS: KIND_NOUNS.COMPONENTS,
  LAYOUTS: KIND_NOUNS.LAYOUTS,
  STRUCTURE: KIND_NOUNS.STRUCTURE,
  READINGS: KIND_NOUNS.READINGS,
  LAYERS: KIND_NOUNS.LAYERS,
  STAGES: KIND_NOUNS.STAGES,
  SOURCES: "Source correction",
  SOURCES_DIFFER: "Sources differ mark"
};

export const STAGED_ACTION_LABELS: Record<StagedAction, string> = {
  ...ACTION_LABELS,
  correct: "Correct the source",
  clear: "Clear the mark"
};

export const BATCH_STATUS_LABELS: Record<BatchStatus, string> = {
  OPEN: "Open",
  CONFIRMED: "Confirmed",
  DISCARDED: "Discarded",
  EXPIRED: "Expired"
};

export const ITEM_STATE_LABELS: Record<ItemState, string> = {
  STAGED: "Waiting for you",
  APPLIED: "Applied",
  REFUSED: "Refused",
  SKIPPED: "Skipped"
};

export function stagedActions(kind: StagedKind): readonly StagedAction[] {
  return STAGED_KIND_ACTIONS[kind];
}

export function refilesUnder(kind: StagedKind, action: StagedAction): boolean {
  return kind === "FACTS" && action === "approve";
}

export function isSourceKind(value: string): value is SourceKind {
  return (SOURCE_KINDS as readonly string[]).includes(value);
}

function fileUnderOf(decision: StagedDecision): string {
  if (decision.craft) return `${FILE_UNDER_CRAFT}${decision.craft}`;
  if (decision.family) return `${FILE_UNDER_FAMILY}${decision.family}`;
  return "";
}

export function sourceDraftOf(fix: SourceFix | null): SourceDraft | null {
  if (!fix) return null;
  return {
    title: fix.title ?? "",
    authors: (fix.authors ?? []).join("\n"),
    year: fix.year === null || fix.year === undefined ? "" : String(fix.year),
    containerTitle: fix.containerTitle ?? "",
    kind: fix.kind ?? ""
  };
}

export function draftOf(item: StagedItemView): StagedDraft {
  const decision = item.decision;
  return {
    id: item.id,
    kind: decision.kind,
    selected: true,
    action: decision.action,
    reason: decision.reason,
    fileUnder: fileUnderOf(decision),
    source: sourceDraftOf(decision.source)
  };
}

export function sourceFixOf(draft: SourceDraft): SourceFix {
  const authors = draft.authors
    .split("\n")
    .map((name) => name.trim())
    .filter(Boolean);
  const year = draft.year.trim();
  return {
    title: draft.title.trim() || null,
    authors: authors.length ? authors : null,
    year: year ? Number(year) : null,
    containerTitle: draft.containerTitle.trim() || null,
    kind: isSourceKind(draft.kind) ? draft.kind : null
  };
}

export function confirmedItemOf(draft: StagedDraft): ConfirmedItem {
  const filing = refilesUnder(draft.kind, draft.action) ? filingOf(draft.fileUnder) : null;
  return {
    id: draft.id,
    action: draft.action,
    reason: draft.reason.trim(),
    craft: filing && "craft" in filing ? filing.craft : null,
    family: filing && "family" in filing ? filing.family : null,
    source: draft.kind === "SOURCES" && draft.source ? sourceFixOf(draft.source) : null
  };
}

export function confirmBody(drafts: readonly StagedDraft[]): StagedConfirmation {
  return { items: drafts.filter((draft) => draft.selected).map(confirmedItemOf) };
}

export function reasonProblem(reason: string): string | null {
  const length = reason.trim().length;
  if (length < STAGED_REASON_MIN) return `Give the reason in at least ${STAGED_REASON_MIN} characters.`;
  if (length > STAGED_REASON_MAX) return `Keep the reason to ${STAGED_REASON_MAX} characters.`;
  return null;
}

export function sourceProblem(draft: SourceDraft): string | null {
  const year = draft.year.trim();
  const whole = /^\d{4}$/.test(year) ? Number(year) : NaN;
  if (year && !(whole >= SOURCE_YEAR_MIN && whole <= SOURCE_YEAR_MAX)) return `Give the year in four digits, from ${SOURCE_YEAR_MIN} to ${SOURCE_YEAR_MAX}.`;
  const fix = sourceFixOf(draft);
  const authors = fix.authors ?? [];
  if (authors.length > SOURCE_AUTHORS_MAX) return `Name at most ${SOURCE_AUTHORS_MAX} authors.`;
  if (authors.some((name) => name.length > SOURCE_AUTHOR_MAX)) return `Keep each author to ${SOURCE_AUTHOR_MAX} characters.`;
  if (Object.values(fix).every((value) => value === null)) return "Give at least one corrected field.";
  return null;
}

export function draftProblems(draft: StagedDraft): DraftProblems {
  return { reason: reasonProblem(draft.reason), source: draft.kind === "SOURCES" && draft.source ? sourceProblem(draft.source) : null };
}

export function confirmProblem(drafts: readonly StagedDraft[]): string | null {
  const chosen = drafts.filter((draft) => draft.selected);
  if (!chosen.length) return "Select at least one item to confirm.";
  if (chosen.length > CONFIRM_MAX) return `Confirm at most ${CONFIRM_MAX} items at once.`;
  const faulty = chosen.some((draft) => {
    const problems = draftProblems(draft);
    return Boolean(problems.reason || problems.source);
  });
  return faulty ? "Correct the items marked above, then confirm." : null;
}

export function withDraft(drafts: readonly StagedDraft[], next: StagedDraft): StagedDraft[] {
  return drafts.map((draft) => (draft.id === next.id ? next : draft));
}

export function withBatch(batches: readonly StagedBatchView[], next: StagedBatchView): StagedBatchView[] {
  return batches.map((batch) => (batch.id === next.id ? next : batch));
}

export function batchHeading(batch: StagedBatchView): string {
  return batch.proposedBy ? `Proposed through ${batch.clientName} by ${batch.proposedBy}` : `Proposed through ${batch.clientName}`;
}

export function batchTally(batch: StagedBatchView): string {
  const counted = (state: ItemState) => batch.items.filter((item) => item.state === state).length;
  return `${counted("APPLIED")} applied · ${counted("REFUSED")} refused · ${counted("SKIPPED")} skipped`;
}

export function decisionShown(item: StagedItemView): StagedDecision {
  return item.applied ?? item.decision;
}

export function filingLine(decision: StagedDecision): string | null {
  if (decision.craft) return decision.craft;
  return decision.family ? `${decision.family}, family science` : null;
}

export function outcomeLine(item: StagedItemView): string | null {
  if (item.state === "STAGED") return null;
  if (item.outcome) return item.outcome;
  if (item.state === "APPLIED") return item.applied ? "Applied as you changed it." : "Applied as proposed.";
  if (item.state === "SKIPPED") return "Not applied, so nothing changed.";
  return null;
}
