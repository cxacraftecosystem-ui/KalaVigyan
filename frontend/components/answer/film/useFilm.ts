"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { hasRenderer } from "@/components/answer/blockRenderers";
import { useListenScript } from "@/components/answer/useListenScript";
import type { LedeBlock } from "@/lib/explainerContract";
import type { SectionView } from "@/lib/explainerState";
import { FILM_START, filmDuration, filmElapsed, filmScenes, filmStep, filmWaits, sceneProgress, type FilmAction, type FilmClock, type FilmScene } from "@/lib/filmScenes";

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
  waiting: boolean;
  send: (action: FilmAction) => void;
  retry: () => void;
  broken: () => void;
};

const TICK_MS = 100;
const FAILED_TO_START = "Couldn't start the film. Try again.";
const FAILED_TO_PLAY = "Couldn't play the narration. Try again.";

function useScript(answerId: string, language: string) {
  const { script, load, error, stalled, request } = useListenScript(answerId, language, FAILED_TO_START);
  const [broke, setBroke] = useState<string | null>(null);
  useEffect(() => request(), [request]);
  const retry = useCallback(() => {
    setBroke(null);
    request();
  }, [request]);
  const broken = useCallback(() => setBroke(FAILED_TO_PLAY), []);
  const state: FilmLoad = broke || load === "failed" ? "failed" : load === "ready" ? "ready" : "loading";
  return { script, load: state, error: broke ?? error, stalled, retry, broken };
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
  const { script, load: loaded, error: loadError, stalled, retry, broken } = useScript(answerId, language);
  const scenes = useMemo(() => (script ? filmScenes(sections, script, hasRenderer, lede) : []), [sections, script, lede]);
  const [clock, setClock] = useState<FilmClock>(FILM_START);
  const ready = loaded === "ready";
  const send = useCallback(
    (action: FilmAction) => {
      if (ready) setClock((current) => filmStep(current, action, scenes));
    },
    [ready, scenes]
  );
  const scene = scenes[clock.scene];
  const waiting = ready && filmWaits(scene, clock);
  const stalledHere = waiting && stalled !== null;
  useHoldTimer(ready && clock.playing && !clock.ended && scene !== undefined && scene.tracks.length === 0 && !scene.pending, send);
  return {
    load: stalledHere ? "failed" : loaded,
    error: stalledHere ? stalled : loadError,
    scenes,
    clock,
    scene,
    total: filmDuration(scenes),
    elapsed: filmElapsed(scenes, clock),
    progress: sceneProgress(scene, clock.time),
    waiting,
    send,
    retry,
    broken
  };
}
