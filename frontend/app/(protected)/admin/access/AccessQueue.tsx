"use client";

import { useState } from "react";
import { UserCheck, UserX } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { Pagination } from "@/components/Pagination";
import { RecordNotice } from "@/components/records/RecordNotice";
import { RecordSection } from "@/components/records/RecordSection";
import { RowActions, RowButton } from "@/components/RowActions";
import { Dropdown } from "@/components/ui/Dropdown";
import { FieldLabelProvider } from "@/components/ui/fieldLabel";
import { Skeleton } from "@/components/ui/Skeleton";
import type { AccessEntryOffers, AccessRosterEntry, AccessRosterPage } from "@/lib/accessRoster";
import { byCount, formatDateTime } from "@/lib/format";
import { roleLabel } from "@/lib/permissions";
import type { UserRole } from "@/lib/types";

export type QueueDecisions = {
  offersFor: (entry: AccessRosterEntry) => AccessEntryOffers;
  grantable: UserRole[];
  onApprove: (entry: AccessRosterEntry, role: UserRole | "") => void;
  onReject: (entry: AccessRosterEntry) => void;
};

function QueueRow({ entry, decisions }: { entry: AccessRosterEntry; decisions: QueueDecisions }) {
  const [role, setRole] = useState<UserRole | "">("");
  const offers = decisions.offersFor(entry);
  const labelId = `tier-label-${entry.id}`;
  return (
    <li className="grid gap-3 border-b border-rule py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:gap-6">
      <div className="grid min-w-0 gap-1">
        <span className="truncate font-ui text-ui font-medium text-ink-1">{entry.email}</span>
        <span className="font-ui text-label text-ink-3 tabular-nums lining-nums">
          {entry.requestedAt ? `Asked ${formatDateTime(entry.requestedAt)}` : "Asked at an unrecorded time"}
          {` · ${entry.attemptCount} ${byCount(entry.attemptCount, "attempt", "attempts")}`}
          {entry.lastAttemptAt ? `, last ${formatDateTime(entry.lastAttemptAt)}` : ""}
        </span>
      </div>
      {offers.admit || offers.refuse ? (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,16rem)_auto] sm:items-center">
          {offers.admit ? (
            <>
              <span id={labelId} className="sr-only">
                The role {entry.email} joins with
              </span>
              <FieldLabelProvider value={labelId}>
                <Dropdown
                  value={role}
                  onChange={(next) => setRole(next as UserRole | "")}
                  options={[{ value: "", label: "Joins with the default role" }, ...decisions.grantable.map((option) => ({ value: option, label: `Joins as ${roleLabel(option)}` }))]}
                  advanceOnSelect={false}
                />
              </FieldLabelProvider>
            </>
          ) : null}
          <RowActions>
            {offers.admit ? (
              <RowButton onClick={() => decisions.onApprove(entry, role)}>
                <UserCheck className="size-3.5" aria-hidden />
                Approve
              </RowButton>
            ) : null}
            {offers.refuse ? (
              <RowButton danger onClick={() => decisions.onReject(entry)}>
                <UserX className="size-3.5" aria-hidden />
                Refuse
              </RowButton>
            ) : null}
          </RowActions>
        </div>
      ) : null}
    </li>
  );
}

export type QueueView = { queue: AccessRosterPage | null; pageSize: number; capReached: boolean; capacity: number | null; onPage: (page: number) => void };

export function AccessQueue({ view, decisions }: { view: QueueView; decisions: QueueDecisions }) {
  const { queue } = view;
  return (
    <RecordSection
      title="Waiting for a decision"
      description="Signed in but not on the list yet."
      aside={queue ? <span className="tabular-nums lining-nums">{`${queue.total} waiting`}</span> : null}
      testId="access-queue"
    >
      {view.capReached ? <RecordNotice tone="warning">{`The queue is full at ${view.capacity ?? "its limit"}. New requests are not recorded until some are decided.`}</RecordNotice> : null}
      {queue === null ? <Skeleton shape="lede" label="Reading the approval queue" /> : null}
      {queue && queue.items.length === 0 ? <EmptyState title="Nobody is waiting" body="A person who signs in without being on the list appears here, to approve or refuse." headingLevel={3} /> : null}
      {queue && queue.items.length > 0 ? (
        <ul className="grid border-t border-ink-1">
          {queue.items.map((entry) => (
            <QueueRow key={entry.id} entry={entry} decisions={decisions} />
          ))}
        </ul>
      ) : null}
      {queue && queue.total > view.pageSize ? <Pagination page={queue.page} pages={queue.pages} total={queue.total} onPage={view.onPage} noun={{ one: "request", many: "requests" }} label="Pages of the queue" /> : null}
    </RecordSection>
  );
}
