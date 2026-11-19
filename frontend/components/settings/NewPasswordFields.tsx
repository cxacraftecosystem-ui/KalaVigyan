"use client";

import { PasswordRevealButton } from "@/components/ui/PasswordReveal";
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from "@/lib/signIn";

export type PasswordDraft = {
  next: string;
  confirm: string;
  show: boolean;
  onNext: (value: string) => void;
  onConfirm: (value: string) => void;
  onShow: (value: boolean) => void;
};

export function NewPasswordFields({ draft }: { draft: PasswordDraft }) {
  const type = draft.show ? "text" : "password";
  return (
    <>
      <div className="grid gap-1.5">
        <label htmlFor="settings-new-password" className="field-label">
          New password
        </label>
        <div className="relative">
          <input
            id="settings-new-password"
            type={type}
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={MAX_PASSWORD_LENGTH}
            value={draft.next}
            onChange={(event) => draft.onNext(event.target.value)}
            className="kv-input pe-12"
          />
          <PasswordRevealButton revealed={draft.show} onToggle={() => draft.onShow(!draft.show)} size={20} noun="passwords" />
        </div>
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="settings-confirm-password" className="field-label">
          Repeat password
        </label>
        <input
          id="settings-confirm-password"
          type={type}
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          maxLength={MAX_PASSWORD_LENGTH}
          value={draft.confirm}
          onChange={(event) => draft.onConfirm(event.target.value)}
          className="kv-input"
        />
      </div>
    </>
  );
}
