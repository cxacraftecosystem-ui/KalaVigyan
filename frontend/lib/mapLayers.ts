import { apiFetch } from "@/lib/api";
import { MAP_LAYER_PATH, MAP_LAYERS_PATH, mapLayerListShape, mapLayerShape, type MapLayer, type MapLayerList } from "@/lib/regionContract";
import { checkedLayer } from "@/lib/regionView";
import { parseShape } from "@/lib/shape";

export const LAYER_PARAM = "layer";

export async function fetchMapLayers(): Promise<MapLayerList> {
  return parseShape(mapLayerListShape, await apiFetch<unknown>(MAP_LAYERS_PATH, {}, { revalidateFromHttpCache: true }));
}

export async function fetchMapLayer(id: string): Promise<MapLayer> {
  return checkedLayer(parseShape(mapLayerShape, await apiFetch<unknown>(MAP_LAYER_PATH(id), {}, { revalidateFromHttpCache: true })));
}

export function chosenLayerId(list: MapLayerList | null, requested: string | null): string | null {
  if (!list || !requested) return null;
  return list.layers.some((layer) => layer.id === requested) ? requested : null;
}
