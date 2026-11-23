import { expect, test } from "@playwright/test";
import { createElement, createRef } from "react";

import { hasRenderer } from "@/components/answer/blockRenderers";
import { ExplainerHeader } from "@/components/answer/ExplainerHeader";
import { ExplainerView } from "@/components/answer/ExplainerView";
import { FilmButtons, FilmTiming } from "@/components/answer/film/FilmControls";
import { FilmPlayerBody } from "@/components/answer/film/FilmPlayer";
import { FilmScoreControls } from "@/components/answer/film/FilmScoreControls";
import { FilmCaption, FilmStage } from "@/components/answer/film/FilmStage";
import type { Film } from "@/components/answer/film/useFilm";
import { SCORE_FAILED } from "@/components/answer/film/useFilmScore";
import { FilmSceneProvider } from "@/components/answer/FilmScene";
import { ReactionPlayerView } from "@/components/answer/matter/ReactionPlayer";
import { AuthProvider } from "@/components/AuthProvider";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ENGLISH, type AnswerLanguage } from "@/lib/answerLanguages";
import { normaliseAskConfig } from "@/lib/askConfig";
import { explainerShape, type Explainer } from "@/lib/explainerContract";
import { emptyExplainer, type ExplainerState, type SectionView } from "@/lib/explainerState";
import type { UnderstoodPart } from "@/lib/explainerView";
import { checkedFilmScore, filmScoreOffered, type FilmScore } from "@/lib/filmScore";
import {
  FILM_SCENE_SECONDS,
  FILM_START,
  filmCaption,
  filmDuration,
  filmElapsed,
  filmKey,
  filmMark,
  filmScenes,
  filmStep,
  holdSeconds,
  sceneProgress,
  type FilmAction,
  type FilmClock,
  type FilmScene
} from "@/lib/filmScenes";
import { applyLevel, bedDrifted, bedTime, bedVolume, cueDue, cueVolume, filmLevels, FULL_MIX, sceneCue, scoreCredit, volumeIsFixed } from "@/lib/filmSound";
import { checkedScript, type ListenScript } from "@/lib/listen";
import { parseShape } from "@/lib/shape";

import { attribute, shownText, withApp, withReading } from "./explainerRender";
import { eagerModules } from "./moduleGraph";
import { phaseBBlock, readRepo } from "./phaseBFixture";
import { phaseCBlock } from "./playFixture";

const HINDI: AnswerLanguage = { code: "hi", label: "Hindi", autonym: "हिन्दी", script: "Deva", direction: "ltr" };

function document(): Explainer {
  return parseShape(explainerShape, JSON.parse(readRepo("shared", "explainer.document.golden.json")));
}

function script(): ListenScript {
  return checkedScript(JSON.parse(readRepo("shared", "listen.script.golden.json")), document().answerId, "en");
}

function score(): FilmScore {
  const raw = JSON.parse(readRepo("shared", "film.score.golden.json")) as { answerId: string };
  return checkedFilmScore(raw, raw.answerId, "en");
}

function scoreLine(): string {
  const raw = JSON.parse(readRepo("shared", "film.score.golden.json")) as { label: { models: string[]; generatedOn: string } };
  expect(raw.label.generatedOn).toBe("2026-11-18");
  return `AI music and sound · ${raw.label.models.join(", ")} · 18 Nov 2026`;
}

function sections(): SectionView[] {
  return document().sections as SectionView[];
}

function scenes(): FilmScene[] {
  return filmScenes(sections(), script(), hasRenderer);
}

function played(actions: FilmAction[], from: FilmClock = FILM_START): FilmClock {
  return actions.reduce((clock, action) => filmStep(clock, action, scenes()), from);
}

function fakeFilm(clock: FilmClock, load: Film["load"] = "ready"): Film {
  const all = scenes();
  return {
    load,
    error: null,
    scenes: all,
    clock,
    scene: all[clock.scene],
    total: filmDuration(all),
    elapsed: filmElapsed(all, clock),
    progress: sceneProgress(all[clock.scene], clock.time),
    waiting: false,
    send: () => undefined,
    retry: () => undefined,
    broken: () => undefined
  };
}

