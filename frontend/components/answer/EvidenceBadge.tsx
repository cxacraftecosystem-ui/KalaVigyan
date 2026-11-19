import type { EvidenceState } from "@/lib/citationCluster";
import type { EvidenceKind, EvidenceLevel } from "@/lib/types";
import { cn } from "@/lib/utils";

type BadgeMeta = { label: string; state: EvidenceState };

const LEVEL: Record<EvidenceLevel, BadgeMeta> = {
  VERIFIED: { label: "Verified", state: "verified" },
  REVIEWED: { label: "Reviewed", state: "verified" },
  PROVISIONAL: { label: "Provisional", state: "provisional" },
  HYPOTHESIS: { label: "Hypothesis", state: "hypothesis" },
  UNAVAILABLE: { label: "No source found", state: "provisional" }
};

const KIND: Record<EvidenceKind, BadgeMeta> = {
  QUOTED: { label: "Quoted source", state: "verified" },
  INFERRED: { label: "Model-inferred", state: "inferred" }
};

export type EvidenceSignal = "SOURCES_DIFFER" | "EXPERTS_DIFFER" | "OUTSIDE_RANGE" | "UNBALANCED" | "BALANCED";

const SIGNAL: Record<EvidenceSignal, BadgeMeta> = {
  SOURCES_DIFFER: { label: "Sources differ", state: "differ" },
  EXPERTS_DIFFER: { label: "Experts differ", state: "differ" },
  OUTSIDE_RANGE: { label: "Outside usual range", state: "provisional" },
  UNBALANCED: { label: "Unbalanced", state: "provisional" },
  BALANCED: { label: "Balanced", state: "verified" }
};

export function evidenceLevelLabel(level: EvidenceLevel): string {
  return LEVEL[level]?.label ?? level;
}

export function evidenceKindLabel(kind: EvidenceKind): string {
  return KIND[kind]?.label ?? kind;
}

function MetaBadge({ meta, className }: { meta: BadgeMeta; className?: string }) {
  return (
    <span className={cn("kv-ev-tag", className)} data-level={meta.state}>
      {meta.label}
    </span>
  );
}

export function EvidenceLevelBadge({ level, className }: { level: EvidenceLevel; className?: string }) {
  return <MetaBadge meta={LEVEL[level] ?? LEVEL.UNAVAILABLE} className={className} />;
}

export function EvidenceKindBadge({ kind, className }: { kind: EvidenceKind; className?: string }) {
  return <MetaBadge meta={KIND[kind] ?? KIND.INFERRED} className={className} />;
}

export function EvidenceSignalBadge({ signal, className }: { signal: EvidenceSignal; className?: string }) {
  return <MetaBadge meta={SIGNAL[signal]} className={className} />;
}
