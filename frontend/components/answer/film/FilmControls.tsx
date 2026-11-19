"use client";

import type { RefObject } from "react";
import { Pause, Play, RotateCcw, SkipBack, SkipForward, Volume2, VolumeX } from "lucide-react";

import type { Film } from "@/components/answer/film/useFilm";
import { IconButton } from "@/components/ui/IconButton";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { scenePosition } from "@/lib/filmScenes";
import { formatClock } from "@/lib/format";

const MAIN = "grid h-14 w-14 shrink-0 place-items-center rounded-full bg-indigo text-indigo-on transition-colors duration-state hover:bg-indigo-hover aria-disabled:cursor-wait aria-disabled:bg-sunk aria-disabled:text-ink-3";

function MainButton({ film, playRef }: { film: Film; playRef: RefObject<HTMLButtonElement | null> }) {
  const { clock } = film;
  const loading = film.load === "loading";
  const label = clock.ended ? "Play again" : clock.playing ? "Pause" : "Play";
  return (
    <button ref={playRef} type="button" className={MAIN} aria-label={label} aria-disabled={film.load !== "ready" || undefined} onClick={() => film.send({ type: "toggle" })} data-testid="film-play">
      {loading ? (
        <span className="kv-spin" aria-hidden />
      ) : clock.ended ? (
        <RotateCcw className="h-6 w-6 rtl:-scale-x-100" aria-hidden />
      ) : clock.playing ? (
        <Pause className="h-6 w-6" aria-hidden />
      ) : (
        <Play className="h-6 w-6 rtl:-scale-x-100" aria-hidden />
      )}
    </button>
  );
}

export function FilmTiming({ film }: { film: Film }) {
  const percent = film.total > 0 ? Math.round((Math.min(film.elapsed, film.total) / film.total) * 100) : 0;
  return (
    <div className="grid min-w-0 gap-1.5" data-testid="film-timing">
      <ProgressBar percent={percent} role="progressbar" aria-label="Played" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} className="h-1.5" />
      <div className="flex min-w-0 justify-between gap-3 font-ui text-caption tabular-nums text-ink-3">
        <span>{film.scenes.length > 0 ? scenePosition(film.clock.scene, film.scenes.length) : null}</span>
        <span>
          {formatClock(film.elapsed)} of {formatClock(film.total)}
        </span>
      </div>
    </div>
  );
}

export function FilmButtons({ film, muted, onMute, playRef }: { film: Film; muted: boolean; onMute: () => void; playRef: RefObject<HTMLButtonElement | null> }) {
  const ready = film.load === "ready";
  return (
    <div className="flex min-w-0 items-center justify-center gap-3" role="toolbar" aria-label="Film" data-testid="film-buttons">
      <IconButton label="Previous scene" icon={<SkipBack className="rtl:-scale-x-100" />} edge disabled={!ready} onClick={() => film.send({ type: "previous" })} />
      <MainButton film={film} playRef={playRef} />
      <IconButton label="Next scene" icon={<SkipForward className="rtl:-scale-x-100" />} edge disabled={!ready || film.clock.ended} onClick={() => film.send({ type: "next" })} />
      <IconButton label="Mute" icon={muted ? <VolumeX /> : <Volume2 />} edge aria-pressed={muted} onClick={onMute} data-testid="film-mute" />
    </div>
  );
}
