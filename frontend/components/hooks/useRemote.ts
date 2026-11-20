"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, apiErrorMessage } from "@/lib/api";
import { settledFor, UNSETTLED, type RemoteFailure, type Settled } from "@/lib/remoteSettled";

export type { RemoteFailure } from "@/lib/remoteSettled";

export function failureMessage(failure: RemoteFailure, fallback: string): string {
  return failure.cause instanceof ApiError ? apiErrorMessage(failure.cause, fallback) : fallback;
}

export type Remote<T> = { data: T | null; failure: RemoteFailure | null; retry: () => void };

export function useRemote<T>(load: (() => Promise<T>) | null): Remote<T> {
  const [settled, setSettled] = useState<Settled<() => Promise<T>, T>>(UNSETTLED);
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (!load) return;
    let cancelled = false;
    load()
      .then((data) => {
        if (!cancelled) setSettled({ load, round, data, failure: null });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        if (!(cause instanceof ApiError)) console.error(cause);
        setSettled({ load, round, data: null, failure: { cause } });
      });
    return () => {
      cancelled = true;
    };
  }, [load, round]);

  const retry = useCallback(() => setRound((value) => value + 1), []);
  const shown = settledFor(settled, load, round);
  return { data: shown.data, failure: shown.failure, retry };
}
