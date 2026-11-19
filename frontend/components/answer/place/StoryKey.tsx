"use client";

import { saltInView, type StoryGeometry } from "@/components/answer/place/storyGeometry";
import type { StoryLayer } from "@/components/answer/place/useStoryLayer";
import { LegendExtras, placeExtra, SALT_EXTRA, type LegendExtra } from "@/components/map/ChoroplethLegend";
import type { RegionStoryBlock } from "@/lib/explainerPlace";
import { riverLabel } from "@/lib/regionStory";

export const PLACE_KEY = "Districts in this story";

function RiverMark() {
  return (
    <svg width={18} height={12} aria-hidden className="shrink-0 [forced-color-adjust:none]">
      <path d="M1 9 C6 2 11 11 17 3" fill="none" strokeWidth={2} strokeLinecap="round" stroke="var(--map-river)" />
    </svg>
  );
}

export function keyExtras(geometry: StoryGeometry, layered: boolean): LegendExtra[] {
  const extras = layered ? [] : [placeExtra(PLACE_KEY)];
  return saltInView(geometry.view) ? [...extras, SALT_EXTRA] : extras;
}

export function StoryKey({ block, geometry, layered }: { block: RegionStoryBlock; geometry: StoryGeometry; layered: boolean }) {
  const extras = keyExtras(geometry, layered);
  if (extras.length === 0 && !geometry.river) return null;
  return (
    <ul className="mt-3 grid gap-x-5 gap-y-1.5 font-ui text-caption text-ink-2 sm:grid-cols-[repeat(2,minmax(0,1fr))]" data-testid="story-key">
      {geometry.river ? (
        <li className="inline-flex items-center gap-2" data-key="river">
          <RiverMark />
          {riverLabel(block)}
        </li>
      ) : null}
      <LegendExtras extras={extras} />
    </ul>
  );
}

export function StoryLayerPicker({ story, base }: { story: StoryLayer; base: string }) {
  if (story.offered.length === 0) return null;
  const options = [{ id: null, label: base }, ...story.offered.map((layer) => ({ id: layer.id, label: layer.title }))];
  return (
    <div role="group" aria-label="Map layer" className="flex min-w-0 flex-wrap gap-2" data-testid="story-layers">
      {options.map((option) => (
        <button key={option.id ?? "story"} type="button" aria-pressed={story.chosen === option.id} onClick={() => story.choose(option.id)} className="kv-chip max-w-full whitespace-normal text-start">
          {option.label}
        </button>
      ))}
    </div>
  );
}
