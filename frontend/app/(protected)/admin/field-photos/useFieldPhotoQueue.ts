"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiErrorMessage } from "@/lib/api";
import { fetchFieldPhotos, type FieldPhoto, type FieldPhotoQueue, type QueueState, type SwitchState } from "@/lib/fieldPhotoReviewContract";
import { withDecided, withMore } from "@/lib/fieldPhotoReviewView";

const LOAD_FAILED = "Couldn't load the field photographs. Reload the page to try again.";

export type FieldPhotoQueueState = {
  queue: FieldPhotoQueue | null;
  error: string | null;
  busy: boolean;
  reload: () => void;
  showMore: () => void;
  decided: (photo: FieldPhoto) => void;
  switched: (visibility: SwitchState) => void;
};

export function useFieldPhotoQueue(state: QueueState): FieldPhotoQueueState {
  const [queue, setQueue] = useState<FieldPhotoQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);

  const load = useCallback(
    async (cursor: string | null, kept: FieldPhotoQueue | null) => {
      const mine = ++generation.current;
      setBusy(true);
      try {
        const found = await fetchFieldPhotos(state, cursor);
        if (mine !== generation.current) return;
        setQueue(kept ? withMore(kept, found) : found);
        setError(null);
      } catch (cause) {
        if (mine === generation.current) setError(apiErrorMessage(cause, LOAD_FAILED));
      } finally {
        if (mine === generation.current) setBusy(false);
      }
    },
    [state]
  );

  useEffect(() => {
    void load(null, null);
  }, [load]);

  const reload = useCallback(() => void load(null, null), [load]);
  const showMore = useCallback(() => {
    if (queue?.nextCursor) void load(queue.nextCursor, queue);
  }, [load, queue]);
  const decided = useCallback((photo: FieldPhoto) => setQueue((current) => (current ? withDecided(current, photo) : current)), []);
  const switched = useCallback((visibility: SwitchState) => setQueue((current) => (current ? { ...current, visibility } : current)), []);

  return { queue, error, busy, reload, showMore, decided, switched };
}
