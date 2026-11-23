import { readFileSync } from "node:fs";
import { join } from "node:path";

export const LATIN_FONTS = join(__dirname, "..", "app", "latinFonts.ts");

export type FaceVariant = { style: string; weights: [number, number] };
export type LatinFace = { name: string; family: string; files: string[]; preloaded: boolean; variants: FaceVariant[]; ranges: [number, number][] };
export type DrawnText = { family: string; style: string; weight: number; text: string; where?: string };

function weights(value: string): [number, number] {
  const [low, high = low] = value.trim().split(/\s+/).map(Number);
  return [low, high];
}

function variants(block: string): FaceVariant[] {
  const listed = [...block.matchAll(/\{ path: "[^"]+", weight: "([^"]+)", style: "(\w+)" \}/g)].map((found) => ({ style: found[2], weights: weights(found[1]) }));
  if (listed.length) return listed;
  const weight = /\n {2}weight: "([^"]+)"/.exec(block)?.[1] ?? "400";
  const style = /\n {2}style: "(\w+)"/.exec(block)?.[1] ?? "normal";
  return [{ style, weights: weights(weight) }];
}

export function codeRanges(value: string): [number, number][] {
  return value.split(",").map((part) => {
    const [low, high = low] = part.trim().replace(/^U\+/i, "").split("-");
    return [parseInt(low, 16), parseInt(high, 16)];
  });
}

export function latinFaces(source: string = readFileSync(LATIN_FONTS, "utf8")): LatinFace[] {
  return source
    .split(/\nconst /)
    .slice(1)
    .filter((block) => block.includes("localFont("))
    .map((block) => ({
      name: block.slice(0, block.indexOf(" ")),
      family: /prop: "font-family", value: "([^"]+)"/.exec(block)?.[1] ?? "",
      files: [...block.matchAll(/\.\.\/fonts\/([a-z0-9-]+\.woff2)/g)].map((found) => found[1]),
      preloaded: !block.includes("preload: false"),
      variants: variants(block),
      ranges: codeRanges(/prop: "unicode-range", value: "([^"]+)"/.exec(block)?.[1] ?? "")
    }));
}

function distance(variant: FaceVariant, weight: number): number {
  const [low, high] = variant.weights;
  return weight < low ? low - weight : weight > high ? weight - high : 0;
}

export function faceFor(faces: readonly LatinFace[], drawn: Omit<DrawnText, "text">, codepoint: number): LatinFace | null {
  const covering = faces.filter((face) => face.family === drawn.family && face.ranges.some(([low, high]) => codepoint >= low && codepoint <= high));
  const styled = covering.flatMap((face) => face.variants.filter((variant) => variant.style === drawn.style).map((variant) => ({ face, gap: distance(variant, drawn.weight) })));
  styled.sort((left, right) => left.gap - right.gap);
  return styled[0]?.face ?? null;
}

export function facesDrawn(faces: readonly LatinFace[], texts: readonly DrawnText[]): Set<string> {
  const drawn = new Set<string>();
  for (const text of texts) {
    for (const character of text.text.replace(/\s/g, "")) {
      const face = faceFor(faces, text, character.codePointAt(0) ?? 0);
      if (face) drawn.add(face.name);
    }
  }
  return drawn;
}
