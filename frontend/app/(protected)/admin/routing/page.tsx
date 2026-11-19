"use client";

import { PageHeader } from "@/components/PageHeader";
import { RoutingPanel } from "@/components/settings/RoutingPanel";

export default function RoutingPage() {
  return (
    <>
      <PageHeader title="AI routing" kicker="Admin" description="The first working model in each list takes the call." />
      <RoutingPanel />
    </>
  );
}
