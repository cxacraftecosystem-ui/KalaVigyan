import { renderChemistry } from "@/lib/chemistry";
import { chemistryKey, type ChemistryAsk, type RenderedChemistry } from "@/lib/chemistryKeys";

export function renderedChemistry(asks: readonly ChemistryAsk[]): RenderedChemistry {
  return Object.fromEntries(asks.map((ask) => [chemistryKey(ask.equation, ask.display), renderChemistry(ask.equation, ask.display)]));
}
