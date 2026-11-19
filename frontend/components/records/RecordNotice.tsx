import type { ReactNode } from "react";

import { STATUS_TONES, type StatusTone } from "@/components/records/statusTone";
import { cn } from "@/lib/utils";

export function RecordNotice({ tone, children, action, className }: { tone: StatusTone; children: ReactNode; action?: ReactNode; className?: string }) {
  const { icon: Icon, ink, wash } = STATUS_TONES[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex flex-wrap items-start gap-x-3 gap-y-2 rounded-card px-4 py-3", wash, className)}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", ink)} aria-hidden />
      <div className="min-w-0 flex-1 font-ui text-ui font-normal text-ink-1">{children}</div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