test("scenes are the drawn blocks in reading order, timed by their Listen tracks or a hold per kind", () => {
  const all = scenes();
  expect(all.map((scene) => scene.block.id)).toEqual(["s1.b1", "s1.b2", "s2.b1", "s3.b1"]);
  expect(all.map((scene) => scene.seconds)).toEqual([6, 6, 14.7, 6]);
  expect(all.slice(0, 3).map((scene) => scene.start)).toEqual([0, 6, 12]);
  expect(all[3].start).toBeCloseTo(26.7, 9);
  expect(all.map((scene) => scene.tracks.length)).toEqual([0, 0, 1, 0]);
  expect(filmDuration(all)).toBeCloseTo(32.7, 9);
  expect(holdSeconds(phaseBBlock("region_story", "s1.b1"))).toBe(16);
  expect(holdSeconds(phaseBBlock("reaction_player", "s4.b1"))).toBe(16);
  expect(holdSeconds(phaseBBlock("molecule_3d", "s4.b3"))).toBe(6);
  expect(filmScenes(sections(), null, hasRenderer).map((scene) => scene.seconds)).toEqual([6, 6, 6, 6]);
  expect(filmScenes(sections(), script(), (block) => block.kind !== "images").map((scene) => scene.block.id)).toEqual(["s1.b1", "s2.b1", "s3.b1"]);
});

test("sections play by their order, and a hidden generated explainer is left out", () => {
  const [first, second, third] = sections();
  const reordered = filmScenes([third, { ...first, order: 2 }, { ...second, order: 1 }], script(), hasRenderer);
  expect(reordered.map((scene) => scene.block.id)).toEqual(["s2.b1", "s1.b1", "s1.b2", "s3.b1"]);
  const simulation = phaseCBlock("simulation", "s1.b1");
  const withSimulation = (hidden: boolean) =>
    filmScenes([{ ...third, blocks: [...third.blocks, { ...simulation, id: "s3.b9", hidden }] } as unknown as SectionView], null, () => true).map((scene) => scene.block.id);
  expect(withSimulation(false)).toEqual(["s3.b1", "s3.b9"]);
  expect(withSimulation(true)).toEqual(["s3.b1"]);
});

test("a film opens on the lede, drawn as its sentences without a heading, narrated by the lede's track", () => {
  const answered = parseShape(explainerShape, JSON.parse(readRepo("shared", "explainer.lede.golden.json")));
  const lede = answered.lede ?? null;
  const unheard = filmScenes(answered.sections as SectionView[], null, hasRenderer, lede);
  expect(unheard.map((scene) => scene.block.id)).toEqual(["lede", "s1.b1", "s2.b1", "s3.b1"]);
  expect(unheard[0].section).toBeNull();
  expect(unheard[0].seconds).toBe(FILM_SCENE_SECONDS.block);
  expect(filmCaption(unheard[0], 0, ENGLISH)).toMatchObject({ text: "Alum is the mordant that fixes the red, together with dhaori (tamarisk galls).", narrated: false, mark: null });
  const words = [{ sentenceId: "lede.1", text: "Alum", start: 0, end: 0.4 }, { sentenceId: "lede.1", text: "is", start: 0.5, end: 0.6 }];
  const heard: ListenScript = { schemaVersion: 1, answerId: answered.answerId, language: "en", tracks: [{ blockId: "lede", audioUrl: "https://example.org/lede.mp3", durationSeconds: 9.5, words }] };
  const [opening] = filmScenes(answered.sections as SectionView[], heard, hasRenderer, lede);
  expect([opening.tracks.length, opening.seconds]).toEqual([1, 9.5]);
  expect(filmCaption(opening, 0.55, ENGLISH)).toMatchObject({ narrated: true, mark: { from: 5, to: 7 } });
});

