"use client";

import { useState } from "react";

import { RecordNotice } from "@/components/records/RecordNotice";
import type { ManagedSecret } from "@/components/settings/managedSecrets";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { OtpCodeInput } from "@/components/ui/OtpCodeInput";
import { isCompleteCode } from "@/components/ui/otpCode";
import { PasswordRevealButton } from "@/components/ui/PasswordReveal";

export type KeyFormProps = {
  secret: ManagedSecret;
  busy: boolean;
  stepCode: string;
  onStepCode: (code: string) => void;
  onCancel: () => void;
};

export function ReplaceKeyForm({ secret, busy, stepCode, onStepCode, onCancel, onSave }: KeyFormProps & { onSave: (value: string) => void }) {
  const [draft, setDraft] = useState("");
  const [revealed, setRevealed] = useState(false);
  const ready = draft.trim().length > 0 && isCompleteCode(stepCode);
  const inputId = `secret-${secret.key}`;

  return (
    <form
      className="grid max-w-xl gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) onSave(draft.trim());
      }}
    >
      <div className="grid gap-1.5">
        <label htmlFor={inputId} className="field-label">
          {secret.source === "unset" ? `New ${secret.label} key` : `Replace the ${secret.label} key`}
        </label>
        <div className="relative">
          <input
            id={inputId}
            autoComplete="off"
            autoFocus
            className="kv-input pe-12 font-code"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") onCancel();
            }}
            placeholder="Paste the key. Spaces at either end are trimmed."
            spellCheck={false}
            type={revealed ? "text" : "password"}
            value={draft}
          />
          <PasswordRevealButton revealed={revealed} onToggle={() => setRevealed((value) => !value)} size={16} noun="key" />
        </div>
      </div>
      <OtpCodeInput label="Your two-step code" value={stepCode} onChange={onStepCode} disabled={busy} />
      <ActionGroup align="start">
        <Button type="button" variant="quiet" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" busy={busy} busyLabel="Saving" disabled={!ready}>
          Save key
        </Button>
      </ActionGroup>
    </form>
  );
}

export function ClearKeyForm({ secret, busy, stepCode, onStepCode, onCancel, onClear }: KeyFormProps & { onClear: () => void }) {
  return (
    <div className="grid max-w-xl gap-4">
      <RecordNotice tone="warning">
        <span className="font-semibold">Clear the stored {secret.label} key?</span> {secret.overrideUnreadable ? "Nothing is using it." : "The default value applies again, if there is one."}
      </RecordNotice>
      <OtpCodeInput label="Your two-step code" value={stepCode} onChange={onStepCode} disabled={busy} />
      <ActionGroup align="start">
        <Button type="button" variant="quiet" onClick={onCancel}>
          Keep it
        </Button>
        <Button type="button" variant="destroy" data-danger busy={busy} busyLabel="Clearing" disabled={!isCompleteCode(stepCode)} onClick={onClear}>
          Clear override
        </Button>
      </ActionGroup>
    </div>
  );
}
