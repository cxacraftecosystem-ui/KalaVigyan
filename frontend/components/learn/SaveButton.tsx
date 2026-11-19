"use client";

import { useEffect, useState } from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api";
import { fetchSavedExplainers, saveExplainer, unsaveExplainer } from "@/lib/learningApi";

const SAVE_FAILED = "Couldn't save this. Try again.";

type Saved = { known: boolean; saved: boolean };

function useSaved(explainerId: string) {
  const [state, setState] = useState<Saved>({ known: false, saved: false });
  useEffect(() => {
    let cancelled = false;
    setState({ known: false, saved: false });
    fetchSavedExplainers()
      .then((list) => {
        if (!cancelled) setState({ known: true, saved: list.items.some((item) => item.explainerId === explainerId) });
      })
      .catch(() => {
        if (!cancelled) setState({ known: true, saved: false });
      });
    return () => {
      cancelled = true;
    };
  }, [explainerId]);
  return [state, setState] as const;
}

export function SaveButton({ explainerId }: { explainerId: string }) {
  const [state, setState] = useSaved(explainerId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      if (state.saved) await unsaveExplainer(explainerId);
      else await saveExplainer(explainerId);
      setState({ known: true, saved: !state.saved });
    } catch (cause) {
      setError(apiErrorMessage(cause, SAVE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="grid min-w-0 justify-items-start gap-1" data-testid="save-explainer" data-saved={state.saved ? "true" : "false"}>
      <Button type="button" variant="quiet" size="sm" aria-pressed={state.saved} disabled={!state.known} busy={busy} onClick={() => void toggle()}>
        {state.saved ? <BookmarkCheck aria-hidden /> : <Bookmark aria-hidden />}
        {state.saved ? "Saved" : "Save"}
      </Button>
      {error ? (
        <span role="alert" className="font-ui text-label text-error">
          {error}
        </span>
      ) : null}
    </span>
  );
}
