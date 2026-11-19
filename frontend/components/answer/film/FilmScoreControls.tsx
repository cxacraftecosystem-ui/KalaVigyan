"use client";

import { useId } from "react";

import type { FilmScoreState } from "@/components/answer/film/useFilmScore";
import { Toggle } from "@/components/ui/Toggle";
import { percentOf, scoreCredit, type FilmMix } from "@/lib/filmSound";

function VolumeSlider({ label, value, onChange, testId }: { label: string; value: number; onChange: (value: number) => void; testId: string }) {
  const id = useId();
  const percent = percentOf(value);
  return (
    <div className="grid min-w-0 gap-0.5">
      <div className="flex min-w-0 items-baseline justify-between gap-3">
        <label htmlFor={id} className="font-ui text-label text-ink-2">
          {label}
        </label>
        <span className="font-ui text-caption tabular-nums text-ink-3">{percent}%</span>
      </div>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={5}
        value={percent}
        aria-valuetext={`${percent}%`}
        onChange={(event) => onChange(Number(event.currentTarget.value) / 100)}
        className="h-9 w-full min-w-0 cursor-pointer accent-indigo"
        data-testid={testId}
      />
    </div>
  );
}

export function FilmScoreControls({ score, mix, onMix }: { score: FilmScoreState; mix: FilmMix; onMix: (mix: FilmMix) => void }) {
  const status = score.score ? scoreCredit(score.score) : undefined;
  return (
    <div className="grid min-w-0 gap-2 border-t border-rule pt-3" data-testid="film-score">
      <Toggle label="Music and sound" status={status} checked={score.on} busy={score.loading} busyLabel="Preparing the music…" onChange={score.toggle} testId="film-score-toggle" />
      {score.on && score.score ? (
        <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          {score.score.music ? <VolumeSlider label="Music" value={mix.music} onChange={(music) => onMix({ ...mix, music })} testId="film-music-volume" /> : null}
          {score.score.cues.length > 0 ? <VolumeSlider label="Sound effects" value={mix.effects} onChange={(effects) => onMix({ ...mix, effects })} testId="film-effects-volume" /> : null}
        </div>
      ) : null}
      {score.error ? (
        <p role="alert" className="font-ui text-ui text-error" data-testid="film-score-failed">
          {score.error}
        </p>
      ) : null}
    </div>
  );
}
