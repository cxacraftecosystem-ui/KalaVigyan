"use client";

import { failureMessage, useRemote } from "@/components/hooks/useRemote";
import { OpenDataView } from "@/components/openData/OpenDataView";
import { RetryPanel } from "@/components/RemotePanels";
import { Skeleton } from "@/components/ui/Skeleton";
import { fetchOpenData } from "@/lib/openData";
import type { OpenDataListing } from "@/lib/openDataContract";

export const OPEN_DATA_UNREAD = "The dataset's record could not be read. Try again in a moment.";

export function OpenDataScreen({ initial }: { initial: OpenDataListing | null }) {
  const remote = useRemote(initial ? null : fetchOpenData);
  const listing = initial ?? remote.data;
  if (listing) return <OpenDataView listing={listing} />;
  if (remote.failure) return <RetryPanel message={failureMessage(remote.failure, OPEN_DATA_UNREAD)} onRetry={remote.retry} className="mt-6" />;
  return <Skeleton shape="lede" label="Opening the dataset's record" className="pt-6" />;
}
