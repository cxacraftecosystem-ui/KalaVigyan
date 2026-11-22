import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import type { Citation } from "@/lib/types";

export const DIFFER_READINGS_MIN = 2;

export type DifferNote = { sentenceId: string; about: string | null; readings: Citation[] };

export function differingReadings(citations: readonly Citation[]): Citation[] {
  const quoted = citations.filter((citation) => (citation.quote ?? "").trim().length > 0);
  return quoted.filter((citation, at) => quoted.findIndex((other) => other.sourceId === citation.sourceId) === at);
}

export function differNotes(sentences: readonly ExplainerSentence[]): DifferNote[] {
  return sentences.flatMap((sentence) => {
    if (sentence.sourcesDiffer !== true) return [];
    const readings = differingReadings(sentence.citations);
    return readings.length < DIFFER_READINGS_MIN ? [] : [{ sentenceId: sentence.id, about: sentence.differsOn ?? null, readings }];
  });
}
