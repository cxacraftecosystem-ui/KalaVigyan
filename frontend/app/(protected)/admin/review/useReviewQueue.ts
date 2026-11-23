"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { QueueHandlers } from "@/components/review/QueueItemView";
import { apiErrorMessage } from "@/lib/api";
import { decideQueueItem, fetchReviewQueue, type Filing, type QueueAction, type QueueItem, type ReviewFilters, type ReviewQueuePage } from "@/lib/reviewQueueContract";
import { withNextPage, withoutItem } from "@/lib/reviewQueueView";

const LOAD_FAILED = "Couldn't load the queue. Reload the page to try again.";
const DECIDE_FAILED = "Couldn't save the decision. Reload the queue and try again.";
const SAVED_ELSEWHERE = "Saved. The queue is up to date.";

export type ReviewQueueState = {
  page: ReviewQueuePage | null;
  error: string | null;
  busy: boolean;
  notice: string | null;
  showMore: () => void;
  handlers: QueueHandlers;
};

function useQueuePages(filters: ReviewFilters) {
  const [page, setPage] = useState<ReviewQueuePage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);

  const load = useCallback(
    async (cursor: string | null, kept: ReviewQueuePage | null) => {
      const mine = ++generation.current;
      setBusy(true);
      try {
        const found = await fetchReviewQueue(filters, cursor);
        if (mine !== generation.current) return;
        setPage(kept ? withNextPage(kept, found) : found);
        setError(null);
      } catch (cause) {
        if (mine === generation.current) setError(apiErrorMessage(cause, LOAD_FAILED));
      } finally {
        if (mine === generation.current) setBusy(false);
      }
    },
    [filters]
  );

  useEffect(() => {
    void load(null, null);
  }, [load]);

  return { page, setPage, error, busy, load };
}

export function useReviewQueue(filters: ReviewFilters): ReviewQueueState {
  const { page, setPage, error, busy, load } = useQueuePages(filters);
  const [notice, setNotice] = useState<string | null>(null);

  const decide = useCallback(
    async (item: QueueItem, action: QueueAction, words: string, filing: Filing | null = null) => {
      try {
        const decided = await decideQueueItem(item.kind, item.id, action, words, filing);
        setPage((current) => (current ? withoutItem(current, item) : current));
        setNotice(decided.message);
        return null;
      } catch (cause) {
        return apiErrorMessage(cause, DECIDE_FAILED);
      }
    },
    [setPage]
  );

  const decidedElsewhere = useCallback(() => {
    setNotice(SAVED_ELSEWHERE);
    void load(null, null);
  }, [load]);

  const showMore = useCallback(() => {
    if (page?.nextCursor) void load(page.nextCursor, page);
  }, [load, page]);

  return { page, error, busy, notice, showMore, handlers: { decide, decidedElsewhere } };
}
