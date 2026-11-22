"use client";

import { useMemo, useState, type ReactNode } from "react";

import { AnswerActions } from "@/components/answer/AnswerActions";
import { AnswerIdProvider } from "@/components/answer/AnswerContext";
import { AnswerHead } from "@/components/answer/AnswerHead";
import { CitationProvider, type CitationLookup } from "@/components/answer/CitationContext";
import type { CitedAnswer } from "@/lib/answerCitation";
import { ExplainerBody } from "@/components/answer/ExplainerBody";
import { ExplainerHeader, ORIGINAL_TEXT, ReadingToolsBand } from "@/components/answer/ExplainerHeader";
import { ExplainerReadingProvider, type ExplainerReading } from "@/components/answer/ExplainerReading";
import { lazyBlock } from "@/components/answer/lazyBlock";
import { ListenDock } from "@/components/answer/ListenDock";
import { SignatureFigure } from "@/components/answer/SignatureFigure";
import { TermSheet } from "@/components/answer/TermSheet";
import type { UnderstoodChange } from "@/components/answer/UnderstoodLine";
import { useListen } from "@/components/answer/useListen";
import { useTermState } from "@/components/answer/useTermState";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { answeredOn, essayDirection, essaySections, essaySourceNumbers } from "@/lib/answerEssay";
import { languageFor, type AnswerLanguage } from "@/lib/answerLanguages";
import type { Term } from "@/lib/explainerContract";
import type { ExplainerState } from "@/lib/explainerState";
import { explainerRef } from "@/lib/explainerVersions";
import { explainerSourceNumbers, hasTranslatedText, showsEarlierResearch, termQuestion } from "@/lib/explainerView";

export type ExplainerViewProps = {
  state: ExplainerState;
  streaming: boolean;
  languages: AnswerLanguage[];
  depthLabel: string | null;
  change: UnderstoodChange;
  listenLanguages: readonly string[];
  onFollowUp: ((question: string) => void) | null;
  onFreshResearch: (() => void) | null;
  tools?: ReactNode;
  versions?: ReactNode;
  footer?: ReactNode;
  filmScore?: boolean;
};

const FilmPlayer = lazyBlock(() => import("@/components/answer/film/FilmPlayer").then((module) => module.FilmPlayer), null);

function useCitationLookup(state: ExplainerState): CitationLookup {
  const sourcesById = useMemo(() => new Map(state.sources.map((source) => [source.id, source])), [state.sources]);
  const numbers = useMemo(
    () => essaySourceNumbers(explainerSourceNumbers(state.sections, state.openQuestions, state.reactions, state.lede), state.sections),
    [state.sections, state.openQuestions, state.reactions, state.lede]
  );
  return useMemo(() => ({ numbers, sourcesById }), [numbers, sourcesById]);
}

function citedAnswer(state: ExplainerState): CitedAnswer | null {
  const ref = explainerRef(state);
  if (state.phase !== "done" || !ref) return null;
  return { explainerId: ref.explainerId, version: ref.version, question: state.question };
}

function Essay({ state, streaming, reduce, active, onActive, onFollowUp, direction, lang }: { state: ExplainerState; streaming: boolean; reduce: boolean; active: string | null; onActive: (id: string) => void; onFollowUp: ((question: string) => void) | null; direction: "ltr" | "rtl"; lang: string | undefined }) {
  const provenance = { sources: state.sources, craft: state.understood?.crafts[0] ?? null, answered: answeredOn(state.mark?.createdAt) };
  return (
    <article lang={lang} dir={direction === "rtl" ? "rtl" : undefined} className="min-w-0" aria-busy={streaming || undefined} data-testid="answer-view">
      <AnswerHead question={state.question} lede={state.lede} provenance={provenance} actions={<AnswerActions answer={citedAnswer(state)} />} />
      {state.lede?.figure ? (
        <div className="mt-18 rail:mt-28">
          <SignatureFigure block={state.lede.figure} number={1} />
        </div>
      ) : null}
      <AnswerIdProvider value={state.phase === "done" ? state.answerId : null}>
        <ExplainerBody state={state} sections={essaySections(state.sections, streaming)} streaming={streaming} reduce={reduce} active={active} onActive={onActive} onFollowUp={onFollowUp} />
      </AnswerIdProvider>
    </article>
  );
}

export function ExplainerView({ state, streaming, languages, depthLabel, change, listenLanguages, onFollowUp, onFreshResearch, tools, versions, footer, filmScore = false }: ExplainerViewProps) {
  const reduce = useAppReducedMotion();
  const language = languageFor(state.language, languages);
  const [shown, setShown] = useState("translated");
  const [active, setActive] = useState<string | null>(null);
  const [filming, setFilming] = useState(false);
  const terms = useTermState();
  const listen = useListen(state.answerId, state.language);
  const lookup = useCitationLookup(state);
  const translated = hasTranslatedText(state.sections, state.lede);
  const original = translated && shown === ORIGINAL_TEXT;
  const direction = translated ? essayDirection(language, original) : "ltr";
  const filmable = state.phase === "done" && state.answerId !== null && listenLanguages.includes(state.language);
  const listenable = filmable && listen.status === "idle";
  const refreshable = state.phase === "done" && showsEarlierResearch(state.sections);
  const startFilm = () => {
    listen.stop();
    setFilming(true);
  };
  const reading = useMemo<ExplainerReading>(
    () => ({ language, original, hiddenTerms: terms.hidden, onTerm: terms.open, listen: listen.marks }),
    [language, original, terms.hidden, terms.open, listen.marks]
  );
  const craftName = state.understood?.crafts[0]?.name ?? null;
  const ask = onFollowUp ? (term: Term) => onFollowUp(termQuestion(term.label, craftName)) : null;

  return (
    <ExplainerReadingProvider value={reading}>
      <CitationProvider value={lookup}>
        <div className="grid min-w-0 gap-4">
          <ExplainerHeader understood={state.understood} depthLabel={depthLabel} language={language} change={change} shown={{ translated, original, onShow: setShown }} onListen={null} onFresh={null} />
          {versions}
          <Essay state={state} streaming={streaming} reduce={reduce} active={active} onActive={setActive} onFollowUp={onFollowUp} direction={direction} lang={direction === "rtl" ? language.code : undefined} />
          <ReadingToolsBand onListen={listenable ? listen.start : null} onFilm={filmable ? startFilm : null} onFresh={refreshable ? onFreshResearch : null} tools={tools} />
          {footer ? <div className="mx-auto mt-8 w-full max-w-measure">{footer}</div> : null}
          <TermSheet span={terms.span} language={state.language} onClose={terms.close} onMissing={terms.missing} onAsk={ask} />
          <ListenDock listen={listen} language={language} />
          {filming && state.answerId ? (
            <FilmPlayer answerId={state.answerId} question={state.question} language={language} sections={state.sections} lede={state.lede} scoreOffered={filmScore} onClose={() => setFilming(false)} />
          ) : null}
        </div>
      </CitationProvider>
    </ExplainerReadingProvider>
  );
}
