"use client";

import { Cite } from "@/components/editorial/CitationCluster";
import { sentenceAnchor } from "@/lib/answerEssay";
import { headingView, paragraphAttributes, sentenceView, type AnswerLanguage } from "@/lib/answerLanguages";
import type { AnswerSection, AnswerSentence, SourceRef } from "@/lib/types";
import { cn } from "@/lib/utils";

type Citing = { numbers: ReadonlyMap<string, number>; sourcesById: ReadonlyMap<string, SourceRef> };

export function SectionBlock({
  section,
  numbers,
  sourcesById,
  compact = false,
  language = null,
  original = false
}: Citing & {
  section: AnswerSection;
  reduce?: boolean;
  compact?: boolean;
  language?: AnswerLanguage | null;
  original?: boolean;
}) {
  const heading = headingView(section, language, original);
  const paragraph = paragraphAttributes(section, language, original);
  return (
    <section className={compact ? "min-w-0" : "min-w-0 border-t border-rule pt-4"}>
      {heading.text ? (
        <h3 lang={heading.lang} dir={heading.dir} className="font-reading text-h3 text-ink-1">
          {heading.text}
        </h3>
      ) : null}
      <p lang={paragraph.lang} dir={paragraph.dir} className={cn("font-reading text-body-sm text-ink-1", heading.text ? "mt-2" : null)}>
        {section.sentences.map((sentence) => (
          <SentenceRun key={sentence.id} sentence={sentence} numbers={numbers} sourcesById={sourcesById} language={language} original={original} />
        ))}
      </p>
    </section>
  );
}

function SentenceRun({ sentence, numbers, sourcesById, language, original }: Citing & { sentence: AnswerSentence; language: AnswerLanguage | null; original: boolean }) {
  const shown = sentenceView(sentence, language, original);
  return (
    <span id={sentenceAnchor(sentence.id)} className="kv-sentence inline" data-testid="answer-sentence" data-sentence-id={sentence.id} data-level={sentence.level}>
      <span lang={shown.lang} dir={shown.dir}>
        {shown.text}
      </span>
      <Cite citations={sentence.citations} numbers={numbers} sourcesById={sourcesById} />{" "}
    </span>
  );
}
