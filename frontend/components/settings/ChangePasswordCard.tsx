"use client";

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { RecordSection } from "@/components/records/RecordSection";
import { NewPasswordFields, type PasswordDraft } from "@/components/settings/NewPasswordFields";
import { TwoStepCodeEntry, type TwoStepCodeKind } from "@/components/TwoStepCodeEntry";
import { ConfirmItsYou } from "@/components/settings/ConfirmItsYou";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { isCompleteCode } from "@/components/ui/otpCode";
import { isUnreachable } from "@/lib/failureTriage";
import { CONFIRM_STATE_PREFIX, parseCallbackFragment } from "@/lib/oidcSignIn";
import {
  CONFIRMED_NOTE,
  FIRST_PASSWORD_NOTE,
  PASSWORD_CHANGE_SESSIONS,
  type ConfirmProvider,
  canSetFirstPassword,
  confirmPrompt,
  confirmProviderFor,
  confirmReturn,
  currentPasswordRefused,
  firstPasswordNeedsCode,
  newPasswordProblem,
  providerConfirmationRequired,
  twoFactorCodeRequired
} from "@/lib/passwordChange";
import {
  MAX_PASSWORD_LENGTH,
  type ProviderProof,
  changeOwnPassword,
  passwordRuleLine,
  setFirstPassword
} from "@/lib/signIn";

const CHANGED_HERE_ONLY = "Password changed. You are still signed in here; everywhere else, sign in with the new one.";
const CHANGED = "Password changed. Use the new one the next time you sign in.";
const PASSWORD_ADDED = "Password set. You can now sign in with your email address and this password too.";
const NOTE_SHOWN = "rounded-card px-4 py-3 font-ui text-ui font-normal text-ink-1";

export function ChangePasswordCard() {
  const { user, refreshMe } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [codeKind, setCodeKind] = useState<TwoStepCodeKind>("totp");
  const [codeErrorKey, setCodeErrorKey] = useState(0);
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changed, setChanged] = useState<string | null>(null);
  const [currentRefusals, setCurrentRefusals] = useState(0);
  const [proof, setProof] = useState<ProviderProof | null>(null);
  const [askedProvider, setAskedProvider] = useState<ConfirmProvider | null>(null);
  const currentBox = useRef<HTMLInputElement | null>(null);
  const section = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (currentRefusals > 0) currentBox.current?.focus();
  }, [currentRefusals]);

  useEffect(() => {
    const callback = parseCallbackFragment(window.location.hash);
    if (!callback || !callback.state.startsWith(CONFIRM_STATE_PREFIX)) return;
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    const outcome = confirmReturn(callback);
    if ("proof" in outcome) {
      setProof(outcome.proof);
      setChanged(CONFIRMED_NOTE);
    } else {
      setError(outcome.error);
    }
    section.current?.scrollIntoView({ block: "start" });
  }, []);

  if (!user) return null;
  const settingFirst = canSetFirstPassword(user);
  const askCode = settingFirst && firstPasswordNeedsCode(user);
  const confirmWith = askedProvider ?? confirmProviderFor(user);
  const draft: PasswordDraft = { next, confirm, show, onNext: setNext, onConfirm: setConfirm, onShow: setShow };

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setChanged(null);
    if (settingFirst && !proof) {
      setError(confirmPrompt(confirmWith));
      return;
    }
    const problem = settingFirst
      ? next !== confirm
        ? newPasswordProblem({ current: "", next, confirm })
        : null
      : newPasswordProblem({ current, next, confirm });
    if (problem) {
      setError(problem);
      return;
    }
    if (askCode && (codeKind === "totp" ? !isCompleteCode(code) : !code.trim())) {
      setError("Enter the code from your authenticator app to set a password.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const fresh =
        settingFirst && proof ? await setFirstPassword(next, proof, askCode ? code : undefined) : await changeOwnPassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setCode("");
      setShow(false);
      setProof(null);
      if (fresh) {
        void refreshMe();
        setChanged(settingFirst ? PASSWORD_ADDED : CHANGED_HERE_ONLY);
      } else if (settingFirst) {
        void refreshMe();
        setChanged(PASSWORD_ADDED);
      } else {
        setChanged(CHANGED);
      }
    } catch (err) {
      const confirmAgain = settingFirst ? providerConfirmationRequired(err) : null;
      if (confirmAgain) {
        setProof(null);
        setAskedProvider(confirmAgain);
      } else if (settingFirst && twoFactorCodeRequired(err)) {
        setCode("");
        setCodeErrorKey((key) => key + 1);
        if (askCode) setProof(null);
        else void refreshMe();
      } else if (!settingFirst && currentPasswordRefused(err)) {
        setCurrent("");
        setCurrentRefusals((count) => count + 1);
      }
      setError(
        isUnreachable(err)
          ? "Couldn't connect. Check your connection and try again."
          : err instanceof Error
            ? err.message
            : "Could not change the password."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <RecordSection
      ref={section}
      className="scroll-mt-28"
      title={settingFirst ? "Set a password" : "Change password"}
      description={
        settingFirst
          ? "You sign in with Google, Microsoft or Yahoo. Add a password to sign in with your email address as well."
          : "The password you sign in with. You need the current one to choose another."
      }
      testId="change-password"
    >
      <form onSubmit={submit} className="grid max-w-md gap-4">
        <input type="text" name="username" autoComplete="username" value={user.email} readOnly hidden />

        <div role="alert" aria-live="assertive" className={error ? `${NOTE_SHOWN} bg-error-wash` : "sr-only"}>
          {error ?? ""}
        </div>
        {settingFirst && !proof ? (
          <ConfirmItsYou
            provider={confirmWith}
            onProof={(value) => {
              setProof(value);
              setError(null);
              setChanged(CONFIRMED_NOTE);
            }}
            onError={setError}
          />
        ) : null}
        <p role="status" aria-live="polite" className={changed ? `${NOTE_SHOWN} bg-sunk` : "sr-only"}>
          {changed ?? ""}
        </p>

        {settingFirst ? null : (
          <div className="grid gap-1.5">
            <label htmlFor="settings-current-password" className="field-label">
              Current password
            </label>
            <input
              id="settings-current-password"
              ref={currentBox}
              type={show ? "text" : "password"}
              autoComplete="current-password"
              required
              maxLength={MAX_PASSWORD_LENGTH}
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              className="kv-input"
            />
          </div>
        )}

        {settingFirst && !proof ? null : (
          <>
            <NewPasswordFields draft={draft} />
            {askCode ? (
              <TwoStepCodeEntry
                idPrefix="settings-two-factor"
                kind={codeKind}
                onKindChange={setCodeKind}
                value={code}
                onChange={setCode}
                allowRecovery
                totpLabel="Code from your authenticator app"
                totpHint="Two-step verification is on for your account."
                error={codeErrorKey > 0 && !code}
                errorKey={codeErrorKey}
                disabled={saving}
              />
            ) : null}
            <p className="font-ui text-label text-ink-3">{passwordRuleLine(settingFirst ? FIRST_PASSWORD_NOTE : PASSWORD_CHANGE_SESSIONS)}</p>
            <ActionGroup align="start">
              <Button type="submit" variant="primary" busy={saving} busyLabel="Saving">
                {settingFirst ? "Set password" : "Change password"}
              </Button>
            </ActionGroup>
          </>
        )}
      </form>
    </RecordSection>
  );
}
