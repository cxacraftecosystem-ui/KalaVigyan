"use client";

import type { StoryLayer } from "@/components/answer/place/useStoryLayer";
import { DatasetCredit } from "@/components/DatasetCredit";
import type { Remote } from "@/components/hooks/useRemote";
import { MapLegend, NO_READING_EXTRA } from "@/components/map/ChoroplethLegend";
import { LayerStatus } from "@/components/map/MapLayerView";
import type { DistrictShape } from "@/components/map/shapeGeometry";
import type { RegionStoryBlock } from "@/lib/explainerPlace";
import { layerColours } from "@/lib/mapRamps";
import type { MapLayer } from "@/lib/regionContract";
import { districtReading, layerCaption, layerClassLabels, layerSummary } from "@/lib/regionView";

export function storyScopeNote(shown: MapLayer): string {
  const count = Object.keys(shown.values).length;
  return `Shades compare the ${count} ${count === 1 ? "district" : "districts"} on this map.`;
}

export function outsideNote(layer: MapLayer): string {
  return `${layer.layer.title} is read for districts beyond this map. Choose another layer to shade it.`;
}

export function StoryReadings({ block, layer }: { block: RegionStoryBlock; layer: MapLayer }) {
  return (
    <dl className="mt-3 grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1 font-ui text-ui font-normal sm:grid-cols-[repeat(2,minmax(0,1fr))] sm:gap-x-6" aria-label={`${layer.layer.title} by district`} data-testid="story-readings">
      {block.districts.map((district) => (
        <div key={district.districtLgd} className="flex min-w-0 items-baseline justify-between gap-2 border-b border-rule py-1.5">
          <dt className="min-w-0 break-words text-ink-1">{district.name}</dt>
          <dd className="shrink-0 font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{districtReading(layer, district.districtLgd)}</dd>
        </div>
      ))}
    </dl>
  );
}

function ShownLegend({ shown }: { shown: MapLayer }) {
  const colours = layerColours(shown);
  const steps = layerClassLabels(shown).map((label, at) => ({ label, colour: colours[at] }));
  return (
    <div className="mt-4 grid gap-2">
      <MapLegend title={shown.layer.title} steps={steps} extras={[NO_READING_EXTRA]} note={storyScopeNote(shown)} caption={layerCaption(shown)} summary={layerSummary(shown)} />
      <DatasetCredit dataset={shown.dataset} />
    </div>
  );
}

export function StoryLayerReadout({ block, story, shown, shapes }: { block: RegionStoryBlock; story: StoryLayer; shown: MapLayer | null; shapes: Remote<DistrictShape[]> }) {
  if (!story.chosen) return null;
  const national = story.layer.data;
  if (shown && national && shapes.data) {
    return (
      <>
        <StoryReadings block={block} layer={national} />
        <ShownLegend shown={shown} />
      </>
    );
  }
  if (national && shapes.data) {
    return (
      <p role="status" className="mt-4 border-t border-rule pt-3 font-ui text-ui font-normal text-ink-2" data-testid="story-layer-empty">
        {outsideNote(national)}
      </p>
    );
  }
  return <LayerStatus layer={story.layer} shapes={shapes} />;
}
