import { apiFetch } from "@/lib/api";
import { DEPTHS } from "@/lib/explainerContract";
import { ROLES_BY_RANK } from "@/lib/permissions";
import { dictionary, integer, list, nullable, number, object, parseShape, text, type Shape } from "@/lib/shape";
import type { UserRole } from "@/lib/types";

export const AI_BUDGET_PATH = "/settings/ai-budget";
export const ALLOWANCE_RESOURCES = ["VOICE_SECONDS", "IMAGE", "VIDEO"] as const;
export const USD_CAP_MAX = 100_000;
export const ANSWER_CAP_MAX = 1_000;
export const ALLOWANCE_MAX = 1_000_000;
export const NO_CAP = "No cap";
export const CAPPED_ROLES: UserRole[] = ROLES_BY_RANK.filter((role) => role !== "MASTER_ADMIN").reverse();

export type Depth = (typeof DEPTHS)[number];
export type AllowanceResource = (typeof ALLOWANCE_RESOURCES)[number];
type Cap = number | null;

export type AiBudget = {
  monthlyCeilingUsd: Cap;
  mediaCapUsd: Cap;
  degradeAtFraction: Cap;
  roleDailyUsd: Record<string, Cap>;
  answerCapUsd: Record<string, Cap>;
  dailyAllowances: Record<string, Record<string, Cap>>;
};

export type AiBudgetView = AiBudget & { signUpMode: string; domainAllowlist: string[] };

export type AiBudgetDraft = {
  monthlyCeilingUsd: string;
  mediaCapUsd: string;
  degradeAtFraction: string;
  roleDailyUsd: Record<string, string>;
  answerCapUsd: Record<string, string>;
  dailyAllowances: Record<string, Record<string, string>>;
};

export type AiBudgetProblems = Record<string, string>;

export const ALLOWANCE_LABELS: Record<AllowanceResource, string> = { VOICE_SECONDS: "Voice seconds", IMAGE: "Images", VIDEO: "Video clips" };
export const DEPTH_NAMES: Record<Depth, string> = { BASIC: "Basic", DETAILED: "Detailed", EXPERT: "Expert" };

const KEY = /^[A-Z_]+$/;
const cap: Shape<Cap> = nullable(number);

export const aiBudgetShape: Shape<AiBudgetView> = object<AiBudgetView>({
  monthlyCeilingUsd: cap,
  mediaCapUsd: cap,
  degradeAtFraction: cap,
  roleDailyUsd: dictionary(KEY, cap),
  answerCapUsd: dictionary(KEY, cap),
  dailyAllowances: dictionary(KEY, dictionary(KEY, nullable(integer))),
  signUpMode: text,
  domainAllowlist: list(text)
});

function shown(value: Cap | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

function mapped<U>(keys: readonly string[], value: (key: string) => U): Record<string, U> {
  return Object.fromEntries(keys.map((key) => [key, value(key)]));
}

export function budgetDraft(budget: AiBudget): AiBudgetDraft {
  return {
    monthlyCeilingUsd: shown(budget.monthlyCeilingUsd),
    mediaCapUsd: shown(budget.mediaCapUsd),
    degradeAtFraction: shown(budget.degradeAtFraction),
    roleDailyUsd: mapped(CAPPED_ROLES, (role) => shown(budget.roleDailyUsd[role])),
    answerCapUsd: mapped(DEPTHS, (depth) => shown(budget.answerCapUsd[depth])),
    dailyAllowances: mapped(CAPPED_ROLES, (role) => mapped(ALLOWANCE_RESOURCES, (resource) => shown(budget.dailyAllowances[role]?.[resource])))
  };
}

function capOf(text: string): Cap {
  return text.trim() === "" ? null : Number(text.trim());
}

function outOfRange(text: string, { max, whole = false, above = false }: { max: number; whole?: boolean; above?: boolean }): boolean {
  const value = capOf(text);
  if (value === null) return false;
  if (!Number.isFinite(value) || value > max || (above ? value <= 0 : value < 0)) return true;
  return whole && !Number.isInteger(value);
}

export function budgetProblems(draft: AiBudgetDraft): AiBudgetProblems {
  const problems: AiBudgetProblems = {};
  const money = `Enter an amount from 0 to ${USD_CAP_MAX} dollars, or leave it empty for no cap.`;
  if (outOfRange(draft.monthlyCeilingUsd, { max: USD_CAP_MAX })) problems.monthlyCeilingUsd = money;
  if (outOfRange(draft.mediaCapUsd, { max: USD_CAP_MAX })) problems.mediaCapUsd = money;
  const monthly = capOf(draft.monthlyCeilingUsd);
  const media = capOf(draft.mediaCapUsd);
  if (!problems.mediaCapUsd && media !== null && monthly !== null && media > monthly) problems.mediaCapUsd = "The media cap can't exceed the monthly ceiling.";
  if (outOfRange(draft.degradeAtFraction, { max: 1, above: true })) problems.degradeAtFraction = "Enter a share above 0 and up to 1, or leave it empty for no mark.";
  for (const role of CAPPED_ROLES) if (outOfRange(draft.roleDailyUsd[role] ?? "", { max: USD_CAP_MAX })) problems[`roleDailyUsd.${role}`] = money;
  for (const depth of DEPTHS) if (outOfRange(draft.answerCapUsd[depth] ?? "", { max: ANSWER_CAP_MAX })) problems[`answerCapUsd.${depth}`] = `Enter an amount from 0 to ${ANSWER_CAP_MAX} dollars, or leave it empty for no cap.`;
  for (const role of CAPPED_ROLES) {
    for (const resource of ALLOWANCE_RESOURCES) {
      if (outOfRange(draft.dailyAllowances[role]?.[resource] ?? "", { max: ALLOWANCE_MAX, whole: true })) problems[`dailyAllowances.${role}.${resource}`] = "Enter a whole number, or leave it empty for no cap.";
    }
  }
  return problems;
}

export function draftBudget(draft: AiBudgetDraft): AiBudget {
  return {
    monthlyCeilingUsd: capOf(draft.monthlyCeilingUsd),
    mediaCapUsd: capOf(draft.mediaCapUsd),
    degradeAtFraction: capOf(draft.degradeAtFraction),
    roleDailyUsd: mapped(CAPPED_ROLES, (role) => capOf(draft.roleDailyUsd[role] ?? "")),
    answerCapUsd: mapped(DEPTHS, (depth) => capOf(draft.answerCapUsd[depth] ?? "")),
    dailyAllowances: mapped(CAPPED_ROLES, (role) => mapped(ALLOWANCE_RESOURCES, (resource) => capOf(draft.dailyAllowances[role]?.[resource] ?? "")))
  };
}

export async function fetchAiBudget(): Promise<AiBudgetView> {
  return parseShape(aiBudgetShape, await apiFetch<unknown>(AI_BUDGET_PATH));
}

export async function saveAiBudget(budget: AiBudget, twoFactorCode: string): Promise<AiBudgetView> {
  const body = await apiFetch<unknown>(AI_BUDGET_PATH, { method: "PUT", body: JSON.stringify({ ...budget, twoFactorCode }) });
  return parseShape(aiBudgetShape, body);
}
