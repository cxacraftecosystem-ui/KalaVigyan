"use client";

import { ChemEquation } from "@/components/answer/ChemEquation";
import { EvidenceTag } from "@/components/editorial/EvidenceMark";
import { Cite } from "@/components/editorial/CitationCluster";
import { evidenceState } from "@/lib/citationCluster";
import type { AnswerReaction, SourceRef } from "@/lib/types";

function ReactionRow({ reaction, numbers, sourcesById }: { reaction: AnswerReaction; numbers: ReadonlyMap<string, number>; sourcesById: ReadonlyMap<string, SourceRef> }) {
  const state = evidenceState({ evidence: "QUOTED", level: reaction.level });
  return (
    <li className="min-w-0 border-t border-rule py-4" data-testid="reaction">
      <p className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="font-ui text-h4 text-ink-1">{reaction.label}</span>
        <span className="flex flex-wrap items-center gap-3">
          {state !== "verified" ? <EvidenceTag state={state} /> : null}
          {reaction.balanced ? null : <span className="kv-tag">Unbalanced as written</span>}
        </span>
      </p>
      <ChemEquation equation={reaction.equation} className="mt-3 font-reading text-body" />
      {reaction.conditions || reaction.citations.length > 0 ? (
        <p className="mt-2 font-ui text-label text-ink-3" data-cite-host="">
          {reaction.conditions}
          <Cite citations={reaction.citations} numbers={numbers} sourcesById={sourcesById} />
        </p>
      ) : null}
    </li>
  );
}

export function ReactionsPanel({ reactions, numbers, sourcesById }: { reactions: AnswerReaction[]; numbers: ReadonlyMap<string, number>; sourcesById: ReadonlyMap<string, SourceRef> }) {
  return (
    <section className="min-w-0" aria-labelledby="reactions-heading">
      <h2 id="reactions-heading" className="font-headline text-h2 text-ink-1">
        Reactions
      </h2>
      <ol className="mt-4 grid grid-cols-1 border-b border-rule">
        {reactions.map((reaction) => (
          <ReactionRow key={reaction.id} reaction={reaction} numbers={numbers} sourcesById={sourcesById} />
        ))}
      </ol>
    </section>
  );
}
