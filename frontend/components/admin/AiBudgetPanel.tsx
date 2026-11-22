"use client";

import { useEffect, useState } from "react";

import { AiBudgetForm } from "@/components/admin/AiBudgetForm";
import { Skeleton } from "@/components/ui/Skeleton";
import { fetchAiBudget, saveAiBudget, type AiBudget, type AiBudgetView } from "@/lib/aiBudgetContract";
import { apiErrorMessage } from "@/lib/api";

const LOAD_FAILED = "Couldn't read the AI budget. Reload the page to try again.";
const SAVE_FAILED = "Couldn't save the AI budget. Check the two-step code and try again.";

export function AiBudgetPanel() {
  const [view, setView] = useState<AiBudgetView | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAiBudget()
      .then((found) => {
        if (!cancelled) setView(found);
      })
      .catch((cause) => {
        if (!cancelled) setError(apiErrorMessage(cause, LOAD_FAILED));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function save(budget: AiBudget, twoFactorCode: string) {
    setBusy(true);
    setSaved(false);
    setError(null);
    try {
      setView(await saveAiBudget(budget, twoFactorCode));
      setVersion((current) => current + 1);
      setSaved(true);
    } catch (cause) {
      setError(apiErrorMessage(cause, SAVE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="AI budget" className="grid gap-5" data-testid="ai-budget">
      {view ? <AiBudgetForm key={version} view={view} busy={busy} onSave={(budget, code) => void save(budget, code)} /> : null}
      {!view && !error ? <Skeleton shape="lede" label="Reading the AI budget" /> : null}
      <p role="status" className="font-ui text-label text-ink-2">
        {saved && !busy ? "Saved. Every process reads the new caps within a minute." : ""}
      </p>
      {error ? (
        <p role="alert" className="font-ui text-ui text-error">
          {error}
        </p>
      ) : null}
    </section>
  );
}
