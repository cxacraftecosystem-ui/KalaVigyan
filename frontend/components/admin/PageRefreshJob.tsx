import type { StatusTone } from "@/components/records/statusTone";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime } from "@/lib/format";
import { jobOutcome, jobSummary, OUTCOME_LABELS, refreshSteps, SCOPE_LABELS, startedByLine, type JobOutcome } from "@/lib/pageRefreshView";
import type { RefreshJobView } from "@/lib/sitePagesContract";
import { cn } from "@/lib/utils";

const OUTCOME_TONES: Record<JobOutcome, StatusTone> = { clean: "success", partial: "warning", failed: "error", running: "waiting" };
const AHEAD = "Waiting";

function JobLine({ job, at }: { job: RefreshJobView; at: string }) {
  return (
    <p className="font-ui text-label text-ink-2">
      {SCOPE_LABELS[job.scope]} · {startedByLine(job)} · <time dateTime={at}>{formatDateTime(at)}</time>
    </p>
  );
}

function NameList({ title, names }: { title: string; names: readonly string[] }) {
  if (!names.length) return null;
  return (
    <p className="font-ui text-label text-ink-2 [overflow-wrap:anywhere]">
      {title}: {names.join(", ")}
    </p>
  );
}

export function RunningJob({ job }: { job: RefreshJobView }) {
  return (
    <div className="mt-4 grid gap-3" data-testid="refresh-running">
      <JobLine job={job} at={job.startedAt} />
      <ol className="grid gap-2">
        {refreshSteps(job).map((step) => (
          <li
            key={step.phase}
            aria-current={step.state === "current" ? "step" : undefined}
            className={cn("grid gap-0.5 border-s-2 ps-3 font-ui text-label", step.state === "current" ? "border-ink-1 text-ink-1" : "border-transparent text-ink-2")}
          >
            <span>{step.label}</span>
            <span className="lining-nums tabular-nums text-ink-3">{step.count ?? AHEAD}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function LastJob({ job }: { job: RefreshJobView }) {
  const outcome = jobOutcome(job);
  return (
    <div className="mt-6 grid gap-2" data-testid="refresh-last">
      <h3 className="font-ui text-h4 text-ink-1">Last refresh</h3>
      <StatusBadge tone={OUTCOME_TONES[outcome]} label={OUTCOME_LABELS[outcome]} />
      <JobLine job={job} at={job.finishedAt ?? job.startedAt} />
      <p className="max-w-measure font-ui text-ui text-ink-1 lining-nums tabular-nums">{jobSummary(job.progress)}</p>
      {job.note ? <p className="max-w-measure font-ui text-ui text-ink-1">{job.note}</p> : null}
      <NameList title="Not refreshed on the site" names={job.progress.unrefreshed} />
      <NameList title="Not rebuilt" names={job.progress.failed} />
    </div>
  );
}
