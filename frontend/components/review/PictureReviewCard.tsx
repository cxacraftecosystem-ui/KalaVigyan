"use client";

import { useState } from "react";

import { Field, TextInput } from "@/components/FormControls";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api";
import { HeldReasons } from "@/components/contributions/HeldReasons";
import { decideImage, heldReasons, type ImageContribution } from "@/lib/imageContributionContract";

export function PictureReviewCard({ item, onDecided }: { item: ImageContribution; onDecided: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const open = item.status === "PENDING";

  async function decide(decision: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await decideImage(item.id, decision, note.trim() || null);
      onDecided();
    } catch (cause) {
      setError(apiErrorMessage(cause, "Couldn't save the decision. Reload it."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="grid gap-4 border-t border-rule pt-5 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]" data-testid="picture-review-card">
      {item.fileUrl ? (
        <a href={item.fileUrl} target="_blank" rel="noopener" className="block">
          <>
            {/* eslint-disable-next-line @next/next/no-img-element -- presigned bucket link, nothing for next/image to optimise */}
            <img src={item.fileUrl} alt={item.altText} className="w-full rounded-plate bg-sunk object-contain" loading="lazy" />
          </>
        </a>
      ) : (
        <div className="aspect-[4/3] w-full rounded-plate bg-sunk" aria-hidden />
      )}
      <div className="grid content-start gap-2">
        <p className="kicker">{item.craftName} · {item.label}</p>
        <p className="text-body-sm font-reading text-ink-1">{item.caption}</p>
        <p className="text-label font-ui text-ink-2">Description: {item.altText}</p>
        {item.prompt ? <p className="text-label font-ui text-ink-2">Prompt: {item.prompt}</p> : null}
        <p className="text-label font-ui text-ink-3">
          {item.claimIds.length} {item.claimIds.length === 1 ? "fact" : "facts"} · {item.width && item.height ? `${item.width} × ${item.height}` : "no file"}
          {item.aiMarked ? " · its own metadata says an AI made it" : ""}
        </p>
        <HeldReasons reasons={heldReasons(item)} />
        {item.reviewNote ? <p className="text-label font-ui text-ink-2">Note: {item.reviewNote}</p> : null}
        {open ? (
          <>
            <Field label="Note to the contributor" hint="Needed to refuse it.">
              <TextInput value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} />
            </Field>
            {error ? <p role="alert" className="text-ui font-ui text-error">{error}</p> : null}
            <ActionGroup align="start">
              <Button type="button" disabled={busy} onClick={() => void decide("approve")}>Approve</Button>
              <Button type="button" variant="danger" disabled={busy || note.trim().length < 3} onClick={() => void decide("reject")} data-danger>
                Refuse
              </Button>
            </ActionGroup>
          </>
        ) : null}
      </div>
    </li>
  );
}
