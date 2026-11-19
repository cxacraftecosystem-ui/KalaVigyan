"use client";

import { useState } from "react";
import { ChevronRight, ZoomIn, ZoomOut } from "lucide-react";

import { useFilmScene } from "@/components/answer/FilmScene";
import { ZoomLevelView } from "@/components/answer/journey/ZoomLevelView";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import type { ZoomStoryBlock } from "@/lib/explainerPlay";
import { stepAt } from "@/lib/filmScenes";
import { ZOOM_LEVEL_LABEL, zoomSummary } from "@/lib/zoomView";

type Choose = ((index: number) => void) | null;

function ZoomRail({ block, at, onChoose }: { block: ZoomStoryBlock; at: number; onChoose: Choose }) {
  return (
    <ol className="flex min-w-0 flex-wrap items-center gap-1.5" aria-label="Zoom levels" data-testid="zoom-rail">
      {block.levels.map((level, index) => {
        const label = ZOOM_LEVEL_LABEL[level.level];
        return (
          <li key={level.level} className="flex items-center gap-1.5">
            {index > 0 ? <ChevronRight className="h-3.5 w-3.5 text-ink-3 rtl:-scale-x-100" aria-hidden /> : null}
            {onChoose ? (
              <button type="button" aria-pressed={index === at} onClick={() => onChoose(index)} className="kv-chip" data-testid="zoom-rail-level">
                {label}
              </button>
            ) : (
              <span aria-current={index === at ? "step" : undefined} className="kv-chip" data-testid="zoom-rail-level">
                {label}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function ZoomSteps({ at, count, onChoose }: { at: number; count: number; onChoose: (index: number) => void }) {
  return (
    <ActionGroup align="start">
      <Button variant="quiet" size="sm" disabled={at === 0} onClick={() => onChoose(at - 1)}>
        <ZoomOut className="h-4 w-4" aria-hidden />
        Zoom out
      </Button>
      <Button variant="quiet" size="sm" disabled={at >= count - 1} onClick={() => onChoose(at + 1)}>
        <ZoomIn className="h-4 w-4" aria-hidden />
        Zoom in
      </Button>
    </ActionGroup>
  );
}

function ZoomList({ block }: { block: ZoomStoryBlock }) {
  return (
    <ol className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-8" aria-label="Zoom levels" data-testid="zoom-list">
      {block.levels.map((level, index) => (
        <li key={level.level} className="min-w-0">
          <ZoomLevelView block={block} index={index} moving />
        </li>
      ))}
    </ol>
  );
}

export function ZoomStoryView({ block, reduce, at, onChoose }: { block: ZoomStoryBlock; reduce: boolean; at: number; onChoose: Choose }) {
  const shown = Math.min(Math.max(0, at), block.levels.length - 1);
  if (reduce) {
    return (
      <div className="min-w-0" data-testid="zoom-story" data-motion="none" data-level="all" role="group" aria-label={zoomSummary(block)}>
        <ZoomList block={block} />
      </div>
    );
  }
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4" data-testid="zoom-story" data-motion="zoom" data-level={block.levels[shown].level} role="group" aria-label={zoomSummary(block)}>
      <ZoomRail block={block} at={shown} onChoose={onChoose} />
      <div className="min-w-0" aria-live="polite">
        <ZoomLevelView key={block.levels[shown].level} block={block} index={shown} moving />
      </div>
      {onChoose ? <ZoomSteps at={shown} count={block.levels.length} onChoose={onChoose} /> : null}
    </div>
  );
}

export function ZoomStory({ block }: { block: ZoomStoryBlock }) {
  const reduce = useAppReducedMotion();
  const film = useFilmScene();
  const [chosen, setChosen] = useState(0);
  const at = film ? stepAt(film.progress, block.levels.length) : chosen;
  return <ZoomStoryView block={block} reduce={reduce} at={at} onChoose={film ? null : setChosen} />;
}
