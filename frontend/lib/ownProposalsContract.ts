import { apiFetch, buildQuery } from "@/lib/api";
import { DISCIPLINES, type Discipline } from "@/lib/explainerBlockBase";
import { boolean, dictionary, integer, list, nullable, object, oneOf, optional, parseShape, text, type Shape } from "@/lib/shape";
import { taskPassageShape, type TaskPassage } from "@/lib/translationContract";

export const PROPOSALS_PATH = "/contributions/proposals";
export const MY_PROPOSALS_PATH = `${PROPOSALS_PATH}/mine`;
export const PROPOSAL_FORM_PATH = `${PROPOSALS_PATH}/form`;
export const TERMS_PATH = `${PROPOSALS_PATH}/terms`;
export const OPEN_WORK_PATH = "/knowledge/open-work";

export const PROPOSAL_KINDS = ["FACT", "COMPONENT"] as const;
export const PROPOSAL_STATES = ["PUBLISHED", "APPROVED", "WAITING", "REFUSED", "REJECTED", "WITHDRAWN", "RETIRED"] as const;
export const GATES = ["QUOTES", "SOURCE", "DUPLICATE", "NOVELTY"] as const;
export const TASK_KINDS = ["MISSING_FIELD", "THIN_FIELD", "SECTION", "MISSING_COMPONENT", "FLAGSHIP", "PAGE_FORM", "PAGE_LAYOUT", "SECOND_SOURCE", "SOURCES_DIFFER", "DEAD_SOURCE", "UNARCHIVED_SOURCE", "RESOURCE_FACT", "CORROBORATE_FACT", "FIND_ANOTHER_SOURCE", "REVIEW", "MISSING_PICTURE", "TRANSLATE", "ANSWER_GAP"] as const;
export const FACT_TASK_KINDS: readonly TaskKind[] = ["ANSWER_GAP", "MISSING_FIELD", "THIN_FIELD"];
export const COMPONENT_TASK_KINDS: readonly TaskKind[] = ["MISSING_COMPONENT"];
export const FACT_TASK_SUBJECTS: readonly TaskSubject["kind"][] = ["craft", "category"];
export const COMPONENT_TASK_SUBJECTS: readonly TaskSubject["kind"][] = ["craft"];
export const PRIORITIES = ["HIGH", "MEDIUM", "LOW"] as const;
export const STARTS_SHOWN = 5;

export type ProposalKind = (typeof PROPOSAL_KINDS)[number];
export type ProposalState = (typeof PROPOSAL_STATES)[number];
export type Gate = (typeof GATES)[number];
export type TaskKind = (typeof TASK_KINDS)[number];

export type GateReport = { gate: Gate; passed: boolean; reasons: string[] };
export type TermsStatus = { version: string; acceptedAt: string | null };
export type FieldInfo = { field: Discipline; title: string; covers: string; chapter: string };
export type ProposalForm = {
  schemaVersion: 1;
  terms: TermsStatus;
  fields: FieldInfo[];
  kinds: string[];
  subjectKinds: string[];
  needs: Record<string, string[]>;
};

export type OwnProposal = {
  id: string;
  kind: ProposalKind;
  state: ProposalState;
  status: string;
  text: string;
  description: string | null;
  label: string | null;
  componentKind: string | null;
  field: Discipline | null;
  subjectName: string | null;
  craftSlug: string | null;
  createdAt: string;
  reasons: string[];
  gates: GateReport[];
};

export type TaskSubject = { kind: "craft" | "family" | "category"; slug: string; name: string; pageUrl: string };
export type OpenTask = {
  key: string;
  kind: TaskKind;
  priority: (typeof PRIORITIES)[number];
  subject: TaskSubject | null;
  field: Discipline | null;
  need: string | null;
  needed: string;
  acceptance: string;
  count: number;
  factIds: string[];
  sourceIds: string[];
  prompt: string | null;
  reservedUntil: string | null;
  passages?: TaskPassage[];
};

export const GATE_LABELS: Record<Gate, string> = {
  QUOTES: "Quotes found in their sources",
  SOURCE: "Sources graded and licences read",
  DUPLICATE: "Not already held",
  NOVELTY: "Adds to the section"
};

export const STATE_LABELS: Record<ProposalState, string> = {
  PUBLISHED: "Published",
  APPROVED: "Approved, waiting to be built",
  WAITING: "Waiting for review",
  REFUSED: "Not added: the checks refused it",
  REJECTED: "Not added: a reviewer rejected it",
  WITHDRAWN: "Withdrawn",
  RETIRED: "Retired after the evidence changed"
};

export const CONTRIBUTION_TERMS_POINTS = [
  "You give the Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur, a worldwide, royalty-free, perpetual and irrevocable licence to publish, edit, translate, adapt, combine and share your contribution, including under open licences.",
  "It is published without your name. Who contributed what is kept privately, for moderation and audit only.",
  "Consent cannot be revoked: once it is published it stays. You can withdraw it while it still waits for review.",
  "You hold the right to give it, quotes are copied exactly from the sources you name, and it names no private person and shares no restricted or sacred knowledge without permission.",
  "If an AI tool made any part of it, you have said so, named the tool and given the prompt."
] as const;

const fieldShape = oneOf(DISCIPLINES);
export const gateReportShape: Shape<GateReport> = object<GateReport>({ gate: oneOf(GATES), passed: boolean, reasons: list(text) });
export const termsStatusShape: Shape<TermsStatus> = object<TermsStatus>({ version: text, acceptedAt: nullable(text) });

