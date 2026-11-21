import { picturePlateShape, type PicturePlateSpec } from "@/lib/componentSpecsPlates";
import type { FocalBox } from "@/lib/commonsPicture";
import { familyParts, plateMaterial } from "@/lib/craftPlate";
import type { MonographDocument, MonographNode } from "@/lib/monographDocument";
import { citedSourceKeys, nodesText } from "@/lib/monographRender";
import { gradeTally, type GradeTally } from "@/lib/monographRenderKit";
import { citedSources, type LabelMasthead } from "@/lib/monographRenderLayout";
import { parseShape } from "@/lib/shape";

export const GI_TERM = "GI";
export const MONOGRAPH_KICKER = "Monograph";
export const LEDE_KICKER = "The monograph";

export type MastheadPhoto = { src: string; alt: string; originalWidth: number; originalHeight: number; focal: FocalBox | undefined; caption: string; credit: string };

export type DocumentLabel = {
  kicker: string;
  family: string | undefined;
  plateKicker: string | null;
  material: ReturnType<typeof plateMaterial>;
  name: string;
  gi: string | null;
  place: string | null;
  tally: GradeTally;
  photo: MastheadPhoto | null;
};

export type LedeNote = { key: string; number: number; title: string; year: number | null };

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

export function mastheadPhoto(document: MonographDocument, label: string | null): MastheadPhoto | null {
  const spec = label ? document.specs[label] : undefined;
  if (!spec) return null;
  let plate: PicturePlateSpec;
  try {
    plate = parseShape(picturePlateShape, spec);
  } catch {
    return null;
  }
  if (!plate.figure) return null;
  const units = document.content.units;
  const focal = plate.picture.focal;
  const caption = plate.figure.captions.map((line) => nodesText(units[line.unit]?.nodes ?? [])).join(" ").trim();
  return {
    src: plate.picture.src,
    alt: plate.picture.alt,
    originalWidth: plate.picture.width,
    originalHeight: plate.picture.height,
    focal: focal ? [focal.x, focal.y, focal.width, focal.height] : undefined,
    caption,
    credit: nodesText(units[plate.figure.credit]?.nodes ?? []).trim()
  };
}

export function documentLabel(document: MonographDocument, label: LabelMasthead): DocumentLabel {
  const units = document.content.units;
  const [kicker = MONOGRAPH_KICKER, family] = label.kicker ? parts(units[label.kicker].nodes) : [];
  const { family: familyName, kind } = familyParts(family ?? "");
  return {
    kicker,
    family,
    plateKicker: kind,
    material: plateMaterial(familyName, kind),
    name: nodesText(units[label.title].nodes).trim() || document.title,
    ...termValues(document, label.terms),
    tally: gradeTally(document, citedSources(document)),
    photo: mastheadPhoto(document, label.picture)
  };
}

export function ledeNotes(document: MonographDocument, lede: readonly string[]): LedeNote[] {
  const { units, sources } = document.content;
  const keys = [...new Set(lede.flatMap((ref) => citedSourceKeys(units[ref]?.nodes ?? [])))].filter((key) => Object.hasOwn(sources, key));
  return keys
    .map((key) => ({ key, number: sources[key].number, title: sources[key].title, year: sources[key].year }))
    .sort((a, b) => a.number - b.number);
}