test("the hold per kind is the server's", () => {
  const server = /FILM_SCENE_SECONDS: Mapping\[str, float\] = MappingProxyType\(\{"step": ([\d.]+), "picture": ([\d.]+), "block": ([\d.]+)\}\)/.exec(readRepo("backend", "app", "schemas", "film.py"));
  expect(server?.slice(1).map(Number)).toEqual([FILM_SCENE_SECONDS.step, FILM_SCENE_SECONDS.picture, FILM_SCENE_SECONDS.block]);
  expect(FILM_SCENE_SECONDS).toEqual({ step: 4, picture: 3, block: 6 });
});

test("the score golden's cues are numbered by these scenes", () => {
  const numbered = new Map(scenes().map((scene, index) => [scene.block.id, String(index + 1).padStart(2, "0")]));
  for (const cue of score().cues) expect(cue.audioUrl).toContain(`Scene-${numbered.get(cue.blockId)}.mp3`);
  expect(sceneCue(score(), "s1.b1")?.offsetSeconds).toBe(0.5);
  expect(sceneCue(score(), "s2.b1")).toBeNull();
  expect(sceneCue(null, "s1.b1")).toBeNull();
});

test("the clock holds, advances, ends and restarts as the narration and the controls say", () => {
  expect(played([{ type: "tick", seconds: 2 }, { type: "tick", seconds: 2 }])).toMatchObject({ scene: 0, time: 4, playing: true, ended: false });
  expect(played([{ type: "tick", seconds: 6 }])).toMatchObject({ scene: 1, time: 0, take: 1 });
  expect(played([{ type: "pause" }, { type: "tick", seconds: 6 }])).toMatchObject({ scene: 0, time: 0, playing: false });
  const narrating = played([{ type: "choose", scene: 2 }]);
  expect(narrating).toMatchObject({ scene: 2, time: 0, take: 1 });
  expect(filmStep(narrating, { type: "tick", seconds: 1 }, scenes())).toMatchObject({ scene: 2, time: 1 });
  expect(filmStep(narrating, { type: "heard", scene: 2, time: 3.2 }, scenes())).toMatchObject({ scene: 2, time: 3.2 });
  expect(filmStep(narrating, { type: "heard", scene: 1, time: 3.2 }, scenes())).toEqual(narrating);
  expect(filmStep(narrating, { type: "heard", scene: 2, time: 99 }, scenes())).toMatchObject({ scene: 2, time: 14.7 });
  expect(filmStep(narrating, { type: "trackEnded", scene: 2, time: 14.7 }, scenes())).toMatchObject({ scene: 3, time: 0, take: 2 });
  const ended = played([{ type: "choose", scene: 3 }, { type: "next" }]);
  expect(ended).toMatchObject({ scene: 3, time: 6, playing: false, ended: true });
  expect(filmStep(ended, { type: "tick", seconds: 1 }, scenes())).toEqual(ended);
  expect(filmStep(ended, { type: "toggle" }, scenes())).toMatchObject({ scene: 0, time: 0, playing: true, ended: false });
  expect(filmStep(ended, { type: "previous" }, scenes())).toMatchObject({ scene: 3, time: 0, ended: false });
  expect(played([{ type: "tick", seconds: 1 }, { type: "previous" }])).toMatchObject({ scene: 0, time: 0 });
  expect(played([{ type: "choose", scene: 2 }, { type: "tick", seconds: 1 }, { type: "previous" }])).toMatchObject({ scene: 1, time: 0 });
  expect(played([{ type: "choose", scene: 2 }, { type: "heard", scene: 2, time: 5 }, { type: "previous" }])).toMatchObject({ scene: 2, time: 0 });
  expect(played([{ type: "choose", scene: 40 }])).toMatchObject({ scene: 3 });
  expect(filmStep(FILM_START, { type: "play" }, [])).toMatchObject({ playing: false, ended: true });
});

