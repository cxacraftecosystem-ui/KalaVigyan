"use client";

import { CitedText } from "@/components/answer/ProseBlockView";
import type { LedeBlock as Lede } from "@/lib/explainerContract";

export function LedeBlock({ lede }: { lede: Lede; reduce?: boolean }) {
  return (
    <div className="min-w-0" data-testid="answer-lede">
      <CitedText id={lede.id} sentences={lede.sentences} className="font-reading text-lede text-ink-1" />
    </div>
  );
}
