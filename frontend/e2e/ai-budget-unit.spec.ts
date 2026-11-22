import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AiBudgetForm } from "@/components/admin/AiBudgetForm";
import { AuthProvider } from "@/components/AuthProvider";
import { ThemeProvider } from "@/components/ThemeProvider";
import { aiBudgetShape, ALLOWANCE_MAX, budgetDraft, budgetProblems, CAPPED_ROLES, draftBudget, USD_CAP_MAX, type AiBudgetView } from "@/lib/aiBudgetContract";
import { canAccessRoute } from "@/lib/permissions";
import { parseShape, ShapeError } from "@/lib/shape";
import type { User, UserRole } from "@/lib/types";

import { readRepo } from "./phaseBFixture";

const NONE = { VOICE_SECONDS: null, IMAGE: null, VIDEO: null };
const VIEW: AiBudgetView = {
  monthlyCeilingUsd: 800,
  mediaCapUsd: null,
  degradeAtFraction: 0.8,
  roleDailyUsd: { STUDENT: 0.5, ARTISAN: null, RESEARCHER: 3, PROFESSOR: 5, ADMIN: 10, MASTER_ADMIN: null },
  answerCapUsd: { BASIC: 0.25, DETAILED: 1, EXPERT: null },
  dailyAllowances: { STUDENT: { VOICE_SECONDS: 600, IMAGE: 5, VIDEO: 0 }, ARTISAN: NONE, RESEARCHER: NONE, PROFESSOR: NONE, ADMIN: NONE, MASTER_ADMIN: NONE },
  signUpMode: "ROSTER",
  domainAllowlist: []
};

function person(role: UserRole): User {
  return { id: role, email: `${role.toLowerCase()}@example.org`, name: role, role } as User;
}

test("the budget is read in the server's shape and an allowance must be whole", () => {
  expect(parseShape(aiBudgetShape, VIEW)).toEqual(VIEW);
  expect(() => parseShape(aiBudgetShape, { ...VIEW, extra: 1 })).toThrow(ShapeError);
  const halved = { ...VIEW, dailyAllowances: { ...VIEW.dailyAllowances, STUDENT: { VOICE_SECONDS: 2.5 } } };
  expect(() => parseShape(aiBudgetShape, halved)).toThrow(ShapeError);
});

test("an empty field is no cap both ways, and a Master Admin is never capped", () => {
  const draft = budgetDraft(VIEW);
  expect(CAPPED_ROLES).toEqual(["STUDENT", "ARTISAN", "RESEARCHER", "PROFESSOR", "ADMIN"]);
  expect([draft.mediaCapUsd, draft.answerCapUsd.EXPERT, draft.roleDailyUsd.STUDENT, draft.dailyAllowances.STUDENT.VIDEO]).toEqual(["", "", "0.5", "0"]);
  expect(draft.roleDailyUsd).not.toHaveProperty("MASTER_ADMIN");
  const sent = draftBudget({ ...draft, monthlyCeilingUsd: "", answerCapUsd: { ...draft.answerCapUsd, EXPERT: "2.5" } });
  expect([sent.monthlyCeilingUsd, sent.mediaCapUsd, sent.answerCapUsd.EXPERT, sent.dailyAllowances.STUDENT.VOICE_SECONDS]).toEqual([null, null, 2.5, 600]);
  expect(Object.keys(sent).sort()).toEqual(["answerCapUsd", "dailyAllowances", "degradeAtFraction", "mediaCapUsd", "monthlyCeilingUsd", "roleDailyUsd"]);
});

test("a draft is checked as the server checks it", () => {
  const draft = budgetDraft(VIEW);
  expect(budgetProblems(draft)).toEqual({});
  expect(Object.keys(budgetProblems({ ...draft, monthlyCeilingUsd: "-1" }))).toEqual(["monthlyCeilingUsd"]);
  expect(Object.keys(budgetProblems({ ...draft, monthlyCeilingUsd: String(USD_CAP_MAX + 1) }))).toEqual(["monthlyCeilingUsd"]);
  expect(budgetProblems({ ...draft, mediaCapUsd: "900" })).toEqual({ mediaCapUsd: "The media cap can't exceed the monthly ceiling." });
  for (const mark of ["0", "1.5"]) expect(Object.keys(budgetProblems({ ...draft, degradeAtFraction: mark }))).toEqual(["degradeAtFraction"]);
  const halved = { ...draft, dailyAllowances: { ...draft.dailyAllowances, ADMIN: { VOICE_SECONDS: "2.5", IMAGE: "", VIDEO: String(ALLOWANCE_MAX + 1) } } };
  expect(Object.keys(budgetProblems(halved))).toEqual(["dailyAllowances.ADMIN.VOICE_SECONDS", "dailyAllowances.ADMIN.VIDEO"]);
  const admin = readRepo("backend", "app", "schemas", "admin.py");
  expect(admin).toContain("monthlyCeilingUsd: float | None = Field(default=None, ge=0, le=100_000)");
  expect(admin).toContain("dailyAllowances: dict[str, dict[str, Annotated[int, Field(ge=0, le=1_000_000)] | None]] | None = None");
});

test("the form shows every cap with No cap as its empty state and saves with one primary button", () => {
  const form = createElement(AiBudgetForm, { view: VIEW, busy: false, onSave: () => undefined });
  const html = renderToStaticMarkup(createElement(AuthProvider, null, createElement(ThemeProvider, null, form)));
  expect(html).toContain("Monthly ceiling, dollars");
  expect(html).toContain("Expert, dollars");
  expect(html).toContain("Student&#x27;s daily allowances");
  expect(html).not.toContain("Master Admin, dollars");
  expect((html.match(/placeholder="No cap"/g) ?? []).length).toBe(3 + 3 + 5 + 5 * 3);
  expect((html.match(/data-variant="primary"/g) ?? []).length).toBe(1);
  expect(html).toContain("Your two-step code");
});

test("only a Master Admin reaches the AI budget", () => {
  expect(canAccessRoute(person("MASTER_ADMIN"), "/admin/budget")).toBe(true);
  for (const role of ["ADMIN", "PROFESSOR", "STUDENT"] as const) expect(canAccessRoute(person(role), "/admin/budget"), role).toBe(false);
});
