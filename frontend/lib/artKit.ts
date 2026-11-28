import { DEPICTED_MATERIALS } from "@/lib/depictedMaterials";

const MOTIFS = ["star", "lattice", "dots", "lines"] as const;

export const ART_KIT = {
  version: 1,
  families: ["textiles", "metal", "clay", "stone", "wood", "leather", "fibre", "paper", "more"],
  layouts: { steps: [2, 6], before_after: [2, 2], section: [1, 1], sequence: [2, 6] },
  partsPerPanelMax: 3,
  speciesPerSceneMax: 8,
  layers: [2, 6],
  earth: "earth",
  motions: ["dip", "take", "dry", "react"],
  motifs: MOTIFS,
  parts: {
    cloth: { families: ["textiles", "more"], subjects: ["cloth", "cotton", "fabric", "textile", "swatch"], choices: { form: ["swatch", "length", "folded"], "printed.motif": MOTIFS }, materials: ["material", "printed.material"], motion: "take" },
    block: { families: ["textiles", "wood"], subjects: ["block", "blocks", "stamp"], choices: { motif: MOTIFS }, materials: ["paste"], motion: null },
    bath: { families: ["textiles", "metal", "leather", "fibre", "paper"], subjects: ["vat", "vats", "bath", "baths", "liquor"], choices: { vessel: ["vat", "pot", "trough", "pit"] }, materials: ["liquor", "piece"], motion: "dip" },
    paste: { families: ["textiles", "metal", "paper", "more"], subjects: ["paste", "mordant", "resist"], choices: { form: ["spread", "printed", "outline"] }, materials: ["material", "on", "dried"], motion: "dry" },
    heat: { families: ["textiles", "metal", "clay", "wood", "fibre", "paper", "more"], subjects: ["sun", "fire", "furnace", "kiln", "flame"], choices: { source: ["sun", "fire", "furnace", "lamp"] }, materials: [], motion: null },
    water: { families: ["textiles", "metal", "leather", "fibre", "paper"], subjects: ["water", "washing", "rinse", "rinsing"], choices: { form: ["running", "still", "sprinkled"] }, materials: [], motion: null },
    tool: { families: ["textiles", "metal", "stone", "wood", "fibre", "paper", "more"], subjects: ["hand", "hands", "chisel", "mallet", "brush"], choices: { tool: ["block", "brush", "chisel", "mallet", "knife", "stick"] }, materials: ["load"], motion: null },
    section: { families: ["textiles", "metal", "clay", "leather", "more"], subjects: ["section", "cutaway", "strata", "layers"], choices: {}, materials: ["layers.material"], motion: null },
    piece: { families: ["metal", "clay", "stone", "wood", "fibre", "paper", "more"], subjects: ["slab", "billet", "lump"], choices: { shape: ["lump", "vessel", "slab", "billet", "sheet", "figure", "culm"], "inlay.motif": MOTIFS }, materials: ["material", "inlay.material"], motion: null },
    species: { families: ["textiles", "metal", "clay", "stone", "wood", "leather", "fibre", "paper", "more"], subjects: ["species", "reactant", "reactants", "reagent", "reagents"], choices: { role: ["reactant", "reagent", "product"], mark: ["clear", "gas", "ion"] }, materials: ["material"], motion: "react" }
  }
} as const;

export type KitPartName = keyof typeof ART_KIT.parts;
export type KitLayout = keyof typeof ART_KIT.layouts;
export type KitMotion = (typeof ART_KIT.motions)[number];
export type KitMotif = (typeof MOTIFS)[number];
export type KitFamily = (typeof ART_KIT.families)[number];
export type ClothForm = (typeof ART_KIT.parts.cloth.choices.form)[number];
export type Vessel = (typeof ART_KIT.parts.bath.choices.vessel)[number];
export type PasteForm = (typeof ART_KIT.parts.paste.choices.form)[number];
export type HeatSource = (typeof ART_KIT.parts.heat.choices.source)[number];
export type WaterForm = (typeof ART_KIT.parts.water.choices.form)[number];
export type ToolName = (typeof ART_KIT.parts.tool.choices.tool)[number];
export type PieceShape = (typeof ART_KIT.parts.piece.choices.shape)[number];
export type SpeciesRole = (typeof ART_KIT.parts.species.choices.role)[number];
export type SpeciesMark = (typeof ART_KIT.parts.species.choices.mark)[number];

export const KIT_PART_NAMES = Object.keys(ART_KIT.parts) as KitPartName[];
export const KIT_LAYOUTS = Object.keys(ART_KIT.layouts) as KitLayout[];
export const KIT_DIPS = ["dip-1", "dip-2", "dip-3", "dip-4"] as const;
export const KIT_MATERIALS: readonly string[] = [...DEPICTED_MATERIALS.map((name) => `--dye-${name}`), ...KIT_DIPS.map((name) => `--${name}`)];

export const FAMILY_NAMES: Readonly<Record<KitFamily, string>> = {
  textiles: "Textiles",
  metal: "Metal",
  clay: "Clay",
  stone: "Stone",
  wood: "Wood",
  leather: "Leather",
  fibre: "Natural fibre and grass",
  paper: "Paper",
  more: "More crafts"
};

const MATERIAL_TOKEN = /^--(?:dye-([a-z]+(?:-[a-z]+)*)|dip-[1-4])$/;
const RECORDED: ReadonlySet<string> = new Set(DEPICTED_MATERIALS);

export function depictedToken(token: string): boolean {
  const found = MATERIAL_TOKEN.exec(token);
  if (!found) return false;
  return found[1] === undefined || RECORDED.has(found[1]);
}

export function materialName(token: string): string {
  return token.replace(/^--(dye-)?/, "").replaceAll("-", " ");
}