test("a narrated scene is captioned with the sentence being read and its word, a silent one with its section's title", () => {
  const all = scenes();
  const read = filmCaption(all[2], 0.5, ENGLISH);
  expect(read).toMatchObject({ text: "Presence of iron in the water supply dulls and darkens the final result; alum, tin or chrome deposits help brighten colours.", mark: { from: 9, to: 11 }, narrated: true, lang: "en" });
  expect(filmMark(all[2], 0.5)).toMatchObject({ sentenceId: "s2.b1.1", wordIndex: 1 });
  expect(filmCaption(all[0], 3, ENGLISH)).toMatchObject({ text: "How it is made", mark: null, narrated: false });
  expect(filmCaption(all[3], 0, ENGLISH)).toMatchObject({ text: "The chemistry of the colours", narrated: false });
  expect(filmMark(all[0], 3)).toBeNull();
});

test("a scene the Gemini voice read is captioned with the sentence being read and no word", () => {
  const read = checkedScript(JSON.parse(readRepo("shared", "listen.script-sentences.golden.json")), document().answerId, "en");
  const water = filmScenes(sections(), read, hasRenderer)[2];
  expect(filmMark(water, 7)).toEqual({ sentenceId: "s2.b1.2", words: [], wordIndex: -1 });
  expect(filmCaption(water, 7, ENGLISH)).toMatchObject({ text: "Ajrakh printing got concentrated where extra soft water was available.", mark: null, narrated: true });
  expect(filmCaption(water, 0, ENGLISH)).toMatchObject({ narrated: true, mark: null });
});

test("captions are in the answer language even while the page shows the English original", () => {
  const sentence = { id: "s9.b1.1", text: "लोहा पानी में है", original: "Iron is in the water", translated: true, level: "PROVISIONAL", citations: [], terms: [] };
  const words = [
    { sentenceId: "s9.b1.1", text: "लोहा", start: 0, end: 0.4 },
    { sentenceId: "s9.b1.1", text: "पानी", start: 0.5, end: 0.9 }
  ];
  const scene = {
    block: { id: "s9.b1", kind: "prose", version: 1, reuse: null, sentences: [sentence] },
    section: { id: "s9", discipline: "GEOGRAPHY", title: "पानी", original: "Water", order: 1, state: "READY", blocks: [], searched: null },
    tracks: [{ at: 0, start: 0, track: { blockId: "s9.b1", audioUrl: "https://example.org/a.mp3", durationSeconds: 1, words } }],
    start: 0,
    seconds: 1
  } as unknown as FilmScene;
  expect(filmCaption(scene, 0.6, HINDI)).toMatchObject({ text: "लोहा पानी में है", lang: "hi", mark: { from: 5, to: 9 }, narrated: true });
  expect(filmCaption({ ...scene, tracks: [] }, 0.6, HINDI)).toMatchObject({ text: "पानी", lang: "hi", narrated: false });
  const html = withReading(createElement(FilmCaption, { caption: filmCaption(scene, 0.6, HINDI) }));
  expect(html).toContain('lang="hi"');
  expect(html).toContain('<mark class="rounded-plate bg-turmeric-wash text-ink-1" data-testid="film-caption-word">पानी</mark>');
});

test("keys play, pause, step and mute the film, and leave buttons and sliders their own keys", () => {
  expect([filmKey(" ", "DIV"), filmKey(" ", "BUTTON"), filmKey("k", "BUTTON"), filmKey("K", null)]).toEqual(["toggle", null, "toggle", "toggle"]);
  expect([filmKey("ArrowRight", "DIV"), filmKey("l", null), filmKey("ArrowLeft", "BUTTON"), filmKey("j", null)]).toEqual(["next", "next", "previous", "previous"]);
  expect([filmKey("ArrowRight", "INPUT"), filmKey("m", "INPUT"), filmKey("m", "DIV"), filmKey("M", null), filmKey("x", "DIV")]).toEqual([null, null, "mute", "mute", null]);
});

