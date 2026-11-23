import { isReaderCraft } from "@/lib/craftCatalogue";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";
import { roleLabel } from "@/lib/permissions";
import {
  isQueueKind,
  REASON_MAX,
  REASON_MIN,
  REVIEW_ORIGINS,
  type DeliveredFact,
  type Filing,
  type GateCheck,
  type HeldWriteBack,
  type Proposer,
  type QueueAction,
  type QueueItem,
  type QueueKind,
  type ReviewFilters,
  type ReviewOrigin,
  type ReviewQueuePage,
  type SuppliedProvenance
} from "@/lib/reviewQueueContract";

export const EVERY_KIND = "ALL";
export const FILE_UNDER_CRAFT = "craft:";
export const FILE_UNDER_FAMILY = "family:";
export const NO_FILTERS: ReviewFilters = { kind: null, craft: null, origin: null };

export const KIND_LABELS: Record<QueueKind, string> = {
  FACTS: "Facts",
  TESTIMONY: "Testimony",
  IMAGES: "Pictures",
  COMPONENTS: "Components",
  LAYOUTS: "Layouts",
  STRUCTURE: "Structure",
  READINGS: "Readings",
  LAYERS: "Map layers",
  STAGES: "Process stages"
};

export const KIND_NOUNS: Record<QueueKind, string> = {
  FACTS: "Fact",
  TESTIMONY: "Testimony",
  IMAGES: "Picture",
  COMPONENTS: "Component proposal",
  LAYOUTS: "Layout proposal",
  STRUCTURE: "Structure proposal",
  READINGS: "Reading outside its range",
  LAYERS: "Map layer proposal",
  STAGES: "Process stage"
};

export const ORIGIN_LABELS: Record<ReviewOrigin, string> = {
  RESEARCH: "Our research",
  CONTRIBUTION: "Contributors",
  AGENT: "Outside agents",
  TESTIMONY: "Artisans' testimony"
};

export const ACTION_LABELS: Record<QueueAction, string> = {
  approve: "Approve",
  raise: "Approve as reviewed",
  reject: "Reject",
  retract: "Retract"
};

export const FACT_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Waiting, not shown",
  IN_REVIEW: "Shown, not yet reviewed"
};

export const GATE_LABELS: Record<string, string> = {
  STATED: "Every name and number given is in a quote",
  QUOTES: "Quotes found in the source",
  SOURCE: "Source graded and its licence allows it",
  DUPLICATE: "Not a duplicate of a fact held",
  NOVELTY: "Adds to what the section says"
};

const DESTRUCTIVE: ReadonlySet<QueueAction> = new Set(["reject", "retract"]);

const FACT_ACTIONS: Record<string, QueueAction[]> = {
  DRAFT: ["approve", "raise", "reject"],
  IN_REVIEW: ["approve", "raise", "retract"]
};

export function isDestructive(action: QueueAction): boolean {
  return DESTRUCTIVE.has(action);
}

export function factActions(status: string): QueueAction[] {
  return FACT_ACTIONS[status] ?? [];
}

export function componentActions(): QueueAction[] {
  return ["approve", "reject"];
}

export function reasonProblem(action: QueueAction, words: string): string | null {
  const length = words.trim().length;
  if (length > REASON_MAX) return `Keep it to ${REASON_MAX} characters.`;
  if (isDestructive(action) && length < REASON_MIN) return `Give the reason, in at least ${REASON_MIN} characters.`;
  return null;
}

function isOrigin(value: string | null): value is ReviewOrigin {
  return REVIEW_ORIGINS.includes(value as ReviewOrigin);
}

export function filtersFromSearch(params: URLSearchParams): ReviewFilters {
  const kind = params.get("kind");
  const origin = params.get("origin");
  const craft = params.get("craft")?.trim() ?? "";
  return { kind: isQueueKind(kind) ? kind : null, craft: craft || null, origin: isOrigin(origin) ? origin : null };
}

export function filtersSearch(filters: ReviewFilters): string {
  const query = new URLSearchParams();
  if (filters.kind) query.set("kind", filters.kind);
  if (filters.origin) query.set("origin", filters.origin);
  if (filters.craft) query.set("craft", filters.craft);
  return query.toString();
}

export function isFiltered(filters: ReviewFilters): boolean {
  return Boolean(filters.kind || filters.craft || filters.origin);
}

export function waitingCount(page: ReviewQueuePage): number {
  return page.kinds.reduce((sum, kind) => sum + (page.counts[kind] ?? 0), 0);
}

