"use client";

import { useMemo } from "react";

import { Cite } from "@/components/editorial/CitationCluster";
import { italicParts, sourceNumbers, type LandingSentence } from "@/components/landing/landingContent";
import { cn } from "@/lib/utils";
import type { SourceRef } from "@/lib/types";

export type CiteMaps = { numbers: ReadonlyMap<string, number>; sourcesById: ReadonlyMap<string, SourceRef>; italic?: readonly string[] };

export function useCiteMaps(sources: readonly SourceRef[], italic: readonly string[] = []): CiteMaps {
  return useMemo(() => ({ numbers: sourceNumbers(sources), sourcesById: new Map(sources.map((source) => [source.id, source])), italic }), [sources, italic]);
}

export function CitedText({ sentence, cite, className }: { sentence: LandingSentence; cite: CiteMaps; className?: string }) {
  const parts = italicParts(sentence.text, cite.italic ?? []);
  return (
    <span className={cn("kv-sentence", className)} data-cite-host="">
      {parts.map((part, index) => (part.italic ? <i key={index}>{part.text}</i> : part.text))}
      {sentence.citations.length > 0 ? <Cite citations={sentence.citations} numbers={cite.numbers} sourcesById={cite.sourcesById} /> : null}
    </span>
  );
}
