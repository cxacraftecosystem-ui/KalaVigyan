"use client";

import { useState } from "react";

import { useConfirm, type ConfirmOptions } from "@/components/dialogs/ConfirmDialog";
import { StagedItemEditor, StagedItemResult } from "@/components/review/StagedItemRow";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { formatDateTime, lowerFirst } from "@/lib/format";
import type { StagedBatchView, StagedConfirmation } from "@/lib/stagedReviewContract";
import {
  batchHeading,
  batchTally,
  BATCH_STATUS_LABELS,
  confirmBody,
  confirmProblem,
  draftOf,
  draftProblems,
  withDraft,
  type StagedDraft
} from "@/lib/stagedReviewView";

type Step = "confirm" | "discard";

type CardProps = {
  batch: StagedBatchView;
  onConfirm: (body: StagedConfirmation) => Promise<string | null>;
  onDiscard: () => Promise<string | null>;
};

const DISCARD_DIALOG: ConfirmOptions = {
  title: "Discard this batch?",
  body: "None of its decisions is applied, and the batch can no longer be confirmed.",
  tone: "danger",
  confirmLabel: "Discard batch"
};

function BatchHeader({ batch, headingId }: { batch: StagedBatchView; headingId: string }) {
  const open = batch.status === "OPEN";
  const until = open ? batch.expiresAt : (batch.decidedAt ?? batch.expiresAt);
  const decided = `${lowerFirst(BATCH_STATUS_LABELS[batch.status])}${batch.decidedBy ? ` by ${batch.decidedBy}` : ""}`;
  return (
    <header className="grid gap-1">
      <h3 id={headingId} className="font-ui text-h4 text-ink-1">
        {batchHeading(batch)}
      </h3>
      <p className="font-ui text-label text-ink-3">
        Staged <time dateTime={batch.createdAt}>{formatDateTime(batch.createdAt)}</time>
        {` · ${open ? "expires" : decided} `}
        <time dateTime={until}>{formatDateTime(until)}</time>
      </p>
    </header>
  );
}

function BatchItems({ batch, drafts, tried, onDraft }: { batch: StagedBatchView; drafts: StagedDraft[]; tried: boolean; onDraft: (next: StagedDraft) => void }) {
  if (batch.status !== "OPEN") {
    return (
      <ul className="grid gap-4">
        {batch.items.map((item) => (
          <StagedItemResult key={item.id} item={item} />
        ))}
      </ul>
    );
  }
  return (
    <ul className="grid gap-4">
      {batch.items.map((item, index) => {
        const draft = drafts[index];
        return <StagedItemEditor key={item.id} item={item} draft={draft} problems={tried && draft.selected ? draftProblems(draft) : null} onChange={onDraft} />;
      })}
    </ul>
  );
}

function useBatchSteps({ batch, onConfirm, onDiscard }: CardProps) {
  const [drafts, setDrafts] = useState(() => batch.items.map(draftOf));
  const [tried, setTried] = useState(false);
  const [running, setRunning] = useState<Step | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const confirm = useConfirm();

  async function run(step: Step, act: () => Promise<string | null>) {
    setRunning(step);
    setFailure(await act());
    setRunning(null);
  }

  function confirmSelected() {
    setTried(true);
    const problem = confirmProblem(drafts);
    setFailure(problem);
    if (!problem) void run("confirm", () => onConfirm(confirmBody(drafts)));
  }

  async function discard() {
    if (await confirm(DISCARD_DIALOG)) await run("discard", onDiscard);
  }

  const setDraft = (next: StagedDraft) => setDrafts((current) => withDraft(current, next));
  return { drafts, setDraft, tried, running, failure, confirmSelected, discard };
}

export function StagedBatchCard(props: CardProps) {
  const { batch } = props;
  const steps = useBatchSteps(props);
  const headingId = `staged-batch-${batch.id}`;
  const open = batch.status === "OPEN";
  return (
    <article aria-labelledby={headingId} className="grid gap-4" data-testid="staged-batch" data-status={batch.status}>
      <BatchHeader batch={batch} headingId={headingId} />
      <BatchItems batch={batch} drafts={steps.drafts} tried={steps.tried} onDraft={steps.setDraft} />
      <p role="status" className="max-w-measure font-ui text-ui text-ink-1">
        {open ? "" : [`${batchTally(batch)}.`, batch.refresh].filter(Boolean).join(" ")}
      </p>
      {steps.failure ? (
        <p role="alert" className="font-ui text-ui text-error">
          {steps.failure}
        </p>
      ) : null}
      {open ? (
        <ActionGroup align="start">
          <Button variant="quiet" busy={steps.running === "confirm"} busyLabel="Confirming" disabled={steps.running === "discard"} onClick={steps.confirmSelected}>
            Confirm selected
          </Button>
          <Button variant="danger" data-danger="" busy={steps.running === "discard"} busyLabel="Discarding" disabled={steps.running === "confirm"} onClick={() => void steps.discard()}>
            Discard batch
          </Button>
        </ActionGroup>
      ) : null}
    </article>
  );
}
