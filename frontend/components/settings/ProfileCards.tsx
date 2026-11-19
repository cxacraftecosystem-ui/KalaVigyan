"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { ArtisanProfileForm } from "@/components/onboarding/ArtisanProfileForm";
import { RecordingAgreement } from "@/components/onboarding/RecordingAgreement";
import { StudentProfileForm } from "@/components/onboarding/StudentProfileForm";
import { RecordSection } from "@/components/records/RecordSection";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api";
import { fetchProfile, withdrawRecording, type ProfileView } from "@/lib/profileContract";

function RecordingStatus({ profile, onChanged }: { profile: ProfileView; onChanged: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const artisan = profile.artisan;
  if (!artisan) return null;
  if (!artisan.recordingConsent) {
    return <RecordingAgreement language={artisan.spokenLanguage ?? "en"} onDone={onChanged} />;
  }

  async function withdraw() {
    try {
      const done = await withdrawRecording();
      setMessage(`Taken back: ${done.withdrawnContributions} facts, ${done.deletedConversations} conversations.`);
      onChanged();
    } catch (cause) {
      setMessage(apiErrorMessage(cause, "Couldn't withdraw. Try again."));
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="grid gap-3 border-t border-rule pt-5">
      <h3 className="font-ui text-h4 text-ink-1">Recording</h3>
      <p className="font-ui text-ui font-normal text-ink-2">You agreed to be recorded.</p>
      {confirming ? <p className="rounded-card bg-madder-wash px-4 py-3 font-ui text-ui font-normal text-ink-1">This deletes every recording and takes back every fact you shared.</p> : null}
      {message ? <p role="status" className="font-ui text-ui font-normal text-ink-2">{message}</p> : null}
      <ActionGroup align="start">
        {confirming ? (
          <>
            <Button type="button" variant="quiet" onClick={() => setConfirming(false)}>
              Keep my recordings
            </Button>
            <Button type="button" variant="destroy" data-danger onClick={() => void withdraw()}>
              Withdraw and delete
            </Button>
          </>
        ) : (
          <Button type="button" variant="danger" onClick={() => setConfirming(true)}>
            Withdraw agreement
          </Button>
        )}
      </ActionGroup>
    </div>
  );
}

export function ProfileCards() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<ProfileView | null>(null);
  const [saved, setSaved] = useState(false);

  function load() {
    fetchProfile().then(setProfile).catch(() => setProfile(null));
  }

  useEffect(load, []);

  function stored(view: ProfileView) {
    setProfile(view);
    setSaved(true);
  }

  if (!user || !profile) return null;
  if (profile.student) {
    return (
      <RecordSection title="Your profile" testId="student-profile-card">
        <div className="max-w-measure">
          <StudentProfileForm ageBand={profile.student.ageBand} gender={profile.student.gender} action="Save" onSaved={stored} />
        </div>
        {saved ? <p role="status" className="font-ui text-label text-ink-2">Saved.</p> : null}
      </RecordSection>
    );
  }
  if (!profile.artisan) return null;
  return (
    <RecordSection title="Your craft profile" testId="artisan-profile-card">
      <ArtisanProfileForm current={profile.artisan} accountName={user.name} action="Save" onSaved={stored} />
      {saved ? <p role="status" className="font-ui text-label text-ink-2">Saved.</p> : null}
      <RecordingStatus profile={profile} onChanged={load} />
    </RecordSection>
  );
}
