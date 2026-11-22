"use client";

import { useId } from "react";

import { FieldLabelProvider } from "@/components/ui/fieldLabel";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import { scopeChosen, scopeValue, type McpActivity, type McpScope } from "@/lib/mcpActivityContract";
import { KEPT_NOTE, activityStats, scopeOptions } from "@/lib/mcpActivityView";

import { McpActivitySeries } from "./McpActivitySeries";
import { McpActivityTables } from "./McpActivityTables";
import { McpFailures } from "./McpFailures";

type BodyProps = { activity: McpActivity; scope: McpScope; onScope: (next: McpScope) => void };

function ActivityStats({ activity }: { activity: McpActivity }) {
  return (
    <dl className="grid border-t border-ink-1 sm:grid-cols-3 sm:gap-x-8" data-testid="mcp-activity-stats">
      {activityStats(activity).map((stat) => (
        <div key={stat.label} className="grid content-start gap-1.5 border-b border-rule py-5">
          <dt className="font-ui text-label text-ink-3">{stat.label}</dt>
          <dd className="font-headline text-stat text-ink-1 tabular-nums lining-nums">{stat.value}</dd>
          <dd className="font-ui text-label text-ink-2 tabular-nums lining-nums">{stat.note}</dd>
        </div>
      ))}
    </dl>
  );
}

function ScopeField({ activity, scope, onScope }: BodyProps) {
  const label = useId();
  return (
    <div className="grid max-w-md gap-1.5">
      <span id={label} className="font-ui text-label font-medium text-ink-2">
        Show
      </span>
      <FieldLabelProvider value={label}>
        <SearchableSelect value={scopeValue(scope)} onChange={(value) => onScope(scopeChosen(value, scope.days))} options={scopeOptions(activity)} ariaLabel="Show the calls of" />
      </FieldLabelProvider>
    </div>
  );
}

export function McpActivityBody({ activity, scope, onScope }: BodyProps) {
  return (
    <div className="grid gap-12">
      <ActivityStats activity={activity} />
      <ScopeField activity={activity} scope={scope} onScope={onScope} />
      <McpActivitySeries activity={activity} />
      <McpActivityTables activity={activity} />
      <McpFailures activity={activity} />
      <p className="max-w-measure font-ui text-label text-ink-3">{KEPT_NOTE(activity.keptDays)}</p>
    </div>
  );
}
