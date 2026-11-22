import type { MaterialKind, MaterialRole, ReactionKind, ReactionSpecies, StageType } from "@/lib/scienceContract";
import { ShapeError } from "@/lib/shape";

export const STAGE_TYPE_LABEL: Record<StageType, string> = {
  PREP: "Preparation",
  SCOUR: "Scouring",
  MORDANT: "Mordanting",
  DYE: "Dyeing",
  RESIST: "Resist",
  PRINT: "Printing",
  WASH: "Washing",
  DRY: "Drying",
  SHAPE: "Shaping",
  CARVE: "Carving",
  FIRE: "Firing",
  CAST: "Casting",
  FINISH: "Finishing",
  OTHER: "Step"
};

export const MATERIAL_ROLE_LABEL: Record<MaterialRole, string> = {
  INPUT: "Input",
  MORDANT: "Mordant",
  DYE: "Dye",
  RESIST: "Resist",
  BINDER: "Binder",
  FLUX: "Flux",
  FUEL: "Fuel",
  TOOL: "Tool",
  PRODUCT: "Product",
  OTHER: "Other"
};

export const MATERIAL_KIND_LABEL: Record<MaterialKind, string> = {
  FIBRE: "Fibre",
  DYE: "Dye",
  MORDANT: "Mordant",
  MINERAL: "Mineral",
  CLAY: "Clay",
  METAL: "Metal",
  WOOD: "Wood",
  RESIN: "Resin",
  FUEL: "Fuel",
  WATER: "Water",
  OTHER: "Other"
};

export const REACTION_KIND_LABEL: Record<ReactionKind, string> = {
  REDOX: "Redox",
  ACID_BASE: "Acid–base",
  COMPLEXATION: "Complexation",
  PRECIPITATION: "Precipitation",
  DEHYDRATION: "Dehydration",
  DEHYDROXYLATION: "Dehydroxylation",
  PHASE_CHANGE: "Phase change",
  POLYMERISATION: "Polymerisation",
  HYDROLYSIS: "Hydrolysis",
  OTHER: "Reaction"
};

export function materialRoleText(role: MaterialRole | null, kind: MaterialKind | null): string | null {
  const roleLabel = role ? MATERIAL_ROLE_LABEL[role] : null;
  const kindLabel = kind ? MATERIAL_KIND_LABEL[kind] : null;
  if (roleLabel && kindLabel && roleLabel !== kindLabel) return `${roleLabel} · ${kindLabel}`;
  return roleLabel ?? kindLabel;
}

const PUBCHEM_COMPOUND = "https://pubchem.ncbi.nlm.nih.gov/compound/";

export type SpeciesTerm = Pick<ReactionSpecies, "role" | "formula" | "name" | "coefficient">;
export type SpeciesReaction = { species: readonly SpeciesTerm[]; balanced: boolean };

export function speciesSides<S extends SpeciesTerm>(reaction: { species: readonly S[] }): { reactants: S[]; products: S[] } {
  return {
    reactants: reaction.species.filter((species) => species.role === "REACTANT"),
    products: reaction.species.filter((species) => species.role === "PRODUCT")
  };
}

export function speciesName(species: SpeciesTerm): string {
  const name = species.name ?? species.formula;
  if (!name) throw new ShapeError("species", "a name or a formula");
  return name;
}

function spokenSide(species: readonly SpeciesTerm[], balanced: boolean): string {
  return species
    .map((entry) => (balanced && entry.coefficient !== null && entry.coefficient > 1 ? `${entry.coefficient} ${speciesName(entry)}` : speciesName(entry)))
    .join(" + ");
}

export function reactionSpoken(reaction: SpeciesReaction): string {
  const { reactants, products } = speciesSides(reaction);
  return `${spokenSide(reactants, reaction.balanced)} gives ${spokenSide(products, reaction.balanced)}`;
}

export function speciesNamesLine(reaction: { species: readonly SpeciesTerm[] }): string {
  const { reactants, products } = speciesSides(reaction);
  return `${reactants.map(speciesName).join(" · ")} → ${products.map(speciesName).join(" · ")}`;
}

export function pubchemHref(cid: number | null): string | null {
  return cid !== null && Number.isInteger(cid) && cid > 0 ? `${PUBCHEM_COMPOUND}${cid}` : null;
}
