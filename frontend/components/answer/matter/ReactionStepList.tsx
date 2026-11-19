"use client";

import { StepDetail } from "@/components/answer/matter/StepDetail";
import { STEP_NUMBER } from "@/components/answer/place/figureMarks";
import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import type { ReactionStep } from "@/lib/explainerMatter";
import { stepKindLabel } from "@/lib/reactionPlayer";
import { cn } from "@/lib/utils";

type StepListProps = {
  steps: readonly ReactionStep[];
  open: number | null;
  animate: boolean;
  onChoose: (index: number) => void;
  notesFor: (step: ReactionStep) => readonly ExplainerSentence[];
};

function StepNumber({ number, reached }: { number: number; reached: boolean }) {
  return (
    <span aria-hidden className={cn(STEP_NUMBER, reached ? "bg-ink-1 text-ground" : "border border-rule-strong text-ink-3")}>
      {number}
    </span>
  );
}

function StepLabel({ step, number, reached }: { step: ReactionStep; number: number; reached: boolean }) {
  return (
    <span className="flex min-w-0 items-start gap-3">
      <StepNumber number={number} reached={reached} />
      <span className="min-w-0 pt-1">
        <span className="block break-words font-ui text-h4 text-ink-1">{step.label}</span>
        <span className="block font-ui text-caption text-ink-3">{step.stage ? `${stepKindLabel(step)} · ${step.stage}` : stepKindLabel(step)}</span>
      </span>
    </span>
  );
}

function StepItem({ step, index, open, animate, onChoose, notesFor }: Omit<StepListProps, "steps"> & { step: ReactionStep; index: number }) {
  const current = open === index;
  const expanded = open === null || current;
  const reached = open === null || index <= open;
  return (
    <li
      aria-current={current ? "step" : undefined}
      data-testid="reaction-step"
      data-open={expanded ? "true" : "false"}
      className={cn("min-w-0 border-b border-s-2 border-b-rule ps-3 transition-colors duration-state sm:ps-4", current ? "border-s-ink-1" : "border-s-transparent")}
    >
      {open === null ? (
        <div className="py-3">
          <StepLabel step={step} number={index + 1} reached={reached} />
        </div>
      ) : (
        <button type="button" onClick={() => onChoose(index)} aria-expanded={current} className="block w-full rounded-control py-3 text-start hover:bg-sunk">
          <StepLabel step={step} number={index + 1} reached={reached} />
        </button>
      )}
      {expanded ? <StepDetail step={step} notes={notesFor(step)} animate={current && animate} /> : null}
    </li>
  );
}

export function ReactionStepList({ steps, open, animate, onChoose, notesFor }: StepListProps) {
  return (
    <ol className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-rule" aria-label="Reaction steps">
      {steps.map((step, index) => (
        <StepItem key={step.reactionId} step={step} index={index} open={open} animate={animate} onChoose={onChoose} notesFor={notesFor} />
      ))}
    </ol>
  );
}
