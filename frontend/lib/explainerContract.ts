import { languageCodeShape } from "@/lib/answerLanguages";
import { answerSentenceShape, citationShape, craftLinkShape, INSTANT, shownLevelShape, sourceRefShape, UUID, type CraftLink } from "@/lib/answerShapes";
import {
  DISCIPLINES,
  envelope,
  explainerSentenceShape,
  IMAGE_RELEVANCE,
  ladderConditionShape,
  mediaRefShape,
  TERM_KEY,
  WIKIDATA_ID,
  type BlockEnvelope,
  type Discipline,
  type ExplainerSentence,
  type LadderCondition,
  type MediaRef
} from "@/lib/explainerBlockBase";
import { DIFFER_WEIGHTS } from "@/lib/craftPageContext";
import { componentBlockShape, type ComponentBlock } from "@/lib/explainerComponent";
import { expertViewBlockShape, type ExpertViewBlock } from "@/lib/explainerExperts";
import { artisanVoiceBlockShape, type ArtisanVoiceBlock } from "@/lib/explainerVoices";
import {
  climateRiskBlockShape,
  marketGiBlockShape,
  measureBlockShape,
  quantitiesBlockShape,
  type ClimateRiskBlock,
  type MarketGiBlock,
  type MeasureBlock,
  type QuantitiesBlock
} from "@/lib/explainerInsight";
import {
  compareBlockShape,
  conceptGraphBlockShape,
  quizBlockShape,
  type CompareBlock,
  type ConceptGraphBlock,
  type QuizBlock
} from "@/lib/explainerLearning";
import {
  COLOUR_WORDS,
  materialCardBlockShape,
  molecule3dBlockShape,
  reactionPlayerBlockShape,
  type MaterialCardBlock,
  type Molecule3dBlock,
  type ReactionPlayerBlock
} from "@/lib/explainerMatter";
import {
  mapLayerBlockShape,
  regionStoryBlockShape,
  seasonsBlockShape,
  supplyMapBlockShape,
  type MapLayerBlock,
  type RegionStoryBlock,
  type SeasonsBlock,
  type SupplyMapBlock
} from "@/lib/explainerPlace";
import {
  simulationBlockShape,
  timelineMapBlockShape,
  whatIfBlockShape,
  zoomStoryBlockShape,
  type SimulationBlock,
  type TimelineMapBlock,
  type WhatIfBlock,
  type ZoomStoryBlock
} from "@/lib/explainerPlay";
import { MATERIAL_KINDS, MATERIAL_ROLES, STAGE_TYPES } from "@/lib/scienceContract";
import {
  firingBlockShape,
  indigoVatBlockShape,
  lostWaxBlockShape,
  mordantBathBlockShape,
  SIGNATURE_KINDS,
  type FiringBlock,
  type IndigoVatBlock,
  type LostWaxBlock,
  type MordantBathBlock,
  type SignatureBlock
} from "@/lib/explainerSignature";
import { boolean, integer, list, matching, nullable, object, oneOf, optional, positive, ShapeError, tagged, text, type Shape } from "@/lib/shape";
import type { AnswerSentence, Citation, EvidenceLevel, SourceRef } from "@/lib/types";

