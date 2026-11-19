"use client";

import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { RowFacts } from "@/components/learn/RowFacts";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import type { Notification } from "@/lib/learningContract";
import { explainerHref, newsText, notesCapText, NOTE_TITLE } from "@/lib/savedView";

export type NotesActions = { busy: string | null; onUpdate: (note: Notification) => void; onRead: (note: Notification) => void };

export const NOTES_EMPTY_TITLE = "Notes on your saved answers";
export const NOTES_EMPTY_BODY = "When the sources behind a saved answer grow, a note here says what they add and offers the update.";

function NoteCard({ note, actions }: { note: Notification; actions: NotesActions }) {
  const unread = note.readAt === null;
  const { payload } = note;
  return (
    <li className="grid min-w-0 gap-2.5 border-b border-rule py-4" data-testid="note" data-unread={unread ? "true" : "false"}>
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        <h3 className="min-w-0 font-ui text-h4 text-ink-1">{NOTE_TITLE}</h3>
        {unread ? <Badge>New</Badge> : null}
        <span className="ms-auto font-ui text-label text-ink-3 tabular-nums">{formatDate(note.createdAt)}</span>
      </div>
      <p className="min-w-0 font-reading text-body-sm [overflow-wrap:anywhere]">
        <Link href={explainerHref(payload.explainerId)} className="kv-link font-normal">
          {payload.question}
        </Link>
      </p>
      <p className="font-ui text-ui font-normal text-ink-1" data-testid="note-news">
        {newsText(payload.news)}
      </p>
      <RowFacts
        facts={[
          { label: "Craft", value: payload.craft.name },
          { label: "Version", value: payload.version },
          { label: "Checked", value: formatDate(payload.checkedAt) }
        ]}
      />
      <ActionGroup align="start">
        <Button type="button" variant="quiet" size="sm" disabled={actions.busy !== null} onClick={() => actions.onUpdate(note)} data-testid="note-update">
          Update the answer
        </Button>
        {unread ? (
          <Button type="button" variant="text" size="sm" disabled={actions.busy !== null} onClick={() => actions.onRead(note)} data-testid="note-read">
            Mark read
          </Button>
        ) : null}
      </ActionGroup>
    </li>
  );
}

export function NotesInbox({ notes, actions }: { notes: readonly Notification[]; actions: NotesActions; reduce?: boolean }) {
  if (notes.length === 0) {
    return (
      <div data-testid="notes-empty">
        <EmptyState headingLevel={3} title={NOTES_EMPTY_TITLE} body={NOTES_EMPTY_BODY} />
      </div>
    );
  }
  const cap = notesCapText(notes.length);
  return (
    <>
      <ul className="grid min-w-0 border-t border-ink-1" data-testid="notes">
        {notes.map((note) => (
          <NoteCard key={note.id} note={note} actions={actions} />
        ))}
      </ul>
      {cap ? <p className="font-ui text-label text-ink-3">{cap}</p> : null}
    </>
  );
}
