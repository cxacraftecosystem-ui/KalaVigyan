import { bytes, countNoun } from "@/lib/format";
import type { LayerBounds, LayerGeometry, LayerReview, MapLayerPlan } from "@/lib/layerReviewContract";
import { codeLabel } from "@/lib/reviewQueueView";

export type LayerTerm = { term: string; value: string };

export const LAYER_CLASS_LABELS: Record<string, string> = {
  RIVERS: "Rivers and their centre lines",
  BASIN_REACHES: "A river basin's reaches",
  LAKES: "Lakes",
  COUNTRY_OUTLINES: "Country outlines",
  RELIEF_BANDS: "Relief bands",
  DISTRICT_SHAPES: "District shapes",
  POINT_SITES: "Point sites"
};

export const GEOMETRY_LABELS: Record<LayerGeometry, string> = { POINT: "Points", LINE: "Lines", SHAPE: "Shapes" };

export const LAYER_WRITES =
  "Approving says the layer is fit to ship: an engineer then adds it to the site's maps from the stored file and its record. Nothing is drawn before that, and rejecting keeps it private.";

export function layerClassLabel(code: string): string {
  return LAYER_CLASS_LABELS[code] ?? codeLabel(code);
}

export function simplificationLine(plan: MapLayerPlan): string {
  return plan.simplifiedTo === null ? "Not simplified" : `Simplified to ${plan.simplifiedTo} degree`;
}

export function valueLine(plan: MapLayerPlan): string {
  if (!plan.valueProperty) return "Geometry alone";
  const what = plan.variable ?? plan.valueProperty;
  return `${what}, in ${plan.unit ?? "the unit its dataset states"} (property ${plan.valueProperty})`;
}

export function boundsLine(bounds: LayerBounds): string {
  return `${bounds.west}° to ${bounds.east}° east, ${bounds.south}° to ${bounds.north}° north`;
}

export function sizeLine(review: Pick<LayerReview, "features" | "byteSize">): string {
  return `${countNoun(review.features, "feature")}, ${bytes(review.byteSize)}`;
}

export function layerTerms(review: LayerReview): LayerTerm[] {
  const { dataset, plan } = review;
  const edition = dataset.version ? `${dataset.edition}, version ${dataset.version}` : dataset.edition;
  const terms: (LayerTerm | null)[] = [
    { term: "Layer", value: layerClassLabel(plan.layerClass) },
    { term: "Geometry", value: GEOMETRY_LABELS[review.geometry] },
    { term: "Simplification", value: simplificationLine(plan) },
    { term: "Values", value: valueLine(plan) },
    { term: "Method", value: plan.method },
    { term: "File", value: sizeLine(review) },
    { term: "Spans", value: boundsLine(review.bounds) },
    { term: "Edition", value: edition },
    { term: "Period", value: dataset.period },
    { term: "Licence", value: dataset.licence },
    dataset.attribution ? { term: "Attribution", value: dataset.attribution } : null
  ];
  return terms.filter((term): term is LayerTerm => term !== null);
}
