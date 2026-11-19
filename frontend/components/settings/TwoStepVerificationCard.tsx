"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { RecordNotice } from "@/components/records/RecordNotice";
import { RecordSection } from "@/components/records/RecordSection";
import { NewCodesStep, RecoveryCodes, SetupStep, TurnOffStep, type CodeState } from "@/components/settings/TwoStepSteps";
import type { TwoStepCodeEntryHandle, TwoStepCodeKind } from "@/components/TwoStepCodeEntry";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import type { OtpCodeInputHandle } from "@/components/ui/OtpCodeInput";
import { isCompleteCode } from "@/components/ui/otpCode";
import { Toggle } from "@/components/ui/Toggle";
import { saveBlob } from "@/lib/download";
import { isUnreachable } from "@/lib/failureTriage";
import { exportFilename } from "@/lib/naming";
import {
  beginTwoFactorSetup,
  cancelTwoFactorSetup,
  disableTwoFactor,
  enableTwoFactor,
  fetchTwoFactorStatus,
  makeNewRecoveryCodes,
  recoveryCodesFileText,
  type TwoFactorSetup,
  type TwoFactorStatus
} from "@/lib/twoFactor";
import { leavingSetupDiscards, twoStepSwitchView, type TwoStepPhase } from "@/lib/twoStepSwitch";

type Step =
  | { kind: "idle" }
  | { kind: "setup"; setup: TwoFactorSetup }
  | { kind: "codes"; codes: string[] }
  | { kind: "disable" }
  | { kind: "regenerate" };

const AWAY_NOTICE = "Setup was stopped because you were away. Two-step verification is still off. Switch it on to get a new code to scan.";

function messageOf(err: unknown, fallback: string): string {
  if (isUnreachable(err)) return "Couldn't connect. Check your connection and try again.";
  return err instanceof Error ? err.message : fallback;
}

function useTwoFactorStatus(settingUpRef: React.RefObject<boolean>) {
  const [status, setStatus] = useState<TwoFactorStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      let answer = await fetchTwoFactorStatus();
      if (!answer.enabled && answer.pending && !settingUpRef.current) {
        await cancelTwoFactorSetup().catch(() => undefined);
        answer = { ...answer, pending: false };
      }
      setStatus(answer);
      setLoadError(null);
    } catch (err) {
      setLoadError(messageOf(err, "Two-step verification could not be loaded."));
    }
  }, [settingUpRef]);

  useEffect(() => {
    void load();
  }, [load]);

  return { status, loadError, load };
}

function useSetupLeftBehind(settingUpRef: React.RefObject<boolean>, onAway: () => void) {
  const away = useRef(onAway);
  useEffect(() => {
    away.current = onAway;
  });

  useEffect(() => {
    let hiddenAt: number | null = null;
    function onPageHide() {
      if (settingUpRef.current) void cancelTwoFactorSetup({ keepalive: true }).catch(() => undefined);
    }
    function onVisibility() {
      if (document.visibilityState === "hidden") {
        hiddenAt = Date.now();
        return;
      }
      const gone = hiddenAt === null ? 0 : Date.now() - hiddenAt;
      hiddenAt = null;
      if (settingUpRef.current && leavingSetupDiscards("hidden", gone)) {
        settingUpRef.current = false;
        away.current();
      }
    }
    window.addEventListener("pagehide", onPageHide);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibility);
      if (settingUpRef.current) void cancelTwoFactorSetup({ keepalive: true }).catch(() => undefined);
    };
  }, [settingUpRef]);
}

