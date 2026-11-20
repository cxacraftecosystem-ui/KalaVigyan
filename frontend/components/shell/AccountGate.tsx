"use client";

import type { ReactNode } from "react";
import dynamic from "next/dynamic";

import { AuthShell } from "@/components/auth/AuthShell";
import { useAuth } from "@/components/AuthProvider";
import { FirstPasswordGate } from "@/components/FirstPasswordGate";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { mustChangePassword } from "@/lib/signIn";
import type { User } from "@/lib/types";

const FirstEntryGate = dynamic(() => import("@/components/onboarding/FirstEntryGate").then((gate) => gate.FirstEntryGate));
const GuardianHold = dynamic(() => import("@/components/onboarding/FirstEntryGate").then((gate) => gate.GuardianHold));
const TwoStepVerificationCard = dynamic(() => import("@/components/settings/TwoStepVerificationCard").then((card) => card.TwoStepVerificationCard));

export function AccountGate({ user, children }: { user: User; children: ReactNode }) {
  const { retryMe, logout, markPasswordChanged } = useAuth();
  const signOut = () => {
    logout().catch(() => undefined);
  };
  if (mustChangePassword(user)) return <FirstPasswordLocked onDone={markPasswordChanged} onSignOut={signOut} />;
  if (user.twoFactorRequired && !user.twoFactorEnabled) return <TwoStepRequired onSignOut={signOut} />;
  if (user.profileRequired) return <FirstEntryGate user={user} onDone={retryMe} onSignOut={signOut} />;
  if (user.guardianConsentRequired) return <GuardianHold onCheck={retryMe} onSignOut={signOut} />;
  return <>{children}</>;
}

function FirstPasswordLocked({ onDone, onSignOut }: { onDone: () => void; onSignOut: () => void }) {
  return (
    <AuthShell title="Set a new password" subtitle="One more step before you go on.">
      <FirstPasswordGate currentPassword="" onDone={onDone} onSignOut={onSignOut} />
    </AuthShell>
  );
}

function TwoStepRequired({ onSignOut }: { onSignOut: () => void }) {
  return (
    <AuthShell title="Turn on two-step verification" subtitle="Your role needs it.">
      <div data-testid="two-step-required">
        <TwoStepVerificationCard />
        <ActionGroup className="mt-6">
          <Button variant="quiet" onClick={onSignOut}>
            Sign out
          </Button>
        </ActionGroup>
      </div>
    </AuthShell>
  );
}
