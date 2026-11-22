"use client";

import { useEffect, useState } from "react";

import { VoiceSettingsForm } from "@/components/admin/VoiceSettingsForm";
import { useAuth } from "@/components/AuthProvider";
import { Skeleton } from "@/components/ui/Skeleton";
import { apiErrorMessage } from "@/lib/api";
import { canManageRouting } from "@/lib/permissions";
import { fetchVoiceSettings, saveVoiceSettings, type VoiceSettings, type VoiceSettingsView } from "@/lib/voiceSettingsContract";

const LOAD_FAILED = "Couldn't read the voice settings. Reload the page to try again.";
const SAVE_FAILED = "Couldn't save the voice settings. Try again.";

export function VoiceSettingsCard() {
  const { user } = useAuth();
  const allowed = canManageRouting(user);
  const [view, setView] = useState<VoiceSettingsView | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    fetchVoiceSettings()
      .then((found) => {
        if (!cancelled) setView(found);
      })
      .catch((cause) => {
        if (!cancelled) setError(apiErrorMessage(cause, LOAD_FAILED));
      });
    return () => {
      cancelled = true;
    };
  }, [allowed]);

  if (!allowed) return null;

  async function save(settings: VoiceSettings) {
    setBusy(true);
    setSaved(false);
    setError(null);
    try {
      setView(await saveVoiceSettings(settings));
      setSaved(true);
    } catch (cause) {
      setError(apiErrorMessage(cause, SAVE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="voice-settings-title" className="mt-section grid gap-5 border-t border-rule pt-6" data-testid="voice-settings">
      <div className="grid max-w-measure gap-2">
        <h2 id="voice-settings-title" className="font-headline text-h3 text-ink-1">
          Voice calls
        </h2>
        <p className="font-ui text-ui text-ink-2">How a live call reaches ElevenLabs, how many calls run at once, and the voice that speaks in calls, Listen and film.</p>
      </div>
      {view ? <VoiceSettingsForm view={view} busy={busy} onSave={(settings) => void save(settings)} /> : null}
      {!view && !error ? <Skeleton shape="lede" label="Reading the voice settings" /> : null}
      <p role="status" className="font-ui text-label text-ink-2">
        {saved && !busy ? "Saved." : ""}
      </p>
      {error ? (
        <p role="alert" className="font-ui text-ui text-error">
          {error}
        </p>
      ) : null}
    </section>
  );
}
