"use client";

import { useEffect, useState } from "react";

import { RecordSection } from "@/components/records/RecordSection";
import { Toggle } from "@/components/ui/Toggle";
import { apiErrorMessage, apiFetch } from "@/lib/api";
import { PREFERENCES_PATH } from "@/lib/preferences";
import { digestChoice, type DigestChoice } from "@/lib/savedView";

const SAVE_FAILED = "Couldn't change the weekly email. Try again.";

export function AlertDigestCard() {
  const [choice, setChoice] = useState<DigestChoice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<unknown>(PREFERENCES_PATH)
      .then((raw) => {
        if (!cancelled) setChoice(digestChoice(raw));
      })
      .catch(() => {
        if (!cancelled) setChoice(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!choice?.offered) return null;

  async function change(next: boolean) {
    setBusy(true);
    setError(null);
    try {
      setChoice(digestChoice(await apiFetch<unknown>(PREFERENCES_PATH, { method: "PUT", body: JSON.stringify({ alertDigest: next }) })));
    } catch (cause) {
      setError(apiErrorMessage(cause, SAVE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  return (
    <RecordSection title="Updates" testId="alert-digest">
      <div className="max-w-measure">
        <Toggle label="Weekly email" description="When a saved answer gets better." checked={choice.on} busy={busy} onChange={(next) => void change(next)} />
      </div>
      {error ? (
        <p role="alert" className="font-ui text-ui font-normal text-error">
          {error}
        </p>
      ) : null}
    </RecordSection>
  );
}
