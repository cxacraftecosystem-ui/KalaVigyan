"use client";

import { useState, type FormEvent } from "react";

import { BudgetGroup, CapField } from "@/components/admin/AiBudgetFields";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { OtpCodeInput } from "@/components/ui/OtpCodeInput";
import { isCompleteCode } from "@/components/ui/otpCode";
import {
  ALLOWANCE_LABELS,
  ALLOWANCE_RESOURCES,
  budgetDraft,
  budgetProblems,
  CAPPED_ROLES,
  DEPTH_NAMES,
  draftBudget,
  type AiBudget,
  type AiBudgetDraft,
  type AiBudgetView
} from "@/lib/aiBudgetContract";
import { DEPTHS } from "@/lib/explainerContract";
import { roleLabel } from "@/lib/permissions";

type FormProps = { view: AiBudgetView; busy: boolean; onSave: (budget: AiBudget, twoFactorCode: string) => void };
type Change = (next: (draft: AiBudgetDraft) => AiBudgetDraft) => void;

export function AiBudgetForm({ view, busy, onSave }: FormProps) {
  const [draft, setDraft] = useState<AiBudgetDraft>(() => budgetDraft(view));
  const [code, setCode] = useState("");
  const [checked, setChecked] = useState(false);
  const problems = checked ? budgetProblems(draft) : {};
  const change: Change = (next) => setDraft((current) => next(current));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setChecked(true);
    if (Object.keys(budgetProblems(draft)).length === 0 && isCompleteCode(code)) onSave(draftBudget(draft), code);
  }

  return (
    <form className="grid gap-6" noValidate onSubmit={submit} data-testid="ai-budget-form">
      <BudgetGroup id="ai-budget-month" title="This month" note="Every AI call counts against the month; past the mark, answers plan cheaper and Expert answers Detailed.">
        <CapField label="Monthly ceiling, dollars" value={draft.monthlyCeilingUsd} error={problems.monthlyCeilingUsd} busy={busy} onChange={(value) => change((d) => ({ ...d, monthlyCeilingUsd: value }))} />
        <CapField label="Images and video, dollars" value={draft.mediaCapUsd} error={problems.mediaCapUsd} busy={busy} onChange={(value) => change((d) => ({ ...d, mediaCapUsd: value }))} />
        <CapField label="Degrade mark, share of the ceiling" hint="From 0.01 to 1." value={draft.degradeAtFraction} error={problems.degradeAtFraction} busy={busy} onChange={(value) => change((d) => ({ ...d, degradeAtFraction: value }))} />
      </BudgetGroup>
      <BudgetGroup id="ai-budget-answer" title="Each answer" note="What one answer may spend at each depth.">
        {DEPTHS.map((depth) => (
          <CapField key={depth} label={`${DEPTH_NAMES[depth]}, dollars`} value={draft.answerCapUsd[depth] ?? ""} error={problems[`answerCapUsd.${depth}`]} busy={busy} onChange={(value) => change((d) => ({ ...d, answerCapUsd: { ...d.answerCapUsd, [depth]: value } }))} />
        ))}
      </BudgetGroup>
      <BudgetGroup id="ai-budget-role" title="Each person's day" note="What one person of each role may spend in a day. Master Admins have no caps.">
        {CAPPED_ROLES.map((role) => (
          <CapField key={role} label={`${roleLabel(role)}, dollars`} value={draft.roleDailyUsd[role] ?? ""} error={problems[`roleDailyUsd.${role}`]} busy={busy} onChange={(value) => change((d) => ({ ...d, roleDailyUsd: { ...d.roleDailyUsd, [role]: value } }))} />
        ))}
      </BudgetGroup>
      {CAPPED_ROLES.map((role) => (
        <BudgetGroup key={role} id={`ai-budget-allowance-${role.toLowerCase()}`} title={`${roleLabel(role)}'s daily allowances`} note="Voice seconds, pictures and clips one person may use in a day.">
          {ALLOWANCE_RESOURCES.map((resource) => (
            <CapField
              key={resource}
              label={ALLOWANCE_LABELS[resource]}
              step="1"
              value={draft.dailyAllowances[role]?.[resource] ?? ""}
              error={problems[`dailyAllowances.${role}.${resource}`]}
              busy={busy}
              onChange={(value) => change((d) => ({ ...d, dailyAllowances: { ...d.dailyAllowances, [role]: { ...d.dailyAllowances[role], [resource]: value } } }))}
            />
          ))}
        </BudgetGroup>
      ))}
      <div className="grid max-w-measure gap-4 border-t border-rule pt-5">
        <OtpCodeInput label="Your two-step code" value={code} onChange={setCode} disabled={busy} />
        {checked && !isCompleteCode(code) ? <p className="font-ui text-label text-error">Enter the six digits your authenticator shows.</p> : null}
        <ActionGroup align="start">
          <Button type="submit" variant="primary" busy={busy} busyLabel="Saving">
            Save the AI budget
          </Button>
        </ActionGroup>
      </div>
    </form>
  );
}
