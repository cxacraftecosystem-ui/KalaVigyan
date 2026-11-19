"use client";

import { Suspense } from "react";

import { useAuth } from "@/components/AuthProvider";
import { PageHeader } from "@/components/PageHeader";
import { AccountFacts, SignInFacts } from "@/components/settings/AccountFacts";
import { AlertDigestCard } from "@/components/settings/AlertDigestCard";
import { ChangePasswordCard } from "@/components/settings/ChangePasswordCard";
import { ConnectedClientsCard } from "@/components/settings/ConnectedClientsCard";
import { PreferencesPanel } from "@/components/settings/PreferencesPanel";
import { ProfileCards } from "@/components/settings/ProfileCards";
import { TwoStepVerificationCard } from "@/components/settings/TwoStepVerificationCard";
import { SETTINGS_TAB_LABELS } from "@/components/settings/settingsTabs";
import { useSettingsTab } from "@/components/settings/useSettingsTab";
import { Tabs } from "@/components/ui/Tabs";
import { roleLabel } from "@/lib/permissions";

export default function SettingsPage() {
  return (
    <Suspense fallback={<PageHeader title="Settings" back={false} />}>
      <SettingsScreen />
    </Suspense>
  );
}

const PANEL = "grid gap-12 pt-2 [&>section:first-child]:border-t-0 [&>section:first-child]:pt-0";

function SettingsScreen() {
  const { user } = useAuth();
  const [tab, choose] = useSettingsTab();
  const items = [
    {
      value: "profile",
      label: SETTINGS_TAB_LABELS.profile,
      panel: (
        <div className={PANEL}>
          <AccountFacts />
          <ProfileCards />
        </div>
      )
    },
    {
      value: "preferences",
      label: SETTINGS_TAB_LABELS.preferences,
      panel: (
        <div className={PANEL}>
          <PreferencesPanel />
          <AlertDigestCard />
        </div>
      )
    },
    {
      value: "security",
      label: SETTINGS_TAB_LABELS.security,
      panel: (
        <div className={PANEL}>
          <SignInFacts />
          <div className="grid gap-12 lg:grid-cols-2 lg:gap-10">
            <TwoStepVerificationCard />
            <ChangePasswordCard />
          </div>
          <ConnectedClientsCard />
        </div>
      )
    }
  ];

  return (
    <>
      <PageHeader title="Settings" description={user ? `${user.name || user.email} · ${roleLabel(user.role)}` : undefined} back={false} />
      <Tabs label="Settings" value={tab} onChange={choose} items={items} />
    </>
  );
}
