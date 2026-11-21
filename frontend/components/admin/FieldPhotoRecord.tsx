import { RecordNotice } from "@/components/records/RecordNotice";
import { StatusBadge } from "@/components/StatusBadge";
import type { FieldPhoto } from "@/lib/fieldPhotoReviewContract";
import { decidedLine, reasonLine } from "@/lib/fieldPhotoReviewView";

const FLAG_NAMES: Record<string, string> = { ID_DOCUMENT: "identity document", FACE: "face" };

export function FieldPhotoRecord({ photo }: { photo: FieldPhoto }) {
  const decision = photo.decision;
  if (!decision) return null;
  const why = reasonLine(decision.reason, decision.note);
  const cleared = decision.clearedFlags.map((flag) => FLAG_NAMES[flag] ?? flag);
  return (
    <section aria-label="The decision on record" className="grid gap-2 border-t border-rule pt-4">
      <h4 className="kicker">The decision on record</h4>
      <StatusBadge tone={decision.decision === "HIDE" ? "neutral" : "success"} label={decidedLine(decision, decision.decidedRole)} note={why ?? undefined} />
      {cleared.length ? <p className="font-ui text-label text-ink-2">{`Flag cleared: ${cleared.join(", ")}.`}</p> : null}
      {!decision.current ? <RecordNotice tone="info">The portal sent a new copy after this decision, so the photograph waits for a decision again.</RecordNotice> : null}
      {photo.history.length > 1 ? (
        <details className="font-ui text-label text-ink-2">
          <summary className="min-h-target cursor-pointer py-2 text-ink-1">{`Every decision (${photo.history.length})`}</summary>
          <ol className="grid gap-2 border-s border-rule ps-4">
            {photo.history.map((entry) => (
              <li key={`${entry.decidedAt}-${entry.decision}`} className="grid gap-0.5">
                <span className="text-ink-1 tabular-nums lining-nums">{decidedLine(entry)}</span>
                {reasonLine(entry.reason, entry.note) ? <span>{reasonLine(entry.reason, entry.note)}</span> : null}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </section>
  );
}
