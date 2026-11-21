"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import type { FieldPhoto } from "@/lib/fieldPhotoReviewContract";
import { firstDraft, STATE_LABELS, type PhotoDraft } from "@/lib/fieldPhotoReviewView";

import { FieldPhotoDecision } from "./FieldPhotoDecision";
import { FieldPhotoFacts } from "./FieldPhotoFacts";
import { FieldPhotoFigure } from "./FieldPhotoFigure";
import { FieldPhotoRecord } from "./FieldPhotoRecord";

export function FieldPhotoCard({ photo, master, onDecided }: { photo: FieldPhoto; master: boolean; onDecided: (photo: FieldPhoto) => void }) {
  const [draft, setDraft] = useState<PhotoDraft>(() => firstDraft(photo));
  const headingId = `field-photo-${photo.id}`;
  const stateTone = photo.state === "SHOWN" ? "success" : photo.state === "HIDDEN" ? "neutral" : "waiting";

  function decided(next: FieldPhoto) {
    setDraft(firstDraft(next));
    onDecided(next);
  }

  return (
    <li aria-labelledby={headingId} className="grid gap-6 border-t border-ink-1 pt-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-10" data-testid="field-photo-card" data-state={photo.state} data-risk={photo.risk}>
      <FieldPhotoFigure photo={photo} trims={draft.decision === "CROP" ? draft.trims : null} />
      <div className="grid min-w-0 content-start gap-4">
        <header className="grid gap-2">
          <p className="kicker">{`${photo.publisher} · ${photo.crafts[0] ?? "Field photograph"}`}</p>
          <h3 id={headingId} className="font-ui text-h4 text-ink-1 [overflow-wrap:anywhere]">
            {photo.caption ?? photo.alt}
          </h3>
          <StatusBadge tone={stateTone} label={STATE_LABELS[photo.state]} />
        </header>
        <FieldPhotoFacts photo={photo} />
        <FieldPhotoRecord photo={photo} />
        <FieldPhotoDecision photo={photo} master={master} draft={draft} onDraft={setDraft} onDecided={decided} />
      </div>
    </li>
  );
}
