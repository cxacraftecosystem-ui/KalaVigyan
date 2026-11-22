"use client";

import { SectionBlock } from "@/components/answer/AnswerSectionBlock";
import { AnswerProgress } from "@/components/answer/AnswerProgress";
import { useCitations } from "@/components/answer/CitationContext";
import { useExplainerReading } from "@/components/answer/ExplainerReading";
import { ExplainerSectionView } from "@/components/answer/ExplainerSectionView";
import { NumberedFigures } from "@/components/answer/place/AnswerFigure";
import { ReactionsPanel } from "@/components/answer/ReactionsPanel";
import { ResearchTrail } from "@/components/answer/ResearchTrail";
import { SectionBar } from "@/components/answer/SectionBar";
import { SourcesList, type NumberedSource } from "@/components/answer/SourcesList";
import { Spread } from "@/components/editorial/MarginNotes";
import { Accordion } from "@/components/ui/Accordion";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { attributesForText } from "@/lib/answerLanguages";
import type { ExplainerState, SectionView } from "@/lib/explainerState";

export type BodyProps = {
  state: ExplainerState;
  sections: SectionView[];
  streaming: boolean;
  reduce: boolean;
  active: string | null;
  onActive: (id: string) => void;
  onFollowUp: ((question: string) => void) | null;
};

function numberedSources(numbers: ReadonlyMap<string, number>, sourcesById: ReadonlyMap<string, ExplainerState["sources"][number]>): NumberedSource[] {
  return [...numbers.entries()].sort((a, b) => a[1] - b[1]).map(([id, number]) => ({ number, id, source: sourcesById.get(id) ?? null }));
}

function OpenQuestions({ state }: { state: ExplainerState }) {
  const { language, original } = useExplainerReading();
  const { numbers, sourcesById } = useCitations();
  if (!state.openQuestions.some((section) => section.sentences.length > 0)) return null;
  return (
    <Accordion title="Open questions" subtitle="Hypotheses the sources raise without settling.">
      <div className="grid gap-4">
        {state.openQuestions.map((section) => (
          <SectionBlock key={section.id} section={section} numbers={numbers} sourcesById={sourcesById} compact language={language} original={original} />
        ))}
      </div>
    </Accordion>
  );
}

function FollowUps({ items, onFollowUp }: { items: string[]; onFollowUp: (question: string) => void }) {
  const { language } = useExplainerReading();
  return (
    <section aria-labelledby="ask-next-heading" className="min-w-0" data-testid="follow-ups">
      <h2 id="ask-next-heading" className="font-headline text-h2 text-ink-1">
        Ask next
      </h2>
      <ActionGroup align="start" className="mt-4">
        {items.map((question) => (
          <Button key={question} variant="quiet" onClick={() => onFollowUp(question)} {...attributesForText(question, language)}>
            {question}
          </Button>
        ))}
      </ActionGroup>
    </section>
  );
}

export function ExplainerBody({ state, sections, streaming, reduce, active, onActive, onFollowUp }: BodyProps) {
  const { numbers, sourcesById } = useCitations();
  const numbered = numberedSources(numbers, sourcesById);
  const writing = sections.some((section) => section.blocks.length > 0);
  const asking = !streaming && state.followUps.length > 0 && onFollowUp !== null;
  const closing = state.reactions.length > 0 || state.openQuestions.length > 0 || numbered.length > 0 || asking;
  return (
    <>
      {streaming ? <ResearchTrail trail={state.trail} /> : null}
      <SectionBar sections={sections} active={active} streaming={streaming} onPick={onActive} />
      {streaming ? (
        <div className="mx-auto mt-6 max-w-measure">
          <AnswerProgress status={state.status} writing={writing} />
        </div>
      ) : null}
      <NumberedFigures.Provider value>
        {sections.map((section, index) => (
          <ExplainerSectionView key={section.id} section={section} number={index + 1} streaming={streaming} reduce={reduce} onActive={onActive} />
        ))}
      </NumberedFigures.Provider>
      {closing ? (
        <Spread className="border-t border-ink-1 pt-12">
          <div className="grid min-w-0 gap-12">
            {state.reactions.length > 0 ? <ReactionsPanel reactions={state.reactions} numbers={numbers} sourcesById={sourcesById} /> : null}
            <OpenQuestions state={state} />
            {numbered.length > 0 ? <SourcesList entries={numbered} /> : null}
            {asking && onFollowUp ? <FollowUps items={state.followUps} onFollowUp={onFollowUp} /> : null}
          </div>
        </Spread>
      ) : null}
    </>
  );
}
