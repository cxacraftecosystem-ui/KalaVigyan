"use client";

import { useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useRemote } from "@/components/hooks/useRemote";
import { DistrictPanel, useDistrict } from "@/components/map/DistrictPanel";
import { LayerPicker } from "@/components/map/LayerPicker";
import { MapLayerFigure } from "@/components/map/MapLayerFigure";
import { useMapLayer } from "@/components/map/MapLayerView";
import { MapStatesFigure } from "@/components/map/MapStatesFigure";
import { PhysicalLayerFigure } from "@/components/map/physical/PhysicalLayerFigure";
import { StateCraftsList } from "@/components/map/StateCraftsList";
import { useStateRanking } from "@/components/map/useStateRanking";
import { Toggle } from "@/components/ui/Toggle";
import { placedCountLine } from "@/lib/craftCatalogue";
import { DISTRICT_PARAM } from "@/lib/districtView";
import { placeMarkers } from "@/lib/mapFamilies";
import { chosenLayerId, fetchMapLayers, LAYER_PARAM } from "@/lib/mapLayers";
import { physicalLayerId } from "@/lib/mapPhysical";
import { positiveParam } from "@/lib/searchParams";

export const MAP_TITLE = "Map";
export const PLACES_TOGGLE = "Craft places";

export function placesNote(count: number): string {
  return `${count.toLocaleString("en-IN")} ${count === 1 ? "place" : "places"} where the listed crafts are practised, drawn over the layer as discs`;
}

function useParamWriter() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  return (param: string, value: string | null) => {
    const search = new URLSearchParams(params.toString());
    if (value) search.set(param, value);
    else search.delete(param);
    if (param === LAYER_PARAM) search.delete(DISTRICT_PARAM);
    const query = search.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };
}

export function CraftsMapScreen() {
  const params = useSearchParams();
  const write = useParamWriter();
  const ranking = useStateRanking();
  const layers = useRemote(fetchMapLayers);
  const requested = params.get(LAYER_PARAM);
  const physical = physicalLayerId(requested);
  const layerId = physical ? null : chosenLayerId(layers.data, requested);
  const [chosenPlaces, setShowPlaces] = useState<boolean | null>(null);
  const showPlaces = chosenPlaces ?? physical === null;
  const layerData = useMapLayer(layerId);
  const districtLgd = layerId ? positiveParam(params.get(DISTRICT_PARAM)) : null;
  const district = useDistrict(districtLgd);
  const markers = useMemo(() => placeMarkers(ranking.points.data ?? [], ranking.catalogue), [ranking.points.data, ranking.catalogue]);
  const pick = { lgd: districtLgd, onPick: (lgd: number | null) => write(DISTRICT_PARAM, lgd === null ? null : String(lgd)) };
  const boundary = layers.data?.boundary ?? null;
  const shown = showPlaces ? markers : [];
  const placesToggle = markers.length ? <Toggle label={PLACES_TOGGLE} description={placesNote(markers.length)} checked={showPlaces} onChange={setShowPlaces} className="border-b border-rule" testId="places-toggle" /> : null;

  return (
    <article className="grid min-w-0 gap-8 pb-section" data-testid="crafts-map">
      <header className="grid gap-6 pt-8 md:pt-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end lg:gap-16">
        <div className="min-w-0">
          <p className="kicker">The atlas</p>
          <h1 className="mt-3 font-headline text-h1 text-ink-1">{MAP_TITLE}</h1>
          {ranking.catalogue ? <p className="mt-4 max-w-[44ch] font-reading text-lede text-ink-2">{placedCountLine(ranking.catalogue)}</p> : null}
        </div>
        <LayerPicker list={layers.data} value={physical ?? layerId} onChange={(id) => write(LAYER_PARAM, id)} />
      </header>
      {physical ? (
        <PhysicalLayerFigure id={physical} markers={shown} boundary={boundary} controls={placesToggle} />
      ) : layerId ? (
        <MapLayerFigure data={layerData} markers={shown} boundary={boundary} pick={pick} controls={placesToggle} />
      ) : (
        <MapStatesFigure ranking={ranking} boundary={boundary} />
      )}
      {districtLgd !== null ? <DistrictPanel district={district} onClose={() => pick.onPick(null)} /> : null}
      {!layerId && !physical && ranking.lists ? <StateCraftsList lists={ranking.lists} /> : null}
    </article>
  );
}
