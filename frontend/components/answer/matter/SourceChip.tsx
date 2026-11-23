"use client";

import { CHIP_SHAPE, QUOTED_CHIP_TONE } from "@/components/answer/CitationChip";
import { useCitations } from "@/components/answer/CitationContext";
import { sourceHref } from "@/lib/citations";
import { cn } from "@/lib/utils";

export function SourceChip({ sourceId }: { sourceId: string }) {
  const { numbers, sourcesById } = useCitations();
  const source = sourcesById.get(sourceId) ?? null;
  const number = numbers.get(sourceId) ?? null;
  const href = source ? sourceHref(source) : null;
  const label = `Source ${number ?? ""}${source ? `: ${source.title}` : ""}`;
  const body = <span className="tabular-nums">{number ?? "·"}</span>;
  if (!href) {
    return (
      <span aria-label={label} title={source?.title} className={cn(CHIP_SHAPE, QUOTED_CHIP_TONE)} data-testid="source-chip">
        {body}
      </span>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={`${label} (opens in a new tab)`} title={source?.title} className={cn(CHIP_SHAPE, QUOTED_CHIP_TONE)} data-testid="source-chip">
      {body}
    </a>
  );
}
