import type { PlateMaterial } from "@/components/editorial/TypographicPlate";
import { familyParts, plateMaterial } from "@/lib/craftPlate";
import { listText } from "@/lib/format";
import { boolean, list, matching, nullable, object, text } from "@/lib/shape";

export type KinCraft = { name: string; path: string; place: string | null; gi: boolean; monograph: boolean; shares: string[]; sentence: string };
export type KinHead = { title: string; family: string | null };
export type KinCraftsSpec = { head: KinHead; crafts: KinCraft[] };

const CRAFT_PATH = /^\/crafts\/[A-Za-z0-9-]+$/;

export const kinCraftsShape = object<KinCraftsSpec>({
  head: object<KinHead>({ title: text, family: nullable(text) }),
  crafts: list(
    object<KinCraft>({
      name: text,
      path: matching(CRAFT_PATH, "a craft page path"),
      place: nullable(text),
      gi: boolean,
      monograph: boolean,
      shares: list(text),
      sentence: text
    }),
    1
  )
});

export function kinMaterial(family: string | null): PlateMaterial {
  const parts = family ? familyParts(family) : { family: null, kind: null };
  return plateMaterial(parts.family, parts.kind);
}

export function sharesLine(shares: readonly string[]): string | null {
  return shares.length === 0 ? null : `Shares ${listText(shares)}`;
}
