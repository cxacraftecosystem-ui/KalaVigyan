"use client";

import { OpenableRow } from "@/components/data/OpenableRow";
import { RECORD_CELL, RECORD_HEAD_ROW, RECORD_NOTE, RECORD_TABLE } from "@/components/records/recordTable";
import { ResizableTh } from "@/components/ResizableTh";
import { RowActions, RowButton } from "@/components/RowActions";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime } from "@/lib/format";
import { roleLabel } from "@/lib/permissions";
import type { User } from "@/lib/types";

import { STANDING_LABEL, accountStanding, guardianConsentMissing, offersGuardianConfirmation, rowOffers, twoStepFact } from "./userAdmin";

export type UserRowHandlers = {
  open: (account: User) => void;
  changeRole: (account: User) => void;
  confirmGuardian: (account: User) => void;
  resetTwoStep: (account: User) => void;
  reactivate: (account: User) => void;
  suspend: (account: User) => void;
};

function UserActions({ viewer, account, busy, on }: { viewer: User | null; account: User; busy: boolean; on: UserRowHandlers }) {
  const offers = rowOffers(viewer, account);
  return (
    <RowActions>
      {offers.role ? (
        <RowButton disabled={busy} onClick={() => on.changeRole(account)}>
          Change role
        </RowButton>
      ) : null}
      {offersGuardianConfirmation(viewer, account) ? (
        <RowButton disabled={busy} onClick={() => on.confirmGuardian(account)}>
          Confirm guardian consent
        </RowButton>
      ) : null}
      {offers.resetTwoStep ? (
        <RowButton disabled={busy} onClick={() => on.resetTwoStep(account)}>
          Reset two-step
        </RowButton>
      ) : null}
      {offers.reactivate ? (
        <RowButton disabled={busy} onClick={() => on.reactivate(account)}>
          Reactivate
        </RowButton>
      ) : null}
      {offers.suspend ? (
        <RowButton danger disabled={busy} onClick={() => on.suspend(account)}>
          Suspend
        </RowButton>
      ) : null}
    </RowActions>
  );
}

function UserRow({ viewer, account, busy, on }: { viewer: User | null; account: User; busy: boolean; on: UserRowHandlers }) {
  const suspended = accountStanding(account) === "SUSPENDED";
  return (
    <OpenableRow onOpen={() => on.open(account)} className="border-b border-rule">
      <td className={RECORD_CELL}>
        <button type="button" onClick={() => on.open(account)} className="rounded-control text-start">
          <span className="block font-ui text-ui font-medium text-ink-1">{account.name || account.email}</span>
          <span className="block break-all font-ui text-label text-ink-3">{account.email}</span>
        </button>
      </td>
      <td className={RECORD_CELL}>
        {roleLabel(account.role)}
        {guardianConsentMissing(account) ? (
          <span className="mt-1 block">
            <StatusBadge tone="warning" label="Guardian consent not confirmed" />
          </span>
        ) : null}
      </td>
      <td className={`${RECORD_CELL} text-ink-2`}>{twoStepFact(account)}</td>
      <td className={`${RECORD_CELL} text-ink-2`}>
        {account.lastLoginAt ? formatDateTime(account.lastLoginAt) : "Never"}
        {account.firstLoginAt ? <span className={RECORD_NOTE}>First {formatDateTime(account.firstLoginAt)}</span> : null}
      </td>
      <td className={RECORD_CELL}>
        <StatusBadge tone={suspended ? "error" : "success"} label={STANDING_LABEL[accountStanding(account)]} />
      </td>
      <td className={RECORD_CELL}>
        <UserActions viewer={viewer} account={account} busy={busy} on={on} />
      </td>
    </OpenableRow>
  );
}

export function UserTable({ viewer, accounts, busyId, on }: { viewer: User | null; accounts: User[]; busyId: string | null; on: UserRowHandlers }) {
  return (
    <div className="overflow-x-auto">
      <table className={`${RECORD_TABLE} min-w-4xl`}>
        <caption className="sr-only">Accounts</caption>
        <thead>
          <tr className={RECORD_HEAD_ROW}>
            <ResizableTh>Account</ResizableTh>
            <ResizableTh>Role</ResizableTh>
            <ResizableTh>Two-step</ResizableTh>
            <ResizableTh>Last sign-in</ResizableTh>
            <ResizableTh>Status</ResizableTh>
            <ResizableTh className="text-end">
              <span className="sr-only">Actions</span>
            </ResizableTh>
          </tr>
        </thead>
        <tbody>
          {accounts.map((account) => (
            <UserRow key={account.id} viewer={viewer} account={account} busy={busyId === account.id} on={on} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
