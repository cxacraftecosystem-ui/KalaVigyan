"use client";

import { useMemo, useState } from "react";

import { useFilmScene } from "@/components/answer/FilmScene";
import { TimelineEntries, TimelineSlider, TimelineUndatedList } from "@/components/answer/journey/TimelineEntries";
import { TimelinePins } from "@/components/answer/journey/TimelinePins";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { INDIA_BOUNDS } from "@/components/map/indiaBounds";
import type { TimelineMapBlock } from "@/lib/explainerPlay";
import { sceneStep } from "@/lib/filmScenes";
import { boundaryNote } from "@/lib/placeView";
import { placedPlaces, reachedPlaces, routeLines, timelineEntries, timelineStops, timelineSummary } from "@/lib/timelineView";

const WITH_MAP = "grid min-w-0 grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-start";
const WITHOUT_MAP = "grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4";

export function TimelineMapView({ block, at, onChoose }: { block: TimelineMapBlock; at: number; onChoose: (index: number) => void }) {
  const entries = useMemo(() => timelineEntries(block), [block]);
  const stops = useMemo(() => timelineStops(entries), [entries]);
  const placed = useMemo(() => placedPlaces(block, INDIA_BOUNDS), [block]);
  const shown = Math.min(Math.max(0, at), Math.max(0, stops.length - 1));
  const year = stops[shown] ?? 0;
  const reached = useMemo(() => reachedPlaces(entries, year), [entries, year]);
  const routes = useMemo(() => routeLines(entries.filter((entry) => entry.yearFrom <= year), placed), [entries, placed, year]);
  const mapped = placed.length > 0;
  return (
    <div className={mapped ? WITH_MAP : WITHOUT_MAP} data-testid="timeline-map" data-year={year} role="group" aria-label={timelineSummary(block, entries)}>
      {mapped ? <TimelinePins placed={placed} reached={reached} routes={routes} boundary={boundaryNote(block.boundaryCaption, block.datasets)} /> : null}
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4">
        {stops.length > 1 ? <TimelineSlider entries={entries} stops={stops} at={shown} onChoose={onChoose} /> : null}
        <TimelineEntries block={block} entries={entries} placed={placed} year={year} />
        {block.undated && block.undated.length > 0 ? <TimelineUndatedList block={block} undated={block.undated} placed={placed} /> : null}
      </div>
    </div>
  );
}

export function TimelineMap({ block }: { block: TimelineMapBlock }) {
  const reduce = useAppReducedMotion();
  const film = useFilmScene();
  const count = useMemo(() => timelineStops(timelineEntries(block)).length, [block]);
  const [chosen, setChosen] = useState(count - 1);
  const at = sceneStep(chosen, count, film ? film.progress : null, reduce);
  return <TimelineMapView block={block} at={at} onChoose={setChosen} />;
}
