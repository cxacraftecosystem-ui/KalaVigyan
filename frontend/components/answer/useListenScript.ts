"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiErrorMessage } from "@/lib/api";
import { extendedScript, fetchListenScript, LISTEN_POLLS_MAX, pendingBlocks, pollDelayMs, type ListenScript } from "@/lib/listen";

export type ScriptLoad = "idle" | "loading" | "ready" | "failed";

export type ListenFeed = {
  script: ListenScript | null;
  load: ScriptLoad;
  error: string | null;
  stalled: string | null;
  request: () => void;
  drop: () => void;
};

export const REST_FAILED = "Couldn't prepare the rest of the audio. Try again.";

function reported(cause: unknown, fallback: string): string {
  if (!(cause instanceof ApiError)) console.error(cause);
  return apiErrorMessage(cause, fallback);
}

type Asked = { answerId: string | null; language: string; script: ListenScript | null; round: number };

function usePolledRest({ answerId, language, script, round }: Asked, onScript: (next: ListenScript) => void, onStall: (message: string) => void): void {
  const pollsRef = useRef({ round, count: 0 });
  useEffect(() => {
    if (!answerId || !script || pendingBlocks(script).length === 0) return;
    if (pollsRef.current.round !== round) pollsRef.current = { round, count: 0 };
    if (pollsRef.current.count >= LISTEN_POLLS_MAX) {
      onStall(REST_FAILED);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      pollsRef.current.count += 1;
      fetchListenScript(answerId, language, script.voice)
        .then((polled) => {
          if (cancelled) return;
          const next = extendedScript(script, polled);
          if (next) onScript(next);
          else onStall(REST_FAILED);
        })
        .catch((cause: unknown) => {
          if (!cancelled) onStall(reported(cause, REST_FAILED));
        });
    }, pollDelayMs(script));
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [answerId, language, script, round, onScript, onStall]);
}

export function useListenScript(answerId: string | null, language: string, failedToStart: string): ListenFeed {
  const [script, setScript] = useState<ListenScript | null>(null);
  const [load, setLoad] = useState<ScriptLoad>("idle");
  const [error, setError] = useState<string | null>(null);
  const [stalled, setStalled] = useState<string | null>(null);
  const [round, setRound] = useState(0);
  usePolledRest({ answerId, language, script: stalled ? null : script, round }, setScript, setStalled);

  useEffect(() => {
    if (round === 0 || !answerId) return;
    let cancelled = false;
    setScript(null);
    setLoad("loading");
    setError(null);
    setStalled(null);
    fetchListenScript(answerId, language)
      .then((loaded) => {
        if (cancelled) return;
        setScript(loaded);
        setLoad("ready");
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(reported(cause, failedToStart));
        setLoad("failed");
      });
    return () => {
      cancelled = true;
    };
  }, [answerId, language, round, failedToStart]);

  const request = useCallback(() => setRound((value) => value + 1), []);
  const drop = useCallback(() => {
    setScript(null);
    setLoad("idle");
  }, []);
  return { script, load, error, stalled, request, drop };
}
