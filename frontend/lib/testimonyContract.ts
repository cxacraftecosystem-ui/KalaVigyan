import { apiFetch } from "@/lib/api";
import { citationShape, craftLinkShape, INSTANT, type CraftLink } from "@/lib/answerShapes";
import { integer, list, nullable, object, oneOf, parseShape, ShapeError, text, type Shape } from "@/lib/shape";
import type { Citation } from "@/lib/types";

export const CONTRIBUTIONS_PATH = "/artisan/contributions";
export const WITHDRAW_PATH = (id: string) => `/artisan/contributions/${encodeURIComponent(id)}/withdraw`;
export const REVIEW_PATH = "/testimony/review";
export const REVIEW_ITEM_PATH = (id: string) => `/testimony/review/${encodeURIComponent(id)}`;

export const CONTRIBUTION_STATUSES = ["PENDING", "APPROVED", "REJECTED", "WITHDRAWN"] as const;
export const TESTIMONY_ENGLISH_SOURCES = ["ORIGINAL", "MACHINE", "REVIEWED"] as const;
export const TESTIMONY_REJECT_REASONS = ["NOT_ABOUT_THE_CRAFT", "MISHEARD", "PERSONAL_DETAILS", "ABOUT_OTHER_PEOPLE", "DUPLICATE", "UNCLEAR", "OTHER"] as const;
export const TESTIMONY_SCREENS = ["NAME_HELD_BACK"] as const;
export const LOCATOR_PRECISIONS = ["WORD", "TURN"] as const;

export type ContributionStatus = (typeof CONTRIBUTION_STATUSES)[number];
export type RejectReason = (typeof TESTIMONY_REJECT_REASONS)[number];
export type Counts = { pending: number; approved: number; rejected: number; withdrawn: number };

export const REJECT_REASON_LABELS: Record<RejectReason, string> = {
  NOT_ABOUT_THE_CRAFT: "Not about the craft",
  MISHEARD: "Misheard",
  PERSONAL_DETAILS: "Personal details",
  ABOUT_OTHER_PEOPLE: "About other people",
  DUPLICATE: "Already given",
  UNCLEAR: "Unclear",
  OTHER: "Other"
};

export const STATUS_LABELS: Record<ContributionStatus, string> = { PENDING: "Waiting for review", APPROVED: "Shown", REJECTED: "Not shown", WITHDRAWN: "Taken back" };

export type Contribution = {
  id: string;
  status: Exclude<ContributionStatus, "WITHDRAWN">;
  conversationId: string;
  craft: CraftLink;
  discipline: string;
  claimText: string | null;
  quote: string | null;
  language: string;
  english: string | null;
  englishSource: (typeof TESTIMONY_ENGLISH_SOURCES)[number];
  locator: string;
  recordedAt: string;
  line: string;
  submittedAt: string;
  reviewedAt: string | null;
  reviewerRole: string | null;
  rejectReason: RejectReason | null;
  reviewNote: string | null;
  approvedAt: string | null;
  withdrawnAt: null;
};
export type WithdrawnContribution = { id: string; status: "WITHDRAWN"; conversationId: string; withdrawnAt: string };
export type ContributionItem = Contribution | WithdrawnContribution;
export type ContributionList = { counts: Counts; items: ContributionItem[] };

export type ReviewItem = {
  id: string;
  version: number;
  status: ContributionStatus;
  craft: CraftLink;
  discipline: string;
  conceptType: string;
  conceptName: string;
  claimText: string | null;
  quote: string | null;
  language: string;
  script: string;
  direction: "ltr" | "rtl";
  english: string | null;
  englishSource: (typeof TESTIMONY_ENGLISH_SOURCES)[number];
  locator: string;
  locatorPrecision: (typeof LOCATOR_PRECISIONS)[number];
  recordedAt: string;
  speaker: { name: string | null; role: "ARTISAN"; district: string | null; state: string | null };
  line: string;
  screens: (typeof TESTIMONY_SCREENS)[number][];
  corroboratedBy: Citation[];
  context: {
    before: { text: string | null; english: string | null; answerId: string | null };
    turnText: string | null;
    audio: { url: string; expiresAt: string; mimeType: string; startMs: number; endMs: number } | null;
  };
  submittedAt: string;
  reviewedAt: string | null;
  reviewerRole: string | null;
  rejectReason: RejectReason | null;
  reviewNote: string | null;
};
export type ClosedReviewItem = { id: string; status: "WITHDRAWN" | "REJECTED"; craft: CraftLink; withdrawnAt: string | null };
export type ReviewPage = { counts: Counts; total: number; items: (ReviewItem | ClosedReviewItem)[]; nextCursor: string | null };

