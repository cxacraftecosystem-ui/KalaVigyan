import type { ReactNode } from "react";

import { STATUS_TONES, type StatusTone } from "@/components/records/statusTone";
import { cn } from "@/lib/utils";

export function StatusBadge({ tone, label, note }: { tone: StatusTone; label: string; note?: ReactNode }) {
  const { icon: Icon, ink } = STATUS_TONES[tone];
  return (
    <span className="inline-grid min-w-0 gap-0.5" data-status={tone}>
      <span className="inline-flex items-center gap-1.5 font-ui text-label text-ink-1">
        <Icon className={cn("size-3.5 shrink-0", ink)} aria-hidden />
        {label}
      </span>
      {note ? <span className="font-ui text-caption text-ink-3">{note}</span> : null}
    </span>
  );
}
