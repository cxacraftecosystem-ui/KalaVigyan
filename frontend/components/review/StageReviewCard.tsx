"use client";

import { useState } from "react";

import { FieldBlock } from "@/components/FormControls";
import { FactSources } from "@/components/review/FactEvidence";
import { QueueDecisionBar } from "@/components/review/QueueDecisionBar";
import { QueueItemHeader } from "@/components/review/QueueItemHeader";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import type { Placement, QueueAction, StageItem, StageProcess } from "@/lib/reviewQueueContract";
import { placementOf, placeOptions, placeProblem, stageActions, stageFactsLine, stageSources } from "@/lib/stageReviewView";

const PLACE_IT = "Place it";

type Decide = (action: QueueAction, words: string, placement: Placement | null) => Promise<string | null>;

export function StageReviewCard({ item, onDecide }: { item: StageItem; onDecide: Decide }) {
  const [place, setPlace] = useState("");
  const placing = item.stage;
  const sources = stageSources(placing);

  async function decide(action: QueueAction, words: string): Promise<string | null> {
    return placeProblem(action, place) ?? onDecide(action, words, action === "approve" ? placementOf(place) : null);
  }

  return (
    <article className="grid gap-4" data-testid="stage-review-card">
      <QueueItemHeader item={item} />
      <div className="grid max-w-measure gap-1">
        <h3 className="font-headline text-h3 text-ink-1">{placing.name}</h3>
        {placing.description ? <p className="font-reading text-body-sm text-ink-1">{placing.description}</p> : null}
      </div>
      <section className="grid max-w-measure gap-2">
        <h4 className="font-ui text-h4 text-ink-1">{stageFactsLine(placing.facts.length)}</h4>
        <ul className="grid gap-2">
          {placing.facts.map((fact) => (
            <li key={fact.id} className="font-reading text-body-sm text-ink-1">
              {fact.text}
            </li>
          ))}
        </ul>
      </section>
      <div className="grid gap-5 md:grid-cols-2">
        {sources.length ? <FactSources sources={sources} /> : null}
        <div className="grid content-start gap-4">
          {placing.processes.map((process) => (
            <ProcessNow key={process.id} process={process} />
          ))}
        </div>
      </div>
      <FieldBlock label={PLACE_IT} hint="Approve writes the stage into this process, with your note kept beside it.">
        <SearchableSelect value={place} onChange={setPlace} options={placeOptions(placing)} ariaLabel={PLACE_IT} placeholder="Choose where it goes" />
      </FieldBlock>
      <QueueDecisionBar actions={stageActions()} onDecide={decide} />
    </article>
  );
}

function ProcessNow({ process }: { process: StageProcess }) {
  return (
    <section className="grid gap-2">
      <h4 className="font-ui text-h4 text-ink-1">{process.name}</h4>
      <ol className="grid list-decimal gap-1 ps-5 font-ui text-ui text-ink-1">
        {process.stages.map((stage) => (
          <li key={stage.id}>{stage.name}</li>
        ))}
      </ol>
    </section>
  );
}