export { DISCIPLINES, type Discipline };
export const DEPTHS = ["BASIC", "DETAILED", "EXPERT"] as const;
export const UNDERSTANDING_BASES = ["MODEL", "RESOLVER"] as const;
export const BLOCK_KINDS = [
  "prose",
  "process_ladder",
  "region_story",
  "map_layer",
  "reaction_player",
  "material_card",
  "molecule_3d",
  "images",
  "simulation",
  "what_if",
  "timeline_map",
  "zoom_story",
  "expert_view",
  "seasons",
  "supply_map",
  "compare",
  "in_practice",
  "quiz",
  "open_questions",
  "artisan_voice",
  "designs",
  "concept_graph",
  "measure",
  "market_gi",
  "climate_risk",
  "indigo_vat",
  "mordant_bath",
  "lost_wax",
  "firing",
  "quantities",
  "component"
] as const;
export const BUILT_BLOCK_KINDS = ["prose", "process_ladder", "images", "region_story", "map_layer", "expert_view", "seasons", "supply_map", "reaction_player", "material_card", "molecule_3d", "compare", "concept_graph", "climate_risk", "measure", "market_gi", "quantities", "simulation", "what_if", "zoom_story", "timeline_map", "component"] as const;
export const BUILT_FIGURE_KINDS = ["indigo_vat", "mordant_bath", "lost_wax", "firing"] as const satisfies readonly (typeof SIGNATURE_KINDS)[number][];
export const WORKING_SECTION_STATES = ["RESEARCHING", "WRITING", "CHECKING"] as const;
export const FINAL_SECTION_STATES = ["READY", "EMPTY"] as const;
export const TERM_BASES = ["STORED", "WIKIPEDIA", "WEB_SEARCH"] as const;

export type Depth = (typeof DEPTHS)[number];
export type UnderstandingBasis = (typeof UNDERSTANDING_BASES)[number];
export type BlockKind = (typeof BLOCK_KINDS)[number];
export type WorkingSectionState = (typeof WORKING_SECTION_STATES)[number];
export type FinalSectionState = (typeof FINAL_SECTION_STATES)[number];

export type ProseBlock = BlockEnvelope<"prose"> & { sentences: ExplainerSentence[] };
export type LadderMaterial = {
  materialId: string;
  name: string;
  kind: (typeof MATERIAL_KINDS)[number];
  role: (typeof MATERIAL_ROLES)[number];
  citations: Citation[];
  botanicalName?: string;
  pubchemCid?: number;
  localNames?: string[];
};
export type StageAfter = { text: string; colours: (typeof COLOUR_WORDS)[number][]; citations: Citation[] };
export type LadderTool = { toolId: string; name: string; localNames: string[]; citations: Citation[] };
export type DifferRead = { sentence: ExplainerSentence | null; shownIn: string | null };
export type DifferReading = { key: string; about: string; weight: (typeof DIFFER_WEIGHTS)[number]; readings: DifferRead[] };
export type StagePicture = { media: MediaRef; caption: string; standIn: string | null };
export type LadderStage = {
  stageId: string;
  ordinal: number;
  name: string;
  stageType: (typeof STAGE_TYPES)[number];
  level: EvidenceLevel;
  sentences: ExplainerSentence[];
  materials: LadderMaterial[];
  conditions: LadderCondition[];
  reactionIds: string[];
  localName?: string;
  unnumbered?: boolean;
  after?: StageAfter;
  why?: ExplainerSentence;
  tools?: LadderTool[];
  differs?: DifferReading[];
  pictures?: StagePicture[];
};
export type ProcessLadderBlock = BlockEnvelope<"process_ladder"> & { craft: CraftLink; processId: string; stages: LadderStage[] };
export type ImageItem = { media: MediaRef; claimIds: string[]; relevance: (typeof IMAGE_RELEVANCE)[number] };
export type ImagesBlock = BlockEnvelope<"images"> & { items: ImageItem[] };
export type BlockByKind = {
  prose: ProseBlock;
  process_ladder: ProcessLadderBlock;
  region_story: RegionStoryBlock;
  map_layer: MapLayerBlock;
  reaction_player: ReactionPlayerBlock;
  material_card: MaterialCardBlock;
  molecule_3d: Molecule3dBlock;
  images: ImagesBlock;
  expert_view: ExpertViewBlock;
  artisan_voice: ArtisanVoiceBlock;
  seasons: SeasonsBlock;
  supply_map: SupplyMapBlock;
  simulation: SimulationBlock;
  what_if: WhatIfBlock;
  zoom_story: ZoomStoryBlock;
  timeline_map: TimelineMapBlock;
  quiz: QuizBlock;
  compare: CompareBlock;
  concept_graph: ConceptGraphBlock;
  measure: MeasureBlock;
  market_gi: MarketGiBlock;
  climate_risk: ClimateRiskBlock;
  quantities: QuantitiesBlock;
  indigo_vat: IndigoVatBlock;
  mordant_bath: MordantBathBlock;
  lost_wax: LostWaxBlock;
  firing: FiringBlock;
  component: ComponentBlock;
};
export type TypedBlockKind = keyof BlockByKind;
export type BuiltBlockKind = (typeof BUILT_BLOCK_KINDS)[number];
export type ExplainerBlock = BlockByKind[BuiltBlockKind];
export type ExplainerSection = {
  id: string;
  discipline: Discipline;
  title: string;
  original?: string;
  order: number;
  state: FinalSectionState;
  blocks: ExplainerBlock[];
  searched: string | null;
  withdrawn?: number;
};
export type Understood = { crafts: CraftLink[]; candidates: CraftLink[]; depth: Depth; language: string; basis?: UnderstandingBasis };
export type LedeBlock = BlockEnvelope<"lede"> & { headline: string; sentences: ExplainerSentence[]; figure: SignatureBlock | null };
export type Explainer = {
  schemaVersion: 1;
  answerId: string;
  question: string;
  understood: Understood;
  lede?: LedeBlock;
  sections: ExplainerSection[];
  sources: SourceRef[];
  followUps: string[];
  createdAt: string;
};
export type Term = {
  schemaVersion: 1;
  key: string;
  label: string;
  language: string;
  localNames: string[];
  craftSlugs: string[];
  wikidataId: string | null;
  basis: (typeof TERM_BASES)[number];
  summary: AnswerSentence[];
  sources: SourceRef[];
  checkedAt: string;
};