test("the score sits low under the narration, fades over the film's last two seconds and stays in step", () => {
  expect(bedVolume(FULL_MIX, 0, 60)).toBe(0.25);
  expect(bedVolume(FULL_MIX, 59, 60)).toBe(0.125);
  expect(bedVolume(FULL_MIX, 60, 60)).toBe(0);
  expect(bedVolume({ ...FULL_MIX, music: 0.4 }, 10, 60)).toBeCloseTo(0.1, 9);
  expect(bedVolume({ ...FULL_MIX, muted: true }, 10, 60)).toBe(0);
  expect([cueVolume(FULL_MIX), cueVolume({ ...FULL_MIX, effects: 0.5 }), cueVolume({ ...FULL_MIX, muted: true })]).toEqual([0.8, 0.4, 0]);
  expect(bedTime(130, 60)).toBe(10);
  expect([bedDrifted(10.5, 130, 60), bedDrifted(20, 130, 60), bedDrifted(59.9, 120.2, 60)]).toEqual([false, true, false]);
  const cue = sceneCue(score(), "s1.b1")!;
  expect([cueDue(cue, 0.4), cueDue(cue, 0.5)]).toEqual([false, true]);
  expect(scoreCredit(score())).toBe(scoreLine());
});

test("the score control is drawn only when the config offers it", () => {
  expect(filmScoreOffered(undefined)).toBe(false);
  expect(filmScoreOffered({ score: true })).toBe(true);
  expect(filmScoreOffered({ score: false })).toBe(false);
  const original = console.error;
  const logged: unknown[] = [];
  console.error = (...args: unknown[]) => void logged.push(...args);
  try {
    expect(filmScoreOffered({ score: "yes" })).toBe(false);
  } finally {
    console.error = original;
  }
  expect(String(logged[0])).toContain("answers/config film");
  expect(normaliseAskConfig({ film: { score: true } }).filmScore).toBe(true);
  expect(normaliseAskConfig({}).filmScore).toBe(false);
});

test("the stage plays a scene's own block with the sentence being read marked, and the ladder fills with the scene", () => {
  const all = scenes();
  const prose = withApp(createElement(FilmStage, { scene: all[2], progress: 0.1, mark: filmMark(all[2], 0.5) }));
  expect(attribute(prose, "film-scene", "data-kind")).toEqual(["prose"]);
  expect(attribute(prose, "answer-sentence", "data-listening")[0]).toBe("true");
  expect(prose).toContain('data-testid="listen-word">of</mark>');
  expect(shownText(prose)).toContain("Why the water matters");
  const ladder = (progress: number) => attribute(withApp(createElement(FilmStage, { scene: all[0], progress, mark: null })), "process-ladder", "data-reached");
  expect([ladder(0), ladder(0.5), ladder(1)]).toEqual([["1"], ["2"], ["4"]]);
});

test("in a film the reaction player steps with the scene and hides its own controls; reduced motion shows every step", () => {
  const block = phaseBBlock("reaction_player", "s4.b1");
  const inFilm = (progress: number, reduce: boolean) => withReading(createElement(FilmSceneProvider, { value: { progress } }, createElement(ReactionPlayerView, { block, reduce })));
  expect(attribute(inFilm(0.6, false), "reaction-player", "data-step")).toEqual(["3"]);
  expect(attribute(inFilm(0, false), "reaction-player", "data-step")).toEqual(["1"]);
  expect(inFilm(0.6, false)).not.toContain('data-testid="reaction-controls"');
  expect(attribute(inFilm(0.6, true), "reaction-player", "data-step")).toEqual(["all"]);
});

test("the controls say where the film is, and offer play, pause or play again", () => {
  const ref = createRef<HTMLButtonElement>();
  const timing = withReading(createElement(FilmTiming, { film: fakeFilm({ ...FILM_START, scene: 2, time: 0 }) }));
  expect(timing).toContain("Scene 3 of 4");
  expect(timing).toContain("0:12 of 0:33");
  expect(timing).toMatch(/aria-valuenow="37"/);
  const buttons = (clock: FilmClock, muted = false, load: Film["load"] = "ready") => withReading(createElement(FilmButtons, { film: fakeFilm(clock, load), muted, onMute: () => undefined, playRef: ref }));
  expect(attribute(buttons(FILM_START), "film-play", "aria-label")).toEqual(["Pause"]);
  expect(attribute(buttons({ ...FILM_START, playing: false }), "film-play", "aria-label")).toEqual(["Play"]);
  expect(attribute(buttons({ ...FILM_START, scene: 3, time: 6, playing: false, ended: true }), "film-play", "aria-label")).toEqual(["Play again"]);
  expect(attribute(buttons(FILM_START, true), "film-mute", "aria-pressed")).toEqual(["true"]);
  expect(attribute(buttons(FILM_START, false, "loading"), "film-play", "aria-disabled")).toEqual(["true"]);
  expect(attribute(buttons(FILM_START), "film-play", "aria-disabled")).toEqual([""]);
});

