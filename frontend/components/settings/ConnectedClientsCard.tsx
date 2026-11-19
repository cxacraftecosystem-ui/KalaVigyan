"use client";

import { useCallback, useEffect, useState } from "react";

import { useConfirm } from "@/components/dialogs/ConfirmDialog";
import { RecordSection } from "@/components/records/RecordSection";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/Skeleton";
import { apiErrorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { scopeList } from "@/lib/oauthConsent";
import { fetchConnections, revokeConnection, type Connection, type ConnectionList } from "@/lib/oauthContract";

const LOAD_FAILED = "Couldn't load your connected apps.";
const REVOKE_FAILED = "Couldn't revoke the app. Try again.";

function ConnectedClientRow({ item, busy, onRevoke }: { item: Connection; busy: boolean; onRevoke: (item: Connection) => void }) {
  return (
    <li className="grid gap-x-8 gap-y-2 border-t border-rule py-4 first:border-t-0 first:pt-0 md:grid-cols-[minmax(0,1fr)_auto] md:items-start" data-testid="connected-app">
      <div className="grid min-w-0 gap-1">
        <p className="font-ui text-h4 text-ink-1">
          {item.clientName} <span className="font-ui text-label text-ink-3">· {item.clientHost}</span>
        </p>
        <p className="font-ui text-label text-ink-2">May {scopeList(item.scopes)}</p>
        <p className="font-ui text-label text-ink-3 tabular-nums lining-nums">
          Connected {formatDateTime(item.connectedAt)} · {item.lastUsedAt ? `last used ${formatDateTime(item.lastUsedAt)}` : "never used"}
        </p>
      </div>
      <ActionGroup align="end">
        <Button type="button" variant="danger" size="sm" busy={busy} busyLabel="Revoking" onClick={() => onRevoke(item)} data-danger>
          Revoke
        </Button>
      </ActionGroup>
    </li>
  );
}

export function ConnectedClientsCard() {
  const confirm = useConfirm();
  const [list, setList] = useState<ConnectionList | null>(null);
  const [failed, setFailed] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setList(await fetchConnections());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (list && !list.serverUrl && !list.connections.length) return null;

  async function revoke(item: Connection) {
    const sure = await confirm({
      title: `Revoke ${item.clientName}?`,
      body: "It can no longer use KalaVigyan in your name. Connect it again from the app if you need it.",
      tone: "danger",
      confirmLabel: "Revoke"
    });
    if (!sure) return;
    setBusyId(item.id);
    setError(null);
    try {
      await revokeConnection(item.id);
      await load();
    } catch (cause) {
      setError(apiErrorMessage(cause, REVOKE_FAILED));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <RecordSection title="Connected apps" description="Apps that use KalaVigyan in your name through its MCP server." testId="connected-apps">
      {!list && !failed ? <Skeleton shape="lede" label="Fetching your connected apps" /> : null}
      {failed ? (
        <div role="alert" className="grid justify-items-start gap-2">
          <p className="text-ui font-ui text-error">{LOAD_FAILED}</p>
          <Button type="button" variant="quiet" size="sm" onClick={() => void load()}>
            Try again
          </Button>
        </div>
      ) : null}
      {list && !list.connections.length ? (
        <p className="text-body-sm font-reading text-ink-2">
          Apps you connect to KalaVigyan appear here with what each may do. To connect one, add <span className="font-code break-all">{list.serverUrl}</span> as an MCP server in the app.
        </p>
      ) : null}
      {list?.connections.length ? (
        <ul className="grid gap-3">
          {list.connections.map((item) => (
            <ConnectedClientRow key={item.id} item={item} busy={busyId === item.id} onRevoke={(next) => void revoke(next)} />
          ))}
        </ul>
      ) : null}
      {error ? <p role="alert" className="text-ui font-ui text-error">{error}</p> : null}
    </RecordSection>
  );
}
