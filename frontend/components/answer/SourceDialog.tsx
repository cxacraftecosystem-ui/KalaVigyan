"use client";

import { FieldDialog } from "@/components/dialogs/FieldDialog";
import { EvidenceTag, ReliabilityMark } from "@/components/editorial/EvidenceMark";
import { Button } from "@/components/ui/button";
import { entryRights, evidenceState } from "@/lib/citationCluster";
import { highlightQuote, sourceByline, sourceHost, sourceHref, sourceKindLabel } from "@/lib/citations";
import type { Citation, SourceRef } from "@/lib/types";

export type OpenCitation = { citations: readonly Citation[]; source: SourceRef | null; number: number | null };

export function openedSource(citations: readonly Citation[], numbers: ReadonlyMap<string, number>, sourcesById: ReadonlyMap<string, SourceRef>): OpenCitation {
  const sourceId = citations[0]?.sourceId ?? "";
  return { citations, source: sourcesById.get(sourceId) ?? null, number: numbers.get(sourceId) ?? null };
}

function Passage({ citation }: { citation: Citation }) {
  const parts = highlightQuote(citation.context, citation.quote);
  const state = evidenceState(citation);
  return (
    <div className="grid gap-1.5 border-t border-rule pt-3" data-testid="source-quote">
      {parts.length > 0 ? (
        <p className="kv-quote mt-0" data-testid="source-passage">
          {parts.map((part, index) =>
            part.mark ? (
              <mark key={index} className="bg-turmeric-wash text-ink-1">
                {part.text}
              </mark>
            ) : (
              <span key={index}>{part.text}</span>
            )
          )}
        </p>
      ) : (
        <p className="font-ui text-caption text-ink-2">Inferred from the cited source; no passage is quoted.</p>
      )}
      {citation.locator ? <p className="kv-meta">{citation.locator}</p> : null}
      {state !== "verified" ? (
        <p>
          <EvidenceTag state={state} />
        </p>
      ) : null}
    </div>
  );
}

export function SourceDetails({ open }: { open: OpenCitation }) {
  const source = open.source;
  const rights = entryRights(source);
  return (
    <div className="grid gap-3 font-ui text-ink-1">
      {open.number ? <p className="kicker">Source {open.number}</p> : null}
      {open.citations.map((citation, index) => (
        <Passage key={`${citation.id}:${index}`} citation={citation} />
      ))}
      {source ? (
        <p className="border-t border-rule pt-3 font-ui text-label text-ink-3">
          {sourceKindLabel(source.kind)}
          {rights ? ` · ${rights}` : null}
          {source.doi ? <span className="block break-all">DOI {source.doi}</span> : null}
        </p>
      ) : null}
      {source?.reliability ? <ReliabilityMark reliability={source.reliability} /> : null}
    </div>
  );
}

export function SourceDialog({ open, onClose }: { open: OpenCitation | null; onClose: () => void }) {
  const source = open?.source ?? null;
  const href = source ? sourceHref(source) : null;
  return (
    <FieldDialog
      open={open !== null}
      onClose={onClose}
      title={source?.title ?? "Source"}
      description={source ? sourceByline(source) || undefined : undefined}
      className="max-w-xl"
      footer={
        <>
          {href ? (
            <a href={href} target="_blank" rel="noopener noreferrer" className="kv-btn" data-variant="quiet" data-testid="source-outbound">
              Read at {sourceHost(href) ?? "the source"}
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          ) : null}
          <Button variant="quiet" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      {open && open.citations.length > 0 ? <SourceDetails open={open} /> : null}
    </FieldDialog>
  );
}
