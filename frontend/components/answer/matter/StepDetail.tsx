"use client";

import { ChemEquation } from "@/components/answer/ChemEquation";
import { CitationChips } from "@/components/answer/CitationContext";
import { StepColours } from "@/components/answer/matter/StepColours";
import { CitedText } from "@/components/answer/ProseBlockView";
import { SpeciesRow } from "@/components/answer/SpeciesRow";
import { EvidenceTag } from "@/components/editorial/EvidenceMark";
import { levelMark, signalMark } from "@/lib/citationCluster";
import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import type { ReactionStep } from "@/lib/explainerMatter";
import { reactionSpoken, speciesNamesLine } from "@/lib/processView";
import { stepSignal } from "@/lib/reactionPlayer";

function StepConditions({ step }: { step: ReactionStep }) {
  const conditions = step.conditions ?? [];
  if (conditions.length === 0) return null;
  return (
    <dl className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-rule font-ui text-label font-normal sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)]" aria-label="Conditions">
      {conditions.map((condition, index) => (
        <div key={`${condition.label}:${index}`} className="contents" data-testid="step-condition">
          <dt className="pt-2 font-semibold text-ink-1 sm:border-b sm:border-rule sm:pb-2">{condition.label}</dt>
          <dd className="border-b border-rule pb-2 text-ink-2 sm:pt-2">
            {condition.stated}
            <CitationChips citations={condition.citations} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function StepWhy({ id, notes }: { id: string; notes: readonly ExplainerSentence[] }) {
  if (notes.length === 0) return null;
  return (
    <div className="min-w-0" data-testid="step-why">
      <p className="kicker">What happens and why</p>
      <CitedText id={id} sentences={notes} className="mt-1 max-w-measure font-reading text-body-sm text-ink-1" />
    </div>
  );
}

export function StepDetail({ step, notes, animate }: { step: ReactionStep; notes: readonly ExplainerSentence[]; animate: boolean }) {
  const signal = stepSignal(step);
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3 pb-3 sm:ps-11" data-testid="reaction-step-detail">
      <span className="flex flex-wrap items-center gap-1.5">
        {signal ? <EvidenceTag {...signalMark(signal)} /> : null}
        <EvidenceTag {...levelMark(step.level)} />
      </span>
      {step.equation ? (
        <>
          <ChemEquation equation={step.equation} label={reactionSpoken(step)} className="text-body" />
          <p className="font-ui text-caption text-ink-3">{speciesNamesLine(step)}</p>
        </>
      ) : (
        <SpeciesRow reaction={step} />
      )}
      <StepColours step={step} animate={animate} />
      <StepConditions step={step} />
      <StepWhy id={`${step.reactionId}.why`} notes={notes} />
      <p className="font-ui text-label">
        <CitationChips citations={step.citations} />
      </p>
    </div>
  );
}
