"use client";

import { useCallback, useState } from "react";

import { ApiError, apiErrorMessage } from "@/lib/api";
import { fetchListenScript, LISTEN_RATES, nextRate, type ListenScript } from "@/lib/listen";
import { listenMarkStore, type ListenMarks } from "@/lib/listenMarks";

export type ListenStatus = "idle" | "loading" | "playing" | "paused" | "failed";

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
  const [script, setScript] = useState<ListenScript | null>(null);
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

  const start = useCallback(() => {
    if (!answerId) return;
    setError(null);
    if (script) {
      setStatus("playing");
      return;
    }
    setStatus("loading");
    fetchListenScript(answerId, language)
      .then((loaded) => {
        setScript(loaded);
        setTrack(0);
        marks.follow(null, 0);
        setStatus("playing");
      })
      .catch((cause: unknown) => {
        if (!(cause instanceof ApiError)) console.error(cause);
        fail(apiErrorMessage(cause, FAILED_TO_START));
      });
  }, [answerId, language, script, marks, fail]);

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

  const onTime = useCallback((time: number) => marks.follow(script?.tracks[track]?.words ?? null, time), [marks, script, track]);

  const onEnded = useCallback(() => {
    if (script && track + 1 < script.tracks.length) {
      setTrack(track + 1);
      marks.follow(script.tracks[track + 1].words, 0);
    } else stop();
  }, [script, track, marks, stop]);

  const onBroken = useCallback(() => {
    setScript(null);
    fail(FAILED_TO_PLAY);
  }, [fail]);

  const onRefused = useCallback(() => fail(FAILED_TO_PLAY), [fail]);

  return { status, script, track, marks, rate, error, start, toggle, stop, cycleRate: () => setRate(nextRate), onTime, onEnded, onBroken, onRefused };
}
