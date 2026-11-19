"use client";

import type { TrailEntry } from "@/lib/explainerStream";
import { reusedLabel, TRAIL_STAGE_LABEL } from "@/lib/explainerView";

export const LIVE_TRAIL_ROWS = 5;

function entryMeta(entry: TrailEntry): string {
  if (entry.storedAt) return reusedLabel(entry.storedAt);
  return [entry.publisher, entry.year ? String(entry.year) : null].filter(Boolean).join(" · ");
}

function TrailRow({ entry }: { entry: TrailEntry }) {
  const meta = entryMeta(entry);
  return (
    <li className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)] gap-x-3 font-ui text-label" data-testid="trail-entry" data-stage={entry.stage}>
      <span className="text-ink-3">{TRAIL_STAGE_LABEL[entry.stage]}</span>
      <span className="min-w-0">
        {entry.url ? (
          <a href={entry.url} target="_blank" rel="noopener noreferrer" className="kv-link line-clamp-2 break-words font-normal">
            {entry.title}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        ) : (
          <span className="line-clamp-2 break-words text-ink-1">{entry.title}</span>
        )}
        {meta ? <span className="block font-ui text-caption text-ink-3">{meta}</span> : null}
      </span>
    </li>
  );
}

export function ResearchTrail({ trail }: { trail: readonly TrailEntry[] }) {
  if (trail.length === 0) return null;
  const latest = trail.slice(-LIVE_TRAIL_ROWS).reverse();
  return (
    <section aria-label="Reading now" className="mx-auto max-w-measure border-y border-rule py-3" data-testid="research-trail" data-live="true">
      <p className="kicker">Reading now</p>
      <ol className="mt-2 grid gap-2" aria-label="Latest sources">
        {latest.map((entry) => (
          <TrailRow key={entry.key} entry={entry} />
        ))}
      </ol>
    </section>
  );
}
