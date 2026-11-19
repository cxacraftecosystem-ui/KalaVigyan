"use client";

import { useMemo, useState } from "react";
import { Link2 } from "lucide-react";

import { useConfirm } from "@/components/dialogs/ConfirmDialog";
import { useRemote } from "@/components/hooks/useRemote";
import { buttonLook } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api";
import { fetchShareLink, sharedAddress, startSharing, stopSharing, type ShareLink } from "@/lib/shareContract";
import { SHARE_NOTICE, type SharedKind } from "@/lib/shareNotice";

const PILL = buttonLook({ variant: "quiet", size: "sm" });
const SHARE_FAILED = "Couldn't change the share link. Try again.";

export function ShareControl({ sharePath, kind }: { sharePath: string; kind: SharedKind }) {
  const confirm = useConfirm();
  const load = useMemo(() => () => fetchShareLink(sharePath), [sharePath]);
  const remote = useRemote(load);
  const [changed, setChanged] = useState<ShareLink | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const link = changed ?? remote.data;
  if (!link) return null;

  async function run(change: () => Promise<ShareLink>, done: (next: ShareLink) => Promise<string | null>) {
    setBusy(true);
    setNote(null);
    try {
      const next = await change();
      setChanged(next);
      setNote(await done(next));
    } catch (cause) {
      setNote(apiErrorMessage(cause, SHARE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  const copy = async (next: ShareLink) => {
    const address = sharedAddress(window.location.origin, next);
    if (!address) return null;
    try {
      await navigator.clipboard.writeText(address);
      return "Link copied. Anyone with it can read this.";
    } catch {
      return address;
    }
  };

  async function share() {
    if (!(await confirm(SHARE_NOTICE[kind]))) return;
    await run(() => startSharing(sharePath), copy);
  }

  return (
    <>
      {link.shared ? (
        <>
          <button type="button" {...PILL} disabled={busy} onClick={() => void run(async () => link, copy)} data-testid="share-copy">
            <Link2 className="h-4 w-4" aria-hidden />
            Copy link
          </button>
          <button type="button" {...PILL} disabled={busy} onClick={() => void run(() => stopSharing(sharePath), async () => "Sharing stopped. The link no longer opens.")} data-testid="share-stop">
            Stop sharing
          </button>
        </>
      ) : (
        <button type="button" {...PILL} disabled={busy} onClick={() => void share()} data-testid="share-start">
          <Link2 className="h-4 w-4" aria-hidden />
          Share link
        </button>
      )}
      <span role="status" aria-live="polite" className="basis-full font-ui text-label text-ink-2 [overflow-wrap:anywhere] empty:hidden" data-testid="share-note">
        {note}
      </span>
    </>
  );
}
