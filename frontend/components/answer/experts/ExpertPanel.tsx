"use client";

import { useMemo } from "react";

import { EvidenceSignalBadge } from "@/components/answer/EvidenceBadge";
import { ExplainerBlockView } from "@/components/answer/ExplainerBlockView";
import { CitedText } from "@/components/answer/ProseBlockView";
import { expertsDiffer, type ExpertViewBlock, type ExpertsDiffer } from "@/lib/explainerExperts";
import { differKey, differSides } from "@/lib/expertPanel";

export function ExpertsDifferCard({ pair }: { pair: ExpertsDiffer }) {
  return (
    <div className="min-w-0 border-s-2 border-madder py-1 ps-4" data-testid="experts-differ">
      <EvidenceSignalBadge signal="EXPERTS_DIFFER" />
      <div className="mt-3 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-[repeat(2,minmax(0,1fr))]">
        {differSides(pair).map((side) => (
          <div key={side.seat} className="min-w-0" data-testid="experts-differ-side" data-seat={side.seat}>
            <p className="font-ui text-label text-ink-3">{side.label}</p>
            <CitedText id={side.view.id} sentences={[side.view]} className="mt-1 font-reading text-body-sm text-ink-2" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ExpertPanel({ views, reduce }: { views: ExpertViewBlock[]; reduce: boolean }) {
  const pairs = useMemo(() => expertsDiffer(views), [views]);
  return (
    <section aria-label="Expert panel" className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6" data-testid="expert-panel">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-x-8 gap-y-6 md:grid-cols-[repeat(2,minmax(0,1fr))]">
        {views.map((view) => (
          <ExplainerBlockView key={view.id} block={view} reduce={reduce} />
        ))}
      </div>
      {pairs.map((pair) => (
        <ExpertsDifferCard key={differKey(pair)} pair={pair} />
      ))}
    </section>
  );
}
