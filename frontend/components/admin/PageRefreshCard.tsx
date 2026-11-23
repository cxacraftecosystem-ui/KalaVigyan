"use client";

import { LastJob, RunningJob } from "@/components/admin/PageRefreshJob";
import { usePageRefresh, type PageRefresh } from "@/components/admin/usePageRefresh";
import { useConfirm, type ConfirmOptions } from "@/components/dialogs/ConfirmDialog";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import { everyWaitsUntil, mayStartEvery, refreshStatus, type RefreshStatus } from "@/lib/pageRefreshView";
import type { PageRefreshState } from "@/lib/sitePagesContract";

const COPY = {
  title: "Refresh pages now",
  lede: "Rebuilds the pages and stored documents that changed since the last refresh and refreshes them on the site. A refresh calls no model, and the night refreshes the pages that changed in any case.",
  unset: "The site's refresh secret is not set on the server, so rebuilt pages reach the site with its next build.",
  changed: "Refresh changed pages",
  every: "Refresh every page",
  starting: "Starting"
};

const EVERY_DIALOG: ConfirmOptions = {
  title: "Refresh every page?",
  body: "This rebuilds every stale page and stored document and refreshes every page on the site. It can run once a day.",
  confirmLabel: COPY.every
};

function statusLine(status: RefreshStatus, state: PageRefreshState | null): string {
  if (status === "loading") return "Reading the refresh status.";
  if (status === "running") return "A refresh is running. This card follows it until it finishes.";
  if (status === "waiting") return `The next refresh can start after ${formatDateTime(state?.nextAllowedAt)}.`;
  return "A refresh can start now.";
}

function everyLine(state: PageRefreshState | null, now: Date): string | null {
  if (!state?.mayRefreshEvery) return null;
  const until = everyWaitsUntil(state, now);
  return until ? `Every page can be refreshed again after ${formatDateTime(until.toISOString())}.` : null;
}

function RefreshActions({ refresh, status, now }: { refresh: PageRefresh; status: RefreshStatus; now: Date }) {
  const confirm = useConfirm();
  const startEvery = async () => {
    if (await confirm(EVERY_DIALOG)) await refresh.start("every");
  };
  return (
    <ActionGroup className="mt-4">
      <Button variant="quiet" busy={refresh.busy === "changed"} busyLabel={COPY.starting} disabled={status !== "ready" || refresh.busy === "every"} onClick={() => void refresh.start("changed")}>
        {COPY.changed}
      </Button>
      {refresh.state?.mayRefreshEvery ? (
        <Button variant="quiet" busy={refresh.busy === "every"} busyLabel={COPY.starting} disabled={!mayStartEvery(refresh.state, now) || refresh.busy === "changed"} onClick={() => void startEvery()}>
          {COPY.every}
        </Button>
      ) : null}
    </ActionGroup>
  );
}

export function PageRefreshCard() {
  const refresh = usePageRefresh();
  if (!refresh.allowed) return null;
  const { state, error } = refresh;
  const now = new Date();
  const status = refreshStatus(state, now);
  const every = everyLine(state, now);
  return (
    <section aria-labelledby="page-refresh-title" className="mt-8 border-t border-rule pt-6" data-testid="page-refresh">
      <h2 id="page-refresh-title" className="font-headline text-h3 text-ink-1">
        {COPY.title}
      </h2>
      <p className="mt-2 max-w-measure font-ui text-ui text-ink-2">{COPY.lede}</p>
      <p className="mt-2 font-ui text-label text-ink-3" role="status">
        {statusLine(status, state)}
      </p>
      {every ? <p className="mt-1 font-ui text-label text-ink-3">{every}</p> : null}
      {state && !state.configured ? <p className="mt-2 max-w-measure font-ui text-ui text-ink-2">{COPY.unset}</p> : null}
      {error ? (
        <p role="alert" className="mt-2 font-ui text-ui text-error">
          {error}
        </p>
      ) : null}
      {state?.running ? <RunningJob job={state.running} /> : null}
      {state?.last ? <LastJob job={state.last} /> : null}
      <RefreshActions refresh={refresh} status={status} now={now} />
    </section>
  );
}
