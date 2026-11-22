"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { RosterFilterBar } from "@/components/admin/RosterFilterBar";
import { clearRosterFilters, hasActiveRosterFilters, rosterFiltersFromSearchParams, type RosterFilters } from "@/components/admin/rosterFilters";
import type { RosterSortControl } from "@/components/admin/SortableTh";
import { useAuth } from "@/components/AuthProvider";
import { CappedListNotice } from "@/components/data/CappedListNotice";
import { CUT_NOTICE_LIVE_REGION, searchCutNotice } from "@/components/data/cappedList";
import { useConfirm, type ConfirmOptions } from "@/components/dialogs/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { refreshPendingAccessCount, usePendingAccessCount } from "@/components/hooks/usePendingAccessCount";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { RecordDetailsDialog } from "@/components/records/RecordDetailsDialog";
import { RecordNotice } from "@/components/records/RecordNotice";
import { RecordSection } from "@/components/records/RecordSection";
import { RestrictedPanel } from "@/components/settings/RestrictedPanel";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api";
import {
  accessEntryDetails,
  accessEntryOffers,
  addToAccessRoster,
  decideAccessRequest,
  listAccessRoster,
  promotionHeldSentence,
  suspendAccessEntry,
  updateAccessEntry,
  type AccessRosterEntry,
  type AccessRosterPage
} from "@/lib/accessRoster";
import { formatDate } from "@/lib/format";
import { assignableRoles, canManageAccessRoster, roleLabel } from "@/lib/permissions";
import type { UserRole } from "@/lib/types";

import { AccessEntryForm, NEW_ACCOUNTS_ONLY } from "./AccessEntryForm";
import { AccessQueue } from "./AccessQueue";
import { AccessRosterTable, type EntryHandlers } from "./AccessRosterTable";
import {
  ACCESS_LIST_STALE_NOTE,
  ACCESS_LIST_UNREADABLE_BODY,
  ACCESS_LIST_UNREADABLE_TITLE,
  ACCESS_NOBODY_YET_BODY,
  ACCESS_NOBODY_YET_TITLE,
  ACCESS_NO_MATCH_BODY,
  ACCESS_NO_MATCH_TITLE,
  ACCESS_PAST_END_TITLE,
  accessRoleCutNotice,
  accessRosterHref,
  listFilteredAccessRoster,
  type AccessRosterAnswer
} from "./rosterQuery";

const PAGE_SIZE = 20;
const QUEUE_PAGE_SIZE = 8;
const KIND = "access" as const;
const ENTRIES = { one: "entry", many: "entries" };

type Notice = { text: string; held: boolean };

export default function PlatformAccessPage() {
  return (
    <Suspense fallback={<Header />}>
      <PlatformAccessScreen />
    </Suspense>
  );
}

function Header() {
  return <PageHeader title="Who may sign in" kicker="Admin" description="Who may sign in, and who is waiting." />;
}

