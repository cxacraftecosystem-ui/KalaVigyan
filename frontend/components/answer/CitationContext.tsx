"use client";

import { createContext, useContext } from "react";

import { Cite } from "@/components/editorial/CitationCluster";
import type { Citation, SourceRef } from "@/lib/types";
import { cn } from "@/lib/utils";

export type CitationLookup = {
  numbers: Map<string, number>;
  sourcesById: Map<string, SourceRef>;
  onOpen?: (citations: readonly Citation[]) => void;
};

const CitationContext = createContext<CitationLookup | null>(null);

export const CitationProvider = CitationContext.Provider;

export function useCitations(): CitationLookup {
  const lookup = useContext(CitationContext);
  if (!lookup) throw new Error("Citation chips need a CitationProvider above them.");
  return lookup;
}

export function useOptionalCitations(): CitationLookup | null {
  return useContext(CitationContext);
}

export function CitationChips({ citations, className }: { citations: readonly Citation[]; className?: string }) {
  const { numbers, sourcesById } = useCitations();
  if (citations.length === 0) return null;
  return (
    <span className={cn("inline", className)}>
      <Cite citations={citations} numbers={numbers} sourcesById={sourcesById} />
    </span>
  );
}
