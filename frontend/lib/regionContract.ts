import { craftLinkShape, HTTPS_URL, sourceRefShape, storedLevelShape, type CraftLink, type StoredLevel } from "@/lib/answerShapes";
import { boolean, dictionary, integer, list, matching, nullable, number, object, oneOf, optional, text, type Shape } from "@/lib/shape";
import type { SourceRef } from "@/lib/types";

export const CRAFT_REGION_PATH = (slug: string) => `/crafts/${encodeURIComponent(slug)}/region`;
export const MAP_LAYERS_PATH = "/map/layers";
export const BOUNDARY_DATASET_CODE = "DR_DISTRICT_SHAPES";
export const MAP_LAYER_PATH = (id: string) => `/map/layers/${encodeURIComponent(id)}`;

export const REGION_FACETS = ["SOIL", "CLIMATE", "WATER", "FOREST", "LAND_COVER", "TERRAIN", "GEOLOGY"] as const;
export const ENV_STATS = [
  "DISTRICT_MEAN",
  "DISTRICT_P10",
  "DISTRICT_P90",
  "UNCERTAINTY_Q05_MEAN",
  "UNCERTAINTY_Q95_MEAN",
  "SHARE",
  "CLASS",
  "NORMAL",
  "DISTRICT_MIN",
  "DISTRICT_MAX",
  "TOTAL",
  "DENSITY",
  "DISTANCE",
  "COUNT",
  "TREND_PER_DECADE",
  "TREND_P_VALUE"
] as const;
export const AGGREGATIONS = ["DISTRICT", "STATE_AREA_MEAN", "STATE_SUM", "STATE_MIN", "STATE_MAX"] as const;
export const PLACE_SCOPES = ["DISTRICT", "STATE"] as const;
export const PLACE_BASES = ["CRAFT_LOCATION", "MASTER_LIST"] as const;
export const INHERITED_REASON = "NO_DISTRICT_POLYGON";

export type RegionFacetName = (typeof REGION_FACETS)[number];
export type PlaceScope = (typeof PLACE_SCOPES)[number];
export type RegionDataset = {
  code: string;
  title: string;
  publisher: string | null;
  edition: string;
  period: string;
  nativeResolution: string;
  licence: string;
  licenceUrl: string | null;
  attribution: string | null;
  citation: string | null;
  url: string | null;
  version?: string;
  crs?: string;
  redistributable?: boolean;
  doi?: string | null;
  landingUrl?: string;
  readOn?: string;
  sha256?: string;
};
export type RegionValue = {
  datasetCode: string;
  variable: string;
  depth: string | null;
  period: string;
  stat: (typeof ENV_STATS)[number];
  aggregation: (typeof AGGREGATIONS)[number];
  value: number | null;
  valueText: string | null;
  unit: string;
  resolution: string;
  method: string | null;
  districtCount: number | null;
  districtTotal: number | null;
};
export type RegionFacet = { facet: RegionFacetName; values: RegionValue[] };
export type PlaceBasis = { kind: (typeof PLACE_BASES)[number]; sourceId: string | null; label: string; level: StoredLevel };
export type RegionPlace = {
  key: string;
  scope: PlaceScope;
  stateLgd: number;
  stateName: string;
  districtLgd: number | null;
  districtName: string | null;
  placeLabel: string;
  basis: PlaceBasis;
  valuesFrom: PlaceScope;
  inheritedReason: string | null;
  facets: RegionFacet[];
};
export type CraftRegion = { schemaVersion: 1; craft: CraftLink; places: RegionPlace[]; datasets: RegionDataset[]; sources: SourceRef[] };
export type BoundaryNote = { caption: string; dataset: RegionDataset };
export type MapLayerSummary = {
  id: string;
  facet: RegionFacetName;
  title: string;
  datasetCode: string;
  variable: string;
  depth: string | null;
  period: string;
  stat: (typeof ENV_STATS)[number];
  unit: string;
};
export type MapLayerList = { layers: MapLayerSummary[]; datasets: RegionDataset[]; boundary: BoundaryNote };
export type LayerClass = { min: number; max: number };
export type MapLayer = {
  layer: MapLayerSummary;
  dataset: RegionDataset;
  resolution: string;
  classes: LayerClass[];
  values: Record<string, number>;
  version: string;
  boundary: BoundaryNote;
};