export const SECTION_ID = matching(/^s[1-9]\d{0,2}$/, "a section id");

const differReadShape: Shape<DifferRead> = {
  expected: "a reading's sentence or where it is shown",
  parse(value, path) {
    const read = object<DifferRead>({ sentence: nullable(explainerSentenceShape), shownIn: nullable(text) }).parse(value, path);
    if ((read.sentence === null) === (read.shownIn === null)) throw new ShapeError(path, "a sentence, or the id of the sentence that shows it");
    return read;
  }
};

export const differReadingShape: Shape<DifferReading> = object<DifferReading>({
  key: text,
  about: text,
  weight: oneOf(DIFFER_WEIGHTS),
  readings: list(differReadShape, 2)
});

const ladderStageShape: Shape<LadderStage> = object<LadderStage>({
  stageId: UUID,
  ordinal: integer,
  name: text,
  stageType: oneOf(STAGE_TYPES),
  level: shownLevelShape,
  sentences: list(explainerSentenceShape, 1),
  materials: list(
    object<LadderMaterial>({
      materialId: UUID,
      name: text,
      kind: oneOf(MATERIAL_KINDS),
      role: oneOf(MATERIAL_ROLES),
      citations: list(citationShape, 1),
      botanicalName: optional(text),
      pubchemCid: optional(integer),
      localNames: optional(list(text, 1))
    })
  ),
  conditions: list(ladderConditionShape),
  reactionIds: list(UUID),
  localName: optional(text),
  unnumbered: optional(boolean),
  after: optional(object<StageAfter>({ text, colours: list(oneOf(COLOUR_WORDS)), citations: list(citationShape, 1) })),
  why: optional(explainerSentenceShape),
  tools: optional(list(object<LadderTool>({ toolId: UUID, name: text, localNames: list(text), citations: list(citationShape, 1) }), 1)),
  differs: optional(list(differReadingShape, 1)),
  pictures: optional(list(object<StagePicture>({ media: mediaRefShape, caption: text, standIn: nullable(text) }), 1))
});

