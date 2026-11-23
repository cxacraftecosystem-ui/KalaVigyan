"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { hasRank } from "@/lib/permissions";
import { SITE_BUILD_PATH, parseSiteBuildState, siteBuildStatus, type SiteBuildState, type SiteBuildStatus } from "@/lib/sitePagesContract";

const COPY = {
  title: "Site build",
  lede: "Publishes every craft page from the database to the site. The night starts no build; it refreshes only the pages that changed.",
  start: "Start a build",
  starting: "Starting",
  loadFailed: "Couldn't read the build status. Reload the page to try again.",
  startFailed: "Couldn't start the build. Try again in a few minutes."
};

const READY: ReadonlySet<SiteBuildStatus> = new Set(["last", "never"]);

function statusLine(status: SiteBuildStatus, state: SiteBuildState | null): string {
  const last = formatDateTime(state?.lastTriggeredAt);
  if (status === "loading") return "Reading the build status.";
  if (status === "unset") return "The deploy hook is not set on the server, so pages publish only with a deploy.";
  if (status === "started") return "Build started. Pages update in a few minutes.";
  if (status === "waiting") return `A build started ${last}. Another can start after ${formatDateTime(state?.nextAllowedAt)}.`;
  if (status === "last") return `Last build started ${last}.`;
  return "No build has been started from here.";
}

export function SiteBuildCard() {
  const { user } = useAuth();
  const allowed = hasRank(user, "ADMIN");
  const [state, setState] = useState<SiteBuildState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    apiFetch<unknown>(SITE_BUILD_PATH)
      .then((raw) => {
        if (!cancelled) setState(parseSiteBuildState(raw));
      })
      .catch(() => {
        if (!cancelled) setError(COPY.loadFailed);
      });
    return () => {
      cancelled = true;
    };
  }, [allowed]);

  if (!allowed) return null;

  async function start() {
    setBusy(true);
    setError(null);
    try {
      setState(parseSiteBuildState(await apiFetch<unknown>(SITE_BUILD_PATH, { method: "POST" })));
      setStarted(true);
    } catch (cause) {
      setError(apiErrorMessage(cause, COPY.startFailed));
    } finally {
      setBusy(false);
    }
  }

  const status = siteBuildStatus(state, new Date(), started);
  return (
    <section aria-labelledby="site-build-title" className="mt-8 border-t border-rule pt-6" data-testid="site-build">
      <h2 id="site-build-title" className="font-headline text-h3 text-ink-1">
        {COPY.title}
      </h2>
      <p className="mt-2 max-w-measure font-ui text-ui text-ink-2">{COPY.lede}</p>
      <p className="mt-2 font-ui text-label text-ink-3" role="status">
        {statusLine(status, state)}
      </p>
      {error ? (
        <p role="alert" className="mt-2 font-ui text-ui text-error">
          {error}
        </p>
      ) : null}
      <ActionGroup className="mt-4">
        <Button variant="quiet" busy={busy} busyLabel={COPY.starting} disabled={!READY.has(status)} onClick={() => void start()}>
          {COPY.start}
        </Button>
      </ActionGroup>
    </section>
  );
}