function useAccessLists(permitted: boolean, filters: RosterFilters) {
  const [queue, setQueue] = useState<AccessRosterPage | null>(null);
  const [queuePage, setQueuePage] = useState(1);
  const [data, setData] = useState<AccessRosterAnswer | null>(null);
  const [page, setPage] = useState(1);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const queueGeneration = useRef(0);

  const loadQueue = useCallback(async () => {
    if (!permitted) return;
    const mine = ++queueGeneration.current;
    try {
      const result = await listAccessRoster({ page: queuePage, pageSize: QUEUE_PAGE_SIZE, status: "PENDING" });
      if (mine !== queueGeneration.current) return;
      setQueue(result);
      if (result.items.length === 0 && result.pages > 0 && queuePage > result.pages) setQueuePage(result.pages);
    } catch (err) {
      if (mine !== queueGeneration.current) return;
      setError(err instanceof Error ? err.message : "Unable to load the approval queue");
    }
  }, [permitted, queuePage]);

  const load = useCallback(async () => {
    if (!permitted) return;
    const mine = ++generation.current;
    try {
      const result = await listFilteredAccessRoster({ page, pageSize: PAGE_SIZE, filters });
      if (mine !== generation.current) return;
      setData(result);
      setLoadFailed(false);
      setError(null);
      if (result.items.length === 0 && result.pages > 0 && page > result.pages) setPage(result.pages);
    } catch (err) {
      if (mine !== generation.current) return;
      setError(err instanceof Error ? err.message : "Unable to load the access list");
      setLoadFailed(true);
    }
  }, [filters, page, permitted]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const reloadAll = useCallback(async () => {
    await Promise.all([load(), loadQueue(), refreshPendingAccessCount()]);
  }, [load, loadQueue]);

  return { queue, setQueuePage, data, setPage, loadFailed, error, setError, reloadAll };
}

function entryFromForm(form: FormData, editing: boolean) {
  const withPassword = !editing && form.get("signInWith") === "PASSWORD";
  return {
    email: String(form.get("email") ?? "").trim(),
    fullName: String(form.get("fullName") ?? "").trim(),
    notes: String(form.get("notes") ?? "").trim(),
    role: String(form.get("role") ?? "").trim(),
    withPassword,
    password: withPassword ? String(form.get("password") ?? "") : "",
    mustChange: form.get("mustChangePassword") === "on"
  };
}

function PlatformAccessScreen() {
  const { user } = useAuth();
  const confirm = useConfirm();
  const permitted = canManageAccessRoster(user);
  const counted = usePendingAccessCount(permitted);
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState<RosterFilters>(() => rosterFiltersFromSearchParams(KIND, new URLSearchParams(searchParams.toString())));
  const lists = useAccessLists(permitted, filters);
  const [searchPending, setSearchPending] = useState(false);
  const [editing, setEditing] = useState<AccessRosterEntry | null>(null);
  const [viewing, setViewing] = useState<AccessRosterEntry | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);
  const { setError, setPage, reloadAll } = lists;

  const applyFilters = useCallback(
    (next: RosterFilters) => {
      setFilters(next);
      setPage(1);
    },
    [setPage]
  );

  useEffect(() => {
    window.history.replaceState(null, "", accessRosterHref(filters));
  }, [filters]);

  function announce(text: string, held = false) {
    setNotice({ text, held });
    setError(null);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const entry = entryFromForm(new FormData(formElement), editing !== null);
    if (!entry.email) return;
    if (entry.withPassword && !entry.fullName) {
      setError("Enter their full name.");
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const fields = { fullName: entry.fullName || null, role: (entry.role || null) as UserRole | null, notes: entry.notes || null };
      if (editing) {
        const updated = await updateAccessEntry(editing.id, fields);
        announce(`Updated the entry for ${updated.email}.`);
        setEditing(null);
      } else {
        const created = await addToAccessRoster({ email: entry.email, ...fields, ...(entry.withPassword ? { password: entry.password, mustChangePassword: entry.mustChange } : {}) });
        const held = entry.withPassword ? null : promotionHeldSentence(created);
        if (entry.withPassword) announce(`${created.email} can sign in with your password${entry.mustChange ? " and will then choose their own" : ""}.`);
        else if (held) announce(held, true);
        else announce(`${created.email} may sign in with Google, as ${roleLabel(created.admitRole) || "the default role"}.`);
      }
      formElement.reset();
      await reloadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add this address");
      if (err instanceof ApiError && err.status === 409) applyFilters({ ...clearRosterFilters(KIND, filters), search: entry.email });
    } finally {
      setSaving(false);
    }
  }

  async function decide(options: ConfirmOptions, action: () => Promise<AccessRosterEntry & { accountPromotionHeld?: string | null }>, done: (email: string) => string) {
    if (!(await confirm(options))) return;
    try {
      const updated = await action();
      const held = promotionHeldSentence(updated);
      announce(held ?? done(updated.email), held !== null);
      await reloadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work. Try again.");
    }
  }

  const approve = (entry: AccessRosterEntry, role: UserRole | "") =>
    void decide(
      { title: `Let ${entry.email} in?`, body: role ? `They can sign in now, as ${roleLabel(role)}.` : "They can sign in now, with the default role.", note: NEW_ACCOUNTS_ONLY, confirmLabel: "Approve", tone: "warning" },
      () => decideAccessRequest(entry.id, { decision: "APPROVE", role: role || null }),
      (email) => `${email} may sign in from their next attempt.`
    );
  const reject = (entry: AccessRosterEntry) =>
    void decide(
      { title: `Refuse ${entry.email}?`, body: "They're told it wasn't approved. Any session they are in now ends with it.", note: "The entry stays; you can approve them later.", confirmLabel: "Refuse", tone: "danger" },
      () => decideAccessRequest(entry.id, { decision: "REJECT" }),
      (email) => `${email} was refused. The entry stays on the list.`
    );
  const suspend = (entry: AccessRosterEntry) =>
    void decide(
      { title: `Suspend ${entry.fullName || entry.email}?`, body: "They can't sign in again. Any session they are in now ends immediately.", note: "The entry is kept. Approve again to restore access.", confirmLabel: "Suspend", tone: "danger" },
      () => suspendAccessEntry(entry.id),
      (email) => `${email} can no longer sign in. The entry stays on the list.`
    );
  const restore = (entry: AccessRosterEntry) =>
    void decide(
      { title: `Let ${entry.email} back in?`, body: "They will be able to sign in again immediately.", note: entry.joinedAt ? `Their joining date stays ${formatDate(entry.joinedAt)}.` : undefined, confirmLabel: "Restore", tone: "warning" },
      () => decideAccessRequest(entry.id, { decision: "APPROVE" }),
      (email) => `${email} can sign in again.`
    );

  function startEdit(entry: AccessRosterEntry) {
    setEditing(entry);
    setError(null);
    setNotice(null);
    requestAnimationFrame(() => formRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
  }

  if (!permitted) {
    return (
      <>
        <Header />
        <RestrictedPanel title="Admin access required" body="Admins only." />
      </>
    );
  }

  const offersFor = accessEntryOffers;
  const handlers: EntryHandlers = { offersFor, view: setViewing, update: startEdit, suspend, admit: restore, refuse: reject };
  const sort: RosterSortControl = { kind: KIND, filters, onChange: applyFilters };

  return (
    <>
      <Header />
      <div className="grid gap-12">
        {lists.error ? <RecordNotice tone="error">{lists.error}</RecordNotice> : null}
        {notice ? <RecordNotice tone={notice.held ? "warning" : "info"}>{notice.text}</RecordNotice> : null}
        <AccessQueue
          view={{ queue: lists.queue, pageSize: QUEUE_PAGE_SIZE, capReached: Boolean(counted?.capReached), capacity: counted?.capacity ?? null, onPage: lists.setQueuePage }}
          decisions={{ offersFor, grantable: assignableRoles(user), onApprove: approve, onReject: reject }}
        />
        <AccessEntryForm editing={editing} grantable={assignableRoles(user)} saving={saving} formRef={formRef} onSubmit={(event) => void submit(event)} onCancel={() => setEditing(null)} />
        <RosterSection lists={lists} filters={filters} searchPending={searchPending} sort={sort} handlers={handlers}>
          <RosterFilterBar kind={KIND} filters={filters} onChange={applyFilters} onSearchPendingChange={setSearchPending} />
        </RosterSection>
      </div>
      <RecordDetailsDialog
        open={viewing !== null}
        onClose={() => setViewing(null)}
        title={viewing?.fullName || "Name not recorded"}
        description={viewing?.email}
        details={viewing ? accessEntryDetails(viewing) : []}
        onUpdate={
          viewing && accessEntryOffers(viewing).update
            ? () => {
                setViewing(null);
                startEdit(viewing);
              }
            : undefined
        }
      />
    </>
  );
}

type RosterSectionProps = {
  lists: ReturnType<typeof useAccessLists>;
  filters: RosterFilters;
  searchPending: boolean;
  sort: RosterSortControl;
  handlers: EntryHandlers;
  children: React.ReactNode;
};

function RosterSection({ lists, filters, searchPending, sort, handlers, children }: RosterSectionProps) {
  const { data, loadFailed } = lists;
  const rows = data?.items ?? [];
  const filtered = hasActiveRosterFilters(KIND, filters);
  const emptyBody = searchCutNotice({ noun: "entries", loaded: 0, total: data?.total ?? 0, term: filters.search, emptyLabel: filtered ? ACCESS_NO_MATCH_BODY : ACCESS_NOBODY_YET_BODY, pending: searchPending });
  const emptyTitle = data && data.total > 0 ? ACCESS_PAST_END_TITLE : filtered ? ACCESS_NO_MATCH_TITLE : ACCESS_NOBODY_YET_TITLE;

  return (
    <RecordSection title="Everyone on the list" aside={data ? <span className="tabular-nums lining-nums">{`${data.total} ${data.total === 1 ? "entry" : "entries"}`}</span> : null} testId="access-roster">
      {children}
      <div {...CUT_NOTICE_LIVE_REGION}>
        <CappedListNotice cuts={[accessRoleCutNotice(data?.roleMatchTruncated)]} className="grid gap-0.5" />
      </div>
      {loadFailed && data !== null ? <RecordNotice tone="warning">{ACCESS_LIST_STALE_NOTE}</RecordNotice> : null}
      <div {...CUT_NOTICE_LIVE_REGION}>
        {data === null && !loadFailed ? <Skeleton shape="lede" label="Reading the list" /> : null}
        {data === null && loadFailed ? <EmptyState title={ACCESS_LIST_UNREADABLE_TITLE} body={ACCESS_LIST_UNREADABLE_BODY} headingLevel={3} /> : null}
        {data !== null && rows.length === 0 && searchPending ? <p className="font-ui text-ui font-normal text-ink-2">Searching</p> : null}
        {data !== null && rows.length === 0 && !searchPending ? <EmptyState title={emptyTitle} body={emptyBody} headingLevel={3} /> : null}
      </div>
      {rows.length > 0 ? <AccessRosterTable rows={rows} sort={sort} on={handlers} /> : null}
      {data ? <Pagination page={data.page} pages={data.pages} total={data.total} onPage={lists.setPage} noun={ENTRIES} label="Pages of the list" /> : null}
    </RecordSection>
  );
}
