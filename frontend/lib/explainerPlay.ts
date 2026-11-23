import { citationShape, INSTANT, UUID } from "@/lib/answerShapes";
import {
  envelope,
  explainerSentenceShape,
  IMAGE_RELEVANCE,
  mediaRefShape,
  TERM_KEY,
  WIKIDATA_ID,
  type BlockEnvelope,
  type ExplainerSentence,
  type MediaRef
} from "@/lib/explainerBlockBase";
import { districtShape, type DistrictRef } from "@/lib/explainerPlace";
import { datasetShape, type RegionDataset } from "@/lib/regionContract";
import { reactionSpeciesShape, type ReactionSpecies } from "@/lib/scienceContract";
import { boolean, integer, list, matching, nullable, number, object, oneOf, optional, ShapeError, text, type Shape } from "@/lib/shape";
import type { Citation } from "@/lib/types";

export const ZOOM_LEVELS = ["DISTRICT", "WORKSHOP", "CLOTH", "FIBRE", "MOLECULE"] as const;
export const SANDBOX_ATTRIBUTE = "allow-scripts";
export const SANDBOX_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; webrtc 'block'";
export const SANDBOX_DATA_ELEMENT_ID = "kv-data";
export const SANDBOX_MAX_BYTES = 200 * 1024;

export type ZoomLevelName = (typeof ZOOM_LEVELS)[number];
export type SimulationValue = {
  key: string;
  label: string;
  value: number;
  unit: string | null;
  stated: string | null;
  citations: Citation[];
  datasetCode: string | null;
};
export type SimulationReaction = {
  reactionId: string;
  label: string;
  species: ReactionSpecies[];
  equation: string | null;
  balanced: boolean;
  citations: Citation[];
};
export type SimulationBlock = BlockEnvelope<"simulation"> & {
  concept: string;
  title: string;
  model: string;
  createdAt: string;
  html: string;
  htmlSha256: string;
  values: SimulationValue[];
  datasets: RegionDataset[];
  hidden: boolean;
  grounds?: Citation[];
  reactions?: SimulationReaction[];
};
export type WhatIfOutcome = { sentence: ExplainerSentence; reactionId: string | null };
export type WhatIfOption = { label: string; materialId: string | null; termKey: string | null; outcomes: WhatIfOutcome[] };
export type WhatIfBlock = BlockEnvelope<"what_if"> & { changed: string; stageId: string | null; options: WhatIfOption[] };
export type ZoomCompound = { compoundId: string; pubchemCid: number; name: string; formula: string | null; sourceId: string };
export type ZoomLevel = {
  level: ZoomLevelName;
  sentence: ExplainerSentence;
  district: DistrictRef | null;
  media: MediaRef | null;
  relevance: (typeof IMAGE_RELEVANCE)[number] | null;
  compound: ZoomCompound | null;
};
export type ZoomStoryBlock = BlockEnvelope<"zoom_story"> & { levels: ZoomLevel[]; datasets: RegionDataset[]; boundaryCaption: string | null };
export type TimelinePlace = { name: string; wikidataId: string | null; latitude: number | null; longitude: number | null; districtLgd?: number };
export type TimelinePoint = { place: number; yearFrom: number; yearTo: number; sentence: ExplainerSentence };
export type TimelineRoute = { start: number; end: number; yearFrom: number; yearTo: number; sentence: ExplainerSentence };
export type TimelineUndated = { place: number | null; sentence: ExplainerSentence };
export type TimelineMapBlock = Omit<BlockEnvelope<"timeline_map">, "version"> & {
  version: 1 | 2;
  places: TimelinePlace[];
  points: TimelinePoint[];
  routes: TimelineRoute[];
  undated?: TimelineUndated[];
  datasets: RegionDataset[];
  boundaryCaption: string;
};

const SANDBOX_HTML_EXPECTED = `HTML of 1 to ${SANDBOX_MAX_BYTES} bytes`;

