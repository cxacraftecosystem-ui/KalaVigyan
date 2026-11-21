"use client";

import "katex/dist/katex.min.css";

import { ChemistryMarkup, useChemistryHtml, useRenderedChemistry } from "@/components/answer/RenderedChemistry";
import { chemistryKey } from "@/lib/chemistryKeys";

export function ChemEquation({ equation, display = true, label, className }: { equation: string; display?: boolean; label?: string; className?: string }) {
  const held = useRenderedChemistry()[chemistryKey(equation, display)];
  const html = useChemistryHtml(equation, display, held);
  return <ChemistryMarkup html={html} text={equation} display={display} label={label ?? equation} className={className} />;
}
