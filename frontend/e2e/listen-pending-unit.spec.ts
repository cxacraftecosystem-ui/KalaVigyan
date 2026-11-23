import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { hasRenderer } from "@/components/answer/blockRenderers";
import { ListenDock } from "@/components/answer/ListenDock";
import type { Listen } from "@/components/answer/useListen";
import { ENGLISH } from "@/lib/answerLanguages";
import { explainerShape, type Explainer } from "@/lib/explainerContract";
import type { SectionView } from "@/lib/explainerState";
import { FILM_START, filmScenes, filmStep, filmWaits, type FilmAction, type FilmClock, type FilmScene } from "@/lib/filmScenes";
import { afterTrack, checkedScript, extendedScript, listenPath, scriptDuration, type ListenScript } from "@/lib/listen";
import { listenMarkStore } from "@/lib/listenMarks";
import { parseShape, ShapeError } from "@/lib/shape";

import { attribute, withApp } from "./explainerRender";
import { readRepo } from "./phaseBFixture";

const ANSWER_ID = "0c5e7a1d-2b3f-4c6d-8e9f-a0b1c2d3e4f5";

function golden(name: string): Record<string, unknown> {
  return JSON.parse(readRepo("shared", name)) as Record<string, unknown>;
}

function firstAsk(): ListenScript {
  return checkedScript(golden("listen.script-pending.golden.json"), ANSWER_ID, "en");
}

function water(): ListenScript {
  return checkedScript(golden("listen.script.golden.json"), ANSWER_ID, "en");
}

function polled(): ListenScript {
  const first = firstAsk();
  return { ...first, tracks: [...first.tracks, ...water().tracks], pending: ["s3.b1"], pollAfterSeconds: 3 };
}

function sections(): SectionView[] {
  const document: Explainer = parseShape(explainerShape, golden("explainer.document.golden.json"));
  return document.sections as SectionView[];
}

function played(clock: FilmClock, actions: FilmAction[], scenes: FilmScene[]): FilmClock {
  return actions.reduce((at, action) => filmStep(at, action, scenes), clock);
}

test("a whole answer's first script carries its first block and names the blocks still being read", () => {
  const raw = golden("listen.script-pending.golden.json");
  const script = firstAsk();
  expect(script).toEqual(raw);
  expect(script.tracks.map((track) => track.blockId)).toEqual(["s1.b1"]);
  expect([script.pending, script.pollAfterSeconds]).toEqual([["s2.b1", "s3.b1"], 3]);
  expect(scriptDuration(script)).toBeCloseTo(32.15, 6);
  expect(listenPath(ANSWER_ID, "en", "ELEVENLABS")).toBe(`/answers/${ANSWER_ID}/listen?language=en&voice=ELEVENLABS`);
});

test("a pending block with a track, a wait without pending blocks or pending blocks without a wait are refused", () => {
  const raw = golden("listen.script-pending.golden.json");
  for (const changed of [{ ...raw, pending: ["s1.b1"] }, { ...raw, pending: ["s2.b1", "s2.b1"] }, { ...raw, pending: undefined }, { ...raw, pollAfterSeconds: undefined }, { ...raw, pollAfterSeconds: 0 }]) {
    expect(() => checkedScript(changed, ANSWER_ID, "en")).toThrow(ShapeError);
  }
});

test("a poll keeps the tracks already held and adds the blocks read since, in reading order", () => {
  const first = firstAsk();
  const next = extendedScript(first, polled());
  expect(next?.tracks.map((track) => track.blockId)).toEqual(["s1.b1", "s2.b1"]);
  expect(next?.tracks[0]).toBe(first.tracks[0]);
  expect(next?.pending).toEqual(["s3.b1"]);
  expect(extendedScript(first, { ...polled(), voice: "GEMINI" })).toBeNull();
  expect(extendedScript(first, { ...water(), pending: ["s3.b1"], pollAfterSeconds: 3 })).toBeNull();
});

test("the dock plays the first block, waits at a pending one and stops after the last", () => {
  const first = firstAsk();
  expect(afterTrack(first, 0)).toBe("wait");
  const next = extendedScript(first, polled());
  expect(afterTrack(next, 0)).toBe("next");
  expect(afterTrack(next, 1)).toBe("wait");
  expect(afterTrack(water(), 0)).toBe("end");
  const listen: Listen = {
    status: "waiting",
    script: first,
    track: 0,
    marks: listenMarkStore(),
    rate: 1,
    error: null,
    start: () => undefined,
    toggle: () => undefined,
    stop: () => undefined,
    cycleRate: () => undefined,
    onTime: () => undefined,
    onEnded: () => undefined,
    onBroken: () => undefined,
    onRefused: () => undefined
  };
  const dock = withApp(createElement(ListenDock, { listen, language: ENGLISH }));
  expect(attribute(dock, "listen-dock", "data-status")).toEqual(["waiting"]);
  expect(dock).toContain("Preparing the next part…");
  expect(dock).toMatch(/aria-label="Play" disabled=""/);
});

test("the film plays the first block while the others are pending, holds at a pending scene and plays it once read", () => {
  const scenes = filmScenes(sections(), firstAsk(), hasRenderer);
  expect(scenes.map((scene) => [scene.block.id, scene.tracks.length, scene.pending])).toEqual([
    ["s1.b1", 1, false],
    ["s1.b2", 0, false],
    ["s2.b1", 0, true],
    ["s3.b1", 0, true]
  ]);
  const heard = filmStep(FILM_START, { type: "heard", scene: 0, time: 12 }, scenes);
  expect(heard).toMatchObject({ scene: 0, time: 12, playing: true });
  const atPending = played(heard, [{ type: "trackEnded", scene: 0, time: 32.15 }, { type: "tick", seconds: 6 }], scenes);
  expect(atPending).toMatchObject({ scene: 2, time: 0, playing: true });
  expect(played(atPending, [{ type: "tick", seconds: 5 }, { type: "tick", seconds: 5 }], scenes)).toEqual(atPending);
  expect(filmWaits(scenes[2], atPending)).toBe(true);
  const read = filmScenes(sections(), extendedScript(firstAsk(), polled()), hasRenderer);
  expect([read[2].tracks.length, read[2].pending, read[2].seconds]).toEqual([1, false, 14.7]);
  expect(filmWaits(read[2], atPending)).toBe(false);
  expect(filmStep(atPending, { type: "heard", scene: 2, time: 3 }, read)).toMatchObject({ scene: 2, time: 3 });
});
