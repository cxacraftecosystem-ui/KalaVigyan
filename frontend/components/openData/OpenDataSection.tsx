import type { ReactNode } from "react";

export function OpenDataSection({ id, title, lead, children }: { id: string; title: string; lead?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid min-w-0 gap-5 border-t border-ink-1 pt-4">
      <header className="grid gap-2">
        <h2 id={id} className="font-headline text-h2 text-ink-1">
          {title}
        </h2>
        {lead ? <p className="max-w-measure font-reading text-body text-ink-2">{lead}</p> : null}
      </header>
      {children}
    </section>
  );
}
