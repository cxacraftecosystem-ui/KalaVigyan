"use client";

import type { ReactNode } from "react";

import { CitationChips } from "@/components/answer/CitationContext";
import { useExplainerReading, useSentenceListening } from "@/components/answer/ExplainerReading";
import { EvidenceTag, HypothesisText, InferredText } from "@/components/editorial/EvidenceMark";
import { sentenceAnchor, sentenceMark } from "@/lib/answerEssay";
import { sentenceView } from "@/lib/answerLanguages";
import type { ExplainerSentence as Sentence } from "@/lib/explainerBlockBase";
import { sentenceSegments, type TextPart } from "@/lib/explainerView";
import { wordRanges } from "@/lib/listen";
import { cn } from "@/lib/utils";

export const TERM_CLASS = "font-medium text-ink-1 underline decoration-indigo decoration-dotted decoration-1 underline-offset-[3px] hover:decoration-solid";

function Parts({ parts }: { parts: TextPart[] }) {
  return parts.map((part, index) =>
    part.marked ? (
      <mark key={index} className="rounded-plate bg-turmeric-wash text-ink-1" data-testid="listen-word">
        {part.text}
      </mark>
    ) : (
      <span key={index}>{part.text}</span>
    )
  );
}

function Marked({ sentence, children }: { sentence: Sentence; children: ReactNode }) {
  const mark = sentenceMark(sentence);
  if (mark === "hypothesis") return <HypothesisText>{children}</HypothesisText>;
  if (mark === "inferred") return <InferredText>{children}</InferredText>;
  return <>{children}</>;
}

export function ExplainerSentence({ sentence }: { sentence: Sentence }) {
  const reading = useExplainerReading();
  const shown = sentenceView(sentence, reading.language, reading.original);
  const terms = sentence.terms.filter((span) => !reading.hiddenTerms.has(span.termKey));
  const listening = useSentenceListening(sentence.id);
  const mark = listening ? (wordRanges(shown.text, listening.words)[listening.wordIndex] ?? null) : null;
  const segments = sentenceSegments(shown.text, terms, mark);
  const evidence = sentenceMark(sentence);

  return (
    <span
      id={sentenceAnchor(sentence.id)}
      className={cn("kv-sentence inline", listening ? "bg-turmeric-wash" : null)}
      data-testid="answer-sentence"
      data-sentence-id={sentence.id}
      data-level={sentence.level}
      data-listening={listening ? "true" : undefined}
    >
      <Marked sentence={sentence}>
        <span lang={shown.lang} dir={shown.dir}>
          {segments.map((segment, index) => {
            const term = segment.term;
            return term ? (
              <button key={index} type="button" className={TERM_CLASS} aria-haspopup="dialog" data-testid="term-span" onClick={() => reading.onTerm(term)}>
                <Parts parts={segment.parts} />
              </button>
            ) : (
              <Parts key={index} parts={segment.parts} />
            );
          })}
        </span>
        <CitationChips citations={sentence.citations} />
      </Marked>
      {evidence ? (
        <span aria-hidden>
          {" "}
          <EvidenceTag state={evidence} />
        </span>
      ) : null}
      {sentence.sourcesDiffer ? (
        <span data-testid="sentence-differ">
          {" "}
          <EvidenceTag state="differ" />
        </span>
      ) : null}{" "}
    </span>
  );
}
