"use client";

import { useCallback, useEffect, useState } from "react";

import { useListenScript } from "@/components/answer/useListenScript";
import { afterTrack, LISTEN_RATES, nextRate, type ListenScript } from "@/lib/listen";
import { listenMarkStore, type ListenMarks } from "@/lib/listenMarks";

export type ListenStatus = "idle" | "loading" | "playing" | "paused" | "waiting" | "failed";

export type Listen = {
  status: ListenStatus;
  script: ListenScript | null;
  track: number;
  marks: ListenMarks;
  rate: number;
  error: string | null;
  start: () => void;
  toggle: () => void;
  stop: () => void;
  cycleRate: () => void;
  onTime: (time: number) => void;
  onEnded: () => void;
  onBroken: () => void;
  onRefused: () => void;
};

const FAILED_TO_START = "Couldn't start listening. Try again.";
const FAILED_TO_PLAY = "Couldn't play the audio. Try again.";

export function useListen(answerId: string | null, language: string): Listen {
  const { script, load, error: loadError, stalled, request, drop } = useListenScript(answerId, language, FAILED_TO_START);
  const [status, setStatus] = useState<ListenStatus>("idle");
  const [track, setTrack] = useState(0);
  const [marks] = useState(listenMarkStore);
  const [rate, setRate] = useState<number>(LISTEN_RATES[0]);
  const [error, setError] = useState<string | null>(null);

  const fail = useCallback(
    (message: string) => {
      marks.follow(null, 0);
      setError(message);
      setStatus("failed");
    },
    [marks]
  );

  useEffect(() => {
    if (status !== "loading") return;
    if (load === "failed") fail(loadError ?? FAILED_TO_START);
    else if (load === "ready" && script) {
      setTrack(0);
      marks.follow(null, 0);
      setStatus("playing");
    }
  }, [status, load, loadError, script, marks, fail]);

  useEffect(() => {
    if (status !== "waiting") return;
    if (script && track + 1 < script.tracks.length) {
      setTrack(track + 1);
      marks.follow(script.tracks[track + 1], 0);
      setStatus("playing");
    } else if (stalled) {
      drop();
      fail(stalled);
    }
  }, [status, script, track, stalled, marks, drop, fail]);

  const start = useCallback(() => {
    if (!answerId) return;
    setError(null);
    if (script && load === "ready") {
      setStatus("playing");
      return;
    }
    setStatus("loading");
    request();
  }, [answerId, script, load, request]);

  const stop = useCallback(() => {
    setTrack(0);
    marks.follow(null, 0);
    setStatus("idle");
    setError(null);
  }, [marks]);

  const toggle = useCallback(() => {
    if (status === "playing") setStatus("paused");
    else if (status === "paused") setStatus("playing");
    else start();
  }, [status, start]);

  const onTime = useCallback((time: number) => marks.follow(script?.tracks[track] ?? null, time), [marks, script, track]);

  const onEnded = useCallback(() => {
    const after = afterTrack(script, track);
    if (after === "end") stop();
    else if (after === "wait") setStatus("waiting");
    else {
      setTrack(track + 1);
      marks.follow(script?.tracks[track + 1] ?? null, 0);
    }
  }, [script, track, marks, stop]);

  const onBroken = useCallback(() => {
    drop();
    fail(FAILED_TO_PLAY);
  }, [drop, fail]);

  const onRefused = useCallback(() => fail(FAILED_TO_PLAY), [fail]);

  return { status, script, track, marks, rate, error, start, toggle, stop, cycleRate: () => setRate(nextRate), onTime, onEnded, onBroken, onRefused };
}