test("music and sound: a switch, then one volume per part of the score and the AI credit", () => {
  const off = withApp(createElement(FilmScoreControls, { score: { on: false, score: null, loading: false, error: null, toggle: () => undefined }, mix: FULL_MIX, onMix: () => undefined }));
  expect(off).toContain("Music and sound");
  expect(attribute(off, "film-score-toggle", "aria-checked")).toEqual(["false"]);
  expect(off).not.toContain('type="range"');
  const loading = withApp(createElement(FilmScoreControls, { score: { on: true, score: null, loading: true, error: null, toggle: () => undefined }, mix: FULL_MIX, onMix: () => undefined }));
  expect(loading).toContain("Preparing the music…");
  const on = withApp(createElement(FilmScoreControls, { score: { on: true, score: score(), loading: false, error: null, toggle: () => undefined }, mix: { ...FULL_MIX, music: 0.4 }, onMix: () => undefined }));
  expect(attribute(on, "film-score-toggle", "aria-checked")).toEqual(["true"]);
  expect(attribute(on, "film-music-volume", "value")).toEqual(["40"]);
  expect(attribute(on, "film-effects-volume", "value")).toEqual(["100"]);
  expect(on).toContain(scoreLine());
  const musicOnly = withApp(createElement(FilmScoreControls, { score: { on: true, score: { ...score(), cues: [] }, loading: false, error: null, toggle: () => undefined }, mix: FULL_MIX, onMix: () => undefined }));
  expect(musicOnly).not.toContain('data-testid="film-effects-volume"');
  expect(on).not.toContain('data-testid="film-score-failed"');
});

test("a score that fails to load turns the switch off and says why", () => {
  const failed = withApp(createElement(FilmScoreControls, { score: { on: false, score: null, loading: false, error: SCORE_FAILED, toggle: () => undefined }, mix: FULL_MIX, onMix: () => undefined }));
  expect(attribute(failed, "film-score-toggle", "aria-checked")).toEqual(["false"]);
  expect(attribute(failed, "film-score-failed", "role")).toEqual(["alert"]);
  expect(shownText(failed)).toContain("Couldn't load the music. Try again.");
});

test("mute silences the bed and the cues by muting them, not only by their volume", () => {
  const muted = filmLevels({ ...FULL_MIX, muted: true }, 10, 60);
  expect(muted).toEqual({ bed: { volume: 0, muted: true }, cue: { volume: 0, muted: true } });
  expect(filmLevels(FULL_MIX, 10, 60)).toEqual({ bed: { volume: 0.25, muted: false }, cue: { volume: 0.8, muted: false } });
  const audio = { volume: 1, muted: false };
  applyLevel(audio, muted.bed);
  expect(audio).toEqual({ volume: 0, muted: true });
  const sound = readRepo("frontend", "components", "answer", "film", "FilmSound.tsx");
  expect(sound.split("applyLevel(audio, { volume, muted }, node.current);")).toHaveLength(3);
  expect(sound).toContain("level={levels.bed}");
  expect(sound).toContain("level={levels.cue}");
});

