"use client";

import { AiBudgetPanel } from "@/components/admin/AiBudgetPanel";
import { PageHeader } from "@/components/PageHeader";

export default function AiBudgetPage() {
  return (
    <>
      <PageHeader title="AI budget" kicker="Admin" description="Spend caps and daily allowances. An empty field is no cap." />
      <AiBudgetPanel />
    </>
  );
}
