import type { MonographDocument } from "@/lib/monographDocument";

export type ChemistryAsk = { equation: string; display: boolean };
export type RenderedChemistry = Readonly<Record<string, string>>;

export const NO_CHEMISTRY: RenderedChemistry = {};
const DRAWN_KINDS = new Set(["answer_block"]);
const INLINE_FIELDS = new Set(["formula"]);
const EQUATION_FIELDS = new Set(["equation"]);

export function chemistryKey(equation: string, display: boolean): string {
  return `${display ? "block" : "inline"}:${equation}`;
}

function asksOf(value: unknown, field: string | null, found: Map<string, ChemistryAsk>): void {
  if (Array.isArray(value)) {
    value.forEach((item) => asksOf(item, null, found));
    return;
  }
  if (typeof value === "string" && field !== null && value.trim()) {
    const displays = EQUATION_FIELDS.has(field) ? [true, false] : INLINE_FIELDS.has(field) ? [false] : [];
    for (const display of displays) found.set(chemistryKey(value, display), { equation: value, display });
    return;
  }
  if (typeof value !== "object" || value === null) return;
  for (const [key, inner] of Object.entries(value)) asksOf(inner, key, found);
}

export function chemistryAsks(value: unknown): ChemistryAsk[] {
  const found = new Map<string, ChemistryAsk>();
  asksOf(value, null, found);
  return [...found.values()];
}

export function documentChemistry(document: MonographDocument): ChemistryAsk[] {
  const drawn = document.content.components.filter((component) => DRAWN_KINDS.has(component.kind) && Object.hasOwn(document.specs, component.label));
  return chemistryAsks(drawn.map((component) => document.specs[component.label]));
}
