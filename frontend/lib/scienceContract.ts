import { UUID } from "@/lib/answerShapes";
import { integer, nullable, object, oneOf, text, type Shape } from "@/lib/shape";

export const STAGE_TYPES = ["PREP", "SCOUR", "MORDANT", "DYE", "RESIST", "PRINT", "WASH", "DRY", "SHAPE", "CARVE", "FIRE", "CAST", "FINISH", "OTHER"] as const;
export const MATERIAL_KINDS = ["FIBRE", "DYE", "MORDANT", "MINERAL", "CLAY", "METAL", "WOOD", "RESIN", "FUEL", "WATER", "OTHER"] as const;
export const MATERIAL_ROLES = ["INPUT", "MORDANT", "DYE", "RESIST", "BINDER", "FLUX", "FUEL", "TOOL", "PRODUCT", "OTHER"] as const;
export const REACTION_KINDS = [
  "REDOX",
  "ACID_BASE",
  "COMPLEXATION",
  "PRECIPITATION",
  "DEHYDRATION",
  "DEHYDROXYLATION",
  "PHASE_CHANGE",
  "POLYMERISATION",
  "HYDROLYSIS",
  "OTHER"
] as const;

export type StageType = (typeof STAGE_TYPES)[number];
export type MaterialKind = (typeof MATERIAL_KINDS)[number];
export type MaterialRole = (typeof MATERIAL_ROLES)[number];
export type ReactionKind = (typeof REACTION_KINDS)[number];
export type ReactionSpecies = { role: "REACTANT" | "PRODUCT"; formula: string | null; name: string | null; coefficient: number | null; compoundId: string | null };

export const reactionSpeciesShape: Shape<ReactionSpecies> = object<ReactionSpecies>({
  role: oneOf(["REACTANT", "PRODUCT"] as const),
  formula: nullable(text),
  name: nullable(text),
  coefficient: nullable(integer),
  compoundId: nullable(UUID)
});