export function kindTabs(page: ReviewQueuePage): { value: string; label: string }[] {
  return [
    { value: EVERY_KIND, label: `All (${waitingCount(page)})` },
    ...page.kinds.map((kind) => ({ value: kind, label: `${KIND_LABELS[kind]} (${page.counts[kind] ?? 0})` }))
  ];
}

export function withoutItem(page: ReviewQueuePage, item: QueueItem): ReviewQueuePage {
  if (!page.items.some((each) => each.id === item.id)) return page;
  const counts = { ...page.counts, [item.kind]: Math.max(0, (page.counts[item.kind] ?? 0) - 1) };
  return { ...page, counts, total: Math.max(0, page.total - 1), items: page.items.filter((each) => each.id !== item.id) };
}

export function withNextPage(page: ReviewQueuePage, next: ReviewQueuePage): ReviewQueuePage {
  const seen = new Set(page.items.map((item) => item.id));
  return { ...next, items: [...page.items, ...next.items.filter((item) => !seen.has(item.id))] };
}

export function codeLabel(code: string): string {
  return (code.charAt(0) + code.slice(1).toLowerCase()).replace(/_/g, " ");
}

export function fieldsLine(field: string | null, fields: readonly string[]): string | null {
  if (!field) return null;
  const also = fields.map(codeLabel);
  return also.length ? `${codeLabel(field)}, also ${also.join(", ")}` : codeLabel(field);
}

export function gateLine(check: GateCheck): string {
  return `${GATE_LABELS[check.gate] ?? codeLabel(check.gate)}: ${check.passed ? "passed" : "refused"}`;
}

const INDEX_LABELS: Record<string, string> = { openalex: "OpenAlex", crossref: "Crossref", semantic_scholar: "Semantic Scholar" };

export function suppliedLine(supplied: SuppliedProvenance): string {
  const index = supplied.confirmedBy ? (INDEX_LABELS[supplied.confirmedBy] ?? supplied.confirmedBy) : null;
  const found = index ? `, found in ${index}` : ", not found in a scholarly index";
  return `Text supplied by the proposer (${codeLabel(supplied.access)}, read on ${supplied.accessedOn}${found}); ${supplied.characters} characters held privately, SHA-256 ${supplied.textSha256.slice(0, 12)}`;
}

export function overlapLine(overlap: number): string {
  return `${Math.round(overlap * 100)} per cent of words shared`;
}

export function proposerLine(proposer: Proposer | null): string | null {
  return proposer ? `Proposed by ${proposer.name}, ${roleLabel(proposer.role)}` : null;
}

export function factNumbersLine(claimIds: readonly string[], numbers: ReadonlyMap<string, number>): string {
  const cited = claimIds.map((claim) => numbers.get(claim)).filter((number): number is number => number !== undefined);
  const found = [...new Set(cited)].sort((a, b) => a - b);
  if (!found.length) return "A heading or label, resting on no fact";
  return found.length === 1 ? `Rests on fact ${found[0]}` : `Rests on facts ${found.join(", ")}`;
}

export function deliveredFactLine(number: number, fact: DeliveredFact): string {
  const level = fact.level ? ` · ${codeLabel(fact.level)}` : "";
  return `Fact ${number}${level} · ${fact.shown ? "shown on the page" : "held from the page"}`;
}

export type FilingOption = { value: string; label: string; hint?: string; group: string };

export function heldLine(held: HeldWriteBack): string {
  return `Held for a reviewer: it ${held.reason}.`;
}

export function filingOptions(catalogue: CraftCatalogue): FilingOption[] {
  const crafts = catalogue.crafts
    .filter(isReaderCraft)
    .map((craft) => ({ value: `${FILE_UNDER_CRAFT}${craft.slug}`, label: craft.displayName, hint: craft.familyLabel ?? undefined, group: "Crafts" }));
  const families = catalogue.categories.map((category) => ({
    value: `${FILE_UNDER_FAMILY}${category.slug}`,
    label: `${category.label ?? category.name}, family science`,
    group: "Family science"
  }));
  return [...crafts, ...families];
}

export function filingOf(value: string): Filing | null {
  if (value.startsWith(FILE_UNDER_CRAFT)) return { craft: value.slice(FILE_UNDER_CRAFT.length) };
  if (value.startsWith(FILE_UNDER_FAMILY)) return { family: value.slice(FILE_UNDER_FAMILY.length) };
  return null;
}
