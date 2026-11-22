import { craftLinkShape, sourceRefShape, type CraftLink } from "@/lib/answerShapes";
import { PLACE_ROLES } from "@/lib/districtCraftsContract";
import { datasetShape, type RegionDataset } from "@/lib/regionContract";
import { boolean, integer, list, matching, nullable, number, object, oneOf, optional, parseShape, positive, ShapeError, text, type Shape } from "@/lib/shape";
import type { SourceRef } from "@/lib/types";

export const WHY_HERE_KIND = "why_here";
export const GROUND_LAYER_KEYS = ["ETOPO1", "NE_RIVERS", "NE_LAKES", "USGS_MRDS"] as const;
export const READING_KINDS = ["rainfall", "soil", "cover"] as const;
export const NOTE_READINGS = ["elevation", "river", "lake", "deposits", "rainfall", "soil", "cover"] as const;
export const PLACE_PRECISIONS = ["POINT", "DISTRICT"] as const;
export const MAP_GROUND_PATH = "/map/ground";

export type Point = [number, number];
export type GroundLayerKey = (typeof GROUND_LAYER_KEYS)[number];
export type ReadingKind = (typeof READING_KINDS)[number];
export type NoteReading = (typeof NOTE_READINGS)[number];
export type GroundLayer = { key: GroundLayerKey; title: string; publisher: string; edition: string; url: string; licence: string; citation: string | null };
export type MineralClass = { id: string; label: string };
export type Elevation = { lowM: number | null; highM: number | null };
export type Water = { distanceKm: number; scaleRank: number | null; longitude: number; latitude: number };
export type Tally = { key: string; label: string; count: number };
export type GroundReading = {
  reading: ReadingKind;
  datasetCode: string;
  variable: string;
  depth: string | null;
  period: string;
  stat: string;
  value: number;
  unit: string;
  resolution: string;
};
export type GroundAt = { elevation: Elevation; river: Water | null; lake: Water | null; depositClasses: Tally[]; commodities: Tally[]; readings: GroundReading[] };
export type MaterialDeposits = { material: string; commodities: string[]; count: number; nearestKm: number };
export type GroundPlace = {
  key: string;
  name: string;
  roles: (typeof PLACE_ROLES)[number][];
  precision: (typeof PLACE_PRECISIONS)[number];
  district: string | null;
  state: string | null;
  longitude: number;
  latitude: number;
  sourceId: string;
  ground: GroundAt;
  materials: MaterialDeposits[];
};
export type FrameBand = { lowM: number; rings: Point[][] };
export type FrameLine = { rank: number; points: Point[] };
export type FrameLabel = { text: string; longitude: number; latitude: number; angle: number };
export type GroundFrame = { west: number; south: number; east: number; north: number; bands: FrameBand[]; rivers: FrameLine[]; lakes: Point[][]; labels: FrameLabel[] };
export type GroundDeposit = { depId: number; name: string; longitude: number; latitude: number; classIndex: number; status: string; commodities: string; nearestKm: number; matched: boolean };
export type GroundPin = { key: string; name: string; roles: (typeof PLACE_ROLES)[number][]; country: string; wikidataId: string; longitude: number; latitude: number };
export type GroundRiver = { key: string; name: string; mainRiv: number; reachIds: number[]; hydrorivers: RegionDataset; names: RegionDataset };
export type CraftGround = {
  schemaVersion: 1;
  craft: CraftLink;
  radiusKm: number;
  places: GroundPlace[];
  soilMaterials: string[];
  deposits: GroundDeposit[];
  classes: MineralClass[];
  frame: GroundFrame;
  layers: GroundLayer[];
  datasets: RegionDataset[];
  sources: SourceRef[];
  abroad?: GroundPin[];
  rivers?: GroundRiver[];
};
export type MapPlaceGround = {
  schemaVersion: 1;
  district: string | null;
  longitude: number;
  latitude: number;
  radiusKm: number;
  ground: GroundAt;
  classes: MineralClass[];
  layers: GroundLayer[];
  datasets: RegionDataset[];
};
export type GroundNote = { reading: NoteReading; unit: string };
export type WhyHereSpec = { ground: CraftGround; notes: GroundNote[] };

const point: Shape<Point> = {
  expected: "a longitude and a latitude",
  parse(value, path) {
    if (!Array.isArray(value) || value.length !== 2) throw new ShapeError(path, "a longitude and a latitude");
    return [number.parse(value[0], `${path}[0]`), number.parse(value[1], `${path}[1]`)];
  }
};

