"use client";

import { useMemo, useState } from "react";
import { Pause, Play, RotateCcw, SkipBack, SkipForward } from "lucide-react";

import { useFilmScene } from "@/components/answer/FilmScene";
import { ReactionStepList } from "@/components/answer/matter/ReactionStepList";
import { SpeciesCast } from "@/components/answer/matter/SpeciesCast";
import { usePlayback, type PlaybackControls } from "@/components/answer/matter/usePlayback";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/IconButton";
import { reactionNotes, type ReactionPlayerBlock, type ReactionStep } from "@/lib/explainerMatter";
import { stepAt } from "@/lib/filmScenes";
import { carriedKeys, playable, reactionCast, stepPosition, stepRoles, type PlaybackAction } from "@/lib/reactionPlayer";

const ICON = "h-4 w-4";

function PlayButton({ playback, atEnd }: { playback: PlaybackControls; atEnd: boolean }) {
  if (playback.playing) {
    return (
      <Button variant="quiet" size="sm" className="min-w-28" onClick={() => playback.send({ type: "pause" })} data-testid="reaction-pause">
        <Pause className={ICON} aria-hidden />
        Pause
      </Button>
    );
  }
  return (
    <Button variant="quiet" size="sm" className="min-w-28" onClick={() => playback.send({ type: "play" })} data-testid="reaction-play">
      {atEnd ? <RotateCcw className={ICON} aria-hidden /> : <Play className={ICON} aria-hidden />}
      {atEnd ? "Play again" : "Play"}
    </Button>
  );
}

function PlayerControls({ playback, count }: { playback: PlaybackControls; count: number }) {
  const atEnd = playback.at >= count - 1;
  return (
    <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-rule pt-3" data-testid="reaction-controls">
      <span className="font-ui text-label text-ink-2 [font-variant-numeric:lining-nums_tabular-nums]" aria-live="polite">
        {stepPosition(playback.at, count)}
      </span>
      <div role="toolbar" aria-label="Reaction playback" className="flex items-center gap-2">
        <IconButton label="Previous step" edge icon={<SkipBack className={ICON} />} onClick={() => playback.send({ type: "previous" })} disabled={playback.at === 0} />
        <PlayButton playback={playback} atEnd={atEnd} />
        <IconButton label="Next step" edge icon={<SkipForward className={ICON} />} onClick={() => playback.send({ type: "next" })} disabled={atEnd} />
      </div>
    </div>
  );
}

function useTouchedPlayback(count: number, running: boolean): PlaybackControls & { touched: boolean } {
  const playback = usePlayback(count, running);
  const [touched, setTouched] = useState(false);
  const send = (action: PlaybackAction) => {
    setTouched(true);
    playback.send(action);
  };
  return { ...playback, send, touched };
}

export function ReactionPlayerView({ block, reduce }: { block: ReactionPlayerBlock; reduce: boolean }) {
  const count = block.steps.length;
  const interactive = playable(count, reduce);
  const film = useFilmScene();
  const playback = useTouchedPlayback(count, interactive && film === null);
  const cast = useMemo(() => reactionCast(block.steps), [block.steps]);
  const at = film ? stepAt(film.progress, count) : playback.at;
  const open = interactive ? at : null;
  return (
    <div className="kv-figure grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3" data-testid="reaction-player" data-step={open === null ? "all" : String(open + 1)}>
      {interactive ? (
        <>
          <SpeciesCast cast={cast} roles={stepRoles(block.steps[at] ?? null)} carried={carriedKeys(block.steps, at)} />
          {film ? null : <PlayerControls playback={playback} count={count} />}
        </>
      ) : null}
      <ReactionStepList
        steps={block.steps}
        open={open}
        animate={!reduce && (playback.touched || film !== null)}
        onChoose={(index) => playback.send({ type: "choose", index })}
        notesFor={(step: ReactionStep) => reactionNotes(block, step.reactionId)}
      />
    </div>
  );
}

export function ReactionPlayer({ block }: { block: ReactionPlayerBlock }) {
  const reduce = useAppReducedMotion();
  return <ReactionPlayerView block={block} reduce={reduce} />;
}
