import { UUID } from "@/lib/answerShapes";
import { envelope, explainerSentenceShape, TERM_KEY, WIKIDATA_ID, type BlockEnvelope, type ExplainerSentence } from "@/lib/explainerBlockBase";
import { datasetShape, type RegionDataset } from "@/lib/regionContract";
import { integer, list, matching, nullable, number, object, oneOf, ShapeError, text, type Shape } from "@/lib/shape";

export const SEASONS = ["MONSOON", "WINTER", "SUMMER"] as const;
export const HYDRORIVERS_DATASET_CODE = "HYDRORIVERS_1_0";
export const RIVER_BASIN_PATH = (mainRiv: number) => `/rivers/${mainRiv}`;
export const RIVER_REACHES_OBJECT = "reaches";

export type Season = (typeof SEASONS)[number];
export type DistrictRef = { districtLgd: number; name: string; stateName: string };
export type RiverPath = { datasetCode: typeof HYDRORIVERS_DATASET_CODE; mainRiv: number; reachIds: number[]; districtLgds: number[]; name: string | null };
export type StoryStep = { districtLgd: number | null; sentence: ExplainerSentence };
export type RegionStoryBlock = BlockEnvelope<"region_story"> & {
  river: RiverPath | null;
  districts: DistrictRef[];
  steps: StoryStep[];
  layers: string[];
  datasets: RegionDataset[];
  boundaryCaption: string;
};
export type MapLayerBlock = BlockEnvelope<"map_layer"> & {
  layer: string;
  layerVersion: string;
  title: string;
  datasets: RegionDataset[];
  highlighted: number[];
  boundaryCaption: string;
};
export type SeasonRow = { stageId: string | null; label: string; months: number[]; season: Season | null; sentence: ExplainerSentence };
export type MonthlyRain = { district: DistrictRef; datasetCode: string; period: string; millimetres: number[] };
export type SeasonsBlock = BlockEnvelope<"seasons"> & { rows: SeasonRow[]; rainfall: MonthlyRain | null; datasets: RegionDataset[] };
export type SupplyLink = {
  material: string;
  materialId: string | null;
  termKey: string | null;
  origin: string;
  wikidataId: string | null;
  latitude: number | null;
  longitude: number | null;
  sentence: ExplainerSentence;
};
export type SupplyMapBlock = BlockEnvelope<"supply_map"> & { links: SupplyLink[] };

const LAYER_ID = matching(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "a layer id");
const month = oneOf([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const);

const riverShape: Shape<RiverPath> = object<RiverPath>({
  datasetCode: oneOf([HYDRORIVERS_DATASET_CODE] as const),
  mainRiv: integer,
  reachIds: list(integer, 1),
  districtLgds: list(integer),
  name: nullable(text)
});

export const districtShape: Shape<DistrictRef> = object<DistrictRef>({ districtLgd: integer, name: text, stateName: text });

export const regionStoryBlockShape: Shape<RegionStoryBlock> = object<RegionStoryBlock>({
  ...envelope("region_story"),
  river: nullable(riverShape),
  districts: list(districtShape, 1),
  steps: list(object<StoryStep>({ districtLgd: nullable(integer), sentence: explainerSentenceShape }), 1),
  layers: list(LAYER_ID),
  datasets: list(datasetShape, 1),
  boundaryCaption: text
});

export const mapLayerBlockShape: Shape<MapLayerBlock> = object<MapLayerBlock>({
  ...envelope("map_layer"),
  layer: LAYER_ID,
  layerVersion: matching(/^[0-9a-f]{64}$/, "a layer version"),
  title: text,
  datasets: list(datasetShape, 2),
  highlighted: list(integer, 1),
  boundaryCaption: text
});

const seasonsFields: Shape<SeasonsBlock> = object<SeasonsBlock>({
  ...envelope("seasons"),
  rows: list(object<SeasonRow>({ stageId: nullable(UUID), label: text, months: list(month), season: nullable(oneOf(SEASONS)), sentence: explainerSentenceShape })),
  rainfall: nullable(object<MonthlyRain>({ district: districtShape, datasetCode: text, period: text, millimetres: list(number, 12) })),
  datasets: list(datasetShape)
});

export const seasonsBlockShape: Shape<SeasonsBlock> = {
  expected: seasonsFields.expected,
  parse(value, path) {
    const block = seasonsFields.parse(value, path);
    if (block.rows.length === 0 && block.rainfall === null) throw new ShapeError(path, "season rows, the district's rainfall or both");
    return block;
  }
};

export const supplyMapBlockShape: Shape<SupplyMapBlock> = object<SupplyMapBlock>({
  ...envelope("supply_map"),
  links: list(
    object<SupplyLink>({
      material: text,
      materialId: nullable(UUID),
      termKey: nullable(TERM_KEY),
      origin: text,
      wikidataId: nullable(WIKIDATA_ID),
      latitude: nullable(number),
      longitude: nullable(number),
      sentence: explainerSentenceShape
    }),
    1
  )
});
