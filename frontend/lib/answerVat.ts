import { factsOnce, type SaidFact } from "@/lib/answerSignature";
import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import type { IndigoVatBlock, VatDip } from "@/lib/explainerSignature";
import type { VatPhase } from "@/lib/motion";
import { onceSaid } from "@/lib/sentenceGroups";

export type Atoms = ReadonlyMap<string, number>;
export type FormulaPart = { symbol: string; count: string };
export type Species = { coefficient: number; formula: string; name: string };
export type AtomRow = { atom: string; before: string; after: string };
export type VatEquation = { reactants: Species[]; products: Species[]; rows: AtomRow[]; spoken: string };
export type VatFrame = { key: "in" | "lifted" | "air"; title: string; sentence: ExplainerSentence | null };
export type VatText = { dek: ExplainerSentence | null; frames: VatFrame[]; facts: SaidFact[] };

export const VAT_DIPS = 4;

const ELEMENT = /([A-Z][a-z]?)(\d*)/g;
const FORMULA = /^(?:[A-Z][a-z]?\d*)+$/;
const OXYGEN = "O2";
const WATER = "H2O";

export function formulaParts(formula: string): FormulaPart[] {
  return [...formula.matchAll(ELEMENT)].map((found) => ({ symbol: found[1], count: found[2] }));
}

export function formulaAtoms(formula: string): Atoms | null {
  if (!FORMULA.test(formula)) return null;
  const atoms = new Map<string, number>();
  for (const part of formulaParts(formula)) atoms.set(part.symbol, (atoms.get(part.symbol) ?? 0) + (part.count === "" ? 1 : Number(part.count)));
  return atoms;
}

export function hillOrder(symbols: Iterable<string>): string[] {
  const unique = [...new Set(symbols)];
  const carbon = unique.includes("C");
  const lead = carbon ? ["C", ...(unique.includes("H") ? ["H"] : [])] : [];
  return [...lead, ...unique.filter((symbol) => !lead.includes(symbol)).sort()];
}

function term(coefficient: number, count: number): string {
  if (count === 1) return String(coefficient);
  if (coefficient === 1) return String(count);
  return `${coefficient} × ${count}`;
}

function sideRow(side: readonly Species[], atom: string): { text: string; total: number } {
  const parts = side.flatMap((species) => {
    const count = formulaAtoms(species.formula)?.get(atom) ?? 0;
    return count > 0 ? [{ text: term(species.coefficient, count), value: species.coefficient * count }] : [];
  });
  const total = parts.reduce((sum, part) => sum + part.value, 0);
  return { text: `${parts.map((part) => part.text).join(" + ")} = ${total}`, total };
}

export function atomRows(reactants: readonly Species[], products: readonly Species[]): AtomRow[] | null {
  const symbols = hillOrder([...reactants, ...products].flatMap((species) => [...(formulaAtoms(species.formula)?.keys() ?? [])]));
  const rows = symbols.map((atom) => ({ atom, before: sideRow(reactants, atom), after: sideRow(products, atom) }));
  if (rows.some((row) => row.before.total !== row.after.total)) return null;
  return rows.map((row) => ({ atom: row.atom, before: row.before.text, after: row.after.text }));
}

function differsByHydrogen(leuco: Atoms, keto: Atoms): boolean {
  const symbols = new Set([...leuco.keys(), ...keto.keys()]);
  return [...symbols].every((symbol) => (symbol === "H" ? (leuco.get("H") ?? 0) - (keto.get("H") ?? 0) === 2 : leuco.get(symbol) === keto.get(symbol)));
}

function spokenSide(side: readonly Species[]): string {
  return side.map((species) => (species.coefficient === 1 ? species.name : `${species.coefficient} ${species.name}`)).join(" plus ");
}

export function vatEquation(leuco: { formula: string | null; name: string }, keto: { formula: string | null; name: string }): VatEquation | null {
  if (!leuco.formula || !keto.formula) return null;
  const reduced = formulaAtoms(leuco.formula);
  const oxidised = formulaAtoms(keto.formula);
  if (!reduced || !oxidised || !differsByHydrogen(reduced, oxidised)) return null;
  const reactants = [
    { coefficient: 2, formula: leuco.formula, name: leuco.name },
    { coefficient: 1, formula: OXYGEN, name: "oxygen" }
  ];
  const products = [
    { coefficient: 2, formula: keto.formula, name: keto.name },
    { coefficient: 2, formula: WATER, name: "water" }
  ];
  const rows = atomRows(reactants, products);
  return rows ? { reactants, products, rows, spoken: `${spokenSide(reactants)} gives ${spokenSide(products)}` } : null;
}

export function dipLabel(dip: Pick<VatDip, "stated" | "shade">): string {
  return dip.shade ? `${dip.stated}, ${dip.shade}` : dip.stated;
}

export function vatText(block: IndigoVatBlock): VatText {
  const say = onceSaid();
  const form = (kind: "LEUCO" | "KETO") => block.forms.find((entry) => entry.form === kind)?.sentence;
  const dek = say(block.dips[0]?.sentence);
  const frames: VatFrame[] = [
    { key: "in", title: "In the vat", sentence: say(form("LEUCO")) },
    { key: "lifted", title: "Lifted", sentence: say(block.lift) },
    { key: "air", title: "In the air", sentence: say(form("KETO")) }
  ];
  const contents = block.contents.map((content) => ({ label: content.name, sentence: content.sentence }));
  const dips = block.dips.slice(1).map((dip) => ({ label: dipLabel(dip), sentence: dip.sentence }));
  const facts = factsOnce([...contents, ...dips]).flatMap((fact) => (say(fact.sentence) ? [fact] : []));
  return { dek, frames, facts };
}

export function currentFrame(phase: VatPhase): VatFrame["key"] {
  return phase === "rest" ? "air" : phase;
}

const PHASE_WORDS: Record<VatPhase, string> = {
  in: "In the vat the dissolved dye soaks into the fibre.",
  lifted: "Lifted out, the cloth is green.",
  air: "In the air the cloth turns from green to blue.",
  rest: "In the air the cloth turns from green to blue."
};

export function dipStatus(dip: number, phase: VatPhase): string {
  return `Dip ${dip} of ${VAT_DIPS}. ${PHASE_WORDS[phase]}`;
}

export function nextDip(dip: number): number {
  return dip >= VAT_DIPS ? 1 : dip + 1;
}

export function pubchemHref(cid: number): string {
  return `https://pubchem.ncbi.nlm.nih.gov/compound/${cid}`;
}
