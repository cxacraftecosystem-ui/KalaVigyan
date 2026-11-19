"use client";

import { useId } from "react";
import { ArrowRight } from "lucide-react";

import { PIN_DISC, READING_PROSE } from "@/components/answer/place/figureMarks";
import { CitedText } from "@/components/answer/ProseBlockView";
import type { TimelineMapBlock } from "@/lib/explainerPlay";
import { entryState, stopLabel, yearSpanText, type PlacedPlace, type TimelineEntry, type TimelineEntryState } from "@/lib/timelineView";
import { cn } from "@/lib/utils";

const ENTRY_RULE: Record<TimelineEntryState, string> = {
  current: "border-s-ink-1",
  past: "border-s-transparent",
  later: "border-s-transparent"
};

export function TimelineSlider({ entries, stops, at, onChoose }: { entries: readonly TimelineEntry[]; stops: readonly number[]; at: number; onChoose: (index: number) => void }) {
  const id = useId();
  const label = stopLabel(entries, stops[at]);
  return (
    <div className="grid min-w-0 gap-1" data-testid="timeline-slider">
      <div className="flex min-w-0 items-baseline justify-between gap-3">
        <label htmlFor={id} className="font-ui text-label text-ink-2">
          Year
        </label>
        <span className="font-headline text-h3 text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]" data-testid="timeline-year">
          {label}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={0}
        max={stops.length - 1}
        step={1}
        value={at}
        aria-valuetext={label}
        onChange={(event) => onChoose(Number(event.currentTarget.value))}
        className="h-11 w-full min-w-0 cursor-pointer accent-indigo"
      />
      <div className="flex min-w-0 justify-between gap-3 font-ui text-caption text-ink-3 [font-variant-numeric:lining-nums_tabular-nums]" aria-hidden>
        <span>{stopLabel(entries, stops[0])}</span>
        <span>{stopLabel(entries, stops[stops.length - 1])}</span>
      </div>
    </div>
  );
}

function PlaceName({ name, pin }: { name: string; pin: number | null }) {
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      {pin === null ? null : (
        <span className={PIN_DISC} data-testid="timeline-entry-pin">
          <span className="sr-only">Pin </span>
          {pin}
        </span>
      )}
      <span className="min-w-0 break-words">{name}</span>
    </span>
  );
}

function EntryPlaces({ block, entry, pins }: { block: TimelineMapBlock; entry: TimelineEntry; pins: ReadonlyMap<number, number> }) {
  return (
    <span className="inline-flex min-w-0 flex-wrap items-center gap-1.5 font-ui text-label text-ink-2">
      {entry.places.map((place, index) => (
        <span key={`${entry.key}:${place}`} className="inline-flex min-w-0 items-center gap-1.5">
          {index > 0 ? (
            <>
              <ArrowRight className="h-3.5 w-3.5 shrink-0 text-ink-3 rtl:-scale-x-100" aria-hidden />
              <span className="sr-only">to</span>
            </>
          ) : null}
          <PlaceName name={block.places[place]?.name ?? ""} pin={pins.get(place) ?? null} />
        </span>
      ))}
    </span>
  );
}

export function TimelineEntries({ block, entries, placed, year }: { block: TimelineMapBlock; entries: readonly TimelineEntry[]; placed: readonly PlacedPlace[]; year: number }) {
  const pins = new Map(placed.map((place) => [place.index, place.pin]));
  return (
    <ol className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1" aria-label="Through time" data-testid="timeline-entries">
      {entries.map((entry) => {
        const state = entryState(entry, year);
        return (
          <li
            key={entry.key}
            aria-current={state === "current" ? "step" : undefined}
            className={cn("min-w-0 border-b border-s-2 border-b-rule py-3 ps-3 transition-colors duration-state sm:ps-4", ENTRY_RULE[state])}
            data-testid="timeline-entry"
            data-kind={entry.kind}
            data-state={state}
          >
            <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className={cn("font-ui text-h4 [font-variant-numeric:lining-nums_tabular-nums]", state === "later" ? "text-ink-3" : "text-ink-1")} data-testid="timeline-years">
                {yearSpanText(entry.yearFrom, entry.yearTo)}
              </span>
              <EntryPlaces block={block} entry={entry} pins={pins} />
            </div>
            <CitedText id={entry.sentence.id} sentences={[entry.sentence]} className={state === "later" ? "mt-1.5 max-w-measure font-reading text-body-sm text-ink-2" : `mt-1.5 ${READING_PROSE}`} />
          </li>
        );
      })}
    </ol>
  );
}
