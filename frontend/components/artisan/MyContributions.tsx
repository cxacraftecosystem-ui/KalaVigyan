"use client";

import { useState } from "react";

import { FormAlert } from "@/components/auth/FormAlert";
import { EmptyState } from "@/components/EmptyState";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api";
import { DISCIPLINE_LABEL } from "@/lib/explainerView";
import { formatDate } from "@/lib/format";
import { REJECT_REASON_LABELS, STATUS_LABELS, withdrawContribution, type Contribution, type ContributionList, type Counts } from "@/lib/testimonyContract";

const REVIEWERS: Record<string, string> = { PROFESSOR: "a professor", ADMIN: "an administrator", MASTER_ADMIN: "an administrator" };
const COUNT_LABELS: readonly (readonly [keyof Counts, string])[] = [
  ["pending", "Waiting"],
  ["approved", "Shown"],
  ["rejected", "Not shown"],
  ["withdrawn", "Taken back"]
];
const FIELD_LABELS: Readonly<Record<string, string>> = DISCIPLINE_LABEL;

type Fact = { label: string; value: string };

function itemFacts(item: Contribution): Fact[] {
  const reviewer = item.reviewerRole ? REVIEWERS[item.reviewerRole] : null;
  const facts: (Fact | null)[] = [
    { label: "About", value: FIELD_LABELS[item.discipline] ?? item.discipline },
    { label: "Recorded", value: formatDate(item.recordedAt) },
    { label: "Shared", value: formatDate(item.submittedAt) },
    item.reviewedAt ? { label: "Reviewed", value: reviewer ? `${formatDate(item.reviewedAt)} by ${reviewer}` : formatDate(item.reviewedAt) } : null,
    item.approvedAt ? { label: "Shown since", value: formatDate(item.approvedAt) } : null,
    item.rejectReason ? { label: "Why not shown", value: REJECT_REASON_LABELS[item.rejectReason] } : null
  ];
  return facts.filter((fact): fact is Fact => fact !== null);
}

function Facts({ facts }: { facts: readonly Fact[] }) {
  return (
    <dl className="flex min-w-0 flex-wrap gap-x-5 gap-y-1 font-ui text-label lining-nums tabular-nums">
      {facts.map((fact) => (
        <div key={fact.label} className="flex min-w-0 max-w-full gap-1.5">
          <dt className="shrink-0 text-ink-3">{fact.label}</dt>{" "}
          <dd className="min-w-0 text-ink-1 [overflow-wrap:anywhere]">{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Withdraw({ item, onChanged }: { item: Contribution; onChanged: () => void }) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function withdraw() {
    setBusy(true);
    try {
      await withdrawContribution(item.id);
      onChanged();
    } catch (cause) {
      setError(apiErrorMessage(cause, "Couldn't take it back. Try again."));
    } finally {
      setBusy(false);
      setAsking(false);
    }
  }

  return (
    <div className="grid gap-2">
      {asking ? <p className="font-ui text-ui font-normal text-ink-1">Take this back? It will no longer be shown anywhere.</p> : null}
      {error ? <FormAlert>{error}</FormAlert> : null}
      <ActionGroup align="start">
        {asking ? (
          <>
            <Button type="button" variant="quiet" size="sm" disabled={busy} onClick={() => setAsking(false)}>
              Keep
            </Button>
            <Button type="button" variant="destroy" size="sm" data-danger busy={busy} busyLabel="Taking back" onClick={() => void withdraw()}>
              Take back
            </Button>
          </>
        ) : (
          <Button type="button" variant="danger" size="sm" data-danger onClick={() => setAsking(true)}>
            Withdraw
          </Button>
        )}
      </ActionGroup>
    </div>
  );
}

function Item({ item, onChanged }: { item: Contribution; onChanged: () => void }) {
  return (
    <li className="grid min-w-0 gap-2.5 border-b border-rule py-4" data-testid="contribution">
      <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 font-ui text-label text-ink-3">
        <Badge>{STATUS_LABELS[item.status]}</Badge>
        <span className="text-ink-1">{item.craft.name}</span>
        <span aria-hidden>·</span>
        <span className="lining-nums tabular-nums">{item.locator}</span>
      </p>
      {item.quote ? (
        <blockquote lang={item.language} dir="auto" className="max-w-measure font-reading text-quote italic text-ink-1">
          “{item.quote}”
        </blockquote>
      ) : null}
      {item.english && item.english !== item.quote ? <p className="max-w-measure font-reading text-body-sm text-ink-2">{item.english}</p> : null}
      {item.claimText ? <p className="max-w-measure font-reading text-body-sm text-ink-1">{item.claimText}</p> : null}
      <Facts facts={itemFacts(item)} />
      {item.reviewNote ? (
        <p className="max-w-measure font-ui text-ui font-normal text-ink-1">
          <span className="text-ink-3">Reviewer&apos;s note: </span>
          {item.reviewNote}
        </p>
      ) : null}
      {item.status !== "REJECTED" ? <Withdraw item={item} onChanged={onChanged} /> : null}
    </li>
  );
}

export function MyContributions({ listed, onChanged }: { listed: ContributionList; onChanged: () => void }) {
  const shown = listed.items.filter((item): item is Contribution => item.status !== "WITHDRAWN");
  return (
    <section aria-labelledby="shared-heading" className="grid gap-4" data-testid="my-contributions">
      <h2 id="shared-heading" className="border-t border-ink-1 pt-4 font-reading text-h3 text-ink-1">
        What you shared
      </h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        {COUNT_LABELS.map(([key, label]) => (
          <div key={key} className="grid gap-0.5 border-t border-rule pt-2">
            <dt className="font-ui text-label text-ink-3">{label}</dt>
            <dd className="font-headline text-h3 text-ink-1 lining-nums tabular-nums">{listed.counts[key]}</dd>
          </div>
        ))}
      </dl>
      {shown.length ? (
        <ul className="grid min-w-0 border-t border-rule">
          {shown.map((item) => (
            <Item key={item.id} item={item} onChanged={onChanged} />
          ))}
        </ul>
      ) : (
        <EmptyState headingLevel={3} title="Your shared words" body="Lines you share from a recording wait here for review, with what the reviewers decided." />
      )}
    </section>
  );
}
