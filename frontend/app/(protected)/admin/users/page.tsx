"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useConfirm, type ConfirmOptions } from "@/components/dialogs/ConfirmDialog";
import { FieldDialog } from "@/components/dialogs/FieldDialog";
import { EmptyState } from "@/components/EmptyState";
import { FieldBlock } from "@/components/FormControls";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { RecordDetailsDialog } from "@/components/records/RecordDetailsDialog";
import { RecordNotice } from "@/components/records/RecordNotice";
import { SearchInput } from "@/components/SearchInput";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/Dropdown";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { formatDateTime } from "@/lib/format";
import { ROLES_BY_RANK, roleLabel } from "@/lib/permissions";
import { resetTwoFactorForUser } from "@/lib/twoFactor";
import type { PageResult, User, UserRole } from "@/lib/types";

import { UserTable, type UserRowHandlers } from "./UserRows";
import {
  GUARDIAN_STATEMENT,
  STANDING_LABEL,
  accountStanding,
  changeUserRole,
  confirmGuardianConsent,
  listUsers,
  reactivateUser,
  roleChoices,
  suspendUser,
  twoStepFact
} from "./userAdmin";

const SEARCH_DELAY_MS = 300;
const ACCOUNTS = { one: "account", many: "accounts" };

export default function ManageUsersPage() {
  return (
    <Suspense fallback={<Header />}>
      <ManageUsers />
    </Suspense>
  );
}

function Header() {
  return <PageHeader title="Manage users" kicker="Admin" description="Roles and access for every account." />;
}

function userDetails(viewing: User): Array<readonly [string, string | null]> {
  return [
    ["Email", viewing.email],
    ["Role", roleLabel(viewing.role)],
    ["Affiliation", viewing.affiliation ?? null],
    ["Two-step verification", twoStepFact(viewing)],
    ["Guardian consent", viewing.guardianConsent ? (viewing.guardianConsent === "CONFIRMED" ? "Confirmed" : "Not confirmed") : null],
    ["Status", STANDING_LABEL[accountStanding(viewing)]],
    ["First sign-in", viewing.firstLoginAt ? formatDateTime(viewing.firstLoginAt) : null],
    ["Last sign-in", viewing.lastLoginAt ? formatDateTime(viewing.lastLoginAt) : null]
  ];
}

function useUserList() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PageResult<User> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    const mine = ++generation.current;
    try {
      const next = await listUsers({ search: query || undefined, role: role || undefined, page });
      if (mine !== generation.current) return;
      setData(next);
      setError(null);
    } catch (err) {
      if (mine !== generation.current) return;
      setError(err instanceof Error ? err.message : "Couldn't load accounts.");
    }
  }, [page, query, role]);

  useEffect(() => {
    void load();
  }, [load]);

  const replaceRow = useCallback((next: User) => {
    setData((current) => (current ? { ...current, items: current.items.map((item) => (item.id === next.id ? { ...item, ...next } : item)) } : current));
  }, []);

  const chooseRole = (next: string) => {
    setRole(next);
    setPage(1);
  };

  return { search, setSearch, query, role, chooseRole, setPage, data, error, replaceRow };
}

