import { datasetShape, type RegionDataset } from "@/lib/regionContract";
import { integer, list, nullable, number, object, oneOf, text, type Shape } from "@/lib/shape";

export const LAYER_GEOMETRIES = ["POINT", "LINE", "SHAPE"] as const;

export type LayerGeometry = (typeof LAYER_GEOMETRIES)[number];
export type MapLayerPlan = {
  layerClass: string;
  simplifiedTo: number | null;
  valueProperty: string | null;
  variable: string | null;
  unit: string | null;
  method: string;
};
export type LayerBounds = { west: number; south: number; east: number; north: number };
export type LayerReview = {
  dataset: RegionDataset;
  plan: MapLayerPlan;
  geometry: LayerGeometry;
  features: number;
  byteSize: number;
  bounds: LayerBounds;
  checks: string[];
};

const planShape: Shape<MapLayerPlan> = object<MapLayerPlan>({
  layerClass: text,
  simplifiedTo: nullable(number),
  valueProperty: nullable(text),
  variable: nullable(text),
  unit: nullable(text),
  method: text
});

const boundsShape: Shape<LayerBounds> = object<LayerBounds>({ west: number, south: number, east: number, north: number });

export const layerReviewShape: Shape<LayerReview> = object<LayerReview>({
  dataset: datasetShape,
  plan: planShape,
  geometry: oneOf(LAYER_GEOMETRIES),
  features: integer,
  byteSize: integer,
  bounds: boundsShape,
  checks: list(text)
});
