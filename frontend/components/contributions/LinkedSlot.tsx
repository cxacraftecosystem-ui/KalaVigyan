import { formatDateTime } from "@/lib/format";
import { slotKicker, type UploadLinkView } from "@/lib/uploadLinkContract";

export function LinkedSlot({ view }: { view: UploadLinkView }) {
  return (
    <section className="grid gap-3 border-t border-ink-1 pt-4" aria-labelledby="linked-slot-h" data-testid="linked-slot">
      <p className="kicker">{slotKicker(view)}</p>
      <h2 id="linked-slot-h" className="text-h3 font-reading text-ink-1">
        What the picture shows
      </h2>
      <ul className="grid gap-2">
        {view.facts.map((fact) => (
          <li key={fact.id} className="border-t border-rule pt-2 text-body-sm font-reading text-ink-1">
            {fact.text}
          </li>
        ))}
      </ul>
      <p className="text-label font-ui text-ink-3">The link works until {formatDateTime(view.expiresAt)}.</p>
    </section>
  );
}
