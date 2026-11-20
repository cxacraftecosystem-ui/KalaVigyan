import {
  atlasPlate,
  categoryHref,
  familyCrafts,
  familyMaterial,
  familyName,
  isMonograph,
  sortedFamilies,
  subFamilyCounts,
  type AtlasPlate,
  type SubFamilyCount
} from "@/lib/atlasCollection";
import { monographCount } from "@/lib/atlasIndex";
import type { PlateMaterial } from "@/components/editorial/TypographicPlate";
import type { CatalogueCraft, CraftCatalogue } from "@/lib/craftCatalogueContract";

export const DOCUMENTS_SHOWN = 8;
export const FAMILY_PLATES = 2;

export type LandingStat = { key: string; value: number; label: string };
export type FamilyBlock = { id: string; name: string; href: string; material: PlateMaterial; count: number; documents: number; subFamilies: SubFamilyCount[]; plates: AtlasPlate[] };
export type LandingCollection = { stats: LandingStat[]; documents: AtlasPlate[]; families: FamilyBlock[]; crafts: number };

function slim(craft: CatalogueCraft): CatalogueCraft {
  return { ...craft, aliases: [], stateOfOrigin: craft.stateOfOrigin.slice(0, 1), stateOfPractice: craft.stateOfPractice.slice(0, 1) };
}

function slimPlate(plate: AtlasPlate): AtlasPlate {
  return { ...plate, craft: slim(plate.craft) };
}

export function interleaved<T>(groups: readonly (readonly T[])[]): T[] {
  const longest = groups.reduce((most, group) => Math.max(most, group.length), 0);
  const out: T[] = [];
  for (let at = 0; at < longest; at += 1) for (const group of groups) if (at < group.length) out.push(group[at]);
  return out;
}

export function documentPlates(catalogue: CraftCatalogue): AtlasPlate[] {
  const byFamily = sortedFamilies(catalogue).map((family) => familyCrafts(catalogue, family).filter(isMonograph).map((craft) => atlasPlate(family, craft)));
  const plates = interleaved(byFamily);
  return [...plates.filter((plate) => plate.craft.hero), ...plates.filter((plate) => !plate.craft.hero)].map(slimPlate);
}

export function familyBlocks(catalogue: CraftCatalogue): FamilyBlock[] {
  return sortedFamilies(catalogue).map((family) => {
    const crafts = familyCrafts(catalogue, family);
    const shown = crafts.filter((craft) => !isMonograph(craft)).slice(0, FAMILY_PLATES);
    return {
      id: family.id,
      name: familyName(family),
      href: categoryHref(family),
      material: familyMaterial(family),
      count: family.readerCount,
      documents: crafts.filter(isMonograph).length,
      subFamilies: subFamilyCounts(family),
      plates: shown.map((craft) => slimPlate(atlasPlate(family, craft)))
    };
  });
}

export function collectionStats(catalogue: CraftCatalogue): LandingStat[] {
  const { crafts, giRegistered, states } = catalogue.summary;
  const families = sortedFamilies(catalogue).length;
  return [
    { key: "crafts", value: crafts, label: crafts === 1 ? "craft" : "crafts" },
    { key: "families", value: families, label: families === 1 ? "family" : "families" },
    { key: "states", value: states, label: states === 1 ? "state or union territory" : "states and union territories" },
    { key: "gi", value: giRegistered, label: "with a registered geographical indication" },
    { key: "monographs", value: monographCount(catalogue), label: "monographs read in full" }
  ];
}

export function landingCollection(catalogue: CraftCatalogue | null): LandingCollection | null {
  if (!catalogue) return null;
  return { stats: collectionStats(catalogue), documents: documentPlates(catalogue), families: familyBlocks(catalogue), crafts: catalogue.summary.crafts };
}
