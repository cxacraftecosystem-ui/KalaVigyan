"use client";

import { ChevronDown, ChevronUp, Trash2 } from "lucide-react";

import type { StatusTone } from "@/components/records/statusTone";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { ToggleSwitch } from "@/components/ui/Toggle";
import { formatDateTime } from "@/lib/format";
import { routeKey, type KeyState, type RouteRow } from "@/lib/routing";
import { cn } from "@/lib/utils";

const KEY_STATE: Record<KeyState, { label: string; tone: StatusTone }> = {
  PASSING: { label: "Working", tone: "success" },
  FAILING: { label: "Test failed", tone: "error" },
  UNTESTED: { label: "Not tested", tone: "warning" },
  ABSENT: { label: "No key", tone: "neutral" }
};

export type RouteNames = { model: (row: RouteRow) => string; provider: (row: RouteRow) => string };

export type RouteListHandlers = {
  testing: string | null;
  onTest: (row: RouteRow) => void;
  onMove: (from: number, to: number) => void;
  onRemove: (row: RouteRow) => void;
  onEnable: (row: RouteRow, enabled: boolean) => void;
  register: (key: string, node: HTMLButtonElement | null) => void;
};

function MoveButton({ direction, disabled, label, register, onMove }: { direction: "up" | "down"; disabled: boolean; label: string; register: (node: HTMLButtonElement | null) => void; onMove: () => void }) {
  const Icon = direction === "up" ? ChevronUp : ChevronDown;
  return (
    <Button ref={register} variant="quiet" size="icon" disabled={disabled} aria-label={label} onClick={onMove}>
      <Icon className="size-4" aria-hidden />
    </Button>
  );
}

function RouteItem({ row, index, count, names, on }: { row: RouteRow; index: number; count: number; names: RouteNames; on: RouteListHandlers }) {
  const key = routeKey(row);
  const model = names.model(row);
  const state = KEY_STATE[row.keyState];
  return (
    <li className={cn("grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 border-b border-rule py-4 md:grid-cols-[auto_minmax(0,1fr)_auto]", !row.enabled && "text-ink-3")}>
      <span aria-hidden className={cn("grid size-7 place-items-center rounded-full font-ui text-label tabular-nums lining-nums", row.enabled ? "bg-ink-1 text-ground" : "border border-rule-strong text-ink-3")}>
        {index + 1}
      </span>
      <div className="grid min-w-0 gap-1.5">
        <p className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-ui text-h4 text-ink-1">{model}</span>
          <span className="font-ui text-label text-ink-3">{names.provider(row)}</span>
        </p>
        <StatusBadge tone={state.tone} note={row.testedAt ? `Tested ${formatDateTime(row.testedAt)}` : undefined} label={state.label} />
        {row.testError ? <p className="font-ui text-label text-error">{row.testError}</p> : null}
        <ToggleSwitch label="Use this model" showLabel checked={row.enabled} onChange={(next) => on.onEnable(row, next)} />
      </div>
      <div className="col-span-2 flex flex-wrap items-center gap-2 md:col-span-1 md:justify-end">
        <Button variant="quiet" size="sm" busy={on.testing === key} busyLabel="Testing" disabled={on.testing !== null && on.testing !== key} aria-label={`Test ${model}`} onClick={() => on.onTest(row)}>
          Test
        </Button>
        <MoveButton direction="up" disabled={index === 0} label={`Move ${model} up`} register={(node) => on.register(`${key}:up`, node)} onMove={() => on.onMove(index, index - 1)} />
        <MoveButton direction="down" disabled={index === count - 1} label={`Move ${model} down`} register={(node) => on.register(`${key}:down`, node)} onMove={() => on.onMove(index, index + 1)} />
        <Button variant="danger" size="icon" aria-label={`Remove ${model}`} onClick={() => on.onRemove(row)}>
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </div>
    </li>
  );
}

export function RouteList({ rows, names, on }: { rows: RouteRow[]; names: RouteNames; on: RouteListHandlers }) {
  return (
    <ol className="grid border-t border-ink-1" data-testid="routing-list">
      {rows.map((row, index) => (
        <RouteItem key={routeKey(row)} row={row} index={index} count={rows.length} names={names} on={on} />
      ))}
    </ol>
  );
}
