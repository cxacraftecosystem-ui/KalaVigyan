"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CircleAlert } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { failureMessage, useRemote } from "@/components/hooks/useRemote";
import { NotesInbox, type NotesActions } from "@/components/learn/NotesInbox";
import { SavedList } from "@/components/learn/SavedList";
import { readAllNotes, readNote, refreshNotes, useNotes } from "@/components/learn/useNotes";
import { PageHeader } from "@/components/PageHeader";
import { LoadingPanel, RetryPanel } from "@/components/RemotePanels";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api";
import { fetchSavedExplainers, unsaveExplainer } from "@/lib/learningApi";
import { unreadText, updateHref } from "@/lib/savedView";

const ACTION_FAILED = "Couldn't do that. Try again.";
const NOTES_FAILED = "Couldn't load your notes.";
const SAVED_FAILED = "Couldn't load what you saved.";

function useBusy() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function act(key: string, work: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await work();
    } catch (cause) {
      setError(apiErrorMessage(cause, ACTION_FAILED));
    } finally {
      setBusy(null);
    }
  }
  return { busy, error, act };
}

export default function SavedPage() {
  const router = useRouter();
  const reduce = useAppReducedMotion();
  const account = useAuth().user?.id ?? null;
  const notes = useNotes(account);
  const saved = useRemote(fetchSavedExplainers);
  const [removed, setRemoved] = useState<ReadonlySet<string>>(() => new Set());
  const { busy, error, act } = useBusy();
  const unread = notes.list?.unread ?? 0;

  useEffect(() => {
    if (account !== null) void refreshNotes();
  }, [account]);

  const noteActions: NotesActions = {
    busy,
    onUpdate: (note) =>
      void act(note.id, async () => {
        if (note.readAt === null) await readNote(note.id);
        router.push(updateHref(note));
      }),
    onRead: (note) => void act(note.id, () => readNote(note.id))
  };
  const remove = (id: string) =>
    void act(id, async () => {
      await unsaveExplainer(id);
      setRemoved((current) => new Set([...current, id]));
    });

  return (
    <>
      <PageHeader
        title="Saved"
        description={unreadText(unread) ?? undefined}
        back={false}
        actions={
          unread > 0 ? (
            <Button variant="quiet" size="sm" disabled={busy !== null} onClick={() => void act("all", readAllNotes)} data-testid="notes-read-all">
              Mark all read
            </Button>
          ) : null
        }
      />
      {error ? (
        <p role="alert" className="mb-4 flex items-start gap-2 rounded-control bg-error-wash px-3 py-2.5 font-ui text-ui text-ink-1">
          <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-error" aria-hidden />
          {error}
        </p>
      ) : null}
      <section aria-labelledby="notes-heading" className="grid min-w-0 gap-3 border-t border-ink-1 pt-4">
        <h2 id="notes-heading" className="font-headline text-h3 text-ink-1">
          Notes
        </h2>
        {notes.list ? (
          <NotesInbox notes={notes.list.items} actions={noteActions} reduce={reduce} />
        ) : notes.failure ? (
          <RetryPanel message={apiErrorMessage(notes.failure, NOTES_FAILED)} onRetry={() => void refreshNotes()} />
        ) : (
          <LoadingPanel />
        )}
      </section>
      <section aria-labelledby="saved-heading" className="mt-12 grid min-w-0 gap-3 border-t border-ink-1 pt-4">
        <h2 id="saved-heading" className="font-headline text-h3 text-ink-1">
          Saved answers
        </h2>
        {saved.failure ? (
          <RetryPanel message={failureMessage(saved.failure, SAVED_FAILED)} onRetry={saved.retry} />
        ) : saved.data ? (
          <SavedList items={saved.data.items.filter((item) => !removed.has(item.explainerId))} busy={busy} onRemove={remove} />
        ) : (
          <LoadingPanel />
        )}
      </section>
    </>
  );
}
