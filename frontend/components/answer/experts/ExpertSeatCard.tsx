"use client";

import { CitedText } from "@/components/answer/ProseBlockView";
import type { ExpertViewBlock } from "@/lib/explainerExperts";
import { agreementText, seatLabel } from "@/lib/expertPanel";

export function ExpertSeatCard({ block }: { block: ExpertViewBlock }) {
  const agreement = agreementText(block);
  return (
    <article className="grid h-full min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-2 border-t border-ink-1 pt-3" data-testid="expert-seat" data-seat={block.seat}>
      <h3 className="min-w-0 break-words font-ui text-h4 text-ink-1">{seatLabel(block.seat)}</h3>
      <CitedText id={block.id} sentences={block.take} className="font-reading text-body-sm text-ink-1" />
      {agreement ? (
        <p className="font-ui text-label text-ink-3" data-testid="expert-agrees">
          {agreement}
        </p>
      ) : null}
    </article>
  );
}
