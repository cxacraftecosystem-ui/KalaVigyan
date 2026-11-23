"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { apiErrorMessage } from "@/lib/api";
import { hasRank } from "@/lib/permissions";
import {
  confirmStagedBatch,
  discardStagedBatch,
  fetchStagedBatches,
  type StagedBatchView,
  type StagedConfirmation
} from "@/lib/stagedReviewContract";
import { withBatch } from "@/lib/stagedReviewView";

const LOAD_FAILED = "Couldn't read the staged decisions. Reload the page to try again.";
const CONFIRM_FAILED = "Couldn't confirm the batch. Reload the page and try again.";
const DISCARD_FAILED = "Couldn't discard the batch. Reload the page and try again.";

export type StagedReviews = {
  batches: StagedBatchView[];
  error: string | null;
  confirm: (batchId: string, body: StagedConfirmation) => Promise<string | null>;
  discard: (batchId: string) => Promise<string | null>;
};

export function useStagedReviews(onConfirmed: () => void): StagedReviews {
  const { user } = useAuth();
  const allowed = hasRank(user, "ADMIN");
  const [batches, setBatches] = useState<StagedBatchView[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    fetchStagedBatches()
      .then((found) => {
        if (!cancelled) setBatches(found.batches);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(apiErrorMessage(cause, LOAD_FAILED));
      });
    return () => {
      cancelled = true;
    };
  }, [allowed]);

  const confirm = useCallback(
    async (batchId: string, body: StagedConfirmation) => {
      try {
        const confirmed = await confirmStagedBatch(batchId, body);
        setBatches((current) => withBatch(current, confirmed));
        onConfirmed();
        return null;
      } catch (cause) {
        return apiErrorMessage(cause, CONFIRM_FAILED);
      }
    },
    [onConfirmed]
  );

  const discard = useCallback(async (batchId: string) => {
    try {
      const discarded = await discardStagedBatch(batchId);
      setBatches((current) => withBatch(current, discarded));
      return null;
    } catch (cause) {
      return apiErrorMessage(cause, DISCARD_FAILED);
    }
  }, []);

  return { batches: allowed ? batches : [], error: allowed ? error : null, confirm, discard };
}
