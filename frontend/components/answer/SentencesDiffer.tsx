"use client";

import { CitationChips } from "@/components/answer/CitationContext";
import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { SourcesDifferNote } from "@/components/editorial/EvidenceMark";
import type { ExplainerSentence as Sentence } from "@/lib/explainerBlockBase";
import { differNotes } from "@/lib/sourcesDiffer";

export function SentencesDiffer({ sentences }: { sentences: readonly Sentence[] }) {
  return differNotes(sentences).map((note) => (
    <SourcesDifferNote key={note.sentenceId} summary={note.about}>
      {note.readings.map((citation) => (
        <p key={citation.sourceId} className="py-0.5" data-cite-host="" data-testid="sources-differ-reading">
          <span className="italic">{citation.quote}</span>
          <CitationChips citations={[citation]} />
        </p>
      ))}
    </SourcesDifferNote>
  ));
}

export function SentenceWithReadings({ sentence }: { sentence: Sentence }) {
  return (
    <>
      <ExplainerSentence sentence={sentence} />
      <SentencesDiffer sentences={[sentence]} />
    </>
  );
}
