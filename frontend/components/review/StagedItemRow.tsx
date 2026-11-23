"use client";

import { Field, Select, TextArea } from "@/components/FormControls";
import type { StatusTone } from "@/components/records/statusTone";
import { FilingPicker } from "@/components/review/FilingPicker";
import { ReviewTerm } from "@/components/review/ReviewTerm";
import { StagedSourceFields } from "@/components/review/StagedSourceFields";
import { StatusBadge } from "@/components/StatusBadge";
import { STAGED_REASON_MAX, STAGED_REASON_MIN, type ItemState, type StagedAction, type StagedItemView } from "@/lib/stagedReviewContract";
import {
  decisionShown,
  filingLine,
  ITEM_STATE_LABELS,
  outcomeLine,
  refilesUnder,
  STAGED_ACTION_LABELS,
  STAGED_KIND_LABELS,
  stagedActions,
  type DraftProblems,
  type StagedDraft
} from "@/lib/stagedReviewView";

const REASON_HINT = `From ${STAGED_REASON_MIN} to ${STAGED_REASON_MAX} characters, kept with the decision.`;
const STATE_TONES: Record<ItemState, StatusTone> = { STAGED: "waiting", APPLIED: "success", REFUSED: "error", SKIPPED: "neutral" };

type EditorProps = { item: StagedItemView; draft: StagedDraft; problems: DraftProblems | null; onChange: (next: StagedDraft) => void };

function ActionField({ draft, onChange }: { draft: StagedDraft; onChange: (next: StagedDraft) => void }) {
  const actions = stagedActions(draft.kind);
  if (actions.length === 1) {
    return (
      <dl className="grid content-start font-ui text-label">
        <ReviewTerm term="Action" value={STAGED_ACTION_LABELS[actions[0]]} />
      </dl>
    );
  }
  return (
    <Field label="Action">
      <Select value={draft.action} onChange={(event) => onChange({ ...draft, action: event.target.value as StagedAction })}>
        {actions.map((action) => (
          <option key={action} value={action}>
            {STAGED_ACTION_LABELS[action]}
          </option>
        ))}
      </Select>
    </Field>
  );
}

export function StagedItemEditor({ item, draft, problems, onChange }: EditorProps) {
  return (
    <li className="grid gap-4 border-t border-rule pt-4" data-testid="staged-item">
      <label className="flex min-h-target items-start gap-3">
        <input type="checkbox" className="mt-1.5 h-4 w-4 shrink-0" checked={draft.selected} onChange={(event) => onChange({ ...draft, selected: event.target.checked })} />
        <span className="grid min-w-0 gap-1">
          <span className="kicker">{STAGED_KIND_LABELS[draft.kind]}</span>
          <span className="font-reading text-body-sm text-ink-1 [overflow-wrap:anywhere]">{item.label}</span>
        </span>
      </label>
      <div className="grid gap-4 ps-7">
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <ActionField draft={draft} onChange={onChange} />
          <Field label="Reason" hint={REASON_HINT} error={problems?.reason ?? undefined}>
            <TextArea value={draft.reason} rows={2} maxLength={STAGED_REASON_MAX} onChange={(event) => onChange({ ...draft, reason: event.target.value })} />
          </Field>
        </div>
        {refilesUnder(draft.kind, draft.action) ? <FilingPicker value={draft.fileUnder} onChange={(fileUnder) => onChange({ ...draft, fileUnder })} current={null} /> : null}
        {draft.source ? (
          <StagedSourceFields draft={draft.source} problem={problems?.source ?? null} onChange={(source) => onChange({ ...draft, source })} />
        ) : null}
      </div>
    </li>
  );
}

export function StagedItemResult({ item }: { item: StagedItemView }) {
  const shown = decisionShown(item);
  const outcome = outcomeLine(item);
  const filing = filingLine(shown);
  return (
    <li className="grid gap-2 border-t border-rule pt-4" data-testid="staged-item" data-state={item.state}>
      <p className="kicker">{STAGED_KIND_LABELS[shown.kind]}</p>
      <p className="font-reading text-body-sm text-ink-1 [overflow-wrap:anywhere]">{item.label}</p>
      <StatusBadge tone={STATE_TONES[item.state]} label={ITEM_STATE_LABELS[item.state]} />
      {outcome ? <p className="max-w-measure font-ui text-ui text-ink-1">{outcome}</p> : null}
      <dl className="grid gap-x-6 gap-y-2 font-ui text-label sm:grid-cols-2">
        <ReviewTerm term="Action" value={STAGED_ACTION_LABELS[shown.action]} />
        <ReviewTerm term="Reason" value={shown.reason} />
        {filing ? <ReviewTerm term="File under" value={filing} /> : null}
      </dl>
    </li>
  );
}
