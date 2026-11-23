import { headingView, sentenceView, type AnswerLanguage, type ShownText } from "@/lib/answerLanguages";
import type { LedeBlock } from "@/lib/explainerContract";
import type { SectionView } from "@/lib/explainerState";
import { blockSentences, type TextRange, type TypedBlock } from "@/lib/explainerView";
import { firstSentenceId, pendingBlocks, trackMark, wordRanges, type ListenMark, type ListenScript, type ListenTrack } from "@/lib/listen";

export const FILM_SCENE_SECONDS = { step: 4, picture: 3, block: 6 } as const;
export const PREVIOUS_RESTARTS_AFTER_SECONDS = 2;

export type FilmTrack = { at: number; start: number; track: ListenTrack };
export type FilmScene = { block: TypedBlock; section: SectionView | null; tracks: FilmTrack[]; start: number; seconds: number; pending: boolean };
export type FilmClock = { scene: number; time: number; playing: boolean; ended: boolean; take: number };
export type FilmAction =
  | { type: "play" | "pause" | "toggle" | "next" | "previous" }
  | { type: "tick"; seconds: number }
  | { type: "heard" | "trackEnded"; scene: number; time: number }
  | { type: "choose"; scene: number };
export type FilmCaption = ShownText & { mark: TextRange | null; narrated: boolean };
export type FilmKey = "toggle" | "next" | "previous" | "mute";

export const FILM_START: FilmClock = { scene: 0, time: 0, playing: true, ended: false, take: 0 };

const FORM_FIELDS: ReadonlySet<string> = new Set(["INPUT", "TEXTAREA", "SELECT"]);
const ACTIVATED_BY_SPACE: ReadonlySet<string> = new Set(["BUTTON", "A", "SUMMARY"]);
const KEYS: Readonly<Record<string, FilmKey>> = { k: "toggle", K: "toggle", ArrowRight: "next", l: "next", L: "next", ArrowLeft: "previous", j: "previous", J: "previous", m: "mute", M: "mute" };

export function holdSeconds(block: TypedBlock): number {
  if (block.kind === "reaction_player" || block.kind === "region_story") return FILM_SCENE_SECONDS.step * block.steps.length;
  if (block.kind === "images") return FILM_SCENE_SECONDS.picture * block.items.length;
  return FILM_SCENE_SECONDS.block;
}

function blockTracks(script: ListenScript | null, blockId: string): FilmTrack[] {
  const tracks: FilmTrack[] = [];
  let start = 0;
  (script?.tracks ?? []).forEach((track, at) => {
    if (track.blockId !== blockId) return;
    tracks.push({ at, start, track });
    start += track.durationSeconds;
  });
  return tracks;
}

function narrationSeconds(tracks: readonly FilmTrack[]): number {
  return tracks.reduce((sum, entry) => sum + entry.track.durationSeconds, 0);
}

export function ledeScene(lede: LedeBlock): TypedBlock {
  return { id: lede.id, kind: "prose", version: 1, reuse: null, sentences: lede.sentences };
}

export function filmScenes(sections: readonly SectionView[], script: ListenScript | null, drawn: (block: TypedBlock) => boolean, lede: LedeBlock | null = null): FilmScene[] {
  const scenes: FilmScene[] = [];
  const pending = new Set(pendingBlocks(script));
  let start = 0;
  const play = (block: TypedBlock, section: SectionView | null) => {
    const tracks = blockTracks(script, block.id);
    const seconds = tracks.length > 0 ? narrationSeconds(tracks) : holdSeconds(block);
    scenes.push({ block, section, tracks, start, seconds, pending: pending.has(block.id) });
    start += seconds;
  };
  if (lede) play(ledeScene(lede), null);
  for (const section of [...sections].sort((a, b) => a.order - b.order)) {
    for (const block of section.blocks as TypedBlock[]) {
      if (drawn(block) && !(block.kind === "simulation" && block.hidden)) play(block, section);
    }
  }
  return scenes;
}

export function filmDuration(scenes: readonly FilmScene[]): number {
  const last = scenes.at(-1);
  return last ? last.start + last.seconds : 0;
}

export function filmElapsed(scenes: readonly FilmScene[], clock: FilmClock): number {
  const scene = scenes[clock.scene];
  return scene ? scene.start + clock.time : 0;
}

export function sceneTrack(scene: FilmScene, time: number): FilmTrack | null {
  let current: FilmTrack | null = null;
  for (const entry of scene.tracks) if (current === null || entry.start <= time) current = entry;
  return current;
}

export function stepAt(progress: number, count: number): number {
  if (count <= 1) return 0;
  const clamped = Math.min(1, Math.max(0, Number.isFinite(progress) ? progress : 0));
  return Math.min(count - 1, Math.floor(clamped * count));
}

