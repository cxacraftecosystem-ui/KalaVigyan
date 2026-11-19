"use client";

import { useMemo } from "react";
import "katex/dist/katex.min.css";

import { renderChemistry } from "@/lib/chemistry";
import { cn } from "@/lib/utils";

export function ChemEquation({ equation, display = true, label, className }: { equation: string; display?: boolean; label?: string; className?: string }) {
  const html = useMemo(() => renderChemistry(equation, display), [display, equation]);
  return (
    <span
      role="math"
      aria-label={label ?? equation}
      className={cn("block max-w-full overflow-x-auto text-ink-1", !display && "inline-block align-middle", className)}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
