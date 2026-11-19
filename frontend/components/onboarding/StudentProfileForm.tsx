"use client";

import { useState } from "react";

import { FormAlert } from "@/components/auth/FormAlert";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { apiErrorMessage } from "@/lib/api";
import {
  AGE_BAND_LABELS,
  AGE_BANDS,
  GENDER_LABELS,
  GENDERS,
  saveStudentProfile,
  type AgeBand,
  type Gender,
  type ProfileView
} from "@/lib/profileContract";

const AGE_OPTIONS = AGE_BANDS.map((value) => ({ value, label: AGE_BAND_LABELS[value] }));
const GENDER_OPTIONS = GENDERS.map((value) => ({ value, label: GENDER_LABELS[value] }));
const SAVE_FAILED = "Couldn't save. Try again.";

export function StudentProfileForm({
  ageBand,
  gender,
  action,
  before,
  onSaved
}: {
  ageBand: AgeBand | null;
  gender: Gender | null;
  action: string;
  before?: () => Promise<void>;
  onSaved: (view: ProfileView) => void;
}) {
  const [age, setAge] = useState<AgeBand | "">(ageBand ?? "");
  const [chosen, setChosen] = useState<Gender | "">(gender ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!age || !chosen) return;
    setBusy(true);
    setError(null);
    try {
      if (before) await before();
      onSaved(await saveStudentProfile(age, chosen));
    } catch (cause) {
      setError(apiErrorMessage(cause, SAVE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5" data-testid="student-profile-form">
      <div className="grid gap-1.5">
        <span className="field-label">Age</span>
        <SegmentedChoice label="Age" value={age} options={AGE_OPTIONS} onChange={(next) => setAge(next as AgeBand)} disabled={busy} />
      </div>
      <div className="grid gap-1.5">
        <span className="field-label">Gender</span>
        <SegmentedChoice label="Gender" value={chosen} options={GENDER_OPTIONS} onChange={(next) => setChosen(next as Gender)} disabled={busy} />
      </div>
      <p className="max-w-measure font-ui text-ui font-normal text-ink-2">
        Your age sets how answers are written for you. Your gender is only for drawing story characters. No one else sees either.
      </p>
      {error ? <FormAlert>{error}</FormAlert> : null}
      <ActionGroup fill>
        <Button type="button" variant="primary" disabled={!age || !chosen} busy={busy} busyLabel="Saving" onClick={() => void save()}>
          {action}
        </Button>
      </ActionGroup>
    </div>
  );
}