const DEPTH = nullable(matching(/^\d+-\d+cm$/, "a depth such as 0-5cm"));
const facetShape = oneOf(REGION_FACETS);

export const datasetShape: Shape<RegionDataset> = object<RegionDataset>({
  code: text,
  title: text,
  publisher: nullable(text),
  edition: text,
  period: text,
  nativeResolution: text,
  licence: text,
  licenceUrl: nullable(HTTPS_URL),
  attribution: nullable(text),
  citation: nullable(text),
  url: nullable(HTTPS_URL),
  version: optional(text),
  crs: optional(text),
  redistributable: optional(boolean),
  doi: optional(nullable(text)),
  landingUrl: optional(HTTPS_URL),
  readOn: optional(text),
  sha256: optional(text)
});

const valueShape: Shape<RegionValue> = object<RegionValue>({
  datasetCode: text,
  variable: text,
  depth: DEPTH,
  period: text,
  stat: oneOf(ENV_STATS),
  aggregation: oneOf(AGGREGATIONS),
  value: nullable(number),
  valueText: nullable(text),
  unit: text,
  resolution: text,
  method: nullable(text),
  districtCount: nullable(integer),
  districtTotal: nullable(integer)
});

export const placeBasisShape: Shape<PlaceBasis> = object<PlaceBasis>({
  kind: oneOf(PLACE_BASES),
  sourceId: nullable(text),
  label: text,
  level: storedLevelShape
});

export const regionFacetShape: Shape<RegionFacet> = object<RegionFacet>({ facet: facetShape, values: list(valueShape, 1) });

const placeShape: Shape<RegionPlace> = object<RegionPlace>({
  key: matching(/^(district|state)-[1-9]\d*$/, "a place key"),
  scope: oneOf(PLACE_SCOPES),
  stateLgd: integer,
  stateName: text,
  districtLgd: nullable(integer),
  districtName: nullable(text),
  placeLabel: text,
  basis: placeBasisShape,
  valuesFrom: oneOf(PLACE_SCOPES),
  inheritedReason: nullable(text),
  facets: list(regionFacetShape)
});

const boundaryShape: Shape<BoundaryNote> = object<BoundaryNote>({ caption: text, dataset: datasetShape });

const layerSummaryShape: Shape<MapLayerSummary> = object<MapLayerSummary>({
  id: matching(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "a layer id"),
  facet: facetShape,
  title: text,
  datasetCode: text,
  variable: text,
  depth: DEPTH,
  period: text,
  stat: oneOf(ENV_STATS),
  unit: text
});

export const craftRegionShape: Shape<CraftRegion> = object<CraftRegion>({
  schemaVersion: oneOf([1] as const),
  craft: craftLinkShape,
  places: list(placeShape),
  datasets: list(datasetShape),
  sources: list(sourceRefShape)
});

export const mapLayerListShape: Shape<MapLayerList> = object<MapLayerList>({
  layers: list(layerSummaryShape),
  datasets: list(datasetShape),
  boundary: boundaryShape
});

export const mapLayerShape: Shape<MapLayer> = object<MapLayer>({
  layer: layerSummaryShape,
  dataset: datasetShape,
  resolution: text,
  classes: list(object<LayerClass>({ min: number, max: number }), 1),
  values: dictionary(/^[1-9]\d*$/, number),
  version: matching(/^[0-9a-f]{64}$/, "a sha256"),
  boundary: boundaryShape
});

export function layerClassOf(layer: MapLayer, value: number): number {
  const last = layer.classes.length - 1;
  const index = layer.classes.findIndex((band, position) => value >= band.min && (value < band.max || (position === last && value <= band.max)));
  if (index < 0) throw new RangeError(`${value} is outside layer ${layer.layer.id}`);
  return index;
}