function ManageUsers() {
  const { user: viewer } = useAuth();
  const confirm = useConfirm();
  const { toast } = useToast();
  const list = useUserList();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [roleFor, setRoleFor] = useState<User | null>(null);
  const [viewing, setViewing] = useState<User | null>(null);

  async function run(target: User, action: () => Promise<User>, done: string) {
    setBusyId(target.id);
    try {
      list.replaceRow(await action());
      toast({ title: done, tone: "success" });
    } catch (err) {
      toast({ title: err instanceof Error ? err.message : "That didn't work. Try again.", tone: "error" });
    } finally {
      setBusyId(null);
    }
  }

  async function ask(target: User, options: ConfirmOptions, action: () => Promise<User>, done: string) {
    if (await confirm(options)) await run(target, action, done);
  }

  const name = (target: User) => target.name || target.email;
  const on: UserRowHandlers = {
    open: setViewing,
    changeRole: setRoleFor,
    reactivate: (target) => void run(target, () => reactivateUser(target.id), "Account reactivated."),
    suspend: (target) =>
      void ask(target, { title: `Suspend ${name(target)}?`, body: "They are signed out and can't sign in until reactivated.", confirmLabel: "Suspend", tone: "danger" }, () => suspendUser(target.id), "Account suspended."),
    resetTwoStep: (target) =>
      void ask(target, { title: `Reset two-step verification for ${name(target)}?`, body: "They set it up again at their next sign-in.", confirmLabel: "Reset", tone: "warning" }, () => resetTwoFactorForUser(target.id), "Two-step verification reset."),
    confirmGuardian: (target) =>
      void ask(target, { title: `Confirm guardian consent for ${name(target)}?`, body: GUARDIAN_STATEMENT, confirmLabel: "Confirm" }, () => confirmGuardianConsent(target), "Guardian consent confirmed.")
  };

  const roleOptions = [{ value: "", label: "Every role" }, ...ROLES_BY_RANK.map((value) => ({ value, label: roleLabel(value) }))];
  const { data } = list;
  const filtered = Boolean(list.query || list.role);

  return (
    <>
      <Header />
      <div className="grid gap-6">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_16rem] md:items-end">
          <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search by name or email" ariaLabel="Search accounts" />
          <FieldBlock label="Role">
            <Dropdown value={list.role} onChange={list.chooseRole} options={roleOptions} ariaLabel="Role" searchable={false} advanceOnSelect={false} />
          </FieldBlock>
        </div>
        {list.error ? <RecordNotice tone="error">{list.error}</RecordNotice> : null}
        {data === null && !list.error ? <Skeleton shape="lede" label="Reading the accounts" /> : null}
        {data && data.items.length === 0 ? (
          <EmptyState
            title={filtered ? "No account matches" : "Accounts appear here"}
            body={filtered ? "Try part of a name or an email address, or every role." : "Everyone who signs in has an account listed here, with their role and standing."}
            actions={filtered ? <Button variant="quiet" onClick={() => { list.setSearch(""); list.chooseRole(""); }}>Show every account</Button> : null}
          />
        ) : null}
        {data && data.items.length > 0 ? (
          <>
            <UserTable viewer={viewer} accounts={data.items} busyId={busyId} on={on} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={list.setPage} noun={ACCOUNTS} label="Pages of accounts" />
          </>
        ) : null}
      </div>
      {roleFor ? (
        <RoleDialog
          viewer={viewer}
          target={roleFor}
          onClose={() => setRoleFor(null)}
          onSaved={(next) => {
            list.replaceRow(next);
            setRoleFor(null);
            toast({ title: `${name(next)} is now ${roleLabel(next.role)}.`, tone: "success" });
          }}
        />
      ) : null}
      <RecordDetailsDialog open={viewing !== null} onClose={() => setViewing(null)} title={viewing ? name(viewing) : ""} details={viewing ? userDetails(viewing) : []} />
    </>
  );
}

function RoleDialog({ viewer, target, onClose, onSaved }: { viewer: User | null; target: User; onClose: () => void; onSaved: (next: User) => void }) {
  const [role, setRole] = useState<UserRole>(target.role);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const options = roleChoices(viewer, target).map((value) => ({ value, label: roleLabel(value) }));

  async function save() {
    setSaving(true);
    setError(null);
    try {
      onSaved(await changeUserRole(target.id, role));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't change the role.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <FieldDialog
      open
      onClose={onClose}
      title={`Role for ${target.name || target.email}`}
      busy={saving}
      footer={
        <>
          <Button variant="quiet" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" busy={saving} busyLabel="Saving" disabled={role === target.role} onClick={() => void save()}>
            Save role
          </Button>
        </>
      }
    >
      <div className="mt-4 grid gap-3">
        <FieldBlock label="Role">
          <Dropdown value={role} onChange={(next) => setRole(next as UserRole)} options={options} searchable={false} advanceOnSelect={false} />
        </FieldBlock>
        {error ? <RecordNotice tone="error">{error}</RecordNotice> : null}
      </div>
    </FieldDialog>
  );
}