const proposalFormShape: Shape<ProposalForm> = object<ProposalForm>({
  schemaVersion: oneOf([1] as const),
  terms: termsStatusShape,
  fields: list(object<FieldInfo>({ field: fieldShape, title: text, covers: text, chapter: text }), 1),
  kinds: list(text, 1),
  subjectKinds: list(text, 1),
  needs: dictionary(/^[a-z]+(-[a-z]+)*$/, list(text, 1))
});

export const ownProposalShape: Shape<OwnProposal> = object<OwnProposal>({
  id: text,
  kind: oneOf(PROPOSAL_KINDS),
  state: oneOf(PROPOSAL_STATES),
  status: text,
  text,
  description: nullable(text),
  label: nullable(text),
  componentKind: nullable(text),
  field: nullable(fieldShape),
  subjectName: nullable(text),
  craftSlug: nullable(text),
  createdAt: text,
  reasons: list(text),
  gates: list(gateReportShape)
});

const ownProposalsShape = object<{ schemaVersion: 1; items: OwnProposal[] }>({ schemaVersion: oneOf([1] as const), items: list(ownProposalShape) });

const openTaskShape: Shape<OpenTask> = object<OpenTask>({
  key: text,
  kind: oneOf(TASK_KINDS),
  priority: oneOf(PRIORITIES),
  subject: nullable(object<TaskSubject>({ kind: oneOf(["craft", "family", "category"] as const), slug: text, name: text, pageUrl: text })),
  field: nullable(fieldShape),
  need: nullable(text),
  needed: text,
  acceptance: text,
  count: integer,
  factIds: list(text),
  sourceIds: list(text),
  prompt: nullable(text),
  reservedUntil: nullable(text),
  passages: optional(list(taskPassageShape))
});

export function stateLabel(item: OwnProposal): string {
  if (item.state === "PUBLISHED" && item.status !== "APPROVED") return "Published, waiting for a reviewer's check";
  return STATE_LABELS[item.state];
}

export function termsProblem(terms: TermsStatus | null, ticked: boolean): string | null {
  if (!terms) return "The contribution terms could not be read. Reload the page.";
  return terms.acceptedAt || ticked ? null : `Accept the contribution terms, version ${terms.version}, to send it.`;
}

export function withTerms(problems: readonly string[], terms: TermsStatus | null, ticked: boolean): string[] {
  const missing = termsProblem(terms, ticked);
  return missing ? [...problems, missing] : [...problems];
}

export async function termsAccepted(terms: TermsStatus): Promise<TermsStatus> {
  return terms.acceptedAt ? terms : acceptTerms(terms.version);
}

export function canWithdraw(item: OwnProposal): boolean {
  return item.state === "WAITING";
}

export function withdrawPath(item: OwnProposal): string {
  const kind = item.kind === "FACT" ? "facts" : "components";
  return `${PROPOSALS_PATH}/${kind}/${encodeURIComponent(item.id)}/withdraw`;
}

export function fieldTitle(form: ProposalForm | null, field: Discipline | null): string {
  if (!field) return "";
  return form?.fields.find((each) => each.field === field)?.title ?? field;
}

export function startingTasks(tasks: readonly OpenTask[], kinds: readonly TaskKind[], subjects: readonly TaskSubject["kind"][]): OpenTask[] {
  return tasks.filter((task) => kinds.includes(task.kind) && task.subject !== null && subjects.includes(task.subject.kind)).slice(0, STARTS_SHOWN);
}

export function replaced<T>(items: readonly T[], index: number, item: T): T[] {
  return items.map((each, at) => (at === index ? item : each));
}

export function removed<T>(items: readonly T[], index: number): T[] {
  return items.filter((_, at) => at !== index);
}

export function openWorkFilter(kinds: readonly TaskKind[]): { kind?: TaskKind } {
  return kinds.length === 1 ? { kind: kinds[0] } : {};
}

export function itemsOfKind(items: readonly OwnProposal[], kind: ProposalKind): OwnProposal[] {
  return items.filter((item) => item.kind === kind);
}

export function kindLabel(kind: string): string {
  const words = kind.replace(/[_-]+/g, " ").trim();
  return words ? `${words[0].toUpperCase()}${words.slice(1)}` : kind;
}

export async function fetchProposalForm(): Promise<ProposalForm> {
  return parseShape(proposalFormShape, await apiFetch<unknown>(PROPOSAL_FORM_PATH));
}

export async function acceptTerms(version: string): Promise<TermsStatus> {
  return parseShape(termsStatusShape, await apiFetch<unknown>(TERMS_PATH, { method: "POST", body: JSON.stringify({ version }) }));
}

export async function fetchMyProposals(): Promise<OwnProposal[]> {
  return parseShape(ownProposalsShape, await apiFetch<unknown>(MY_PROPOSALS_PATH)).items;
}

export async function withdrawProposal(item: OwnProposal): Promise<OwnProposal> {
  return parseShape(ownProposalShape, await apiFetch<unknown>(withdrawPath(item), { method: "POST" }));
}

export async function fetchOpenTasks(filters: { craftSlug?: string; kind?: TaskKind }): Promise<OpenTask[]> {
  const body = await apiFetch<{ tasks?: unknown }>(`${OPEN_WORK_PATH}${buildQuery({ ...filters, limit: 50 })}`);
  return parseShape(list(openTaskShape), body.tasks);
}
