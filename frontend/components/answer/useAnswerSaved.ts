"use client";

import { useEffect, useState } from "react";

import { apiErrorMessage } from "@/lib/api";
import { fetchSavedExplainers, saveExplainer, unsaveExplainer } from "@/lib/learningApi";

export const SAVE_FAILED = "Couldn't save this answer. Try again.";

type Saved = { id: string; known: boolean; saved: boolean };

export type AnswerSaved = { known: boolean; saved: boolean; busy: boolean; error: string | null; toggle: () => void };

export function useAnswerSaved(explainerId: string): AnswerSaved {
  const [state, setState] = useState<Saved>({ id: explainerId, known: false, saved: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSavedExplainers()
      .then((list) => {
        if (!cancelled) setState({ id: explainerId, known: true, saved: list.items.some((item) => item.explainerId === explainerId) });
      })
      .catch(() => {
        if (!cancelled) setState({ id: explainerId, known: true, saved: false });
      });
    return () => {
      cancelled = true;
    };
  }, [explainerId]);

  const current = state.id === explainerId ? state : { id: explainerId, known: false, saved: false };

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      if (current.saved) await unsaveExplainer(explainerId);
      else await saveExplainer(explainerId);
      setState({ id: explainerId, known: true, saved: !current.saved });
    } catch (cause) {
      setError(apiErrorMessage(cause, SAVE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  return { known: current.known, saved: current.saved, busy, error, toggle: () => void toggle() };
}
