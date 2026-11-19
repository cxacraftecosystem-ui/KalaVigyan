"use client";

import { KeyRound, Plus, RotateCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { RecordNotice } from "@/components/records/RecordNotice";
import { RecordSection } from "@/components/records/RecordSection";
import { RECORD_CELL, RECORD_HEAD_ROW, RECORD_NOTE, RECORD_ROW, RECORD_TABLE } from "@/components/records/recordTable";
import { ResizableTh } from "@/components/ResizableTh";
import { RowActions, RowButton } from "@/components/RowActions";
import { ClearKeyForm, ReplaceKeyForm } from "@/components/settings/ApiKeyForms";
import {
  SOURCE_META,
  STATUS_META,
  clearSecret,
  fetchSecrets,
  hasStoredOverride,
  maskedValue,
  saveSecret,
  testSecret,
  type ManagedSecret
} from "@/components/settings/managedSecrets";
import { StatusBadge } from "@/components/StatusBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { formatDateTime } from "@/lib/format";

type Busy = { key: string; action: "test" | "save" | "clear" } | null;
type Open = { key: string; form: "replace" | "clear" } | null;
type RowHandlers = { onTest: () => void; onReplace: () => void; onClear: () => void };

const COLUMNS = 6;

function KeyRow({ secret, testing, on }: { secret: ManagedSecret; testing: boolean; on: RowHandlers }) {
  const source = SOURCE_META[secret.source] ?? SOURCE_META.unset;
  const status = STATUS_META[secret.lastStatus] ?? STATUS_META.UNKNOWN;
  return (
    <tr className={RECORD_ROW}>
      <th scope="row" className={`${RECORD_CELL} text-start font-normal`}>
        <span className="block font-ui text-h4 text-ink-1">{secret.label}</span>
        <span className="block font-code text-label text-ink-3">{secret.key}</span>
        <span className="mt-1 block max-w-sm font-ui text-label text-ink-2">{secret.description}</span>
      </th>
      <td className={`${RECORD_CELL} font-code text-label text-ink-2`}>{maskedValue(secret)}</td>
      <td className={RECORD_CELL}>
        <StatusBadge tone={source.tone} note={secret.overrideUnreadable ? "Unreadable, so not in use. Enter it again or clear it." : source.help} label={source.label} />
      </td>
      <td className={RECORD_CELL}>
        <StatusBadge tone={status.tone} note={secret.lastCheckedAt ? `Checked ${formatDateTime(secret.lastCheckedAt)}` : "Never tested"} label={status.label} />
        {secret.lastError ? <span className={`${RECORD_NOTE} max-w-56 text-error`}>{secret.lastError}</span> : null}
      </td>
      <td className={RECORD_CELL}>
        {secret.updatedAt ? formatDateTime(secret.updatedAt) : <span className="text-ink-3">Never edited here</span>}
        {secret.updatedAt && secret.updatedBy ? <span className={RECORD_NOTE}>by {secret.updatedBy}</span> : null}
      </td>
      <td className={RECORD_CELL}>
        <RowActions>
          <RowButton busy={testing} busyLabel="Testing" onClick={on.onTest}>
            <RotateCw className="size-3.5" aria-hidden />
            Test
          </RowButton>
          <RowButton onClick={on.onReplace}>
            {secret.source === "unset" ? <Plus className="size-3.5" aria-hidden /> : <KeyRound className="size-3.5" aria-hidden />}
            {secret.source === "unset" ? "Add key" : "Update"}
          </RowButton>
          {hasStoredOverride(secret) ? (
            <RowButton danger onClick={on.onClear}>
              <Trash2 className="size-3.5" aria-hidden />
              Clear override
            </RowButton>
          ) : null}
        </RowActions>
      </td>
    </tr>
  );
}

function useManagedSecrets() {
  const [secrets, setSecrets] = useState<ManagedSecret[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSecrets()
      .then(setSecrets)
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load the managed keys."));
  }, []);

  const replace = useCallback((row: ManagedSecret) => {
    setSecrets((current) => (current ? current.map((item) => (item.key === row.key ? row : item)) : [row]));
  }, []);

  return { secrets, error, setError, replace };
}

