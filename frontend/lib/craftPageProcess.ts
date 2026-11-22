import { UUID } from "@/lib/answerShapes";
import { MATERIAL_KINDS, MATERIAL_ROLES, REACTION_KINDS, STAGE_TYPES } from "@/lib/scienceContract";
import { boolean, list, nullable, object, oneOf, positive, text, type Shape } from "@/lib/shape";

export const TIMING_KINDS = ["DURATION", "SEASON"] as const;
export const SPECIES_ROLES = ["REACTANT", "PRODUCT"] as const;

const CLAIM_IDS = list(UUID, 1);

export type StageItem = {
  id: string;
  name: string;
  kind: (typeof MATERIAL_KINDS)[number];
  role: (typeof MATERIAL_ROLES)[number];
  localNames: string[];
  botanicalName: string | null;
  pubchemCid: number | null;
  claimIds: string[];
};
export type StageTiming = { kind: (typeof TIMING_KINDS)[number]; text: string; claimId: string };
export type PageSpecies = { role: (typeof SPECIES_ROLES)[number]; name: string | null; formula: string | null; coefficient: number | null };
export type PageReaction = {
  id: string | null;
  kind: (typeof REACTION_KINDS)[number];
  label: string;
  species: PageSpecies[];
  balanced: boolean;
  equation: string | null;
  claimIds: string[];
};
export type PageStage = {
  id: string;
  order: number | null;
  name: string;
  localName: string | null;
  stageType: (typeof STAGE_TYPES)[number];
  claimIds: string[];
  materials: StageItem[];
  tools: StageItem[];
  timing: StageTiming[];
  reactions: PageReaction[];
  differ: string[];
};
export type PageProcess = { processId: string | null; stages: PageStage[]; reactions: PageReaction[] };

const stageItemShape: Shape<StageItem> = object<StageItem>({
  id: UUID,
  name: text,
  kind: oneOf(MATERIAL_KINDS),
  role: oneOf(MATERIAL_ROLES),
  localNames: list(text),
  botanicalName: nullable(text),
  pubchemCid: nullable(positive),
  claimIds: CLAIM_IDS
});

const pageReactionShape: Shape<PageReaction> = object<PageReaction>({
  id: nullable(UUID),
  kind: oneOf(REACTION_KINDS),
  label: text,
  species: list(object<PageSpecies>({ role: oneOf(SPECIES_ROLES), name: nullable(text), formula: nullable(text), coefficient: nullable(positive) }), 2),
  balanced: boolean,
  equation: nullable(text),
  claimIds: CLAIM_IDS
});

const pageStageShape: Shape<PageStage> = object<PageStage>({
  id: UUID,
  order: nullable(positive),
  name: text,
  localName: nullable(text),
  stageType: oneOf(STAGE_TYPES),
  claimIds: CLAIM_IDS,
  materials: list(stageItemShape),
  tools: list(stageItemShape),
  timing: list(object<StageTiming>({ kind: oneOf(TIMING_KINDS), text, claimId: UUID })),
  reactions: list(pageReactionShape),
  differ: list(text)
});

export const pageProcessShape: Shape<PageProcess> = object<PageProcess>({ processId: nullable(UUID), stages: list(pageStageShape), reactions: list(pageReactionShape) });
