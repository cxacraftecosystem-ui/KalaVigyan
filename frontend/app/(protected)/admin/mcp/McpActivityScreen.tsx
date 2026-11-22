"use client";

import type { ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/PageHeader";
import { RecordNotice } from "@/components/records/RecordNotice";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { Skeleton } from "@/components/ui/Skeleton";
import { scopeFromParams, scopeHref, type McpPeriod, type McpScope } from "@/lib/mcpActivityContract";
import { PERIOD_OPTIONS } from "@/lib/mcpActivityView";

import { McpActivityBody } from "./McpActivityBody";
import { useMcpActivity } from "./useMcpActivity";

const TITLE = "MCP activity";
const DESCRIPTION = "Calls to the MCP server by client and connection, and why calls failed.";

export function McpActivityHeader({ actions }: { actions?: ReactNode }) {
  return <PageHeader title={TITLE} kicker="Admin" description={DESCRIPTION} actions={actions} />;
}

export function McpActivityScreen() {
  const router = useRouter();
  const scope = scopeFromParams(useSearchParams());
  const { activity, error, retry } = useMcpActivity(scope);
  const show = (next: McpScope) => router.replace(scopeHref(next), { scroll: false });
  const period = (
    <SegmentedChoice label="Period" value={String(scope.days)} options={PERIOD_OPTIONS} onChange={(days) => show({ ...scope, days: Number(days) as McpPeriod })} />
  );

  return (
    <>
      <McpActivityHeader actions={period} />
      {error ? (
        <RecordNotice tone="error" className="mb-8" action={<Button variant="quiet" size="sm" onClick={retry}>Try again</Button>}>
          {error}
        </RecordNotice>
      ) : null}
      {activity === null ? (
        error ? null : <Skeleton shape="chart" label="Reading the MCP activity" />
      ) : (
        <McpActivityBody activity={activity} scope={scope} onScope={show} />
      )}
    </>
  );
}