export function ApiKeysPanel() {
  const { toast } = useToast();
  const { secrets, error, setError, replace } = useManagedSecrets();
  const [busy, setBusy] = useState<Busy>(null);
  const [open, setOpen] = useState<Open>(null);
  const [stepCode, setStepCode] = useState("");

  async function act(secret: ManagedSecret, action: NonNullable<Busy>["action"], call: () => Promise<ManagedSecret>, done: (row: ManagedSecret) => void) {
    setBusy({ key: secret.key, action });
    setError(null);
    try {
      const row = await call();
      replace(row);
      done(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work. Try again.");
    } finally {
      setBusy(null);
    }
  }

  function close() {
    setOpen(null);
    setStepCode("");
  }

  function openForm(secret: ManagedSecret, form: NonNullable<Open>["form"]) {
    setStepCode("");
    setOpen({ key: secret.key, form });
  }

  const test = (secret: ManagedSecret) =>
    act(secret, "test", () => testSecret(secret.key), (row) =>
      toast({ title: row.lastStatus === "OK" ? `${row.label} is working` : `${row.label} failed`, description: row.lastStatus === "OK" ? "The provider accepted the key." : (row.lastError ?? "The provider refused the key."), tone: row.lastStatus === "OK" ? "success" : "error" })
    );
  const save = (secret: ManagedSecret, value: string) =>
    act(secret, "save", () => saveSecret(secret.key, value, stepCode), (row) => {
      close();
      toast({ title: `${row.label} saved`, description: "It is in use for everyone now.", tone: "success" });
    });
  const clear = (secret: ManagedSecret) =>
    act(secret, "clear", () => clearSecret(secret.key, stepCode), (row) => {
      close();
      toast({ title: `${row.label} override cleared`, description: row.source === "environment" ? "The default value applies again." : "This key has no value now.", tone: "info" });
    });

  const configured = secrets?.filter((secret) => secret.configured).length ?? 0;
  return (
    <RecordSection
      title="Managed API keys"
      description="Saved keys apply to everyone at once. Saving or clearing one asks for your two-step code. Test a key before relying on it."
      aside={secrets ? <span className="tabular-nums lining-nums">{`${configured} of ${secrets.length} set`}</span> : null}
      testId="api-keys"
    >
      {error ? <RecordNotice tone="error">{error}</RecordNotice> : null}
      {!secrets && !error ? <Skeleton shape="lede" label="Reading the managed keys" /> : null}
      {secrets ? (
        <div className="overflow-x-auto">
          <table className={`${RECORD_TABLE} min-w-5xl`}>
            <caption className="sr-only">Managed API keys</caption>
            <thead>
              <tr className={RECORD_HEAD_ROW}>
                <ResizableTh>Key</ResizableTh>
                <ResizableTh>Value</ResizableTh>
                <ResizableTh>Source</ResizableTh>
                <ResizableTh>Status</ResizableTh>
                <ResizableTh>Last updated</ResizableTh>
                <ResizableTh className="text-end">
                  <span className="sr-only">Actions</span>
                </ResizableTh>
              </tr>
            </thead>
            <tbody>
              {secrets.map((secret) => (
                <KeyRows
                  key={secret.key}
                  secret={secret}
                  busy={busy?.key === secret.key ? busy.action : null}
                  open={open?.key === secret.key ? open.form : null}
                  on={{ onTest: () => void test(secret), onReplace: () => openForm(secret, "replace"), onClear: () => openForm(secret, "clear") }}
                  form={{ stepCode, onStepCode: setStepCode, onCancel: close, onSave: (value) => void save(secret, value), onClear: () => void clear(secret) }}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </RecordSection>
  );
}

type FormHandlers = { stepCode: string; onStepCode: (code: string) => void; onCancel: () => void; onSave: (value: string) => void; onClear: () => void };

type KeyRowsProps = { secret: ManagedSecret; busy: NonNullable<Busy>["action"] | null; open: NonNullable<Open>["form"] | null; on: RowHandlers; form: FormHandlers };

function KeyRows({ secret, busy, open, on, form }: KeyRowsProps) {
  return (
    <>
      <KeyRow secret={secret} testing={busy === "test"} on={on} />
      {open ? (
        <tr className={`${RECORD_ROW} bg-sunk`}>
          <td colSpan={COLUMNS} className="px-3 py-5">
            {open === "replace" ? (
              <ReplaceKeyForm secret={secret} busy={busy === "save"} stepCode={form.stepCode} onStepCode={form.onStepCode} onCancel={form.onCancel} onSave={form.onSave} />
            ) : (
              <ClearKeyForm secret={secret} busy={busy === "clear"} stepCode={form.stepCode} onStepCode={form.onStepCode} onCancel={form.onCancel} onClear={form.onClear} />
            )}
          </td>
        </tr>
      ) : null}
    </>
  );
}