export const sandboxHtmlShape: Shape<string> = {
  expected: SANDBOX_HTML_EXPECTED,
  parse(value, path) {
    if (typeof value !== "string" || value === "" || new TextEncoder().encode(value).length > SANDBOX_MAX_BYTES) {
      throw new ShapeError(path, SANDBOX_HTML_EXPECTED);
    }
    return value;
  }
};

const SIMULATION_GROUNDED = "a generated explainer resting on a cited value, statement or stored reaction";

const simulationReactionShape: Shape<SimulationReaction> = object<SimulationReaction>({
  reactionId: UUID,
  label: text,
  species: list(reactionSpeciesShape, 2),
  equation: nullable(text),
  balanced: boolean,
  citations: list(citationShape, 1)
});

const simulationFieldsShape: Shape<SimulationBlock> = object<SimulationBlock>({
  ...envelope("simulation"),
  concept: text,
  title: text,
  model: text,
  createdAt: INSTANT,
  html: sandboxHtmlShape,
  htmlSha256: matching(/^[0-9a-f]{64}$/, "a SHA-256"),
  values: list(
    object<SimulationValue>({
      key: matching(/^[a-z][a-zA-Z0-9]{0,39}$/, "a value key"),
      label: text,
      value: number,
      unit: nullable(text),
      stated: nullable(text),
      citations: list(citationShape),
      datasetCode: nullable(text)
    })
  ),
  datasets: list(datasetShape),
  hidden: boolean,
  grounds: optional(list(citationShape, 1)),
  reactions: optional(list(simulationReactionShape, 1))
});

export function simulationGrounded(block: Pick<SimulationBlock, "values" | "grounds" | "reactions">): boolean {
  return block.values.length > 0 || (block.grounds?.length ?? 0) > 0 || (block.reactions?.length ?? 0) > 0;
}

export const simulationBlockShape: Shape<SimulationBlock> = {
  expected: SIMULATION_GROUNDED,
  parse(value, path) {
    const block = simulationFieldsShape.parse(value, path);
    if (!simulationGrounded(block)) throw new ShapeError(path, SIMULATION_GROUNDED);
    return block;
  }
};

export const whatIfBlockShape: Shape<WhatIfBlock> = object<WhatIfBlock>({
  ...envelope("what_if"),
  changed: text,
  stageId: nullable(UUID),
  options: list(
    object<WhatIfOption>({
      label: text,
      materialId: nullable(UUID),
      termKey: nullable(TERM_KEY),
      outcomes: list(object<WhatIfOutcome>({ sentence: explainerSentenceShape, reactionId: nullable(UUID) }))
    }),
    2
  )
});

export const zoomStoryBlockShape: Shape<ZoomStoryBlock> = object<ZoomStoryBlock>({
  ...envelope("zoom_story"),
  levels: list(
    object<ZoomLevel>({
      level: oneOf(ZOOM_LEVELS),
      sentence: explainerSentenceShape,
      district: nullable(districtShape),
      media: nullable(mediaRefShape),
      relevance: nullable(oneOf(IMAGE_RELEVANCE)),
      compound: nullable(
        object<ZoomCompound>({ compoundId: UUID, pubchemCid: integer, name: text, formula: nullable(text), sourceId: text })
      )
    }),
    2
  ),
  datasets: list(datasetShape),
  boundaryCaption: nullable(text)
});

export const timelineMapBlockShape: Shape<TimelineMapBlock> = object<TimelineMapBlock>({
  ...envelope("timeline_map"),
  version: oneOf([1, 2] as const),
  places: list(
    object<TimelinePlace>({
      name: text,
      wikidataId: nullable(WIKIDATA_ID),
      latitude: nullable(number),
      longitude: nullable(number),
      districtLgd: optional(integer)
    }),
    1
  ),
  points: list(object<TimelinePoint>({ place: integer, yearFrom: integer, yearTo: integer, sentence: explainerSentenceShape })),
  routes: list(
    object<TimelineRoute>({ start: integer, end: integer, yearFrom: integer, yearTo: integer, sentence: explainerSentenceShape })
  ),
  undated: optional(list(object<TimelineUndated>({ place: nullable(integer), sentence: explainerSentenceShape }), 1)),
  datasets: list(datasetShape, 1),
  boundaryCaption: text
});
