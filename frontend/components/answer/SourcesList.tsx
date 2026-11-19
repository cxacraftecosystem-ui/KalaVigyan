import { ReliabilityMark } from "@/components/editorial/EvidenceMark";
import { entryByline } from "@/lib/citationCluster";
import { sourceHost, sourceHref } from "@/lib/citations";
import type { SourceRef } from "@/lib/types";
import { cn } from "@/lib/utils";

export type NumberedSource = { number: number; id: string; source: SourceRef | null };

function SourceRow({ entry, idPrefix, flashed }: { entry: NumberedSource; idPrefix: string; flashed: boolean }) {
  const { number, source } = entry;
  const href = source ? sourceHref(source) : null;
  const byline = entryByline(source);
  return (
    <li id={`${idPrefix}-${number}`} data-flash={flashed ? "true" : undefined} className="fr-flash-row grid grid-cols-[2rem_minmax(0,1fr)] gap-x-2 border-t border-rule py-3" data-testid="source-row">
      <span className="font-ui text-label text-ink-3 lining-nums tabular-nums">{number}</span>
      <span className="min-w-0">
        <span className="block break-words font-reading text-body-sm text-ink-1" data-testid="source-title">
          {source?.title ?? "Source"}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-ui text-caption text-ink-3">
          {byline ? <span>{byline}</span> : null}
          {source?.reliability ? <ReliabilityMark reliability={source.reliability} /> : null}
          {href ? (
            <a href={href} target="_blank" rel="noopener noreferrer" className="kv-link">
              Open the source{sourceHost(href) ? ` at ${sourceHost(href)}` : ""}
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          ) : null}
        </span>
      </span>
    </li>
  );
}

export function SourcesList({ entries, idPrefix = "source", compact = false, flashIds }: { entries: NumberedSource[]; idPrefix?: string; compact?: boolean; flashIds?: ReadonlySet<string> }) {
  const headingId = `${idPrefix}s-heading`;
  return (
    <section className="min-w-0" aria-labelledby={headingId} data-testid="sources-list">
      <h2 id={headingId} className={compact ? "kicker" : "font-headline text-h2 text-ink-1"}>
        Sources
      </h2>
      <ol className={cn("border-b border-rule", compact ? "mt-2" : "mt-4")}>
        {entries.map((entry) => (
          <SourceRow key={entry.id} entry={entry} idPrefix={idPrefix} flashed={flashIds?.has(entry.id) ?? false} />
        ))}
      </ol>
    </section>
  );
}
