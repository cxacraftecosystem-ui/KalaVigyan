"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { HiddenFactsCard } from "@/components/admin/HiddenFactsCard";
import { PageRefreshCard } from "@/components/admin/PageRefreshCard";
import { ReviewSwitchCard } from "@/components/admin/ReviewSwitchCard";
import { SiteBuildCard } from "@/components/admin/SiteBuildCard";
import { VoiceSettingsCard } from "@/components/admin/VoiceSettingsCard";
import { useAuth } from "@/components/AuthProvider";
import { usePendingAccessCount } from "@/components/hooks/usePendingAccessCount";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { byCount } from "@/lib/format";
import { canAccessRoute, canManageAccessRoster, canManageRouting } from "@/lib/permissions";

type HubTool = { href: string; title: string; note: string };

const TOOLS: HubTool[] = [
  { href: "/admin/review", title: "Review", note: "Decide what other people give: facts, testimony, pictures, components and layouts." },
  { href: "/admin/field-photos", title: "Field photographs", note: "Show, crop or keep hidden each photograph the portals filed on an artisan." },
  { href: "/admin/access", title: "Who may sign in", note: "Approve requests and add addresses." },
  { href: "/admin/users", title: "Manage users", note: "Change roles, suspend accounts, reset two-step verification." },
  { href: "/admin/keys", title: "API keys", note: "Set and test the provider keys." },
  { href: "/admin/routing", title: "AI routing", note: "The model order for each task." },
  { href: "/admin/budget", title: "AI budget", note: "Spend caps and daily allowances; empty means no cap." },
  { href: "/admin/usage", title: "Usage", note: "Calls, tokens and spend, by task, model and day." },
  { href: "/admin/mcp", title: "MCP activity", note: "Calls to the MCP server by client and connection, and why calls failed." }
];

function ToolRow({ tool, waiting }: { tool: HubTool; waiting: number }) {
  return (
    <li className="min-w-0 border-b border-rule">
      <Link href={tool.href} className="group grid h-full grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 py-5 pe-1 transition-colors duration-state hover:bg-sunk md:px-3">
        <span className="font-ui text-h4 text-ink-1 underline-offset-3 group-hover:text-indigo-hover group-hover:underline">{tool.title}</span>
        <ArrowRight className="row-span-2 mt-0.5 size-4 text-ink-3 transition-colors duration-state group-hover:text-indigo-hover" aria-hidden />
        <span className="font-ui text-label text-ink-2">{tool.note}</span>
        {waiting > 0 ? (
          <span className="col-span-2 mt-1">
            <StatusBadge tone="waiting" label={`${waiting} ${byCount(waiting, "request", "requests")} waiting`} />
          </span>
        ) : null}
      </Link>
    </li>
  );
}

export default function SettingsHubPage() {
  const { user } = useAuth();
  const visible = TOOLS.filter((tool) => canAccessRoute(user, tool.href));
  const pending = usePendingAccessCount(canManageAccessRoster(user));
  const description = canManageRouting(user) ? "Accounts, keys and model routing." : "Accounts, access and usage.";

  return (
    <>
      <PageHeader title="Settings hub" kicker="Admin" description={description} />
      <nav aria-label="Admin tools">
        <ul className="grid border-t border-ink-1 md:grid-cols-2 md:gap-x-8 lg:grid-cols-3">
          {visible.map((tool) => (
            <ToolRow key={tool.href} tool={tool} waiting={tool.href === "/admin/access" ? (pending?.pending ?? 0) : 0} />
          ))}
        </ul>
      </nav>
      <ReviewSwitchCard />
      <VoiceSettingsCard />
      <SiteBuildCard />
      <PageRefreshCard />
      <HiddenFactsCard />
    </>
  );
}
