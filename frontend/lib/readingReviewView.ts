import type { ReadingReview } from "@/lib/readingReviewContract";
import type { QueueAction } from "@/lib/reviewQueueContract";
import { codeLabel } from "@/lib/reviewQueueView";

const PH = "pH";

export const READING_ACTIONS: QueueAction[] = ["approve", "reject"];
export const READING_OUTCOME =
  "Approve keeps the reading on the page, marked outside its stage's usual range. Reject takes it off the page and keeps your reason.";

function withUnit(value: number, unit: string): string {
  return unit === PH ? `pH ${value}` : `${value} ${unit}`;
}

export function rangeLine(min: number | null, max: number | null, unit: string): string {
  if (min !== null && max !== null) {
    if (min === max) return withUnit(min, unit);
    return unit === PH ? `pH ${min} to ${max}` : `${min} to ${max} ${unit}`;
  }
  if (max !== null) return `up to ${withUnit(max, unit)}`;
  return min !== null ? `at least ${withUnit(min, unit)}` : "";
}

export function readingLine(review: ReadingReview): string {
  return rangeLine(review.min, review.max, review.unit);
}

export function envelopeLine(review: ReadingReview): string {
  return rangeLine(review.envelopeMin, review.envelopeMax, review.unit);
}

export function stageLine(review: ReadingReview): string {
  return `${review.stage}, a ${codeLabel(review.stageType).toLowerCase()} stage`;
}

export function readingTitle(review: ReadingReview): string {
  return `${review.condition}: ${review.stated}`;
}
