"use client";

import { Copy, Download } from "lucide-react";
import type { FormEvent, Ref } from "react";

import { TwoStepCodeEntry, type TwoStepCodeEntryHandle, type TwoStepCodeKind } from "@/components/TwoStepCodeEntry";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { OtpCodeInput, type OtpCodeInputHandle } from "@/components/ui/OtpCodeInput";
import { isCompleteCode } from "@/components/ui/otpCode";
import type { TwoFactorSetup } from "@/lib/twoFactor";

export type CodeState = { value: string; onChange: (next: string) => void; onSubmit: (entered: string) => void; error: boolean; errorKey: number; busy: boolean };

function submitted(code: CodeState) {
  return (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    code.onSubmit(code.value);
  };
}

export function SetupStep({ setup, code, inputRef, onCopy, onCancel }: { setup: TwoFactorSetup; code: CodeState; inputRef: Ref<OtpCodeInputHandle>; onCopy: (text: string) => void; onCancel: () => void }) {
  return (
    <form onSubmit={submitted(code)} className="grid gap-5">
      <ol className="grid gap-5 font-ui text-ui font-normal text-ink-2">
        <li className="grid gap-3">
          <span>
            <span className="font-semibold text-ink-1">1.</span> Scan this code with your authenticator app.
          </span>
          {/* eslint-disable-next-line @next/next/no-img-element -- server-drawn SVG, inline data, nothing to optimise */}
          <img
            src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}`}
            alt="QR code to add this account to your authenticator app"
            width={184}
            height={184}
            className="h-46 w-46 rounded-plate border border-rule"
          />
        </li>
        <li className="grid gap-2">
          <span>
            <span className="font-semibold text-ink-1">Can&rsquo;t scan it?</span> Type this key into the app instead.
          </span>
          <div className="flex flex-wrap items-center gap-3">
            <code className="break-all rounded-control bg-sunk px-3 py-2 font-code text-ui tracking-wider text-ink-1">{setup.secret.replace(/(.{4})/g, "$1 ").trim()}</code>
            <Button variant="quiet" size="sm" onClick={() => onCopy(setup.secret)}>
              <Copy className="size-4" aria-hidden />
              Copy key
            </Button>
          </div>
        </li>
        <li>
          <span className="font-semibold text-ink-1">2.</span> Enter the 6-digit code the app shows. Two-step verification switches on only when this code is checked.
        </li>
      </ol>
      <OtpCodeInput
        ref={inputRef}
        id="two-step-setup-code"
        label="6-digit code"
        hint="Codes change every 30 seconds. Type the one on screen now."
        value={code.value}
        onChange={code.onChange}
        onComplete={code.onSubmit}
        error={code.error}
        errorKey={code.errorKey}
        disabled={code.busy}
      />
      <ActionGroup align="start">
        <Button type="button" variant="quiet" disabled={code.busy} onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" busy={code.busy} busyLabel="Checking" disabled={!isCompleteCode(code.value)}>
          Turn on
        </Button>
      </ActionGroup>
    </form>
  );
}

export function RecoveryCodes({ codes, onCopy, onDownload, onDone }: { codes: string[]; onCopy: () => void; onDownload: () => void; onDone: () => void }) {
  return (
    <div className="grid gap-4">
      <div className="grid gap-1.5">
        <h3 className="font-ui text-h4 text-ink-1">Save these codes</h3>
        <p className="max-w-measure font-ui text-ui font-normal text-ink-2">
          If you lose your phone, each code gets you in once instead of the 6-digit code. Keep them somewhere safe. They will not be shown again.
        </p>
      </div>
      <ul className="grid max-w-md grid-cols-2 gap-x-6 gap-y-2 rounded-card bg-sunk px-4 py-3 font-code text-ui text-ink-1 tabular-nums lining-nums">
        {codes.map((recovery) => (
          <li key={recovery}>{recovery}</li>
        ))}
      </ul>
      <ActionGroup align="start">
        <Button variant="quiet" onClick={onCopy}>
          <Copy className="size-4" aria-hidden />
          Copy
        </Button>
        <Button variant="quiet" onClick={onDownload}>
          <Download className="size-4" aria-hidden />
          Download
        </Button>
        <Button variant="primary" onClick={onDone}>
          I&rsquo;ve saved them
        </Button>
      </ActionGroup>
    </div>
  );
}

export function TurnOffStep({ code, kind, onKind, entryRef, onCancel }: { code: CodeState; kind: TwoStepCodeKind; onKind: (next: TwoStepCodeKind) => void; entryRef: Ref<TwoStepCodeEntryHandle>; onCancel: () => void }) {
  return (
    <form onSubmit={submitted(code)} className="grid gap-4">
      <TwoStepCodeEntry
        ref={entryRef}
        idPrefix="two-step-disable"
        kind={kind}
        onKindChange={onKind}
        value={code.value}
        onChange={code.onChange}
        onComplete={code.onSubmit}
        allowRecovery
        totpHint="Enter the code your authenticator app shows now to turn two-step verification off."
        error={code.error}
        errorKey={code.errorKey}
        disabled={code.busy}
      />
      <ActionGroup align="start">
        <Button type="button" variant="quiet" disabled={code.busy} onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="destroy" data-danger busy={code.busy} busyLabel="Checking" disabled={kind === "totp" ? !isCompleteCode(code.value) : !code.value.trim()}>
          Turn off
        </Button>
      </ActionGroup>
    </form>
  );
}

export function NewCodesStep({ code, inputRef, onCancel }: { code: CodeState; inputRef: Ref<OtpCodeInputHandle>; onCancel: () => void }) {
  return (
    <form onSubmit={submitted(code)} className="grid gap-4">
      <OtpCodeInput
        ref={inputRef}
        id="two-step-regenerate-code"
        label="6-digit code from your authenticator app"
        hint="Your old recovery codes will stop working."
        value={code.value}
        onChange={code.onChange}
        onComplete={code.onSubmit}
        error={code.error}
        errorKey={code.errorKey}
        disabled={code.busy}
        autoFocus
      />
      <ActionGroup align="start">
        <Button type="button" variant="quiet" disabled={code.busy} onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" busy={code.busy} busyLabel="Checking" disabled={!isCompleteCode(code.value)}>
          Make new codes
        </Button>
      </ActionGroup>
    </form>
  );
}
