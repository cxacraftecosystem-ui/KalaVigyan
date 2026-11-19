"use client";

import { useFilmScene } from "@/components/answer/FilmScene";
import { LadderStageCard } from "@/components/answer/LadderStageCard";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import type { ProcessLadderBlock } from "@/lib/explainerContract";
import { ladderReach } from "@/lib/explainerView";

export function ProcessLadder({ block }: { block: ProcessLadderBlock }) {
  const reduce = useAppReducedMotion();
  const film = useFilmScene();
  const count = block.stages.length;
  const shown = reduce || !film ? count : ladderReach(film.progress, count, false);

  return (
    <ol className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1" aria-label="Process steps" data-testid="process-ladder" data-reached={shown}>
      {block.stages.map((stage, index) => (
        <LadderStageCard key={stage.stageId} stage={stage} craft={block.craft} reached={index < shown} />
      ))}
    </ol>
  );
}
