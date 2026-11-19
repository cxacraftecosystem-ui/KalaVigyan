"use client";

import { useMemo, type ReactNode } from "react";

import { CitationProvider, type CitationLookup } from "@/components/answer/CitationContext";
import { ExplainerReadingProvider, type ExplainerReading } from "@/components/answer/ExplainerReading";
import { SourcesList } from "@/components/answer/SourcesList";
import { TermSheet } from "@/components/answer/TermSheet";
import { useTermState } from "@/components/answer/useTermState";
import { ENGLISH, type AnswerLanguage } from "@/lib/answerLanguages";
import { listedSourceNumbers } from "@/lib/citations";
import type { SourceRef } from "@/lib/types";

export type CitedReadingProps = {
  sources: readonly SourceRef[];
  numbers: Map<string, number>;
  language?: AnswerLanguage;
  children: ReactNode;
};

export function CitedReading({ sources, numbers, language = ENGLISH, children }: CitedReadingProps) {
  const terms = useTermState();
  const sourcesById = useMemo(() => new Map(sources.map((source) => [source.id, source])), [sources]);
  const lookup = useMemo<CitationLookup>(() => ({ numbers, sourcesById }), [numbers, sourcesById]);
  const reading = useMemo<ExplainerReading>(
    () => ({ language, original: false, hiddenTerms: terms.hidden, onTerm: terms.open, listen: null }),
    [language, terms.hidden, terms.open]
  );
  return (
    <ExplainerReadingProvider value={reading}>
      <CitationProvider value={lookup}>
        {children}
        <TermSheet span={terms.span} language={language.code} onClose={terms.close} onMissing={terms.missing} onAsk={null} />
      </CitationProvider>
    </ExplainerReadingProvider>
  );
}

export function ListedSources({ sources, idPrefix, numbers }: { sources: readonly SourceRef[]; idPrefix: string; numbers?: ReadonlyMap<string, number> }) {
  const byId = new Map(sources.map((source) => [source.id, source]));
  const entries = [...listedSourceNumbers(sources, numbers)]
    .filter(([id]) => byId.has(id))
    .map(([id, number]) => ({ number, id, source: byId.get(id) ?? null }))
    .sort((a, b) => a.number - b.number);
  return entries.length > 0 ? <SourcesList entries={entries} idPrefix={idPrefix} /> : null;
}
