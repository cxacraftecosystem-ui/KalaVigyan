import { citationShape, shownLevelShape, UUID } from "@/lib/answerShapes";
import {
  envelope,
  explainerSentenceShape,
  ladderConditionShape,
  TERM_KEY,
  WIKIDATA_ID,
  type BlockEnvelope,
  type ExplainerSentence,
  type LadderCondition
} from "@/lib/explainerBlockBase";
import { formatMeasure } from "@/lib/measure";
import { MATERIAL_KINDS, MATERIAL_ROLES, REACTION_KINDS, reactionSpeciesShape, type ReactionSpecies } from "@/lib/scienceContract";
import { boolean, integer, list, nullable, number, object, oneOf, optional, text, type Shape } from "@/lib/shape";
import type { Citation, EvidenceLevel } from "@/lib/types";

export const MOLECULE_CONFORMER_PATH = (pubchemCid: number) => `/molecules/${pubchemCid}/conformer`;
export const COLOUR_WORDS = ["RED", "BLUE", "BLACK", "WHITE", "GREEN", "YELLOW", "BROWN", "GREY", "PINK", "PURPLE", "ORANGE", "MAROON"] as const;
export const COLOUR_SIDES = ["BEFORE", "AFTER"] as const;
export const FORMULA_BASES = ["STATED", "COMPOUND_RECORD"] as const;
export const REACTION_ENERGY_LABEL = "Reaction energy";
export const REACTION_ENERGY_UNIT = "kJ/mol";

export type StepColour = {
  side: (typeof COLOUR_SIDES)[number];
  colour: (typeof COLOUR_WORDS)[number];
  stated: string;
  citations: Citation[];
};
export type StepEnergy = { kjPerMol: number; claimId: string };
export type ShownEnergy = { text: string; citations: Citation[] };
export type ReactionNote = { reactionId: string; sentence: ExplainerSentence };
export type ReactionStep = {
  reactionId: string;
  stageId: string | null;
  kind: (typeof REACTION_KINDS)[number];
  label: string;
  species: ReactionSpecies[];
  equation: string | null;
  balanced: boolean;
  level: EvidenceLevel;
  citations: Citation[];
  stage?: string;
  conditions?: LadderCondition[];
  colours?: StepColour[];
  formulaBasis?: (typeof FORMULA_BASES)[number];
  formulaSources?: string[];
  deltaH?: StepEnergy;
};
export type ReactionPlayerBlock = BlockEnvelope<"reaction_player"> & { steps: ReactionStep[]; notes?: ReactionNote[] };
export type MaterialCardBlock = BlockEnvelope<"material_card"> & {
  materialId: string | null;
  compoundId: string | null;
  termKey: string | null;
  name: string;
  materialKind: (typeof MATERIAL_KINDS)[number] | null;
  role: (typeof MATERIAL_ROLES)[number] | null;
  formula: string | null;
  pubchemCid: number | null;
  wikidataId: string | null;
  localNames: string[];
  facts: ExplainerSentence[];
  handling: ExplainerSentence[];
  sourceId?: string;
};
export type Molecule3dBlock = BlockEnvelope<"molecule_3d"> & {
  compoundId: string;
  pubchemCid: number;
  name: string;
  formula: string | null;
  sourceId: string;
};

export function stepCitations(step: ReactionStep): Citation[] {
  return [...step.citations, ...(step.conditions ?? []).flatMap((condition) => condition.citations), ...(step.colours ?? []).flatMap((colour) => colour.citations)];
}

export function stepEnergy(step: ReactionStep): ShownEnergy | null {
  const deltaH = step.deltaH;
  if (!deltaH) return null;
  const citations = step.citations.filter((citation) => citation.claimId === deltaH.claimId);
  if (citations.length === 0) return null;
  const sign = deltaH.kjPerMol > 0 ? "+" : "";
  return { text: `ΔH = ${sign}${formatMeasure(deltaH.kjPerMol, REACTION_ENERGY_UNIT)}`, citations };
}

export function reactionNotes(block: ReactionPlayerBlock, reactionId: string): ExplainerSentence[] {
  return (block.notes ?? []).filter((note) => note.reactionId === reactionId).map((note) => note.sentence);
}

export function reactionPlayerCitations(block: ReactionPlayerBlock): Citation[] {
  return [...block.steps.flatMap(stepCitations), ...(block.notes ?? []).flatMap((note) => note.sentence.citations)];
}

export const reactionPlayerBlockShape: Shape<ReactionPlayerBlock> = object<ReactionPlayerBlock>({
  ...envelope("reaction_player"),
  steps: list(
    object<ReactionStep>({
      reactionId: UUID,
      stageId: nullable(UUID),
      kind: oneOf(REACTION_KINDS),
      label: text,
      species: list(reactionSpeciesShape, 2),
      equation: nullable(text),
      balanced: boolean,
      level: shownLevelShape,
      citations: list(citationShape, 1),
      stage: optional(text),
      conditions: optional(list(ladderConditionShape)),
      colours: optional(
        list(
          object<StepColour>({ side: oneOf(COLOUR_SIDES), colour: oneOf(COLOUR_WORDS), stated: text, citations: list(citationShape, 1) })
        )
      ),
      formulaBasis: optional(oneOf(FORMULA_BASES)),
      formulaSources: optional(list(text, 1)),
      deltaH: optional(object<StepEnergy>({ kjPerMol: number, claimId: text }))
    }),
    1
  ),
  notes: optional(list(object<ReactionNote>({ reactionId: UUID, sentence: explainerSentenceShape })))
});

export const materialCardBlockShape: Shape<MaterialCardBlock> = object<MaterialCardBlock>({
  ...envelope("material_card"),
  materialId: nullable(UUID),
  compoundId: nullable(UUID),
  termKey: nullable(TERM_KEY),
  name: text,
  materialKind: nullable(oneOf(MATERIAL_KINDS)),
  role: nullable(oneOf(MATERIAL_ROLES)),
  formula: nullable(text),
  pubchemCid: nullable(integer),
  wikidataId: nullable(WIKIDATA_ID),
  localNames: list(text),
  facts: list(explainerSentenceShape, 1),
  handling: list(explainerSentenceShape),
  sourceId: optional(text)
});

export const molecule3dBlockShape: Shape<Molecule3dBlock> = object<Molecule3dBlock>({
  ...envelope("molecule_3d"),
  compoundId: UUID,
  pubchemCid: integer,
  name: text,
  formula: nullable(text),
  sourceId: text
});
