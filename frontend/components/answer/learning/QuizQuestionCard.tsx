"use client";

import { Check, X } from "lucide-react";

import { useExplainerReading } from "@/components/answer/ExplainerReading";
import { READING_PROSE } from "@/components/answer/place/figureMarks";
import { CitedText } from "@/components/answer/ProseBlockView";
import { sentenceView } from "@/lib/answerLanguages";
import type { QuizQuestion } from "@/lib/explainerLearning";
import { optionMark, optionOrder, promptParts, type OptionMark, type QuizPick } from "@/lib/quizView";
import { cn } from "@/lib/utils";

const OPTION = "flex min-h-12 w-full min-w-0 items-center justify-between gap-2 rounded-control border px-4 py-2 text-start font-ui text-ui-lg transition-colors duration-state";

const MARK_CLASS: Record<OptionMark, string> = {
  open: "border-rule-strong bg-raised text-ink-1 hover:border-ink-1",
  right: "border-success bg-success-wash font-semibold text-ink-1",
  wrong: "border-error bg-error-wash text-ink-1",
  other: "border-rule text-ink-3"
};

const MARK_WORDS: Partial<Record<OptionMark, string>> = { right: "right answer", wrong: "your answer" };

function Prompt({ question, id }: { question: QuizQuestion; id: string }) {
  const { language } = useExplainerReading();
  const keyed = question.options[question.answer];
  const shown = keyed ? sentenceView(keyed.sentence, language, false) : null;
  const parts = promptParts(question.prompt);
  return (
    <p id={id} lang={shown?.lang} dir={shown?.dir} className="break-words font-reading text-body text-ink-1">
      {parts ? (
        <>
          {parts[0]}
          <span aria-hidden className="mx-0.5 inline-block w-16 border-b-2 border-ink-2 align-baseline" data-testid="quiz-blank" />
          <span className="sr-only">blank</span>
          {parts[1]}
        </>
      ) : (
        question.prompt
      )}
    </p>
  );
}

function OptionButton({ text, mark, onPick }: { text: string; mark: OptionMark; onPick: () => void }) {
  const words = MARK_WORDS[mark];
  return (
    <button type="button" onClick={onPick} aria-disabled={mark !== "open"} className={cn(OPTION, MARK_CLASS[mark])} data-testid="quiz-option" data-mark={mark}>
      <span className="min-w-0 break-words">{text}</span>
      {mark === "right" ? <Check className="h-4 w-4 shrink-0 text-success" aria-hidden /> : null}
      {mark === "wrong" ? <X className="h-4 w-4 shrink-0 text-error" aria-hidden /> : null}
      {words ? <span className="sr-only">, {words}</span> : null}
    </button>
  );
}

function Reveal({ question, pick, id }: { question: QuizQuestion; pick: number; id: string }) {
  const keyed = question.options[question.answer];
  const right = pick === question.answer;
  const Icon = right ? Check : X;
  return (
    <div className={cn("grid min-w-0 gap-1 border-s-2 px-4 py-3", right ? "border-success bg-success-wash" : "border-error bg-error-wash")} data-testid="quiz-reveal" data-right={right ? "true" : "false"}>
      <p className="inline-flex items-center gap-1.5 font-ui text-ui font-semibold text-ink-1">
        <Icon className={cn("h-4 w-4 shrink-0", right ? "text-success" : "text-error")} aria-hidden />
        {right ? "Right." : `Not quite. It is ${keyed.text}.`}
      </p>
      <CitedText id={id} sentences={[keyed.sentence]} className={READING_PROSE} />
    </div>
  );
}

type CardProps = { question: QuizQuestion; id: string; position: string; pick: QuizPick; onPick: (index: number) => void };

export function QuizQuestionCard({ question, id, position, pick, onPick }: CardProps) {
  const promptId = `${id}-prompt`;
  return (
    <li className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3 border-t border-rule pt-4" data-testid="quiz-question" data-answered={pick === null ? "false" : "true"}>
      <span className="kicker">{position}</span>
      <Prompt question={question} id={promptId} />
      <div role="group" aria-labelledby={promptId} className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2 sm:grid-cols-[repeat(2,minmax(0,1fr))]">
        {optionOrder(question.options).map((index) => (
          <OptionButton key={question.options[index].termKey} text={question.options[index].text} mark={optionMark(question, pick, index)} onPick={() => onPick(index)} />
        ))}
      </div>
      <div aria-live="polite" className="min-w-0">
        {pick !== null ? <Reveal question={question} pick={pick} id={`${id}-answer`} /> : null}
      </div>
    </li>
  );
}
