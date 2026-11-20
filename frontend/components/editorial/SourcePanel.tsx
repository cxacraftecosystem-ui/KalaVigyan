import { X } from "lucide-react";
import type { RefObject } from "react";

import { EvidenceTag, ReliabilityMark } from "@/components/editorial/EvidenceMark";
import { sourceHref } from "@/lib/citations";
import { entryByline, entryRights, evidenceState, sourceCountLine, type ClusterEntry, type EvidenceState } from "@/lib/citationCluster";
import type { Citation } from "@/lib/types";

export type SourcePanelProps = {
  entries: readonly ClusterEntry[];
  headingId: string;
  onClose: () => void;
  closeRef?: RefObject<HTMLButtonElement | null>;
  norm?: EvidenceState;
  borrowed?: ReadonlyMap<string, string>;
};

function Passage({ citation, norm }: { citation: Citation; norm: EvidenceState }) {
  const state = evidenceState(citation);
  return (
    <div className="mt-2" data-testid="source-passage">
      {citation.quote ? <p className="kv-quote">“{citation.quote}”</p> : <p className="font-ui text-caption text-ink-2">Inferred from this source; no passage is quoted.</p>}
      {citation.locator ? <p className="kv-meta mt-1.5">{citation.locator}</p> : null}
      {state !== norm ? (
        <p className="mt-1.5">
          <EvidenceTag state={state} />
        </p>
      ) : null}
    </div>
  );
}

function Entry({ entry, norm, borrowed }: { entry: ClusterEntry; norm: EvidenceState; borrowed?: string }) {
  const href = entry.source ? sourceHref(entry.source) : null;
  const rights = entryRights(entry.source);
  return (
    <div className="kv-src" data-testid="source-entry">
      <div className="kv-src-head">
        <b>{entry.number ?? "·"}</b>
        <strong className="min-w-0 font-semibold">{entry.source?.title ?? "Source"}</strong>
      </div>
      <div className="kv-src-body">
        {entry.source ? <p className="kv-meta mt-0.5">{entryByline(entry.source)}</p> : null}
        {rights ? (
          <p className="kv-meta mt-0.5" data-testid="source-rights">
            {rights}
          </p>
        ) : null}
        {borrowed ? <p className="mt-1 font-ui text-caption font-medium text-ink-2">{borrowed}</p> : null}
        {entry.citations.map((citation, index) => (
          <Passage key={`${citation.id}:${index}`} citation={citation} norm={norm} />
        ))}
        {entry.source?.reliability ? (
          <p className="mt-1.5">
            <ReliabilityMark reliability={entry.source.reliability} />
          </p>
        ) : null}
        {href ? (
          <p className="kv-meta mt-1.5">
            <a href={href} target="_blank" rel="noopener noreferrer" className="kv-link py-1 font-normal underline-offset-2">
              Open the source<span className="sr-only"> (opens in a new tab)</span>
            </a>
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function SourcePanel({ entries, headingId, onClose, closeRef, norm = "verified", borrowed }: SourcePanelProps) {
  return (
    <div className="font-ui text-ink-1" data-testid="source-panel">
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <p id={headingId} className="kv-panel-head">
          {sourceCountLine(entries.length)}
        </p>
        <button ref={closeRef} type="button" className="kv-close" aria-label="Close" onClick={onClose}>
          <X aria-hidden />
        </button>
      </div>
      <div>
        {entries.map((entry) => (
          <Entry key={entry.sourceId} entry={entry} norm={norm} borrowed={borrowed?.get(entry.sourceId)} />
        ))}
      </div>
      <p className="mt-1.5 border-t border-rule pt-2.5 font-ui text-caption text-ink-3">Quotes are verbatim.</p>
    </div>
  );
}
