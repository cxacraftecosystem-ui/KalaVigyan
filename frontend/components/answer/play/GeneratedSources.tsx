"use client";

import { ChemEquation } from "@/components/answer/ChemEquation";
import { CitationChips } from "@/components/answer/CitationContext";
import { DatasetCredit } from "@/components/DatasetCredit";
import type { SimulationReaction, SimulationValue } from "@/lib/explainerPlay";
import { simulationValueText, wordEquation, type ValueBasis } from "@/lib/simulationView";
import type { Citation } from "@/lib/types";

const ROW = "grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1 border-b border-rule py-2.5";
const QUOTE = "min-w-0 break-words font-reading text-quote italic text-ink-2";

function ValueRow({ value, basis }: { value: SimulationValue; basis: ValueBasis }) {
  return (
    <li className={ROW} data-testid="generated-value" data-key={value.key}>
      <span className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 font-ui text-ui font-normal">
        <span className="min-w-0 break-words text-ink-2">{value.label}</span>
        <span className="font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{simulationValueText(value)}</span>
      </span>
      {basis.kind === "stated" ? (
        <span className={QUOTE} data-testid="generated-value-stated">
          <q>{basis.stated}</q>
          <CitationChips citations={value.citations} />
        </span>
      ) : (
        <DatasetCredit dataset={basis.dataset} />
      )}
    </li>
  );
}

function ReactionRow({ reaction }: { reaction: SimulationReaction }) {
  return (
    <li className={ROW} data-testid="generated-reaction" data-reaction={reaction.reactionId}>
      <span className="min-w-0 break-words font-ui text-label text-ink-2">{reaction.label}</span>
      {reaction.equation ? (
        <ChemEquation equation={reaction.equation} display={false} className="text-body" />
      ) : (
        <span className="min-w-0 break-words font-reading text-body-sm text-ink-1">{wordEquation(reaction)}</span>
      )}
      <CitationChips citations={reaction.citations} />
    </li>
  );
}

function GroundRow({ citation }: { citation: Citation }) {
  return (
    <li className={ROW} data-testid="generated-ground">
      <span className={QUOTE}>
        {citation.quote ? <q>{citation.quote}</q> : null}
        <CitationChips citations={[citation]} />
      </span>
    </li>
  );
}

type SourcesProps = { values: readonly SimulationValue[]; bases: readonly ValueBasis[]; grounds?: readonly Citation[]; reactions?: readonly SimulationReaction[] };

export function GeneratedSources({ values, bases, grounds = [], reactions = [] }: SourcesProps) {
  return (
    <section aria-label="Built from" className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2" data-testid="generated-sources">
      <h4 className="kicker">Built from</h4>
      <ul className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1 md:grid-cols-[repeat(2,minmax(0,1fr))] md:gap-x-8">
        {reactions.map((reaction) => (
          <ReactionRow key={reaction.reactionId} reaction={reaction} />
        ))}
        {values.map((value, index) => (
          <ValueRow key={value.key} value={value} basis={bases[index]} />
        ))}
        {grounds.map((citation) => (
          <GroundRow key={citation.id} citation={citation} />
        ))}
      </ul>
    </section>
  );
}
