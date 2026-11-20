import type { ReactNode } from "react";

import { EVIDENCE_WORDS, reliabilityFill, reliabilityWords, type EvidenceState } from "@/lib/citationCluster";
import type { SourceReliability } from "@/lib/types";

export function EvidenceTag({ state }: { state: EvidenceState }) {
  return (
    <span className="kv-ev-tag" data-level={state} data-testid="evidence-tag">
      {EVIDENCE_WORDS[state]}
    </span>
  );
}

export function InferredText({ children }: { children: ReactNode }) {
  return (
    <span className="kv-ev-inferred" data-evidence="inferred">
      {children}
      <span className="sr-only"> (inferred)</span>
    </span>
  );
}

export function HypothesisText({ children }: { children: ReactNode }) {
  return (
    <span className="kv-ev-hypothesis" data-evidence="hypothesis">
      <span className="sr-only">Hypothesis: </span>
      {children}
    </span>
  );
}

export function SourcesDifferNote({ summary, on = false, children }: { summary: string; on?: boolean; children?: ReactNode }) {
  return (
    <details className="kv-differ" data-testid="sources-differ">
      <summary>{on ? `Sources differ on ${summary}` : `Sources differ: ${summary}`}</summary>
      <div className="kv-differ-body">{children}</div>
    </details>
  );
}

export function ReliabilityMark({ reliability }: { reliability: SourceReliability }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-ui text-caption text-ink-2">
      <span aria-hidden className="kv-rel" data-grade={reliability} data-fill={reliabilityFill(reliability)} />
      {reliabilityWords(reliability)}
    </span>
  );
}
