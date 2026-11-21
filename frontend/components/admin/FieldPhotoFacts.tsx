import { RecordNotice } from "@/components/records/RecordNotice";
import { ReviewTerm } from "@/components/review/ReviewTerm";
import { StatusBadge } from "@/components/StatusBadge";
import { formatCalendarDay, formatDate } from "@/lib/format";
import type { FieldPhoto } from "@/lib/fieldPhotoReviewContract";
import { peopleLine, RISK_COPY } from "@/lib/fieldPhotoReviewView";

export function FieldPhotoFacts({ photo }: { photo: FieldPhoto }) {
  const terms: [string, string | null][] = [
    ["Crafts", photo.crafts.join(", ") || null],
    ["People named", peopleLine(photo.people)],
    ["Filed on", photo.placements.join("; ") || null],
    ["Workshop", photo.workshop],
    ["Taken", photo.takenOn ? formatCalendarDay(photo.takenOn) : null],
    ["From", `${photo.publisher}, file ${photo.itemId.split(":").slice(1).join(":")}`],
    ["Rights holder", photo.rightsHolder],
    ["Licence", photo.licence ?? "No open licence: shown with its credit, never offered for reuse"]
  ];
  return (
    <div className="grid gap-4">
      <dl className="grid gap-x-6 gap-y-3 border-t border-ink-1 pt-4 font-ui text-label sm:grid-cols-2">
        {terms.map(([term, value]) => (value ? <ReviewTerm key={term} term={term} value={value} /> : null))}
        <div className="grid gap-0.5 sm:col-span-2">
          <dt className="text-ink-3">Rights statement</dt>
          <dd className="font-reading text-body-sm text-ink-1">{photo.statement}</dd>
        </div>
      </dl>
      <FieldPhotoScreens photo={photo} />
    </div>
  );
}

function FieldPhotoScreens({ photo }: { photo: FieldPhoto }) {
  const screen = photo.screen;
  const risk = RISK_COPY[photo.risk];
  return (
    <section aria-label="What the screens found" className="grid gap-2 border-t border-rule pt-4">
      <h4 className="kicker">What the screens found</h4>
      {screen ? (
        <>
          <StatusBadge tone={risk.tone} label={risk.label} note={`Screened ${formatDate(screen.screenedAt)}${screen.model ? ` by ${screen.model}` : ""}`} />
          {screen.reasons.length ? (
            <ul className="grid list-disc gap-1 ps-5 font-ui text-label text-ink-2">
              {screen.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <StatusBadge tone="neutral" label="Not screened yet" note="The screens look at it on the next sync, or when you screen the waiting photographs." />
      )}
      {photo.masterOnly ? (
        <RecordNotice tone="warning">Only a Master Admin can show it, after clearing the screen&apos;s flag with a note or cropping the region out.</RecordNotice>
      ) : null}
    </section>
  );
}
