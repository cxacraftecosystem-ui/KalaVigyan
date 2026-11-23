"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { apiErrorMessage, apiFetch } from "@/lib/api";
import { nextReadIn } from "@/lib/pageRefreshView";
import { hasRank } from "@/lib/permissions";
import { parsePageRefreshState, SITE_REFRESH_PATH, type PageRefreshState } from "@/lib/sitePagesContract";

const LOAD_FAILED = "Couldn't read the refresh status. Reload the page to try again.";
const START_FAILED = "Couldn't start the refresh. Try again in a few minutes.";

export type RefreshAsk = "changed" | "every";

export type PageRefresh = {
  allowed: boolean;
  state: PageRefreshState | null;
  error: string | null;
  busy: RefreshAsk | null;
  start: (ask: RefreshAsk) => Promise<void>;
};

function useRefreshReads(allowed: boolean) {
  const [state, setState] = useState<PageRefreshState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const read = useCallback(async () => {
    try {
      setState(parsePageRefreshState(await apiFetch<unknown>(SITE_REFRESH_PATH)));
    } catch {
      setError(LOAD_FAILED);
    }
  }, []);

  useEffect(() => {
    if (allowed) void read();
  }, [allowed, read]);

  useEffect(() => {
    const delay = nextReadIn(state, new Date());
    if (!allowed || delay === null) return;
    const timer = window.setTimeout(() => void read(), delay);
    return () => window.clearTimeout(timer);
  }, [allowed, state, read]);

  return { state, setState, error, setError, read };
}

export function usePageRefresh(): PageRefresh {
  const { user } = useAuth();
  const allowed = hasRank(user, "ADMIN");
  const { state, setState, error, setError, read } = useRefreshReads(allowed);
  const [busy, setBusy] = useState<RefreshAsk | null>(null);

  const start = useCallback(
    async (ask: RefreshAsk) => {
      setBusy(ask);
      setError(null);
      try {
        const body = JSON.stringify({ every: ask === "every" });
        setState(parsePageRefreshState(await apiFetch<unknown>(SITE_REFRESH_PATH, { method: "POST", body })));
      } catch (cause) {
        setError(apiErrorMessage(cause, START_FAILED));
        void read();
      } finally {
        setBusy(null);
      }
    },
    [read, setError, setState]
  );

  return { allowed, state, error, busy, start };
}
