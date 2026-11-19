"use client";

import { PageHeader } from "@/components/PageHeader";
import { ApiKeysPanel } from "@/components/settings/ApiKeysPanel";

export default function ApiKeysPage() {
  return (
    <>
      <PageHeader title="API keys" kicker="Admin" description="Provider keys. Changes apply everywhere at once." />
      <ApiKeysPanel />
    </>
  );
}
