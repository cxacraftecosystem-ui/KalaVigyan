"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { hasRenderer } from "@/components/answer/blockRenderers";
import { ApiError, apiErrorMessage } from "@/lib/api";
import type { LedeBlock } from "@/lib/explainerContract";
import type { SectionView } from "@/lib/explainerState";
import { FILM_START, filmDuration, filmElapsed, filmScenes, filmStep, sceneProgress, type FilmAction, type FilmClock, type FilmScene } from "@/lib/filmScenes";
import { fetchListenScript, type ListenScript } from "@/lib/listen";

export type FilmLoad = "loading" | "ready" | "failed";

export type Film = {
  load: FilmLoad;
  error: string | null;
  scenes: FilmScene[];
  clock: FilmClock;
  scene: FilmScene | undefined;
  total: number;
  elapsed: number;
  progress: number;
  send: (action: FilmAction) => void;
  retry: () => void;
  broken: () => void;
};

const TICK_MS = 100;
const FAILED_TO_START = "Couldn't start the film. Try again.";
const FAILED_TO_PLAY = "Couldn't play the narration. Try again.";

function useScript(answerId: string, language: string) {
  const [script, setScript] = useState<ListenScript | null>(null);
  const [load, setLoad] = useState<FilmLoad>("loading");
  const [error, setError] = useState<string | null>(null);
  const [round, setRound] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoad("loading");
    setError(null);
    fetchListenScript(answerId, language)
      .then((loaded) => {
        if (cancelled) return;
        setScript(loaded);
        setLoad("ready");
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        if (!(cause instanceof ApiError)) console.error(cause);
        setError(apiErrorMessage(cause, FAILED_TO_START));
        setLoad("failed");
      });
    return () => {
      cancelled = true;
    };
  }, [answerId, language, round]);

  const retry = useCallback(() => setRound((value) => value + 1), []);
  const broken = useCallback(() => {
    setError(FAILED_TO_PLAY);
    setLoad("failed");
  }, []);
  return { script, load, error, retry, broken };
}

function useHoldTimer(holding: boolean, send: (action: FilmAction) => void) {
  useEffect(() => {
    if (!holding) return;
    let last = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      send({ type: "tick", seconds: (now - last) / 1000 });
      last = now;
    }, TICK_MS);
    return () => window.clearInterval(timer);
  }, [holding, send]);
}

export function useFilm(answerId: string, language: string, sections: readonly SectionView[], lede: LedeBlock | null): Film {
  const { script, load, error, retry, broken } = useScript(answerId, language);
  const scenes = useMemo(() => (script ? filmScenes(sections, script, hasRenderer, lede) : []), [sections, script, lede]);
  const [clock, setClock] = useState<FilmClock>(FILM_START);
  const ready = load === "ready";
  const send = useCallback(
    (action: FilmAction) => {
      if (ready) setClock((current) => filmStep(current, action, scenes));
    },
    [ready, scenes]
  );
  const scene = scenes[clock.scene];
  useHoldTimer(ready && clock.playing && !clock.ended && scene !== undefined && scene.tracks.length === 0, send);
  return {
    load,
    error,
    scenes,
    clock,
    scene,
    total: filmDuration(scenes),
    elapsed: filmElapsed(scenes, clock),
    progress: sceneProgress(scene, clock.time),
    send,
    retry,
    broken
  };
}