const nullOnly: Shape<null> = {
  expected: "null",
  parse(value, path) {
    if (value !== null) throw new ShapeError(path, "null");
    return null;
  }
};
const countsShape: Shape<Counts> = object({ pending: integer, approved: integer, rejected: integer, withdrawn: integer });
const englishSource = oneOf(TESTIMONY_ENGLISH_SOURCES);
const rejectReason = nullable(oneOf(TESTIMONY_REJECT_REASONS));

export const contributionShape: Shape<Contribution> = object<Contribution>({
  id: text,
  status: oneOf(["PENDING", "APPROVED", "REJECTED"] as const),
  conversationId: text,
  craft: craftLinkShape,
  discipline: text,
  claimText: nullable(text),
  quote: nullable(text),
  language: text,
  english: nullable(text),
  englishSource,
  locator: text,
  recordedAt: INSTANT,
  line: text,
  submittedAt: INSTANT,
  reviewedAt: nullable(INSTANT),
  reviewerRole: nullable(text),
  rejectReason,
  reviewNote: nullable(text),
  approvedAt: nullable(INSTANT),
  withdrawnAt: nullOnly
});

export const withdrawnShape: Shape<WithdrawnContribution> = object({ id: text, status: oneOf(["WITHDRAWN"] as const), conversationId: text, withdrawnAt: INSTANT });

export const contributionItemShape: Shape<ContributionItem> = {
  expected: "a contribution",
  parse: (value, path) => ((value as { status?: unknown })?.status === "WITHDRAWN" ? withdrawnShape : contributionShape).parse(value, path)
};

export const contributionListShape: Shape<ContributionList> = object({ counts: countsShape, items: list(contributionItemShape) });

const reviewItemShape: Shape<ReviewItem> = object<ReviewItem>({
  id: text,
  version: integer,
  status: oneOf(CONTRIBUTION_STATUSES),
  craft: craftLinkShape,
  discipline: text,
  conceptType: text,
  conceptName: text,
  claimText: nullable(text),
  quote: nullable(text),
  language: text,
  script: text,
  direction: oneOf(["ltr", "rtl"] as const),
  english: nullable(text),
  englishSource,
  locator: text,
  locatorPrecision: oneOf(LOCATOR_PRECISIONS),
  recordedAt: INSTANT,
  speaker: object({ name: nullable(text), role: oneOf(["ARTISAN"] as const), district: nullable(text), state: nullable(text) }),
  line: text,
  screens: list(oneOf(TESTIMONY_SCREENS)),
  corroboratedBy: list(citationShape),
  context: object({
    before: object({ text: nullable(text), english: nullable(text), answerId: nullable(text) }),
    turnText: nullable(text),
    audio: nullable(object({ url: text, expiresAt: INSTANT, mimeType: text, startMs: integer, endMs: integer }))
  }),
  submittedAt: INSTANT,
  reviewedAt: nullable(INSTANT),
  reviewerRole: nullable(text),
  rejectReason,
  reviewNote: nullable(text)
});

const closedReviewShape: Shape<ClosedReviewItem> = object({
  id: text,
  status: oneOf(["WITHDRAWN", "REJECTED"] as const),
  craft: craftLinkShape,
  withdrawnAt: nullable(INSTANT)
});

export const reviewEntryShape: Shape<ReviewItem | ClosedReviewItem> = {
  expected: "a review item",
  parse: (value, path) => ("version" in (value as object) ? reviewItemShape : closedReviewShape).parse(value, path)
};

export const reviewPageShape: Shape<ReviewPage> = object({ counts: countsShape, total: integer, items: list(reviewEntryShape), nextCursor: nullable(text) });

export function isOpenItem(item: ReviewItem | ClosedReviewItem): item is ReviewItem {
  return "version" in item;
}

export async function fetchContributions(): Promise<ContributionList> {
  return parseShape(contributionListShape, await apiFetch<unknown>(CONTRIBUTIONS_PATH));
}

export async function withdrawContribution(id: string): Promise<void> {
  await apiFetch<unknown>(WITHDRAW_PATH(id), { method: "POST" });
}

export async function fetchReviewPage(status: ContributionStatus, cursor: string | null): Promise<ReviewPage> {
  const query = new URLSearchParams({ status });
  if (cursor) query.set("cursor", cursor);
  return parseShape(reviewPageShape, await apiFetch<unknown>(`${REVIEW_PATH}?${query.toString()}`));
}

export async function editItem(item: ReviewItem, changes: { claimText?: string; english?: string }): Promise<ReviewItem> {
  const body = { version: item.version, ...changes };
  return parseShape(reviewItemShape, await apiFetch<unknown>(REVIEW_ITEM_PATH(item.id), { method: "PUT", body: JSON.stringify(body) }));
}
