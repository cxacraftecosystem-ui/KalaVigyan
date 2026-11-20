import type { StoryGeometry } from "@/components/answer/place/storyGeometry";
import { NO_DATA_TONE, type DistrictFill } from "@/components/map/DistrictLayer";
import { paletteFill } from "@/components/map/rampFills";
import type { DistrictShape } from "@/components/map/shapeGeometry";
import { layerInView } from "@/lib/layerClasses";
import { districtSteps, layerPalette } from "@/lib/mapPalettes";
import type { MapLayer } from "@/lib/regionContract";

export function storyLayerInView(geometry: StoryGeometry, layer: MapLayer): MapLayer | null {
  return layerInView(
    layer,
    geometry.context.map((shape) => shape.lgd)
  );
}

export function shownLayerFill(shown: MapLayer): DistrictFill {
  const { ramp } = layerPalette(shown.layer);
  const { steps } = districtSteps(shown);
  return (shape: DistrictShape) => {
    const step = steps.get(shape.lgd);
    return step === undefined ? NO_DATA_TONE : paletteFill(ramp, step);
  };
}

export function storyLayerFill(geometry: StoryGeometry, layer: MapLayer): DistrictFill {
  const shown = storyLayerInView(geometry, layer);
  return shown ? shownLayerFill(shown) : () => NO_DATA_TONE;
}
