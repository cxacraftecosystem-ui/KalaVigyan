"use client";

import { useCallback, useMemo } from "react";

import { failureMessage, useRemote, type Remote } from "@/components/hooks/useRemote";
import { ChoroplethLegend } from "@/components/map/ChoroplethLegend";
import { NO_DATA_TONE, type DistrictFill } from "@/components/map/DistrictLayer";
import { MapRetry } from "@/components/map/MapRetry";
import { paletteFill, rampFill } from "@/components/map/rampFills";
import { loadShapes, type DistrictShape } from "@/components/map/shapeGeometry";
import { districtSteps, layerPalette } from "@/lib/mapPalettes";
import { layerRamp, rampStep } from "@/lib/mapRamps";
import { fetchMapLayer } from "@/lib/mapLayers";
import { fetchDistricts } from "@/lib/profileContract";
import type { MapLayer } from "@/lib/regionContract";
import { layerFills } from "@/lib/regionView";

export type DistrictName = { name: string; state: string };
export type MapLayerData = { layer: Remote<MapLayer>; shapes: Remote<DistrictShape[]>; names: Remote<Map<number, DistrictName>> };

async function districtNames(): Promise<Map<number, DistrictName>> {
  const list = await fetchDistricts();
  return new Map(list.states.flatMap((state) => state.districts.map((district) => [district.lgd, { name: district.name, state: state.name }] as const)));
}

export function useMapLayer(layerId: string | null): MapLayerData {
  const loadLayer = useCallback(() => fetchMapLayer(layerId as string), [layerId]);
  const layer = useRemote(layerId ? loadLayer : null);
  const shapes = useRemote(layerId ? loadShapes : null);
  const names = useRemote(layerId ? districtNames : null);
  return { layer, shapes, names };
}

export function useLayerFill(data: MapLayer | null): DistrictFill {
  const fills = useMemo(() => (data ? layerFills(data) : null), [data]);
  return useCallback(
    (shape: DistrictShape) => {
      if (!fills || !data) return null;
      const index = fills.get(shape.lgd);
      return index === undefined ? NO_DATA_TONE : rampFill(layerRamp(data.layer), rampStep(index, data.classes.length));
    },
    [data, fills]
  );
}

export function usePaletteFill(data: MapLayer | null): DistrictFill {
  const shown = useMemo(() => (data ? { ramp: layerPalette(data.layer).ramp, steps: districtSteps(data).steps } : null), [data]);
  return useCallback(
    (shape: DistrictShape) => {
      const step = shown?.steps.get(shape.lgd);
      if (!shown) return null;
      return step === undefined ? NO_DATA_TONE : paletteFill(shown.ramp, step);
    },
    [shown]
  );
}

export function LayerStatus({ layer, shapes }: { layer: Remote<MapLayer>; shapes: Remote<DistrictShape[]> }) {
  const failure = layer.failure ?? shapes.failure;
  if (failure) {
    const retry = layer.failure ? layer.retry : shapes.retry;
    return <MapRetry message={failureMessage(failure, "This layer could not be drawn. Try again in a moment.")} onRetry={retry} className="mt-4" />;
  }
  if (!layer.data || !shapes.data) {
    return (
      <p role="status" className="mt-4 border-t border-rule pt-3 font-ui text-ui font-normal text-ink-3">
        Drawing the district values
      </p>
    );
  }
  return <ChoroplethLegend layer={layer.data} />;
}
