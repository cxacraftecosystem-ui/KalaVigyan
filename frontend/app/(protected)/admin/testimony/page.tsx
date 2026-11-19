"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { RecordNotice } from "@/components/records/RecordNotice";
import { ReviewCard } from "@/components/review/ReviewCard";
import { StatusBadge } from "@/components/StatusBadge";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { apiErrorMessage } from "@/lib/api";
import { fetchReviewPage, isOpenItem, STATUS_LABELS, type ContributionStatus, type ReviewPage } from "@/lib/testimonyContract";

const STATUS_OPTIONS = (["PENDING", "APPROVED", "REJECTED", "WITHDRAWN"] as const).map((value) => ({ value, label: STATUS_LABELS[value] }));
const DECIDED_TONE = { APPROVED: "success", REJECTED: "error", WITHDRAWN: "neutral", PENDING: "waiting" } as const;

export default function TestimonyReviewPage() {
  const [status, setStatus] = useState<ContributionStatus>("PENDING");
  const [page, setPage] = useState<ReviewPage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (cursor: string | null, kept: ReviewPage | null) => {
    setBusy(true);
    setError(null);
    try {
      let next = await fetchReviewPage(status, cursor);
      let items = kept ? [...kept.items, ...next.items] : next.items;
      while (kept && next.nextCursor) {
        next = await fetchReviewPage(status, next.nextCursor);
        items = [...items, ...next.items];
      }
      setPage({ ...next, items });
    } catch (cause) {
      setError(apiErrorMessage(cause, "Couldn't load the queue. Try again."));
    } finally {
      setBusy(false);
    }
  }, [status]);

  useEffect(() => {
    void load(null, null);
  }, [load]);

  const shown = page?.items.length ?? 0;
  return (
    <>
      <PageHeader title="Artisan testimony" kicker="Admin" description="Each item is an artisan's quote, its English and the fact drawn from it." />
      <div className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <SegmentedChoice label="Status" value={status} options={STATUS_OPTIONS} onChange={(next) => setStatus(next as ContributionStatus)} disabled={busy} />
          {page ? (
            <p className="font-ui text-label text-ink-3 tabular-nums lining-nums" data-testid="review-count" role="status">
              Showing {shown} of {page.total}
            </p>
          ) : null}
        </div>
        {error ? <RecordNotice tone="error">{error}</RecordNotice> : null}
        <ul className="grid gap-8">
          {page?.items.map((item) =>
            isOpenItem(item) ? (
              <ReviewCard key={`${item.id}-${item.version}`} item={item} onDecided={() => void load(null, null)} />
            ) : (
              <li key={item.id} className="flex flex-wrap items-baseline justify-between gap-3 border-t border-rule pt-4">
                <span className="font-ui text-h4 text-ink-1">{item.craft.name}</span>
                <StatusBadge tone={DECIDED_TONE[item.status]} label={STATUS_LABELS[item.status]} />
              </li>
            )
          )}
        </ul>
        {page && !page.items.length ? (
          <p className="max-w-measure border-t border-rule pt-5 font-reading text-body-sm text-ink-2">Testimony in this state appears here as artisans give it and reviewers decide it.</p>
        ) : null}
        {page?.nextCursor ? (
          <ActionGroup>
            <Button variant="quiet" busy={busy} busyLabel="Loading" onClick={() => void load(page.nextCursor, page)}>
              Show all {page.total}
            </Button>
          </ActionGroup>
        ) : null}
      </div>
    </>
  );
}