export const BLOCK_SHAPES: { readonly [K in TypedBlockKind]: Shape<BlockByKind[K]> } = {
  prose: object<ProseBlock>({ ...envelope("prose"), sentences: list(explainerSentenceShape, 1) }),
  process_ladder: object<ProcessLadderBlock>({ ...envelope("process_ladder"), craft: craftLinkShape, processId: UUID, stages: list(ladderStageShape, 1) }),
  region_story: regionStoryBlockShape,
  map_layer: mapLayerBlockShape,
  reaction_player: reactionPlayerBlockShape,
  material_card: materialCardBlockShape,
  molecule_3d: molecule3dBlockShape,
  images: object<ImagesBlock>({
    ...envelope("images"),
    items: list(object<ImageItem>({ media: mediaRefShape, claimIds: list(UUID, 1), relevance: oneOf(IMAGE_RELEVANCE) }), 1)
  }),
  expert_view: expertViewBlockShape,
  artisan_voice: artisanVoiceBlockShape,
  seasons: seasonsBlockShape,
  supply_map: supplyMapBlockShape,
  simulation: simulationBlockShape,
  what_if: whatIfBlockShape,
  zoom_story: zoomStoryBlockShape,
  timeline_map: timelineMapBlockShape,
  quiz: quizBlockShape,
  compare: compareBlockShape,
  concept_graph: conceptGraphBlockShape,
  measure: measureBlockShape,
  market_gi: marketGiBlockShape,
  climate_risk: climateRiskBlockShape,
  quantities: quantitiesBlockShape,
  indigo_vat: indigoVatBlockShape,
  mordant_bath: mordantBathBlockShape,
  lost_wax: lostWaxBlockShape,
  firing: firingBlockShape,
  component: componentBlockShape
};

export const explainerBlockShape: Shape<ExplainerBlock> = tagged<ExplainerBlock>(
  "kind",
  Object.fromEntries(BUILT_BLOCK_KINDS.map((kind) => [kind, BLOCK_SHAPES[kind]])) as Record<BuiltBlockKind, Shape<ExplainerBlock>>
);

export const signatureFigureShape: Shape<SignatureBlock> = tagged<SignatureBlock>(
  "kind",
  Object.fromEntries(BUILT_FIGURE_KINDS.map((kind) => [kind, BLOCK_SHAPES[kind]])) as Record<string, Shape<SignatureBlock>>
);

export const ledeBlockShape: Shape<LedeBlock> = object<LedeBlock>({
  ...envelope("lede"),
  headline: text,
  sentences: list(explainerSentenceShape, 2),
  figure: nullable(signatureFigureShape)
});

export const understoodShape: Shape<Understood> = object<Understood>({
  crafts: list(craftLinkShape),
  candidates: list(craftLinkShape),
  depth: oneOf(DEPTHS),
  language: languageCodeShape,
  basis: optional(oneOf(UNDERSTANDING_BASES))
});

export const explainerSectionShape: Shape<ExplainerSection> = object<ExplainerSection>({
  id: SECTION_ID,
  discipline: oneOf(DISCIPLINES),
  title: text,
  original: optional(text),
  order: integer,
  state: oneOf(FINAL_SECTION_STATES),
  blocks: list(explainerBlockShape),
  searched: nullable(text),
  withdrawn: optional(positive)
});

export const explainerShape: Shape<Explainer> = object<Explainer>({
  schemaVersion: oneOf([1] as const),
  answerId: UUID,
  question: text,
  understood: understoodShape,
  lede: optional(ledeBlockShape),
  sections: list(explainerSectionShape, 1),
  sources: list(sourceRefShape),
  followUps: list(text),
  createdAt: INSTANT
});

export const termShape: Shape<Term> = object<Term>({
  schemaVersion: oneOf([1] as const),
  key: TERM_KEY,
  label: text,
  language: languageCodeShape,
  localNames: list(text),
  craftSlugs: list(text),
  wikidataId: nullable(WIKIDATA_ID),
  basis: oneOf(TERM_BASES),
  summary: list(answerSentenceShape, 1),
  sources: list(sourceRefShape),
  checkedAt: INSTANT
});
