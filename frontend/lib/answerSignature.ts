import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import type { FIRING_ATMOSPHERES, FiringBlock, LOST_WAX_STEPS, LostWaxBlock, MordantBathBlock, MordantSwatch } from "@/lib/explainerSignature";
import { upperFirst } from "@/lib/format";
import { bySentence } from "@/lib/sentenceGroups";

export type SaidFact = { label: string; sentence: ExplainerSentence };

export const FACT_LABEL_JOIN = " · ";

type SignatureStep = (typeof LOST_WAX_STEPS)[number] | (typeof FIRING_ATMOSPHERES)[number];

const STEP_LABEL: Record<SignatureStep, string> = {
  MODEL: "Wax model",
  JACKET: "Clay jacket",
  BURNOUT: "Wax burnt out",
  POUR: "Metal poured",
  BREAK_OUT: "Mould broken",
  OXIDISING: "Oxidising fire",
  REDUCING: "Reducing fire"
};

export function signatureStepLabel(step: SignatureStep, colour?: string): string {
  return colour ? `${STEP_LABEL[step]}, ${colour}` : STEP_LABEL[step];
}

export function mordantTitle(block: Pick<MordantBathBlock, "dye" | "fibre">): string {
  return `${upperFirst(block.dye)} on ${block.fibre}`;
}

export function mordantLabel(swatch: Pick<MordantSwatch, "mordant" | "colour">): string {
  return swatch.mordant ? `${upperFirst(swatch.mordant)} gives ${swatch.colour}` : `Without a mordant, ${swatch.colour}`;
}

export function lostWaxTitle(block: Pick<LostWaxBlock, "metal">): string {
  return `Casting ${block.metal} by lost wax`;
}

export function factsOnce(facts: readonly SaidFact[]): SaidFact[] {
  return bySentence(facts, (fact) => fact.sentence).map((group) => ({ label: group.items.map((fact) => fact.label).join(FACT_LABEL_JOIN), sentence: group.sentence }));
}

export function firingFacts(block: Pick<FiringBlock, "atmospheres" | "temperature">): SaidFact[] {
  const atmospheres = block.atmospheres.map((atmosphere) => ({ label: signatureStepLabel(atmosphere.atmosphere, atmosphere.colour), sentence: atmosphere.sentence }));
  const temperature = block.temperature ? [{ label: `Temperature, ${block.temperature.stated}`, sentence: block.temperature.sentence }] : [];
  return factsOnce([...atmospheres, ...temperature]);
}

export function firingTitle(block: Pick<FiringBlock, "body">): string {
  return `Firing ${block.body}`;
}
