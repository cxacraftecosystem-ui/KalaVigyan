import type { NoteLine } from "@/lib/monographNotes";

export function noteText(note: NoteLine): string {
  return note.year === null ? note.title : `${note.title}, ${note.year}`;
}

export function NoteList({ notes, label }: { notes: readonly NoteLine[]; label: string }) {
  if (!notes.length) return null;
  return (
    <aside className="margin note" aria-label={label}>
      <ul>
        {notes.map((note) => (
          <li key={note.key} data-g={note.key}>
            <b>{note.number}</b>
            <span>{noteText(note)}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
