"use client";

import { useState, type FormEvent, type Ref } from "react";
import { MailPlus } from "lucide-react";

import { Field, TextArea, TextInput } from "@/components/FormControls";
import { RecordSection } from "@/components/records/RecordSection";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/Dropdown";
import { PasswordRevealButton } from "@/components/ui/PasswordReveal";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { Toggle } from "@/components/ui/Toggle";
import type { AccessRosterEntry } from "@/lib/accessRoster";
import { roleLabel } from "@/lib/permissions";
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, passwordRuleLine } from "@/lib/signIn";
import type { UserRole } from "@/lib/types";

export const NEW_ACCOUNTS_ONLY = "New accounts only. Change an existing account in Manage users.";

const SIGN_IN_OPTIONS = [
  { value: "PROVIDER", label: "Google, Microsoft or Yahoo" },
  { value: "PASSWORD", label: "A password" }
];

function SignInMethodField() {
  const [method, setMethod] = useState("PROVIDER");
  const [showPassword, setShowPassword] = useState(false);
  return (
    <fieldset className="grid gap-3">
      <legend className="field-label mb-1.5">How will they sign in?</legend>
      <SegmentedChoice label="How will they sign in?" value={method} options={SIGN_IN_OPTIONS} onChange={setMethod} />
      <input type="hidden" name="signInWith" value={method} />
      {method === "PASSWORD" ? (
        <div className="grid max-w-md gap-3 rounded-card bg-sunk px-4 py-4">
          <div className="grid gap-1.5">
            <label htmlFor="access-password" className="field-label">
              Password
            </label>
            <div className="relative">
              <input id="access-password" name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={MIN_PASSWORD_LENGTH} maxLength={MAX_PASSWORD_LENGTH} className="kv-input pe-12" />
              <PasswordRevealButton revealed={showPassword} onToggle={() => setShowPassword((value) => !value)} size={20} />
            </div>
          </div>
          <Toggle name="mustChangePassword" defaultChecked label="Ask them to choose a new one at first sign-in" />
          <p className="font-ui text-label text-ink-3">{passwordRuleLine("Full name required.")}</p>
        </div>
      ) : null}
    </fieldset>
  );
}

function AdmitTierField({ grantable, initial }: { grantable: UserRole[]; initial: UserRole | "" }) {
  const [role, setRole] = useState<UserRole | "">(initial);
  return (
    <>
      <Dropdown
        value={role}
        onChange={(next) => setRole(next as UserRole | "")}
        options={[{ value: "", label: "Default role (the lowest)" }, ...grantable.map((option) => ({ value: option, label: roleLabel(option) }))]}
      />
      <input type="hidden" name="role" value={role} />
    </>
  );
}

export type EntryFormProps = {
  editing: AccessRosterEntry | null;
  grantable: UserRole[];
  saving: boolean;
  formRef: Ref<HTMLFormElement>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
};

export function AccessEntryForm({ editing, grantable, saving, formRef, onSubmit, onCancel }: EntryFormProps) {
  return (
    <RecordSection
      title={editing ? `Correct the entry for ${editing.email}` : "Let somebody in by address"}
      description={editing ? "For your records. Use Approve, Refuse, Suspend or Restore to change access." : "Choose how they sign in. Adding them here approves them."}
      testId="access-entry-form"
    >
      <form ref={formRef} onSubmit={onSubmit} key={editing?.id ?? "new"} className="grid gap-5">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Field label="Email address" required>
            <TextInput name="email" type="email" required defaultValue={editing?.email ?? ""} placeholder="colleague@institution.ac.in" readOnly={editing !== null} autoComplete="off" />
          </Field>
          <Field label="Full name">
            <TextInput name="fullName" maxLength={180} defaultValue={editing?.fullName ?? ""} />
          </Field>
          <Field label="Joins as" hint={NEW_ACCOUNTS_ONLY}>
            <AdmitTierField grantable={grantable} initial={editing?.admitRole ?? ""} />
          </Field>
        </div>
        {editing ? null : <SignInMethodField />}
        <Field label="Note">
          <TextArea name="notes" maxLength={4000} rows={2} defaultValue={editing?.notes ?? ""} placeholder="Who they are and why they were admitted." />
        </Field>
        <ActionGroup align="start">
          {editing ? (
            <Button type="button" variant="quiet" onClick={onCancel}>
              Cancel
            </Button>
          ) : null}
          <Button type="submit" variant="primary" busy={saving} busyLabel="Saving">
            <MailPlus className="size-4" aria-hidden />
            {editing ? "Update entry" : "Add to the list"}
          </Button>
        </ActionGroup>
      </form>
    </RecordSection>
  );
}
