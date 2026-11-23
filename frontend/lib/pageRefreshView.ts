import { instantAhead, type PageRefreshState, type RefreshJobView, type RefreshPhase, type RefreshProgress, type RefreshScope } from "@/lib/sitePagesContract";

export const REFRESH_POLL_MS = 5_000;
export const REFRESH_READ_FLOOR_MS = 1_000;

export type RefreshStatus = "loading" | "running" | "waiting" | "ready";
export type StepPhase = Exclude<RefreshPhase, "FINISHED">;
export type StepState = "done" | "current" | "ahead";
export type RefreshStep = { phase: StepPhase; label: string; count: string | null; state: StepState };
export type JobOutcome = "clean" | "partial" | "failed" | "running";

const STEP_PHASES: readonly StepPhase[] = ["PAGES", "DOCUMENTS", "REFRESHING"];

const STEP_LABELS: Record<StepPhase, string> = {
  PAGES: "Rebuild the pages",
  DOCUMENTS: "Rebuild the stored documents",
  REFRESHING: "Refresh the pages on the site"
};

export const SCOPE_LABELS: Record<RefreshScope, string> = {
  CHANGED: "The pages that changed",
  EVERY: "Every page",
  NAMED: "The pages review decisions touched"
};

export const OUTCOME_LABELS: Record<JobOutcome, string> = {
  clean: "Finished",
  partial: "Finished with pages left",
  failed: "Failed",
  running: "Running"
};

export function refreshWaitsUntil(state: PageRefreshState, now: Date): Date | null {
  return instantAhead(state.nextAllowedAt, now);
}

export function everyWaitsUntil(state: PageRefreshState, now: Date): Date | null {
  return instantAhead(state.everyAllowedAt, now);
}

export function refreshStatus(state: PageRefreshState | null, now: Date): RefreshStatus {
  if (!state) return "loading";
  if (state.running) return "running";
  return refreshWaitsUntil(state, now) ? "waiting" : "ready";
}

export function mayStartEvery(state: PageRefreshState | null, now: Date): boolean {
  if (!state?.mayRefreshEvery) return false;
  return refreshStatus(state, now) === "ready" && !everyWaitsUntil(state, now);
}

export function nextReadIn(state: PageRefreshState | null, now: Date): number | null {
  if (!state) return null;
  if (state.running) return REFRESH_POLL_MS;
  const until = refreshWaitsUntil(state, now);
  return until ? Math.max(until.getTime() - now.getTime(), REFRESH_READ_FLOOR_MS) : null;
}

function stepCount(phase: StepPhase, progress: RefreshProgress): string {
  if (phase === "PAGES") return `${progress.pagesRebuilt} of ${progress.pagesStale} rebuilt, ${progress.pagesChanged} changed`;
  if (phase === "DOCUMENTS") return `${progress.documentsRebuilt} of ${progress.documentsStale} rebuilt`;
  return `${progress.pagesRefreshed} of ${progress.pagesToRefresh} refreshed`;
}

export function refreshSteps(job: RefreshJobView): RefreshStep[] {
  const at = job.phase === "FINISHED" ? STEP_PHASES.length : STEP_PHASES.indexOf(job.phase);
  return STEP_PHASES.map((phase, index) => {
    const state: StepState = index < at ? "done" : index === at ? "current" : "ahead";
    return { phase, label: STEP_LABELS[phase], count: state === "ahead" ? null : stepCount(phase, job.progress), state };
  });
}

export function startedByLine(job: RefreshJobView): string {
  if (job.origin === "NIGHT") return "Started by the night's upkeep";
  if (job.origin === "REVIEW") return job.startedBy ? `Started by ${job.startedBy}'s review decisions` : "Started by review decisions";
  const who = job.startedBy ?? "an Admin";
  return job.origin === "MCP" && job.clientName ? `Started by ${who} through ${job.clientName}` : `Started by ${who}`;
}

export function jobOutcome(job: RefreshJobView): JobOutcome {
  if (job.status === "RUNNING") return "running";
  if (job.status === "FAILED") return "failed";
  return job.progress.unrefreshed.length || job.progress.failed.length ? "partial" : "clean";
}

export function jobSummary(progress: RefreshProgress): string {
  const pages = `${progress.pagesRebuilt} of ${progress.pagesStale} pages rebuilt (${progress.pagesChanged} changed)`;
  const documents = `${progress.documentsRebuilt} of ${progress.documentsStale} stored documents rebuilt`;
  return `${pages}, ${documents}, ${progress.pagesRefreshed} of ${progress.pagesToRefresh} pages refreshed on the site.`;
}
