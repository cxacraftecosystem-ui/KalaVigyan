"use client";

import { UserCheck } from "lucide-react";

import { SortableTh, type RosterSortControl } from "@/components/admin/SortableTh";
import { OpenableRow } from "@/components/data/OpenableRow";
import { RECORD_CELL, RECORD_HEAD_ROW, RECORD_NOTE, RECORD_TABLE } from "@/components/records/recordTable";
import { ResizableTh } from "@/components/ResizableTh";
import { RowActions, RowButton } from "@/components/RowActions";
import { StatusBadge } from "@/components/StatusBadge";
import type { AccessEntryOffers, AccessRosterEntry } from "@/lib/accessRoster";
import { byCount, formatDate, formatDateTime } from "@/lib/format";
import { roleLabel } from "@/lib/permissions";

export type EntryHandlers = {
  offersFor: (entry: AccessRosterEntry) => AccessEntryOffers;
  view: (entry: AccessRosterEntry) => void;
  update: (entry: AccessRosterEntry) => void;
  suspend: (entry: AccessRosterEntry) => void;
  admit: (entry: AccessRosterEntry) => void;
  refuse: (entry: AccessRosterEntry) => void;
};

function Standing({ entry }: { entry: AccessRosterEntry }) {
  if (entry.status === "ACTIVE") {
    return (
      <StatusBadge tone="success" note={entry.admitRole ? `as ${roleLabel(entry.admitRole)}` : "with the default role"} label="May sign in" />
    );
  }
  if (entry.status === "PENDING") return <StatusBadge tone="waiting" label="Waiting for a decision" />;
  return (
    <StatusBadge tone="error" note={entry.decidedAt ? `since ${formatDate(entry.decidedAt)}` : "date not recorded"} label={entry.status === "REJECTED" ? "Refused" : "Suspended"} />
  );
}

function EntryActions({ entry, on }: { entry: AccessRosterEntry; on: EntryHandlers }) {
  const offers = on.offersFor(entry);
  return (
    <RowActions>
      {offers.update ? <RowButton onClick={() => on.update(entry)}>Update</RowButton> : null}
      {offers.admit ? (
        <RowButton onClick={() => on.admit(entry)}>
          <UserCheck className="size-3.5" aria-hidden />
          {entry.status === "PENDING" ? "Approve" : "Let back in"}
        </RowButton>
      ) : null}
      {offers.suspend ? (
        <RowButton danger onClick={() => on.suspend(entry)}>
          Suspend
        </RowButton>
      ) : null}
      {offers.refuse ? (
        <RowButton danger onClick={() => on.refuse(entry)}>
          Refuse
        </RowButton>
      ) : null}
    </RowActions>
  );
}

function EntryRow({ entry, on }: { entry: AccessRosterEntry; on: EntryHandlers }) {
  return (
    <OpenableRow onOpen={() => on.view(entry)} className="border-b border-rule">
      <td className={RECORD_CELL}>
        <button type="button" onClick={() => on.view(entry)} className="rounded-control text-start font-ui text-ui font-medium text-ink-1 underline-offset-3 hover:underline">
          {entry.fullName || <span className="font-normal text-ink-3">Name not recorded</span>}
        </button>
      </td>
      <td className={`${RECORD_CELL} break-all text-ink-2`}>{entry.email}</td>
      <td className={RECORD_CELL}>
        <Standing entry={entry} />
      </td>
      <td className={`${RECORD_CELL} text-ink-2`}>{entry.createdAt ? formatDate(entry.createdAt) : "-"}</td>
      <td className={`${RECORD_CELL} text-ink-2`}>{entry.joinedAt ? formatDate(entry.joinedAt) : "-"}</td>
      <td className={`${RECORD_CELL} text-ink-2`}>
        {entry.firstSeenAt ? formatDate(entry.firstSeenAt) : <span className="text-ink-3">{entry.joinedAt ? "Has not signed in" : "Never admitted"}</span>}
      </td>
      <td className={`${RECORD_CELL} text-ink-2`}>
        {entry.attemptCount > 0 ? `${entry.attemptCount} refused ${byCount(entry.attemptCount, "attempt", "attempts")}` : "-"}
        {entry.attemptCount > 0 ? <span className={RECORD_NOTE}>{entry.lastAttemptAt ? `Last ${formatDateTime(entry.lastAttemptAt)}` : "Date not recorded"}</span> : null}
      </td>
      <td className={`${RECORD_CELL} max-w-xs text-ink-2`}>{entry.notes ? <span className="line-clamp-3 whitespace-pre-line">{entry.notes}</span> : "-"}</td>
      <td className={RECORD_CELL}>
        <EntryActions entry={entry} on={on} />
      </td>
    </OpenableRow>
  );
}

export function AccessRosterTable({ rows, sort, on }: { rows: AccessRosterEntry[]; sort: RosterSortControl; on: EntryHandlers }) {
  return (
    <div className="overflow-x-auto">
      <table className={`${RECORD_TABLE} min-w-7xl`}>
        <caption className="sr-only">Everyone on the access list</caption>
        <thead>
          <tr className={RECORD_HEAD_ROW}>
            <SortableTh control={sort} column="name" label="Name" />
            <SortableTh control={sort} column="email" label="Email" />
            <SortableTh control={sort} column="standing" label="Standing" />
            <SortableTh control={sort} column="added" label="Added" />
            <SortableTh control={sort} column="joined" label="Joined" />
            <SortableTh control={sort} column="firstSeen" label="First signed in" />
            <SortableTh control={sort} column="attempts" label="Requests" />
            <ResizableTh>Note</ResizableTh>
            <ResizableTh className="text-end">
              <span className="sr-only">Actions</span>
            </ResizableTh>
          </tr>
        </thead>
        <tbody>
          {rows.map((entry) => (
            <EntryRow key={entry.id} entry={entry} on={on} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
