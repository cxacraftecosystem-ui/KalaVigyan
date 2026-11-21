"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/Toggle";
import { apiErrorMessage } from "@/lib/api";
import { screenFieldPhotos, setFieldPhotoSwitch, type FieldPhotoQueue, type SwitchState } from "@/lib/fieldPhotoReviewContract";
import { screenedLine } from "@/lib/fieldPhotoReviewView";

const SWITCH_FAILED = "Couldn't change the switch. Try again.";
const SCREEN_FAILED = "Couldn't run the screens. Try again in a minute.";
const SWITCH_COPY = "Off hides every photograph filed on an artisan, a session or a participant, whatever its decision. On shows only those an Admin decided to show.";

export function FieldPhotoSwitch({ queue, master, onSwitched, onScreened }: { queue: FieldPhotoQueue; master: boolean; onSwitched: (visibility: SwitchState) => void; onScreened: () => void }) {
  const [busy, setBusy] = useState<"switch" | "screen" | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const on = queue.visibility === "SHOWN";

  async function flip(next: boolean) {
    setBusy("switch");
    setError(null);
    try {
      onSwitched(await setFieldPhotoSwitch(next ? "SHOWN" : "HIDDEN"));
      setStatus(next ? "Reviewed photographs show on craft pages." : "Every field photograph filed on an artisan is hidden.");
    } catch (cause) {
      setError(apiErrorMessage(cause, SWITCH_FAILED));
    } finally {
      setBusy(null);
    }
  }

  async function screen() {
    setBusy("screen");
    setError(null);
    try {
      setStatus(screenedLine(await screenFieldPhotos()));
      onScreened();
    } catch (cause) {
      setError(apiErrorMessage(cause, SCREEN_FAILED));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-labelledby="field-photo-switch" className="grid gap-6 border-t border-ink-1 pt-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-10">
      <div className="grid content-start gap-3">
        <h2 id="field-photo-switch" className="font-headline text-h3 text-ink-1">
          On the craft pages
        </h2>
        {master ? (
          <Toggle checked={on} onChange={(next) => void flip(next)} busy={busy === "switch"} busyLabel="Saving" label="Show reviewed field photographs" description={SWITCH_COPY} />
        ) : (
          <StatusBadge tone={on ? "success" : "neutral"} label={on ? "Reviewed photographs are shown" : "Every field photograph filed on an artisan is hidden"} note={`${SWITCH_COPY} A Master Admin turns it on or off.`} />
        )}
      </div>
      <div className="grid content-start gap-4">
        <dl className="grid grid-cols-3 gap-4 border-t border-rule pt-3 lg:border-t-0 lg:pt-0">
          <Count term="Waiting" value={queue.counts.waiting} />
          <Count term="Shown" value={queue.counts.shown} />
          <Count term="Hidden" value={queue.counts.hidden} />
        </dl>
        <ActionGroup align="start">
          <Button variant="quiet" busy={busy === "screen"} busyLabel="Screening" disabled={busy !== null} onClick={() => void screen()}>
            Screen the waiting photographs
          </Button>
        </ActionGroup>
      </div>
      <p role="status" className="font-ui text-label text-ink-2 lg:col-span-2">
        {status}
      </p>
      {error ? (
        <p role="alert" className="font-ui text-ui text-error lg:col-span-2">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function Count({ term, value }: { term: string; value: number }) {
  return (
    <div className="grid gap-1">
      <dt className="font-ui text-label text-ink-3">{term}</dt>
      <dd className="font-headline text-h2 text-ink-1 tabular-nums lining-nums">{value.toLocaleString("en-IN")}</dd>
    </div>
  );
}
