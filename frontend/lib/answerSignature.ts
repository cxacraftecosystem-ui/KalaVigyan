import type { FIRING_ATMOSPHERES, FiringBlock, LOST_WAX_STEPS, LostWaxBlock, MordantBathBlock, MordantSwatch } from "@/lib/explainerSignature";

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

export function upperFirst(text: string): string {
  const trimmed = text.trim();
  return trimmed ? `${trimmed[0].toLocaleUpperCase("en-GB")}${trimmed.slice(1)}` : trimmed;
}

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

export function firingTitle(block: Pick<FiringBlock, "body">): string {
  return `Firing ${block.body}`;
}
