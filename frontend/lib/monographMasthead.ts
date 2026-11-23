import { picturePlateShape, type CaptionLine, type Picture, type PicturePlateSpec } from "@/lib/componentSpecsPlates";
import type { FocalBox } from "@/lib/commonsPicture";
import { familyParts, plateMaterial } from "@/lib/craftPlate";
import type { MonographDocument, MonographNode } from "@/lib/monographDocument";
import { nodesText } from "@/lib/monographRender";
import { gradeTally, type GradeTally } from "@/lib/monographRenderKit";
import type { LabelMasthead } from "@/lib/monographRenderLayout";
import { sourceSplit } from "@/lib/monographSources";
import { parseShape } from "@/lib/shape";

export const GI_TERM = "GI";
export const MONOGRAPH_KICKER = "Monograph";
export const LEDE_KICKER = "The monograph";
export const TITLE_SIZE_MAX_CHARS = 18;

export type MastheadPhoto = { src: string; alt: string; originalWidth: number; originalHeight: number; focal: FocalBox | undefined; caption: string; credit: string };
export type MastheadPlate = { picture: Picture; captions: CaptionLine[]; credit: string };

export type DocumentLabel = {
  kicker: string;
  family: string | undefined;
  plateKicker: string | null;
  material: ReturnType<typeof plateMaterial>;
  name: string;
  gi: string | null;
  place: string | null;
  tally: GradeTally;
  kin: number;
  plate: MastheadPlate | null;
};

function parts(nodes: readonly MonographNode[]): string[] {
  return nodes.map((node) => (typeof node === "string" ? node : nodesText(node.c ?? []))).map((part) => part.trim()).filter(Boolean);
}

function termValues(document: MonographDocument, terms: readonly string[]): { gi: string | null; place: string | null } {
  const units = document.content.units;
  let gi: string | null = null;
  let place: string | null = null;
  terms.forEach((ref, at) => {
    const term = units[ref];
    const next = units[terms[at + 1]];
    if (term?.tag !== "dt" || next?.tag !== "dd") return;
    const value = nodesText(next.nodes).trim();
    if (nodesText(term.nodes).trim() === GI_TERM) gi = value;
    else place ??= value;
  });
  return { gi, place };
}

function plateSpec(document: MonographDocument, label: string | null): PicturePlateSpec | null {
  const spec = label ? document.specs[label] : undefined;
  if (!spec) return null;
  try {
    return parseShape(picturePlateShape, spec);
  } catch {
    return null;
  }
}

export function mastheadPlate(document: MonographDocument, label: string | null): MastheadPlate | null {
  const plate = plateSpec(document, label);
  if (!plate?.figure) return null;
  return { picture: plate.picture, captions: plate.figure.captions, credit: plate.figure.credit };
}

export function mastheadPhoto(document: MonographDocument, label: string | null): MastheadPhoto | null {
  const plate = mastheadPlate(document, label);
  if (!plate) return null;
  const units = document.content.units;
  const focal = plate.picture.focal;
  return {
    src: plate.picture.src,
    alt: plate.picture.alt,
    originalWidth: plate.picture.width,
    originalHeight: plate.picture.height,
    focal: focal ? [focal.x, focal.y, focal.width, focal.height] : undefined,
    caption: plate.captions.map((line) => nodesText(units[line.unit]?.nodes ?? [])).join(" ").trim(),
    credit: nodesText(units[plate.credit]?.nodes ?? []).trim()
  };
}

export function documentLabel(document: MonographDocument, label: LabelMasthead): DocumentLabel {
  const units = document.content.units;
  const [kicker = MONOGRAPH_KICKER, family] = label.kicker ? parts(units[label.kicker].nodes) : [];
  const { family: familyName, kind } = familyParts(family ?? "");
  const split = sourceSplit(document);
  return {
    kicker,
    family,
    plateKicker: kind,
    material: plateMaterial(familyName, kind),
    name: nodesText(units[label.title].nodes).trim() || document.title,
    ...termValues(document, label.terms),
    tally: gradeTally(document, split.own),
    kin: split.kin.length,
    plate: mastheadPlate(document, label.picture)
  };
}

export function titleSize(name: string): "title" | "h1" {
  return name.length <= TITLE_SIZE_MAX_CHARS ? "title" : "h1";
}
