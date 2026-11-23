"use client";

import { useCallback, useState } from "react";

import { fetchFieldVoices, type FieldVoicesList } from "@/lib/fieldVoicesContract";
import { restOfList } from "@/lib/fieldVoicesView";

export type FieldListPhase = "idle" | "reading" | "failed";

export type FieldListView<T> = { shown: T[]; total: number; open: boolean; phase: FieldListPhase; expandable: boolean; toggle: () => void };

type ListState<T> = { items: T[]; next: string | null; open: boolean; phase: FieldListPhase };

export function useFieldList<T>(first: FieldVoicesList, pick: (list: FieldVoicesList) => T[], take: number): FieldListView<T> {
  const [state, setState] = useState<ListState<T>>(() => ({ items: pick(first), next: first.nextCursor, open: false, phase: "idle" }));
  const { slug } = first.craft;
  const { kind } = first;
  const toggle = useCallback(() => {
    if (state.phase === "reading") return;
    if (state.open || state.next === null) {
      setState((now) => ({ ...now, open: !now.open }));
      return;
    }
    const cursor = state.next;
    setState((now) => ({ ...now, phase: "reading" }));
    restOfList(cursor, (at) => fetchFieldVoices(slug, kind, at), pick).then(
      (rest) => setState((now) => ({ items: [...now.items, ...rest], next: null, open: true, phase: "idle" })),
      () => setState((now) => ({ ...now, phase: "failed" }))
    );
  }, [kind, pick, slug, state.next, state.open, state.phase]);
  return {
    shown: state.open ? state.items : state.items.slice(0, take),
    total: first.total,
    open: state.open,
    phase: state.phase,
    expandable: first.total > take,
    toggle
  };
}
