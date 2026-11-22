"use client";

import { createContext, useContext, useSyncExternalStore } from "react";

import type { AnswerLanguage } from "@/lib/answerLanguages";
import type { TermSpan } from "@/lib/explainerBlockBase";
import type { ListenMark } from "@/lib/listen";
import { markOfSentence, type ListenMarks } from "@/lib/listenMarks";

export type ExplainerReading = {
  language: AnswerLanguage;
  original: boolean;
  hiddenTerms: ReadonlySet<string>;
  onTerm: (span: TermSpan) => void;
  listen: ListenMarks | null;
};

const ReadingContext = createContext<ExplainerReading | null>(null);

export const ExplainerReadingProvider = ReadingContext.Provider;

function subscribeNever(): () => void {
  return () => undefined;
}

export function useExplainerReading(): ExplainerReading {
  const reading = useContext(ReadingContext);
  if (!reading) throw new Error("Explainer sentences need an ExplainerReadingProvider above them.");
  return reading;
}

export function useSentenceListening(sentenceId: string): ListenMark | null {
  const { listen } = useExplainerReading();
  const marked = () => markOfSentence(listen, sentenceId);
  return useSyncExternalStore(listen?.subscribe ?? subscribeNever, marked, marked);
}