test("where a browser fixes the element volume the bed and cues are levelled by one gain each", () => {
  const fixed = {
    get volume() {
      return 1;
    },
    set volume(value: number) {
      void value;
    }
  };
  expect(volumeIsFixed(fixed)).toBe(true);
  expect(volumeIsFixed({ volume: 1 })).toBe(false);
  const audio = { volume: 1, muted: false };
  const gain = { gain: { value: 1 } };
  applyLevel(audio, { volume: 0.2, muted: false }, gain);
  expect([audio.volume, gain.gain.value, audio.muted]).toEqual([1, 0.2, false]);
  applyLevel(audio, { volume: 0, muted: true }, gain);
  expect([audio.volume, gain.gain.value, audio.muted]).toEqual([1, 0, true]);
  const sound = readRepo("frontend", "components", "answer", "film", "FilmSound.tsx");
  expect(sound.split('crossOrigin={gain.routed ? "anonymous" : undefined}')).toHaveLength(3);
  expect(sound).toContain("createMediaElementSource(audio).connect(gain).connect(sound.destination)");
});

function finished(phase: ExplainerState["phase"]): ExplainerState {
  const explainer = document();
  return { ...emptyExplainer(explainer.question, "en"), phase, answerId: explainer.answerId, understood: explainer.understood, sections: sections(), sources: explainer.sources };
}

function view(state: ExplainerState, listenLanguages: string[]): string {
  const element = createElement(ExplainerView, {
    state,
    streaming: state.phase === "streaming",
    languages: [ENGLISH],
    depthLabel: "Expert",
    change: { parts: new Set<UnderstoodPart>(), onChange: () => undefined },
    listenLanguages,
    onFollowUp: null,
    onFreshResearch: null,
    filmScore: true
  });
  return withReading(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));
}

test("the ask screen hands the config's film offer through the explainer to the started film", () => {
  const ask = readRepo("frontend", "app", "(protected)", "ask", "page.tsx");
  const explainer = ask.slice(ask.indexOf("<ExplainerView"), ask.indexOf("/>", ask.indexOf("<ExplainerView")));
  expect(explainer).toContain("filmScore={config.filmScore}");
  expect(readRepo("frontend", "components", "answer", "ExplainerView.tsx")).toContain("scoreOffered={filmScore}");
  const started = (offer: unknown) => {
    const scoreOffered = normaliseAskConfig({ film: offer }).filmScore;
    const body = createElement(FilmPlayerBody, { answerId: document().answerId, language: ENGLISH, sections: sections(), lede: null, scoreOffered, playRef: createRef<HTMLButtonElement>() });
    return withReading(createElement(AuthProvider, null, createElement(ThemeProvider, null, body)));
  };
  expect(started({ score: true })).toContain('data-testid="film-score"');
  expect(started({ score: true })).toContain("Music and sound");
  expect(started({ score: false })).not.toContain('data-testid="film-score"');
  expect(started(undefined)).not.toContain('data-testid="film-score"');
});

test("Film is offered exactly where Listen is, and its code loads only when it starts", () => {
  expect(view(finished("done"), ["en"])).toContain('data-testid="film-start"');
  expect(view(finished("done"), ["en"])).toContain('data-testid="listen-start"');
  expect(view(finished("done"), [])).not.toContain('data-testid="film-start"');
  expect(view(finished("streaming"), ["en"])).not.toContain('data-testid="film-start"');
  expect(view({ ...finished("done"), answerId: null }, ["en"])).not.toContain('data-testid="film-start"');
  const header = withReading(
    createElement(ExplainerHeader, { understood: null, depthLabel: null, language: ENGLISH, change: { parts: new Set<UnderstoodPart>(), onChange: () => undefined }, shown: { translated: false, original: false, onShow: () => undefined }, onListen: null, onFresh: null, onFilm: () => undefined })
  );
  expect(header).toMatch(/data-testid="film-start"><svg[^]*<\/svg>Film<\/button>/);
  const eager = eagerModules("@/app/(protected)/ask/page");
  expect(eager.has("components/answer/ExplainerView.tsx")).toBe(false);
  expect(readRepo("frontend", "app", "(protected)", "ask", "page.tsx")).toContain('dynamic(() => import("@/components/answer/ExplainerView")');
  for (const file of [...eager, ...eagerModules("@/components/answer/ExplainerView")]) expect(file.startsWith("components/answer/film/"), file).toBe(false);
  expect(readRepo("frontend", "components", "answer", "ExplainerView.tsx")).toContain('import("@/components/answer/film/FilmPlayer")');
});