export function sceneStep(chosen: number, count: number, progress: number | null, reduce: boolean): number {
  return reduce || progress === null ? Math.min(Math.max(0, chosen), Math.max(0, count - 1)) : stepAt(progress, count);
}

export function sceneProgress(scene: FilmScene | undefined, time: number): number {
  if (!scene || !(scene.seconds > 0)) return 1;
  return Math.min(1, Math.max(0, time / scene.seconds));
}

function ended(clock: FilmClock, scenes: readonly FilmScene[]): FilmClock {
  const last = Math.max(0, scenes.length - 1);
  return { scene: last, time: scenes[last]?.seconds ?? 0, playing: false, ended: true, take: clock.take };
}

function following(clock: FilmClock, scenes: readonly FilmScene[]): FilmClock {
  if (clock.scene >= scenes.length - 1) return ended(clock, scenes);
  return { scene: clock.scene + 1, time: 0, playing: clock.playing, ended: false, take: clock.take + 1 };
}

function startOf(scene: number, clock: FilmClock, scenes: readonly FilmScene[]): FilmClock {
  return { scene: Math.min(Math.max(0, Math.trunc(scene)), Math.max(0, scenes.length - 1)), time: 0, playing: clock.playing, ended: false, take: clock.take + 1 };
}

function playing(clock: FilmClock, on: boolean): FilmClock {
  if (on && clock.ended) return { ...FILM_START, take: clock.take + 1 };
  return { ...clock, playing: on };
}

function moved(clock: FilmClock, time: number, scenes: readonly FilmScene[], advances: boolean): FilmClock {
  const scene = scenes[clock.scene];
  if (!scene) return clock;
  if (advances && time >= scene.seconds) return following(clock, scenes);
  return { ...clock, time: Math.min(Math.max(0, time), scene.seconds) };
}

export function filmStep(clock: FilmClock, action: FilmAction, scenes: readonly FilmScene[]): FilmClock {
  if (scenes.length === 0) return { ...clock, scene: 0, time: 0, playing: false, ended: true };
  switch (action.type) {
    case "play":
      return playing(clock, true);
    case "pause":
      return playing(clock, false);
    case "toggle":
      return playing(clock, !clock.playing);
    case "next":
      return following(clock, scenes);
    case "previous":
      return startOf(clock.time > PREVIOUS_RESTARTS_AFTER_SECONDS || clock.ended ? clock.scene : clock.scene - 1, clock, scenes);
    case "choose":
      return startOf(action.scene, clock, scenes);
    case "tick":
      return clock.playing && !clock.ended && !scenes[clock.scene]?.pending ? moved(clock, clock.time + action.seconds, scenes, true) : clock;
    case "heard":
    case "trackEnded":
      if (action.scene !== clock.scene || clock.ended) return clock;
      return moved(clock, action.time, scenes, action.type === "trackEnded");
  }
}

export function filmWaits(scene: FilmScene | undefined, clock: FilmClock): boolean {
  return scene !== undefined && scene.pending && clock.playing && !clock.ended;
}

export function filmMark(scene: FilmScene | undefined, time: number): ListenMark | null {
  const current = scene ? sceneTrack(scene, time) : null;
  return current ? trackMark(current.track, time - current.start) : null;
}

function titleCaption(scene: FilmScene, language: AnswerLanguage): FilmCaption {
  const section = scene.section;
  const shown = section
    ? headingView({ id: section.id, heading: section.title, original: section.original, sentences: [] }, language, false)
    : sentenceView(blockSentences(scene.block)[0], language, false);
  return { ...shown, mark: null, narrated: false };
}

export function filmCaption(scene: FilmScene, time: number, language: AnswerLanguage): FilmCaption {
  const current = sceneTrack(scene, time);
  if (!current) return titleCaption(scene, language);
  const mark = trackMark(current.track, time - current.start);
  const sentenceId = mark?.sentenceId ?? firstSentenceId(current.track);
  const sentence = blockSentences(scene.block).find((candidate) => candidate.id === sentenceId);
  if (!sentence) return titleCaption(scene, language);
  const shown = sentenceView(sentence, language, false);
  const range = mark ? (wordRanges(shown.text, mark.words)[mark.wordIndex] ?? null) : null;
  return { ...shown, mark: range, narrated: true };
}

export function filmKey(key: string, tagName: string | null): FilmKey | null {
  if (tagName && FORM_FIELDS.has(tagName)) return null;
  if (key === " " || key === "Spacebar") return tagName && ACTIVATED_BY_SPACE.has(tagName) ? null : "toggle";
  return KEYS[key] ?? null;
}

export function scenePosition(scene: number, count: number): string {
  return `Scene ${Math.min(scene + 1, count)} of ${count}`;
}
