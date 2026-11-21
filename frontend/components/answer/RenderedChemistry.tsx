"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { NO_CHEMISTRY, type RenderedChemistry } from "@/lib/chemistryKeys";
import { cn } from "@/lib/utils";

const RenderedChemistryContext = createContext<RenderedChemistry>(NO_CHEMISTRY);

export function RenderedChemistryProvider({ rendered, children }: { rendered: RenderedChemistry; children?: ReactNode }) {
  return <RenderedChemistryContext.Provider value={rendered}>{children}</RenderedChemistryContext.Provider>;
}

export function useRenderedChemistry(): RenderedChemistry {
  return useContext(RenderedChemistryContext);
}

export function useChemistryHtml(equation: string, display: boolean, held: string | undefined): string | null {
  const [drawn, setDrawn] = useState<{ key: string; html: string } | null>(null);
  const key = `${display}:${equation}`;
  useEffect(() => {
    if (held !== undefined) return;
    let current = true;
    void import("@/lib/chemistry").then(({ renderChemistry }) => {
      if (current) setDrawn({ key, html: renderChemistry(equation, display) });
    });
    return () => {
      current = false;
    };
  }, [display, equation, held, key]);
  if (held !== undefined) return held;
  return drawn !== null && drawn.key === key ? drawn.html : null;
}

export type ChemistryMarkupProps = { html: string | null; text: string; display: boolean; label: string; className?: string };

export function ChemistryMarkup({ html, text, display, label, className }: ChemistryMarkupProps) {
  const shape = cn("block max-w-full overflow-x-auto text-ink-1", !display && "inline-block align-middle", className);
  if (html === null) {
    return (
      <span role="math" aria-label={label} className={shape}>
        {text}
      </span>
    );
  }
  return <span role="math" aria-label={label} className={shape} dangerouslySetInnerHTML={{ __html: html }} />;
}
