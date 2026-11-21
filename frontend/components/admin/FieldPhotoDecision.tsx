"use client";

import { useState } from "react";

import { Field, Select, TextArea } from "@/components/FormControls";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { Toggle } from "@/components/ui/Toggle";
import { apiErrorMessage } from "@/lib/api";
import { decideFieldPhoto, HIDE_REASONS, NOTE_MAX, PHOTO_DECISIONS, type FieldPhoto, type HideReason, type PhotoDecision } from "@/lib/fieldPhotoReviewContract";
import { DECISION_CHOICES, decisionBody, draftProblem, needsMaster, REASON_LABELS, type PhotoDraft } from "@/lib/fieldPhotoReviewView";

import { FieldPhotoCropFields } from "./FieldPhotoCropFields";

const SAVE_FAILED = "Couldn't save the decision. Reload the photographs and try again.";
const NOTE_HINT = "Kept with the decision, for other admins. Needed for another reason and to clear a flag.";

export function FieldPhotoDecision({
  photo,
  master,
  draft,
  onDraft,
  onDecided
}: {
  photo: FieldPhoto;
  master: boolean;
  draft: PhotoDraft;
  onDraft: (next: PhotoDraft) => void;
  onDecided: (photo: FieldPhoto) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const options = PHOTO_DECISIONS.map((value) => ({
    value,
    label: DECISION_CHOICES[value],
    disabled: needsMaster(photo, value) && !master,
    reason: "Only a Master Admin can show this photograph."
  }));

  async function save() {
    const found = draftProblem(draft, photo, master);
    setProblem(found);
    if (found) return;
    setBusy(true);
    try {
      onDecided(await decideFieldPhoto(photo.id, decisionBody(draft, photo)));
    } catch (cause) {
      setProblem(apiErrorMessage(cause, SAVE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Decide" className="grid gap-4 border-t border-rule pt-4">
      <h4 className="kicker">Decide</h4>
      <SegmentedChoice label="Decision" value={draft.decision} options={options} onChange={(next) => onDraft({ ...draft, decision: next as PhotoDecision })} disabled={busy} />
      <DecisionFields photo={photo} master={master} draft={draft} onDraft={onDraft} />
      <Field label="Note" hint={NOTE_HINT}>
        <TextArea value={draft.note} maxLength={NOTE_MAX} rows={2} onChange={(event) => onDraft({ ...draft, note: event.target.value })} />
      </Field>
      {problem ? (
        <p role="alert" className="font-ui text-ui text-error">
          {problem}
        </p>
      ) : null}
      <ActionGroup align="start">
        <SaveButton photo={photo} decision={draft.decision} busy={busy} onSave={() => void save()} />
      </ActionGroup>
    </section>
  );
}

function DecisionFields({ photo, master, draft, onDraft }: { photo: FieldPhoto; master: boolean; draft: PhotoDraft; onDraft: (next: PhotoDraft) => void }) {
  if (draft.decision === "HIDE") {
    return (
      <Field label="Why it stays hidden" required>
        <Select value={draft.reason ?? ""} onChange={(event) => onDraft({ ...draft, reason: (event.target.value || null) as HideReason | null })}>
          <option value="">Choose a reason</option>
          {HIDE_REASONS.map((reason) => (
            <option key={reason} value={reason}>
              {REASON_LABELS[reason]}
            </option>
          ))}
        </Select>
      </Field>
    );
  }
  if (draft.decision === "CROP") {
    return <FieldPhotoCropFields trims={draft.trims} width={photo.width} height={photo.height} onChange={(trims) => onDraft({ ...draft, trims })} />;
  }
  if (!photo.masterOnly || !master) return null;
  return (
    <Toggle
      checked={draft.clearFlags}
      onChange={(clearFlags) => onDraft({ ...draft, clearFlags })}
      label="Clear the screen's flag"
      description="You looked at the whole photograph and the flag is wrong. Say why in the note."
    />
  );
}

function SaveButton({ photo, decision, busy, onSave }: { photo: FieldPhoto; decision: PhotoDecision; busy: boolean; onSave: () => void }) {
  const hidingAgain = decision === "HIDE" && photo.state === "SHOWN";
  const label = hidingAgain ? "Hide it again" : decision === "HIDE" ? "Keep it hidden" : decision === "CROP" ? "Show the crop" : "Show it";
  return (
    <Button variant={hidingAgain ? "danger" : "quiet"} data-danger={hidingAgain ? "" : undefined} busy={busy} busyLabel="Saving" onClick={onSave}>
      {label}
    </Button>
  );
}
