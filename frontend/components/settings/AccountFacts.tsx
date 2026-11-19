"use client";

import { useAuth } from "@/components/AuthProvider";
import { FactGrid } from "@/components/editorial/FactGrid";
import { RecordSection } from "@/components/records/RecordSection";
import { accountFacts, signInFacts } from "@/components/settings/accountFactList";

export function AccountFacts() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <RecordSection title="Your account" description="Your role is set by an administrator." testId="account-facts">
      <FactGrid facts={accountFacts(user)} columns={4} />
    </RecordSection>
  );
}

export function SignInFacts() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <RecordSection title="How you sign in" testId="sign-in-facts">
      <FactGrid facts={signInFacts(user)} columns={4} />
    </RecordSection>
  );
}
