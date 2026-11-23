"use client";

import { Suspense, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { PageHeader } from "@/components/PageHeader";
import { QueueFilterBar } from "@/components/review/QueueFilterBar";
import { QueueItemView } from "@/components/review/QueueItemView";
import { StagedBatches } from "@/components/review/StagedBatches";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs } from "@/components/ui/Tabs";
import { TextLink } from "@/components/ui/TextLink";
import { canAccessRoute } from "@/lib/permissions";
import type { QueueKind, ReviewFilters } from "@/lib/reviewQueueContract";
import { EVERY_KIND, filtersFromSearch, filtersSearch, isFiltered, kindTabs, NO_FILTERS } from "@/lib/reviewQueueView";

import { useReviewQueue, type ReviewQueueState } from "./useReviewQueue";
import { useStagedReviews } from "./useStagedReviews";

const DESCRIPTION =
  "Everything other people have given that waits for a decision: facts, artisans' testimony, pictures, component proposals and page layouts, from the site, the Knowledge API and the MCP server. Your own contributions are approved at once and never wait here.";

export default function ReviewPage() {
  return (
    <Suspense fallback={<Skeleton shape="lede" label="Opening the review queue" />}>
      <ReviewScreen />
    </Suspense>
  );
}

function ReviewScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const filters = useMemo(() => filtersFromSearch(new URLSearchParams(search)), [search]);
  const queue = useReviewQueue(filters);
  const staged = useStagedReviews(queue.handlers.decidedElsewhere);
  const change = (next: ReviewFilters) => {
    const query = filtersSearch(next);
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };

  return (
    <>
      <PageHeader title="Review" kicker="Admin" description={DESCRIPTION} />
      <div className="grid gap-6">
        <StagedBatches batches={staged.batches} error={staged.error} onConfirm={staged.confirm} onDiscard={staged.discard} />
        <QueueFilterBar filters={filters} onChange={change} />
        {queue.page ? (
          <Tabs
            label="Kinds of contribution"
            value={filters.kind ?? EVERY_KIND}
            onChange={(value) => change({ ...filters, kind: value === EVERY_KIND ? null : (value as QueueKind) })}
            items={kindTabs(queue.page).map((tab) => ({ ...tab, panel: <QueueList queue={queue} onClear={isFiltered(filters) ? () => change(NO_FILTERS) : null} /> }))}
          />
        ) : null}
        {!queue.page && !queue.error ? <Skeleton shape="lede" label="Reading the review queue" /> : null}
        {queue.error ? (
          <p role="alert" className="font-ui text-ui text-error">
            {queue.error}
          </p>
        ) : null}
        <DecidedLinks />
      </div>
    </>
  );
}

function DecidedLinks() {
  const { user } = useAuth();
  const pictures = canAccessRoute(user, "/admin/pictures");
  const testimony = canAccessRoute(user, "/admin/testimony");
  if (!pictures && !testimony) return null;
  return (
    <p className="font-ui text-label text-ink-3">
      Decided items stay listed under {pictures ? <TextLink href="/admin/pictures">contributed pictures</TextLink> : null}
      {pictures && testimony ? " and " : null}
      {testimony ? <TextLink href="/admin/testimony">artisan testimony</TextLink> : null}.
    </p>
  );
}

function QueueList({ queue, onClear }: { queue: ReviewQueueState; onClear: (() => void) | null }) {
  const page = queue.page;
  if (!page) return null;
  return (
    <div className="grid gap-5" aria-busy={queue.busy || undefined}>
      <p role="status" className="font-ui text-label text-ink-2">
        {queue.notice ?? ""}
      </p>
      {page.items.length ? (
        <ul className="grid gap-8">
          {page.items.map((item) => (
            <li key={`${item.kind}-${item.id}`} className="border-t border-rule pt-5">
              <QueueItemView item={item} handlers={queue.handlers} />
            </li>
          ))}
        </ul>
      ) : (
        <div className="grid gap-3">
          <p className="max-w-measure font-reading text-body-sm text-ink-2">
            What other people give waits here for a decision: facts that passed the automatic checks, artisans&apos; testimony, pictures, component proposals and page layouts.
          </p>
          {onClear ? (
            <ActionGroup align="start">
              <Button variant="quiet" onClick={onClear}>
                Show every kind and origin
              </Button>
            </ActionGroup>
          ) : null}
        </div>
      )}
      {page.nextCursor ? (
        <ActionGroup align="start">
          <Button variant="quiet" busy={queue.busy} busyLabel="Loading" onClick={queue.showMore}>
            Show more
          </Button>
        </ActionGroup>
      ) : null}
    </div>
  );
}
