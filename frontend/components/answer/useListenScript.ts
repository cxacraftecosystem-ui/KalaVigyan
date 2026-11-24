"use client";

import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";

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

export type ListenAsk = { answerId: string; language: string };

export type HeldScript = Omit<ListenFeed, "request" | "drop"> & { ask: ListenAsk | null };

type HeldChange = Partial<Omit<HeldScript, "ask">>;

export const NOTHING_HELD: HeldScript = { ask: null, script: null, load: "idle", error: null, stalled: null };

export const REST_FAILED = "Couldn't prepare the rest of the audio. Try again.";

export function scriptAsked(ask: ListenAsk): HeldScript {
  return { ask, script: null, load: "loading", error: null, stalled: null };
}

export function replied(held: HeldScript, ask: ListenAsk, change: HeldChange): HeldScript {
  return held.ask === ask ? { ...held, ...change } : held;
}

export function heldFor(held: HeldScript, answerId: string | null, language: string): HeldScript {
  return held.ask !== null && held.ask.answerId === answerId && held.ask.language === language ? held : NOTHING_HELD;
}

function reported(cause: unknown, fallback: string): string {
  if (!(cause instanceof ApiError)) console.error(cause);
  return apiErrorMessage(cause, fallback);
}

function usePolledRest({ ask, script, stalled }: HeldScript, setHeld: Dispatch<SetStateAction<HeldScript>>): void {
  const pollsRef = useRef<{ ask: ListenAsk | null; count: number }>({ ask: null, count: 0 });
  useEffect(() => {
    if (!ask || !script || stalled || pendingBlocks(script).length === 0) return;
    if (pollsRef.current.ask !== ask) pollsRef.current = { ask, count: 0 };
    const reply = (change: HeldChange) => setHeld((held) => replied(held, ask, change));
    if (pollsRef.current.count >= LISTEN_POLLS_MAX) {
      reply({ stalled: REST_FAILED });
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      pollsRef.current.count += 1;
      fetchListenScript(ask.answerId, ask.language, script.voice)
        .then((polled) => {
          if (cancelled) return;
          const next = extendedScript(script, polled);
          reply(next ? { script: next } : { stalled: REST_FAILED });
        })
        .catch((cause: unknown) => {
          if (!cancelled) reply({ stalled: reported(cause, REST_FAILED) });
        });
    }, pollDelayMs(script));
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [ask, script, stalled, setHeld]);
}

export function useListenScript(answerId: string | null, language: string, failedToStart: string): ListenFeed {
  const [held, setHeld] = useState<HeldScript>(NOTHING_HELD);
  const shown = heldFor(held, answerId, language);
  usePolledRest(shown, setHeld);

  const request = useCallback(() => {
    if (!answerId) return;
    const ask: ListenAsk = { answerId, language };
    setHeld(scriptAsked(ask));
    fetchListenScript(answerId, language)
      .then((loaded) => setHeld((current) => replied(current, ask, { script: loaded, load: "ready" })))
      .catch((cause: unknown) => {
        const message = reported(cause, failedToStart);
        setHeld((current) => replied(current, ask, { error: message, load: "failed" }));
      });
  }, [answerId, language, failedToStart]);
  const drop = useCallback(() => setHeld((current) => ({ ...current, script: null, load: "idle" })), []);
  const { script, load, error, stalled } = shown;
  return { script, load, error, stalled, request, drop };
}
