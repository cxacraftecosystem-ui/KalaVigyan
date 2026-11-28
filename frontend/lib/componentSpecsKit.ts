import { ART_KIT, depictedToken, type ClothForm, type HeatSource, type KitLayout, type KitMotif, type KitMotion, type PasteForm, type PieceShape, type SpeciesMark, type SpeciesRole, type ToolName, type Vessel, type WaterForm } from "@/lib/artKit";
import { unitRef } from "@/lib/componentSpecsScienceParts";
import { boolean, list, nullable, object, oneOf, optional, ShapeError, tagged, type Shape } from "@/lib/shape";

export const KIT_KIND = "diagram";

export type KitPrint = { motif: KitMotif; material: string };
export type ClothPart = { part: "cloth"; form: ClothForm; material: string; printed?: KitPrint | null; label: string };
export type BlockPart = { part: "block"; motif: KitMotif; paste?: string | null; label: string };
export type BathPart = { part: "bath"; vessel: Vessel; liquor?: string | null; piece?: string | null; label: string };
export type PastePart = { part: "paste"; form: PasteForm; material: string; on?: string | null; dried?: string | null; label: string };
export type HeatPart = { part: "heat"; source: HeatSource; label: string };
export type WaterPart = { part: "water"; form: WaterForm; label: string };
export type ToolPart = { part: "tool"; tool: ToolName; held?: boolean; load?: string | null; label: string };
export type SectionLayer = { material: string; label: string };
export type SectionPart = { part: "section"; layers: SectionLayer[]; label: string };
export type PiecePart = { part: "piece"; shape: PieceShape; material?: string | null; inlay?: KitPrint | null; label: string };
export type SpeciesPart = { part: "species"; role: SpeciesRole; material?: string | null; mark?: SpeciesMark | null; breaks?: boolean; label: string };
export type KitPart = ClothPart | BlockPart | BathPart | PastePart | HeatPart | WaterPart | ToolPart | SectionPart | PiecePart | SpeciesPart;
export type KitPanel = { label: string; text?: string | null; via?: string | null; motion?: KitMotion | null; parts: KitPart[] };
export type KitHead = { title: string; caption?: string | null };
export type KitDiagramSpec = { head: KitHead; layout: KitLayout; alt: string; panels: KitPanel[] };

const material: Shape<string> = {
  expected: "a depicted material",
  parse(value, path) {
    if (typeof value !== "string" || !depictedToken(value)) throw new ShapeError(path, "a depicted material");
    return value;
  }
};
const layerMaterial: Shape<string> = {
  expected: "a depicted material or earth",
  parse(value, path) {
    if (value === ART_KIT.earth) return value;
    return material.parse(value, path);
  }
};
const maybe = <T>(inner: Shape<T>) => optional(nullable(inner));
const motif = oneOf(ART_KIT.motifs);
const printShape = object<KitPrint>({ motif, material });
const choices = ART_KIT.parts;

export const kitPartShape = tagged<KitPart>("part", {
  cloth: object<ClothPart>({ part: oneOf(["cloth"] as const), form: oneOf(choices.cloth.choices.form), material, printed: maybe(printShape), label: unitRef }),
  block: object<BlockPart>({ part: oneOf(["block"] as const), motif, paste: maybe(material), label: unitRef }),
  bath: object<BathPart>({ part: oneOf(["bath"] as const), vessel: oneOf(choices.bath.choices.vessel), liquor: maybe(material), piece: maybe(material), label: unitRef }),
  paste: object<PastePart>({ part: oneOf(["paste"] as const), form: oneOf(choices.paste.choices.form), material, on: maybe(material), dried: maybe(material), label: unitRef }),
  heat: object<HeatPart>({ part: oneOf(["heat"] as const), source: oneOf(choices.heat.choices.source), label: unitRef }),
  water: object<WaterPart>({ part: oneOf(["water"] as const), form: oneOf(choices.water.choices.form), label: unitRef }),
  tool: object<ToolPart>({ part: oneOf(["tool"] as const), tool: oneOf(choices.tool.choices.tool), held: optional(boolean), load: maybe(material), label: unitRef }),
  section: object<SectionPart>({ part: oneOf(["section"] as const), layers: list(object<SectionLayer>({ material: layerMaterial, label: unitRef }), ART_KIT.layers[0]), label: unitRef }),
  piece: object<PiecePart>({ part: oneOf(["piece"] as const), shape: oneOf(choices.piece.choices.shape), material: maybe(material), inlay: maybe(printShape), label: unitRef }),
  species: object<SpeciesPart>({ part: oneOf(["species"] as const), role: oneOf(choices.species.choices.role), material: maybe(material), mark: maybe(oneOf(choices.species.choices.mark)), breaks: optional(boolean), label: unitRef })
});

const panelShape = object<KitPanel>({ label: unitRef, text: maybe(unitRef), via: maybe(unitRef), motion: maybe(oneOf(ART_KIT.motions)), parts: list(kitPartShape, 1) });

export const kitDiagramShape = object<KitDiagramSpec>({
  head: object<KitHead>({ title: unitRef, caption: maybe(unitRef) }),
  layout: oneOf(Object.keys(ART_KIT.layouts) as KitLayout[]),
  alt: unitRef,
  panels: list(panelShape, 1)
});

const MOVES: Readonly<Record<KitMotion, (part: KitPart) => boolean>> = {
  dip: (part) => part.part === "bath" && Boolean(part.piece),
  take: (part) => part.part === "cloth",
  dry: (part) => part.part === "paste" && Boolean(part.dried),
  react: (part) => part.part === "species" && part.role === "product"
};

export function speciesParts(parts: readonly KitPart[]): SpeciesPart[] | null {
  const species = parts.filter((part): part is SpeciesPart => part.part === "species");
  return species.length > 0 && species.length === parts.length ? species : null;
}

export function movingPart(panel: Pick<KitPanel, "motion" | "parts">): number | null {
  const motion = panel.motion;
  if (!motion) return null;
  const at = panel.parts.findIndex(MOVES[motion]);
  return at < 0 ? null : at;
}

export function partMaterials(part: KitPart): string[] {
  switch (part.part) {
    case "cloth":
      return [part.material, ...(part.printed ? [part.printed.material] : [])];
    case "block":
      return part.paste ? [part.paste] : [];
    case "bath":
      return [part.liquor, part.piece].filter((token): token is string => Boolean(token));
    case "paste":
      return [part.material, ...(part.dried ? [part.dried] : [])];
    case "tool":
      return part.load ? [part.load] : [];
    case "piece":
      return [part.material, part.inlay?.material].filter((token): token is string => Boolean(token));
    case "species":
      return part.material ? [part.material] : [];
    default:
      return [];
  }
}
