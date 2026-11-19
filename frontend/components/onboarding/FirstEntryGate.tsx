"use client";

import { useEffect, useState } from "react";

import { BrandLockup } from "@/components/BrandMark";
import { ArtisanProfileForm } from "@/components/onboarding/ArtisanProfileForm";
import { RecordingAgreement } from "@/components/onboarding/RecordingAgreement";
import { StudentProfileForm } from "@/components/onboarding/StudentProfileForm";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { TextLink } from "@/components/ui/TextLink";
import { apiFetch } from "@/lib/api";
import { fetchProfile, type ProfileView } from "@/lib/profileContract";
import { fetchPrivacyNotice } from "@/lib/signUp";
import type { User } from "@/lib/types";

async function acceptCurrentNotice(): Promise<void> {
  const notice = await fetchPrivacyNotice();
  await apiFetch<unknown>("/auth/consent", { method: "POST", body: JSON.stringify({ kind: "PRIVACY_NOTICE", noticeVersion: notice.version }) });
}

function GateShell({ children }: { children: React.ReactNode }) {
  return (
    <main id="main-content" className="kv-shell-wrap grid min-h-dvh content-start justify-items-center gap-8 py-10 sm:py-16">
      <BrandLockup />
      {children}
    </main>
  );
}

function Frame({ title, line, children, onSignOut }: { title: string; line: string; children: React.ReactNode; onSignOut: () => void }) {
  return (
    <GateShell>
      <section className="grid w-full max-w-2xl gap-6 border-t border-ink-1 pt-6" data-testid="first-entry">
        <div className="grid gap-2">
          <h1 className="font-headline text-h2 text-ink-1">{title}</h1>
          <p className="max-w-measure font-reading text-body-sm text-ink-2">{line}</p>
        </div>
        {children}
        <ActionGroup>
          <Button type="button" variant="text" onClick={onSignOut}>
            Sign out
          </Button>
        </ActionGroup>
      </section>
    </GateShell>
  );
}

export function FirstEntryGate({ user, onDone, onSignOut }: { user: User; onDone: () => void; onSignOut: () => void }) {
  const [profile, setProfile] = useState<ProfileView | null>(null);
  const [recording, setRecording] = useState<string | null>(null);

  useEffect(() => {
    fetchProfile().then(setProfile).catch(() => setProfile(null));
  }, []);

  if (recording) {
    return (
      <Frame title="Recording" line="Read the recording notice before you record." onSignOut={onSignOut}>
        <RecordingAgreement language={recording} onDone={onDone} notNow={onDone} />
      </Frame>
    );
  }
  if (user.role === "ARTISAN") {
    return (
      <Frame title="Your craft" line="Your crafts, district and language, and how your words are credited when they are shown." onSignOut={onSignOut}>
        <ArtisanProfileForm current={profile?.artisan ?? null} accountName={user.name} action="Continue" onSaved={(view) => setRecording(view.artisan?.spokenLanguage ?? "en")} />
      </Frame>
    );
  }
  return (
    <Frame title="Before you start" line="Continuing accepts the privacy notice." onSignOut={onSignOut}>
      <StudentProfileForm ageBand={profile?.student?.ageBand ?? null} gender={profile?.student?.gender ?? null} action="Continue" before={acceptCurrentNotice} onSaved={onDone} />
      <p className="font-ui text-ui text-ink-2">
        <TextLink href="/privacy" external>
          Privacy notice
        </TextLink>
      </p>
    </Frame>
  );
}

export function GuardianHold({ onCheck, onSignOut }: { onCheck: () => void; onSignOut: () => void }) {
  return (
    <GateShell>
      <section className="grid w-full max-w-md gap-5 border-t border-ink-1 pt-6 text-center" data-testid="guardian-hold">
        <h1 className="font-headline text-h2 text-ink-1">A guardian&apos;s agreement</h1>
        <p className="font-reading text-body-sm text-ink-1">Your teacher needs to confirm that your parent or guardian agrees before you continue.</p>
        <ActionGroup>
          <Button type="button" variant="primary" onClick={onCheck}>
            Check again
          </Button>
          <Button type="button" variant="quiet" onClick={onSignOut}>
            Sign out
          </Button>
        </ActionGroup>
      </section>
    </GateShell>
  );
}
