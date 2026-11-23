import { apiFetch } from "@/lib/api";
import { INSTANT, UUID } from "@/lib/answerShapes";
import { count, dictionary, list, matching, nullable, object, parseShape, type Shape } from "@/lib/shape";
import { countNoun } from "@/lib/format";

export const HIDDEN_FACTS_PATH = "/coverage/hidden-facts";
export const HIDDEN_REASONS = ["HELD", "RESTRICTED_FACT", "HIDDEN_CONCEPT", "NO_SHOWN_SOURCE"] as const;

export type HiddenReason = (typeof HIDDEN_REASONS)[number];
export type ReasonCounts = Record<HiddenReason, number>;
export type CraftHidden = { craft: string; approved: number; hidden: Partial<ReasonCounts>; unexplained: string[] };
export type HiddenFactsReport = {
  countedAt: string | null;
  crafts: number;
  byReason: ReasonCounts;
  unexplained: number;
  craftsUnexplained: string[];
  perCraft: CraftHidden[];
};
export type HiddenFacts = { report: HiddenFactsReport | null };
export type HiddenRow = { craft: string; approved: number; reasons: ReasonCounts; unexplained: number; hidden: number };

export const HIDDEN_REASON_LABELS: Readonly<Record<HiddenReason, string>> = {
  HELD: "Held",
  RESTRICTED_FACT: "Restricted fact",
  HIDDEN_CONCEPT: "Hidden concept",
  NO_SHOWN_SOURCE: "No shown source"
};

const SLUG = matching(/^\S+$/, "a craft slug");
const REASON_KEY = new RegExp(`^(${HIDDEN_REASONS.join("|")})$`);

const reasonCountsShape: Shape<ReasonCounts> = object<ReasonCounts>({ HELD: count, RESTRICTED_FACT: count, HIDDEN_CONCEPT: count, NO_SHOWN_SOURCE: count });

const craftHiddenShape: Shape<CraftHidden> = object<CraftHidden>({
  craft: SLUG,
  approved: count,
  hidden: dictionary(REASON_KEY, count) as Shape<Partial<ReasonCounts>>,
  unexplained: list(UUID)
});

const hiddenFactsShape: Shape<HiddenFacts> = object<HiddenFacts>({
  report: nullable(
    object<HiddenFactsReport>({
      countedAt: nullable(INSTANT),
      crafts: count,
      byReason: reasonCountsShape,
      unexplained: count,
      craftsUnexplained: list(SLUG),
      perCraft: list(craftHiddenShape)
    })
  )
});

export function parseHiddenFacts(raw: unknown): HiddenFacts {
  return parseShape(hiddenFactsShape, raw);
}

export async function fetchHiddenFacts(): Promise<HiddenFacts> {
  return parseHiddenFacts(await apiFetch<unknown>(HIDDEN_FACTS_PATH));
}

function reasonCounts(hidden: Partial<ReasonCounts>): ReasonCounts {
  return { HELD: hidden.HELD ?? 0, RESTRICTED_FACT: hidden.RESTRICTED_FACT ?? 0, HIDDEN_CONCEPT: hidden.HIDDEN_CONCEPT ?? 0, NO_SHOWN_SOURCE: hidden.NO_SHOWN_SOURCE ?? 0 };
}

function hiddenRow(entry: CraftHidden): HiddenRow {
  const reasons = reasonCounts(entry.hidden);
  const byReason = HIDDEN_REASONS.reduce((sum, reason) => sum + reasons[reason], 0);
  return { craft: entry.craft, approved: entry.approved, reasons, unexplained: entry.unexplained.length, hidden: byReason + entry.unexplained.length };
}

export function hiddenRows(report: HiddenFactsReport): HiddenRow[] {
  return report.perCraft.map(hiddenRow).sort((a, b) => b.unexplained - a.unexplained || b.hidden - a.hidden || a.craft.localeCompare(b.craft));
}

export function hiddenTotal(report: HiddenFactsReport): number {
  return HIDDEN_REASONS.reduce((sum, reason) => sum + report.byReason[reason], report.unexplained);
}

export const HIDDEN_SUMMARY = {
  waiting: "The night's upkeep writes this count after its next run.",
  allShown: "Every approved fact is shown to signed-out readers."
};

export function hiddenSummary(found: HiddenFacts, formatInstant: (value: string | null) => string): string {
  const report = found.report;
  if (!report) return HIDDEN_SUMMARY.waiting;
  const counted = `Counted ${formatInstant(report.countedAt)}`;
  if (report.crafts === 0) return `${counted}. ${HIDDEN_SUMMARY.allShown}`;
  const unexplained = report.unexplained > 0 ? `, ${report.unexplained} unexplained in ${countNoun(report.craftsUnexplained.length, "craft")}` : "";
  const listed = report.perCraft.length < report.crafts ? ` The first ${report.perCraft.length} by address are listed.` : "";
  return `${counted}: ${countNoun(hiddenTotal(report), "hidden fact")} in ${countNoun(report.crafts, "craft")}${unexplained}.${listed}`;
}
