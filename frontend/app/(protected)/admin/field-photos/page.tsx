"use client";

import { useState } from "react";

import { FieldPhotoCard } from "@/components/admin/FieldPhotoCard";
import { FieldPhotoSwitch } from "@/components/admin/FieldPhotoSwitch";
import { useAuth } from "@/components/AuthProvider";
import { PageHeader } from "@/components/PageHeader";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { Skeleton } from "@/components/ui/Skeleton";
import { TextLink } from "@/components/ui/TextLink";
import type { QueueState } from "@/lib/fieldPhotoReviewContract";
import { STATE_LABELS, stateOptions } from "@/lib/fieldPhotoReviewView";
import { isMasterAdmin } from "@/lib/permissions";

import { useFieldPhotoQueue, type FieldPhotoQueueState } from "./useFieldPhotoQueue";

const DESCRIPTION =
  "Photographs the designer and documentation portals filed on an artisan, a session or a participant. Each stays hidden until an Admin decides it; the screens look first, identity documents and faces lead the queue, and only a Master Admin shows what they flag.";

const EMPTY: Record<QueueState, string> = {
  WAITING: "Photographs filed on artisans wait here after each nightly sync from the portals, screened and sorted with likely identity documents first.",
  SHOWN: "Photographs an Admin decides to show are listed here, each with the decision on record and a way to hide it again.",
  HIDDEN: "Photographs kept hidden are listed here with the reason on record, and can be shown later after a fresh look."
};

export default function FieldPhotosPage() {
  const { user } = useAuth();
  const master = isMasterAdmin(user);
  const [state, setState] = useState<QueueState>("WAITING");
  const photos = useFieldPhotoQueue(state);
  const queue = photos.queue;

  return (
    <>
      <PageHeader title="Field photographs" kicker="Admin" description={DESCRIPTION} />
      <div className="grid gap-8">
        {queue ? <FieldPhotoSwitch queue={queue} master={master} onSwitched={photos.switched} onScreened={photos.reload} /> : null}
        {queue ? (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <SegmentedChoice label="Which photographs" value={state} options={stateOptions(queue.counts)} onChange={(next) => setState(next as QueueState)} disabled={photos.busy} />
            <p className="font-ui text-label text-ink-3">
              Contributed pictures wait under <TextLink href="/admin/pictures">contributed pictures</TextLink>.
            </p>
          </div>
        ) : null}
        {!queue && !photos.error ? <Skeleton shape="plateGrid" label="Reading the field photographs" /> : null}
        {photos.error ? (
          <p role="alert" className="font-ui text-ui text-error">
            {photos.error}
          </p>
        ) : null}
        <PhotoList photos={photos} master={master} state={state} />
      </div>
    </>
  );
}

function PhotoList({ photos, master, state }: { photos: FieldPhotoQueueState; master: boolean; state: QueueState }) {
  const queue = photos.queue;
  if (!queue || queue.state !== state) return null;
  return (
    <section aria-label={`${STATE_LABELS[state]} field photographs`} aria-busy={photos.busy || undefined} className="grid gap-10">
      {queue.items.length ? (
        <ul className="grid gap-12">
          {queue.items.map((photo) => (
            <FieldPhotoCard key={`${photo.id}-${photo.sha256}`} photo={photo} master={master} onDecided={photos.decided} />
          ))}
        </ul>
      ) : (
        <p className="max-w-measure border-t border-rule pt-5 font-reading text-body-sm text-ink-2">{EMPTY[state]}</p>
      )}
      {queue.nextCursor ? (
        <ActionGroup align="start">
          <Button variant="quiet" busy={photos.busy} busyLabel="Loading" onClick={photos.showMore}>
            Show more
          </Button>
        </ActionGroup>
      ) : null}
    </section>
  );
}
