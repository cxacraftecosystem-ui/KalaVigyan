"use client";

import { StagedBatchCard } from "@/components/review/StagedBatchCard";
import type { StagedBatchView, StagedConfirmation } from "@/lib/stagedReviewContract";

const TITLE = "Staged decisions";
const LEDE =
  "An Admin's AI client staged these decisions through the MCP server. Nothing in a batch reaches readers until it is confirmed here, and confirming checks each selected item again before it is applied; items left unselected are skipped.";

export function StagedBatches({
  batches,
  error,
  onConfirm,
  onDiscard
}: {
  batches: StagedBatchView[];
  error: string | null;
  onConfirm: (batchId: string, body: StagedConfirmation) => Promise<string | null>;
  onDiscard: (batchId: string) => Promise<string | null>;
}) {
  if (!batches.length && !error) return null;
  return (
    <section aria-labelledby="staged-title" className="grid gap-4 border-t border-ink-1 pt-5" data-testid="staged-batches">
      <h2 id="staged-title" className="font-headline text-h3 text-ink-1">
        {TITLE}
      </h2>
      <p className="max-w-measure font-ui text-ui text-ink-2">{LEDE}</p>
      {error ? (
        <p role="alert" className="font-ui text-ui text-error">
          {error}
        </p>
      ) : null}
      <ul className="grid gap-8">
        {batches.map((batch) => (
          <li key={batch.id} className="border-t border-rule pt-5">
            <StagedBatchCard batch={batch} onConfirm={(body) => onConfirm(batch.id, body)} onDiscard={() => onDiscard(batch.id)} />
          </li>
        ))}
      </ul>
    </section>
  );
}
