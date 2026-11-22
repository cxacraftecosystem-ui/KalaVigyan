"use client";

import { useState, type FormEvent } from "react";

import { Field, FieldBlock, TextInput } from "@/components/FormControls";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import {
  draftSettings,
  LIVE_CALLS_MAX,
  TRANSPORT_LABELS,
  VOICE_TRANSPORTS,
  voiceDraft,
  voiceSettingProblems,
  type VoiceSettings,
  type VoiceSettingsDraft,
  type VoiceSettingsView,
  type VoiceTransport
} from "@/lib/voiceSettingsContract";

const TRANSPORT_OPTIONS = VOICE_TRANSPORTS.map((value) => ({ value, label: TRANSPORT_LABELS[value] }));

export function VoiceSettingsForm({ view, busy, onSave }: { view: VoiceSettingsView; busy: boolean; onSave: (settings: VoiceSettings) => void }) {
  const [draft, setDraft] = useState<VoiceSettingsDraft>(() => voiceDraft(view));
  const [checked, setChecked] = useState(false);
  const problems = checked ? voiceSettingProblems(draft) : {};
  const change = (next: Partial<VoiceSettingsDraft>) => setDraft((current) => ({ ...current, ...next }));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setChecked(true);
    if (Object.keys(voiceSettingProblems(draft)).length === 0) onSave(draftSettings(draft));
  }

  return (
    <form className="grid max-w-measure gap-5" noValidate onSubmit={submit} data-testid="voice-settings-form">
      <FieldBlock label="How a call is carried" hint={<span className="kv-field-hint">Default: {TRANSPORT_LABELS[view.defaults.transport].toLowerCase()}.</span>}>
        <SegmentedChoice label="How a call is carried" value={draft.transport} options={TRANSPORT_OPTIONS} onChange={(next) => change({ transport: next as VoiceTransport })} disabled={busy} />
      </FieldBlock>
      <Field label="Calls at once" hint={`The plan's limit on calls running together, 0 to ${LIVE_CALLS_MAX}. Default: ${view.defaults.maxLiveSessions}.`} error={problems.maxLiveSessions}>
        <TextInput type="number" inputMode="numeric" min={0} max={LIVE_CALLS_MAX} step={1} value={draft.maxLiveSessions} disabled={busy} onChange={(event) => change({ maxLiveSessions: event.target.value })} />
      </Field>
      <Field label="Voice id" hint={`The ElevenLabs voice of calls, Listen and film; a new voice reads Listen afresh. Default: ${view.defaults.voiceId}.`} error={problems.voiceId}>
        <TextInput className="font-code" autoComplete="off" spellCheck={false} value={draft.voiceId} disabled={busy} onChange={(event) => change({ voiceId: event.target.value })} />
      </Field>
      <ActionGroup align="start">
        <Button type="submit" variant="primary" busy={busy} busyLabel="Saving">
          Save voice settings
        </Button>
      </ActionGroup>
    </form>
  );
}
