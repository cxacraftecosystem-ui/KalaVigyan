"use client";

import { useEffect, useMemo, useState } from "react";
import { CircleAlert } from "lucide-react";

import { HiddenFactsTable } from "@/components/admin/HiddenFactsTable";
import { useAuth } from "@/components/AuthProvider";
import { RecordSection } from "@/components/records/RecordSection";
import { formatDateTime } from "@/lib/format";
import { fetchHiddenFacts, hiddenRows, hiddenSummary, type HiddenFacts } from "@/lib/hiddenFacts";
import { hasRank } from "@/lib/permissions";

const COPY = {
  title: "Facts readers cannot see",
  lede: "Each night counts the approved facts a signed-out reader cannot see, by craft and the rule that hides them. An unexplained fact is one no rule hides, so the night reports it as a fault.",
  loading: "Reading the count.",
  loadFailed: "Couldn't read the count. Reload the page to try again."
};

function statusLine(found: HiddenFacts | null): string {
  return found ? hiddenSummary(found, formatDateTime) : COPY.loading;
}

export function HiddenFactsCard() {
  const { user } = useAuth();
  const allowed = hasRank(user, "ADMIN");
  const [found, setFound] = useState<HiddenFacts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    fetchHiddenFacts()
      .then((loaded) => {
        if (!cancelled) setFound(loaded);
      })
      .catch((cause: unknown) => {
        console.error(cause);
        if (!cancelled) setError(COPY.loadFailed);
      });
    return () => {
      cancelled = true;
    };
  }, [allowed]);

  const rows = useMemo(() => (found?.report ? hiddenRows(found.report) : []), [found]);
  if (!allowed) return null;

  return (
    <RecordSection title={COPY.title} description={COPY.lede} className="mt-8" testId="hidden-facts">
      {error ? (
        <p role="alert" className="flex items-center gap-2 font-ui text-ui text-ink-1">
          <CircleAlert className="size-4 shrink-0 text-error" aria-hidden />
          {error}
        </p>
      ) : (
        <p className="font-ui text-label text-ink-3" role="status">
          {statusLine(found)}
        </p>
      )}
      {rows.length > 0 ? <HiddenFactsTable rows={rows} /> : null}
    </RecordSection>
  );
}