export function TwoStepVerificationCard() {
  const { user, refreshMe } = useAuth();
  const settingUpRef = useRef(false);
  const { status, loadError, load } = useTwoFactorStatus(settingUpRef);
  const [step, setStep] = useState<Step>({ kind: "idle" });
  const [code, setCode] = useState("");
  const [codeKind, setCodeKind] = useState<TwoStepCodeKind>("totp");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const setupBox = useRef<OtpCodeInputHandle | null>(null);
  const entryBox = useRef<TwoStepCodeEntryHandle | null>(null);

  useEffect(() => {
    settingUpRef.current = step.kind === "setup";
  }, [step]);

  function go(next: Step) {
    setStep(next);
    setCode("");
    setCodeKind("totp");
    setError(null);
  }

  useSetupLeftBehind(settingUpRef, () => {
    go({ kind: "idle" });
    setNotice(AWAY_NOTICE);
    void cancelTwoFactorSetup()
      .catch(() => undefined)
      .then(() => load());
  });

  if (!user) return null;

  async function copy(text: string, said: string) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(said);
    } catch {
      setNotice("Copying is blocked in this browser. Select the text and copy it yourself.");
    }
  }

  function download(codes: string[]) {
    const blob = new Blob([recoveryCodesFileText(codes, user?.email ?? "")], { type: "text/plain" });
    saveBlob(blob, exportFilename("Account", "Recovery-Codes", "txt"));
  }

  async function startSetup() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      go({ kind: "setup", setup: await beginTwoFactorSetup() });
      requestAnimationFrame(() => setupBox.current?.focus());
    } catch (err) {
      setError(messageOf(err, "Setup could not be started."));
    } finally {
      setBusy(false);
    }
  }

  async function leaveSetup() {
    settingUpRef.current = false;
    go({ kind: "idle" });
    setNotice("Setup cancelled. Two-step verification is still off.");
    await cancelTwoFactorSetup().catch(() => undefined);
    await load();
  }

  async function check(typed: string) {
    if (step.kind === "setup") {
      const codes = await enableTwoFactor(typed);
      settingUpRef.current = false;
      go({ kind: "codes", codes });
      void refreshMe();
    } else if (step.kind === "regenerate") {
      go({ kind: "codes", codes: await makeNewRecoveryCodes(typed) });
    } else if (step.kind === "disable") {
      await disableTwoFactor(typed);
      go({ kind: "idle" });
      setNotice("Two-step verification is off.");
      void refreshMe();
    }
  }

  async function submit(entered: string) {
    const typed = entered.trim();
    if (!typed || busy) return;
    if ((step.kind !== "disable" || codeKind === "totp") && !isCompleteCode(typed)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await check(typed);
      await load();
    } catch (err) {
      setCode("");
      setError(messageOf(err, "That code didn't work. Try again."));
      setErrorKey((key) => key + 1);
      requestAnimationFrame(() => (step.kind === "disable" ? entryBox.current?.focus() : setupBox.current?.focus()));
    } finally {
      setBusy(false);
    }
  }

  const phase: TwoStepPhase = step.kind;
  const view = twoStepSwitchView(status, phase);
  const codeState: CodeState = { value: code, onChange: setCode, onSubmit: (entered) => void submit(entered), error: Boolean(error), errorKey, busy };

  function onSwitch(next: boolean) {
    if (step.kind === "setup") {
      void leaveSetup();
    } else if (next) {
      void startSetup();
    } else if (status?.enabled) {
      go({ kind: "disable" });
      requestAnimationFrame(() => entryBox.current?.focus());
    }
  }

  return (
    <RecordSection title="Two-step verification" testId="two-step">
      <Toggle
        label="Two-step verification"
        description="After you sign in, also enter a 6-digit code from an authenticator app on your phone, such as Google Authenticator or Microsoft Authenticator."
        checked={view.checked}
        busy={busy || status === null}
        busyLabel={busy ? "Working" : "Reading the setting"}
        status={view.busy && view.busyLabel ? view.busyLabel : view.statusLine}
        disabled={status === null && loadError !== null}
        onChange={onSwitch}
      />
      <div role="alert" className={error || loadError ? "rounded-card bg-error-wash px-4 py-3 font-ui text-ui font-normal text-ink-1" : "sr-only"}>
        {error ?? loadError ?? ""}
      </div>
      <p role="status" className={notice ? "rounded-card bg-sunk px-4 py-3 font-ui text-ui font-normal text-ink-1" : "sr-only"}>
        {notice ?? ""}
      </p>
      {status === null && loadError ? (
        <ActionGroup align="start">
          <Button variant="quiet" onClick={() => void load()}>
            Try again
          </Button>
        </ActionGroup>
      ) : null}
      {status?.enabled && step.kind === "idle" ? (
        <div className="grid gap-3">
          {status.recovery_codes_remaining <= 2 ? <RecordNotice tone="warning">You are running out of recovery codes. Make new ones so you can still get in without your phone.</RecordNotice> : null}
          <ActionGroup align="start">
            <Button variant="quiet" onClick={() => go({ kind: "regenerate" })}>
              Make new recovery codes
            </Button>
          </ActionGroup>
        </div>
      ) : null}
      {step.kind === "setup" ? <SetupStep setup={step.setup} code={codeState} inputRef={setupBox} onCopy={(text) => void copy(text, "Key copied.")} onCancel={() => void leaveSetup()} /> : null}
      {step.kind === "codes" ? (
        <RecoveryCodes
          codes={step.codes}
          onCopy={() => void copy(step.codes.join("\n"), "Recovery codes copied.")}
          onDownload={() => download(step.codes)}
          onDone={() => {
            go({ kind: "idle" });
            setNotice(null);
          }}
        />
      ) : null}
      {step.kind === "disable" ? <TurnOffStep code={codeState} kind={codeKind} onKind={setCodeKind} entryRef={entryBox} onCancel={() => go({ kind: "idle" })} /> : null}
      {step.kind === "regenerate" ? <NewCodesStep code={codeState} inputRef={setupBox} onCancel={() => go({ kind: "idle" })} /> : null}
    </RecordSection>
  );
}
