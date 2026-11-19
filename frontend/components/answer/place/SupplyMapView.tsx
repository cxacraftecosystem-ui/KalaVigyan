"use client";

import { useMemo } from "react";

import { lazyBlock } from "@/components/answer/lazyBlock";
import { PIN_DISC } from "@/components/answer/place/figureMarks";
import { MapPlaceholder } from "@/components/answer/place/MapPlaceholder";
import { CitedText } from "@/components/answer/ProseBlockView";
import { INDIA_BOUNDS } from "@/components/map/indiaBounds";
import type { SupplyMapBlock } from "@/lib/explainerPlace";
import { placedOrigins, supplyGroups, wikidataUrl, type SupplyGroup, type SupplyOrigin } from "@/lib/supplyView";

const SupplyPins = lazyBlock(() => import("@/components/answer/place/SupplyPins").then((module) => module.SupplyPins), <MapPlaceholder />);

function OriginItem({ origin }: { origin: SupplyOrigin }) {
  return (
    <li className="inline-flex min-w-0 max-w-full items-center gap-1.5 font-ui text-ui font-normal text-ink-1" data-testid="supply-origin">
      {origin.place ? (
        <span className={PIN_DISC} data-testid="supply-pin">
          <span className="sr-only">Pin </span>
          {origin.place.pin}
        </span>
      ) : null}
      <span className="min-w-0 break-words">{origin.origin}</span>
      {origin.wikidataId ? (
        <a href={wikidataUrl(origin.wikidataId)} target="_blank" rel="noopener noreferrer" className="kv-link shrink-0 font-ui text-caption">
          Wikidata
          <span className="sr-only"> (opens in a new tab)</span>
        </a>
      ) : null}
    </li>
  );
}

function MaterialRow({ group }: { group: SupplyGroup }) {
  return (
    <li className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2 border-t border-rule pt-3 sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)] sm:gap-x-6" data-testid="supply-material">
      <h3 className="min-w-0 break-words font-ui text-h4 text-ink-1">{group.material}</h3>
      <div className="grid min-w-0 gap-2">
        <ul className="flex min-w-0 flex-wrap gap-x-4 gap-y-1.5" aria-label={`Where ${group.material} comes from`}>
          {group.origins.map((origin) => (
            <OriginItem key={origin.key} origin={origin} />
          ))}
        </ul>
        {group.sentences.map((sentence) => (
          <CitedText key={sentence.id} id={sentence.id} sentences={[sentence]} className="max-w-measure font-reading text-body-sm text-ink-1" />
        ))}
      </div>
    </li>
  );
}

export function SupplyMapView({ block }: { block: SupplyMapBlock }) {
  const groups = useMemo(() => supplyGroups(block, INDIA_BOUNDS), [block]);
  const placed = useMemo(() => placedOrigins(groups), [groups]);
  return (
    <div className={placed.length > 0 ? "grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start lg:gap-10" : "min-w-0"} data-testid="supply-map">
      <ul className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3 border-b border-rule pb-3">
        {groups.map((group) => (
          <MaterialRow key={group.key} group={group} />
        ))}
      </ul>
      {placed.length > 0 ? <SupplyPins origins={placed} /> : null}
    </div>
  );
}
