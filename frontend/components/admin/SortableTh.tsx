"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { ResizableTh } from "@/components/ResizableTh";
import {
  nextRosterSort,
  sortActionLabel,
  type RosterFilters,
  type RosterKind
} from "@/components/admin/rosterFilters";
import { cn } from "@/lib/utils";

export type RosterSortControl = {
  kind: RosterKind;
  filters: RosterFilters;
  onChange: (next: RosterFilters) => void;
};

export function SortableTh({
  control,
  column,
  label,
  className
}: {
  control: RosterSortControl;
  column: string;
  label: string;
  className?: string;
}) {
  const { kind, filters, onChange } = control;
  const active = filters.sort === column;
  const Icon = active ? (filters.dir === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;

  return (
    <ResizableTh aria-sort={active ? (filters.dir === "asc" ? "ascending" : "descending") : "none"} className={className}>
      <button
        type="button"
        title={sortActionLabel(kind, filters, column, label)}
        onClick={() => onChange(nextRosterSort(kind, filters, column))}
        className={cn(
          "-my-1 inline-flex min-h-target max-w-full items-center gap-1.5 rounded-control text-start font-ui text-label transition-colors duration-state hover:text-indigo-hover",
          active ? "text-ink-1" : "text-ink-2"
        )}
      >
        <span className="min-w-0 truncate">{label}</span>
        <Icon className={cn("size-3.5 shrink-0", active ? "text-ink-1" : "text-ink-3")} aria-hidden />
      </button>
    </ResizableTh>
  );
}
