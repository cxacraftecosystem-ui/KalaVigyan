export type FigureKind = "figure" | "table";

export type NativeScript = "Deva" | "Beng" | "Gujr" | "Guru" | "Orya" | "Taml" | "Mlym" | "Telu" | "Knda" | "Aran" | "Arab" | "Mtei" | "Olck";

export type NativeName = {
  text: string;
  lang: string;
  script: NativeScript;
  sourceId: string | null;
  sourceKind: "dossier" | "wikidata";
  reviewed: boolean;
};

export type ShownNativeName = NativeName & { sourceId: string; dir: "ltr" | "rtl" };

const RIGHT_TO_LEFT = new Set<NativeScript>(["Aran", "Arab"]);

export const MASTHEAD_TITLE_LIMIT = 18;

export function figureKicker(kind: FigureKind, number: number): string {
  return kind === "table" ? `Table ${number}` : `Fig. ${number}`;
}

export function figureReference(kind: FigureKind, number: number): string {
  return `(${figureKicker(kind, number)})`;
}

export function shownNativeName(name: NativeName | null | undefined): ShownNativeName | null {
  if (!name || !name.reviewed || !name.sourceId || !name.text.trim()) return null;
  return { ...name, sourceId: name.sourceId, dir: RIGHT_TO_LEFT.has(name.script) ? "rtl" : "ltr" };
}

export function mastheadNameSize(englishName: string): "title" | "h1" {
  return englishName.trim().length <= MASTHEAD_TITLE_LIMIT ? "title" : "h1";
}

export function photoCredit(author: string, licence: string): string {
  return `Photo: ${author}, ${licence}, via Wikimedia Commons`;
}