const layerShape = object<GroundLayer>({ key: oneOf(GROUND_LAYER_KEYS), title: text, publisher: text, edition: text, url: text, licence: text, citation: nullable(text) });
const classShape = object<MineralClass>({ id: text, label: text });
const tallyShape = object<Tally>({ key: text, label: text, count: integer });
const waterShape = object<Water>({ distanceKm: number, scaleRank: nullable(integer), longitude: number, latitude: number });
const readingShape = object<GroundReading>({
  reading: oneOf(READING_KINDS),
  datasetCode: text,
  variable: text,
  depth: nullable(text),
  period: text,
  stat: text,
  value: number,
  unit: text,
  resolution: text
});

export const groundAtShape: Shape<GroundAt> = object<GroundAt>({
  elevation: object<Elevation>({ lowM: nullable(integer), highM: nullable(integer) }),
  river: nullable(waterShape),
  lake: nullable(waterShape),
  depositClasses: list(tallyShape),
  commodities: list(tallyShape),
  readings: list(readingShape)
});

const placeShape = object<GroundPlace>({
  key: text,
  name: text,
  roles: list(oneOf(PLACE_ROLES)),
  precision: oneOf(PLACE_PRECISIONS),
  district: nullable(text),
  state: nullable(text),
  longitude: number,
  latitude: number,
  sourceId: text,
  ground: groundAtShape,
  materials: list(object<MaterialDeposits>({ material: text, commodities: list(text, 1), count: integer, nearestKm: number }))
});

const frameShape = object<GroundFrame>({
  west: number,
  south: number,
  east: number,
  north: number,
  bands: list(object<FrameBand>({ lowM: integer, rings: list(list(point)) })),
  rivers: list(object<FrameLine>({ rank: integer, points: list(point, 2) })),
  lakes: list(list(point)),
  labels: list(object<FrameLabel>({ text, longitude: number, latitude: number, angle: number }))
});

const depositShape = object<GroundDeposit>({
  depId: integer,
  name: text,
  longitude: number,
  latitude: number,
  classIndex: integer,
  status: text,
  commodities: text,
  nearestKm: number,
  matched: boolean
});

const pinShape = object<GroundPin>({
  key: text,
  name: text,
  roles: list(oneOf(PLACE_ROLES), 1),
  country: text,
  wikidataId: matching(/^Q[1-9]\d*$/, "a Wikidata item"),
  longitude: number,
  latitude: number
});

const riverShape = object<GroundRiver>({ key: text, name: text, mainRiv: positive, reachIds: list(positive, 1), hydrorivers: datasetShape, names: datasetShape });

export const craftGroundShape: Shape<CraftGround> = object<CraftGround>({
  schemaVersion: oneOf([1] as const),
  craft: craftLinkShape,
  radiusKm: integer,
  places: list(placeShape, 1),
  soilMaterials: list(text),
  deposits: list(depositShape),
  classes: list(classShape, 1),
  frame: frameShape,
  layers: list(layerShape, 1),
  datasets: list(datasetShape),
  sources: list(sourceRefShape),
  abroad: optional(list(pinShape)),
  rivers: optional(list(riverShape))
});

export const mapPlaceGroundShape: Shape<MapPlaceGround> = object<MapPlaceGround>({
  schemaVersion: oneOf([1] as const),
  district: nullable(text),
  longitude: number,
  latitude: number,
  radiusKm: integer,
  ground: groundAtShape,
  classes: list(classShape, 1),
  layers: list(layerShape, 1),
  datasets: list(datasetShape)
});

export const whyHereSpecShape: Shape<WhyHereSpec> = object<WhyHereSpec>({
  ground: craftGroundShape,
  notes: list(object<GroundNote>({ reading: oneOf(NOTE_READINGS), unit: matching(/^[a-z0-9][a-z0-9-]*$/, "a unit id") }))
});

export function parseWhyHereSpec(spec: unknown): WhyHereSpec | null {
  try {
    return parseShape(whyHereSpecShape, spec);
  } catch (error) {
    if (error instanceof ShapeError) return null;
    throw error;
  }
}

export function parseMapPlaceGround(body: unknown): MapPlaceGround {
  return parseShape(mapPlaceGroundShape, body);
}

export function mapGroundPath(longitude: number, latitude: number): string {
  const query = new URLSearchParams({ longitude: String(longitude), latitude: String(latitude) });
  return `${MAP_GROUND_PATH}?${query.toString()}`;
}
