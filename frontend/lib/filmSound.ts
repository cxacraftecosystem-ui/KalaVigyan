import type { FilmScore, ScoreCue } from "@/lib/filmScore";
import { formatDate } from "@/lib/format";

export const BED_GAIN = 0.25;
export const CUE_GAIN = 0.8;
export const BED_FADE_SECONDS = 2;
export const RESYNC_SECONDS = 1.5;
const PROBE_VOLUME = 0.5;

export type FilmMix = { muted: boolean; music: number; effects: number };

export const FULL_MIX: FilmMix = { muted: false, music: 1, effects: 1 };

function share(value: number): number {
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0;
}

export function bedVolume(mix: FilmMix, elapsed: number, total: number): number {
  if (mix.muted) return 0;
  const fade = share((total - elapsed) / BED_FADE_SECONDS);
  return share(mix.music) * BED_GAIN * fade;
}

export function cueVolume(mix: FilmMix): number {
  return mix.muted ? 0 : share(mix.effects) * CUE_GAIN;
}

export type SoundLevel = { volume: number; muted: boolean };

export type FilmLevels = { bed: SoundLevel; cue: SoundLevel };

export function filmLevels(mix: FilmMix, elapsed: number, total: number): FilmLevels {
  return { bed: { volume: bedVolume(mix, elapsed, total), muted: mix.muted }, cue: { volume: cueVolume(mix), muted: mix.muted } };
}

export type GainTarget = { gain: { value: number } };

export function applyLevel(audio: SoundLevel, level: SoundLevel, gain: GainTarget | null = null): void {
  audio.muted = level.muted;
  if (gain) gain.gain.value = level.volume;
  else audio.volume = level.volume;
}

export function volumeIsFixed(probe: { volume: number }): boolean {
  probe.volume = PROBE_VOLUME;
  const fixed = probe.volume !== PROBE_VOLUME;
  probe.volume = 1;
  return fixed;
}

export function bedTime(elapsed: number, durationSeconds: number): number {
  return durationSeconds > 0 ? Math.max(0, elapsed) % durationSeconds : 0;
}

export function bedDrifted(playedAt: number, expected: number, durationSeconds: number): boolean {
  const gap = Math.abs(playedAt - bedTime(expected, durationSeconds));
  return Math.min(gap, durationSeconds - gap) > RESYNC_SECONDS;
}

export function sceneCue(score: FilmScore | null, blockId: string): ScoreCue | null {
  return score?.cues.find((cue) => cue.blockId === blockId) ?? null;
}

export function cueDue(cue: ScoreCue, sceneTime: number): boolean {
  return sceneTime >= cue.offsetSeconds;
}

export function scoreCredit(score: FilmScore): string {
  return [score.label.text, score.label.models.join(", "), formatDate(score.label.generatedOn)].join(" · ");
}

export function percentOf(value: number): number {
  return Math.round(share(value) * 100);
}
