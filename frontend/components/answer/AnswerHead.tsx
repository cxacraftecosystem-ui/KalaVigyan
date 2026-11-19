"use client";

import { useId, useMemo, useState, type ReactNode } from "react";

import { AnswerProvenance, type ProvenanceFacts } from "@/components/answer/AnswerProvenance";
import { useCitations } from "@/components/answer/CitationContext";
import { useExplainerReading } from "@/components/answer/ExplainerReading";
import { LedeBlock } from "@/components/answer/LedeBlock";
import { MarginNotes, Spread } from "@/components/editorial/MarginNotes";
import { TextLink } from "@/components/ui/TextLink";
import { ledeNotes, scriptLeading, shownQuestion, textScript } from "@/lib/answerEssay";
import { attributesForText } from "@/lib/answerLanguages";
import type { LedeBlock as Lede } from "@/lib/explainerContract";
import { cn } from "@/lib/utils";

function QuestionTitle({ question }: { question: string }) {
  const { language } = useExplainerReading();
  const [whole, setWhole] = useState(false);
  const fullId = useId();
  const shown = shownQuestion(question);
  const text = attributesForText(question, language);
  const script = textScript(text.lang, language);
  return (
    <>
      <h1
        lang={text.lang}
        dir={text.dir}
        data-script={script ?? undefined}
        className={cn("text-balance break-words font-headline text-ink-1", script === "Aran" || script === "Arab" ? "max-w-[22ch] text-h2" : "max-w-[18ch] text-h1", scriptLeading(script, "display"))}
        data-testid="answer-question"
      >
        {shown.shown}
      </h1>
      {shown.full ? (
        <>
          <p className="mt-3">
            <TextLink onClick={() => setWhole((open) => !open)} expanded={whole} controls={whole ? fullId : undefined} standalone>
              {whole ? "Hide the full question" : "Show the full question"}
            </TextLink>
          </p>
          {whole ? (
            <p id={fullId} lang={text.lang} dir={text.dir} className="mt-2 max-w-measure font-reading text-body text-ink-2">
              {shown.full}
            </p>
          ) : null}
        </>
      ) : null}
    </>
  );
}

function LedeSpread({ lede, actions }: { lede: Lede; actions: ReactNode }) {
  const { numbers, sourcesById } = useCitations();
  const notes = useMemo(() => ledeNotes(lede.sentences, numbers, sourcesById), [lede.sentences, numbers, sourcesById]);
  return (
    <Spread className="mt-8" margin={notes.length > 0 ? <MarginNotes notes={notes} label="Sources in this passage" /> : undefined}>
      <LedeBlock lede={lede} />
      {actions}
    </Spread>
  );
}

export function AnswerHead({ question, lede, provenance, actions }: { question: string; lede: Lede | null; provenance: ProvenanceFacts; actions: ReactNode }) {
  return (
    <header className="pb-2 pt-6 sm:pt-10 rail:pt-14" data-testid="answer-head">
      <Spread rail={<AnswerProvenance facts={provenance} />}>
        <AnswerProvenance facts={provenance} inline className="rail:hidden" />
        <QuestionTitle question={question} />
      </Spread>
      {lede ? <LedeSpread lede={lede} actions={actions} /> : <Spread className="mt-8">{actions}</Spread>}
    </header>
  );
}
