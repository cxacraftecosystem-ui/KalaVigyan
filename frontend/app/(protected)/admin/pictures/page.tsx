"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { RecordNotice } from "@/components/records/RecordNotice";
import { PictureReviewCard } from "@/components/review/PictureReviewCard";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { TextLink } from "@/components/ui/TextLink";
import { apiErrorMessage } from "@/lib/api";
import { byCount } from "@/lib/format";
import { fetchImageQueue, IMAGE_STATUS_LABELS, type ImageQueue, type ImageStatus } from "@/lib/imageContributionContract";

const STATUS_OPTIONS = (["PENDING", "APPROVED", "REJECTED", "WITHDRAWN"] as const).map((value) => ({ value, label: IMAGE_STATUS_LABELS[value] }));

export default function PictureReviewPage() {
  const [status, setStatus] = useState<ImageStatus>("PENDING");
  const [queue, setQueue] = useState<ImageQueue | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setQueue(await fetchImageQueue(status));
      setError(null);
    } catch (cause) {
      setError(apiErrorMessage(cause, "Couldn't load the pictures. Try again."));
    } finally {
      setBusy(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Contributed pictures"
        kicker="Admin"
        description="Pictures from Researchers and above. A Professor's, Admin's or Master Admin's own picture is approved at once."
      />
      <div className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <SegmentedChoice label="Status" value={status} options={STATUS_OPTIONS} onChange={(next) => setStatus(next as ImageStatus)} disabled={busy} />
          {queue ? (
            <p role="status" className="font-ui text-label text-ink-3 tabular-nums lining-nums">
              {`${queue.items.length} ${byCount(queue.items.length, "picture", "pictures")}`}
            </p>
          ) : null}
        </div>
        <p className="font-ui text-label text-ink-3">
          Photographs the portals filed on artisans wait under <TextLink href="/admin/field-photos">field photographs</TextLink>.
        </p>
        {error ? <RecordNotice tone="error">{error}</RecordNotice> : null}
        <ul className="grid gap-8">
          {queue?.items.map((item) => <PictureReviewCard key={`${item.id}-${item.status}`} item={item} onDecided={() => void load()} />)}
        </ul>
        {queue && !queue.items.length ? <p className="max-w-measure border-t border-rule pt-5 font-reading text-body-sm text-ink-2">Pictures in this state appear here as people give them.</p> : null}
      </div>
    </>
  );
}
